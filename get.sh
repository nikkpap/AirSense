#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  AirSense — install/update with ONE command (always the latest version)
#  Raspberry Pi (Zero 2 W / 3 / 4 / 5) · Luckfox Pico Pro/Max · other Debian/Ubuntu boards
#
#    wget -qO get.sh https://raw.githubusercontent.com/nikkpap/AirSense/main/get.sh && sudo bash get.sh
#
#  Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM
# ═══════════════════════════════════════════════════════════════════════════
set -e
[ "$(id -u)" = 0 ] || exec sudo bash "$0" "$@"
# low-RAM boards (Luckfox): /run too small for systemd → enlarge (never shrink)
[ "$(df -m --output=size /run 2>/dev/null | tail -1 | tr -d ' ')" -lt 32 ] 2>/dev/null && mount -o remount,size=32M /run 2>/dev/null || true

MODEL=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || true)
case "$MODEL" in
  *Raspberry*)                     PKG=AirSense-Pi ;;
  *Luckfox*|*luckfox*|*LUCKFOX*)   PKG=AirSense-Luckfox ;;
  *) if [ -f /etc/rpi-issue ]; then PKG=AirSense-Pi
     elif grep -qi rv1106 /proc/device-tree/compatible 2>/dev/null; then PKG=AirSense-Luckfox
     else PKG=AirSense-Pi; fi ;;   # any other Debian/Ubuntu board: the generic (Pi) package
esac
echo "🌬 AirSense — board: ${MODEL:-$(uname -m)} → $PKG"

U=${SUDO_USER:-}
[ -z "$U" ] || [ "$U" = root ] && U=$(getent passwd 1000 | cut -d: -f1)
H=$(getent passwd "${U:-root}" | cut -d: -f6); H=${H:-/root}
cd "$H"
echo "… tools (wget, unzip)"
command -v wget >/dev/null && command -v unzip >/dev/null || {
  apt-get -o DPkg::Lock::Timeout=600 update -qq && DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=600 install -y -qq wget unzip >/dev/null; }
echo "… downloading the latest AirSense"
rm -rf "$PKG" "$PKG.zip"
wget -q --show-progress -O "$PKG.zip" "https://github.com/nikkpap/AirSense/releases/latest/download/$PKG.zip"
unzip -oq "$PKG.zip"
[ -n "$U" ] && chown -R "$U": "$PKG" "$PKG.zip" 2>/dev/null || true
exec bash "$PKG/airsense-setup.sh" "$@"
