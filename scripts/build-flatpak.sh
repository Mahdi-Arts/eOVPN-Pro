#!/usr/bin/env bash
# Build and optionally install the Flatpak bundle locally.
# ساخت و نصب اختیاری باندل Flatpak به‌صورت محلی.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="${ROOT_DIR}/dist/flatpak/com.github.mahdi-arts.eovpn-pro.yml"
BUILD_DIR="${ROOT_DIR}/dist/flatpak/build-dir"
REPO_DIR="${ROOT_DIR}/dist/flatpak/repo"
BUNDLE="${ROOT_DIR}/dist/flatpak/eovpn-pro.flatpak"
INSTALL=0

for arg in "$@"; do
  case "$arg" in
    --install) INSTALL=1 ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

command -v flatpak-builder >/dev/null || {
  echo "flatpak-builder is required. Install it first." >&2
  exit 1
}

flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install -y flathub org.gnome.Sdk//50 org.gnome.Platform//50

echo "==> Building Flatpak"
flatpak-builder --repo="${REPO_DIR}" --force-clean "${BUILD_DIR}" "${MANIFEST}"

echo "==> Creating single-file bundle"
flatpak build-bundle "${REPO_DIR}" "${BUNDLE}" com.github.mahdi-arts.eovpn-pro

if [[ "${INSTALL}" == "1" ]]; then
  echo "==> Installing bundle"
  flatpak install -y --user "${BUNDLE}"
  flatpak run com.github.mahdi-arts.eovpn-pro
else
  echo "==> Bundle ready: ${BUNDLE}"
fi
