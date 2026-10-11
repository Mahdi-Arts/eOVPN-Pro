# eOVPN-Pro Final Validation Snapshot

Date: 2026-10-11

This document records the current validation evidence without converting
unattended checks into owner acceptance.

## Verified

- `python3 -m unittest discover -s tests -p 'test*.py' -q`: 106 tests passed.
- `python3 -m mypy --ignore-missing-imports eovpn`: 29 source files, no issues.
- `ruff check eovpn tests`: passed.
- `ruff format --check eovpn tests`: 44 files already formatted.
- `python3 -m compileall -q eovpn tests`: passed.
- `python3 scripts/check_project_meta.py`: metadata version 1.5.0 passed.
- `git diff --check`: passed.
- Out-of-tree Meson build with `-Dopenvpn3=false`: compile and 1/1 Meson test passed.
- Direct dependency audit:
  `/tmp/eovpn-pip-audit-venv/bin/pip-audit --strict -r requirements.txt`
  returned `No known vulnerabilities found` with exit code 0.
- Runtime Python requirements are now exact-pinned (`cffi==1.16.0`,
  `PyGObject==3.48.2`) and the direct audit was rerun successfully.
- GUI startup under a temporary D-Bus session and Xvfb with software X11
  rendering remained alive for the bounded 10-second window and exited only
  because the test timeout fired. The previous GTK CSS warnings for unsupported
  `flex` and `max-width` properties were removed.
- A controlled launch of the rebuilt application under the current desktop
  Wayland session remained alive for 12 seconds and exited only because the
  test timeout fired; no traceback or segmentation fault was emitted. The
  final detached launch is performed only after this validation snapshot.
- All 11 Flatpak `type: git` sources now use immutable `commit:` revisions and
  no `tag:` fields remain in the manifest. The two OpenVPN Codeberg revisions
  were resolved through their verified GitHub mirrors because direct Codeberg
  access was unavailable from this host.
- A fresh Codex Security scan was started against this snapshot, but its
  workbench remains stuck in preflight after the two checks passed and has not
  produced canonical artifacts. It is therefore not claimed as a clean or
  sealed scan.
- An independent headless Standard scan was started as
  `a8dadc1e-913c-480c-a6bb-7e3e1a32b51f`, but its handoff token was reported as
  owned by another continuation when context/progress was requested. No
  artifact or finding was inferred from that condition.
- The independent Deep Scan path could not start because the current host did
  not provide the managed filesystem permission profile required by the
  security worker. This is an execution-environment blocker, not a finding in
  the application code.
- Remediations included: no empty Secret Service credential lookup, HTTPS
  redirects cannot target local/private hosts, OpenVPN3 cannot disconnect
  unowned sessions, OpenVPN3 D-Bus calls have bounded timeouts, and Arch
  release builds refuse an unpinned source checksum. Profiles containing
  executable, plugin, management, or trust-sensitive directives are now
  refused by both connection backends and reported as a connection failure.
- Plugin Management search confirmed that Codex Security is enabled and
  installed; no additional plugin was required for this local repository task.
- A bounded live NetworkManager attempt was made with an existing imported TCP
  profile and a 30-second timeout. It timed out without activating a VPN and
  was confirmed to leave no active VPN connection. This proves the failure is
  bounded and non-sticky, but does not prove a successful VPN connection.
- The NetworkManager operation race that could silently drop a queued
  disconnect/next-candidate request was fixed. Native operations are now
  serialized in order, and a regression test covers connect-then-disconnect
  queueing. The rebuilt prefix was installed and the updated GUI was relaunched
  in a live terminal session.

## Still not owner-verified

- A real VPN connect/disconnect was not performed. Doing so changes
  NetworkManager/system state and requires the owner's live profile choice and
  visual acceptance.
- OpenVPN 3 userspace/backend is not installed on this host. OpenVPN 2.6.19 is
  installed, and the kernel DCO module (`ovpn.ko`) is present and loaded. The
  supported, verified runtime remains NetworkManager with OpenVPN 2; the UI
  reports OpenVPN 3 as unavailable instead of silently falling back.
- An out-of-tree `meson setup -Dopenvpn3=true` probe reached the OpenVPN 3
  subproject but stopped at enum extraction because Python cannot import
  `openvpn3.constants`; the build output explicitly recommends the missing
  `python3-openvpn3` package or `-Dopenvpn3=false`. No privileged install was
  attempted.
- The configured PyPI index has no `openvpn3` distribution and the local APT
  cache has no `python3-openvpn3` or `openvpn3` package, so this dependency
  cannot be resolved from the current package sources without an external
  OpenVPN 3 SDK/repository and privileged installation.
- A read-only inventory of the imported configuration directory found 276
  `.ovpn` files; all 276 contain at least one fail-closed directive from the
  dangerous profile policy (`down`, `up`, `script-security`, `setenv`, or a
  related hook). No profile was rewritten or deleted, and no unsafe bypass was
  introduced.
- A complete interactive GUI scenario pass and owner visual acceptance remain
  pending. Xvfb startup is not a substitute for that acceptance.

## Scan caveat

The prior scan was not used as a clean result: an independent review surfaced
security issues that were remediated in the current tree. The fresh scan must
finish and produce sealed canonical artifacts against this snapshot before
security closure can be claimed. The remaining blocker is the security
workbench execution/artifact gate, not an identified unpinned Flatpak source.
