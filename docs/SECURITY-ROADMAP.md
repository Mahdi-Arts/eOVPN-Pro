# 🛡️ eOVPN-Pro Security Roadmap
# نقشه راه امنیتی eOVPN-Pro

This document tracks the security hardening work that is planned but not yet
implemented in code. Items move from here into `CHANGELOG.md` only when the
feature actually ships and is covered by tests or manual verification steps.

این سند کارهای مقاوم‌سازی امنیتی را دنبال می‌کند که برنامه‌ریزی شده ولی هنوز در
کد پیاده نشده‌اند. هر مورد فقط وقتی به `CHANGELOG.md` منتقل می‌شود که واقعاً
منتشر شده و با تست یا مراحل راستی‌آزمایی دستی پوشش داده شده باشد.

---

## 1. Kill-Switch / کلید قطع اتصال

**Status:** Planned / برنامه‌ریزی‌شده — target 1.6.0

**Problem / مسئله:**
When the tunnel drops, traffic falls back to the default route until
auto-reconnect succeeds (or forever if it never does). A user with a strict
threat model must currently pair eOVPN-Pro with external firewall rules.

هنگام قطع تونل، ترافیک تا زمان موفقیت اتصال مجدد خودکار (یا برای همیشه در صورت
شکست) به مسیر پیش‌فرض بازمی‌گردد. کاربر با مدل تهدید سخت‌گیرانه اکنون باید برنامه
را با قواعد فایروال خارجی همراه کند.

**Design / طراحی:**

1. A `kill-switch` GSettings key (`b`, default `false`) + a toggle in the
   General settings tab.
2. On `DISCONNECTED` (unexpected), before any reconnect attempt: flush
   `conntrack`-tracked non-VPN flows and apply the drop rules.
3. Firewall strategy (ordered by portability):
   - **Preferred:** `nftables` — a dedicated `eovpn` table with an output
     drop-set that only permits `tun+`/loopback and the VPN server endpoint.
   - **Fallback:** `iptables` legacy commands.
   - Both require elevated privileges → integrate via `pkexec` (Polkit)
     so the user gets a single, explicit authorization prompt; the polkit
     action file ships with the package.
4. On clean connect: insert the endpoint allow-rule, then the drop-set.
   On clean disconnect: remove the table atomically.
5. Failure to install rules = fail closed (stay disconnected + notify).

**Acceptance criteria / معیار پذیرش:**

- `nft list ruleset` shows the eovpn table only while connected.
- UDP/TCP to any non-VPN destination is refused while connected with
  kill-switch on.
- Auto-reconnect must still work (endpoint allow-rule).

---

## 2. DNS-leak protection / محافظت در برابر نشت DNS

**Status:** Planned / برنامه‌ریزی‌شده — target 1.6.0

**Design / طراحی:**

1. While connected, pin `/etc/resolv.conf` resolution to the pushed DNS
   servers when `pull-filter ignore dhcp-option DNS` is not acceptable.
2. For NetworkManager backend: prefer profiles with
   `ipv4.dns-search`/`dns-priority` pinned, or add a `dns=none` + systemd
   resolved override during tunnel lifetime.
3. For OpenVPN 3 backend: rely on `--dco` + `redirect-gateway` with
   `def1` verification in the audit step (warn when config lacks it).

---

## 3. Release signing & verification / امضای انتشار و راستی‌آزمایی

**Status:** Partially done / تا حدی انجام‌شده — SHA256SUMS via
`.github/workflows/release.yml`

**Design / طراحی:**

1. ✅ `SHA256SUMS` manifest attached to every release.
2. ⬜ GPG detached signatures for the manifest (`gpg --detach-sign`).
3. ⬜ Sigstore / SLSA provenance on the release workflow (planned:
   `actions/attest-build-provenance` rollout to all artifacts).

---

## 4. Flatpak permission tightening / تنگ‌تر کردن مجوزهای Flatpak

**Status:** Planned / برنامه‌ریزی‌شده

- Replace the broad `--system-talk-name=org.freedesktop.NetworkManager` with
  a D-Bus filter policy via `xdg-dbus-proxy` rules in `finish-args`
  (`--system-talk-name=org.freedesktop.NetworkManager.VPN.*` subset).
- Re-review the bundled `0001-disable-ownership-check-for-plugins.patch`
  against every upstream NetworkManager bump.

---

*یا علی مدد 💚*
