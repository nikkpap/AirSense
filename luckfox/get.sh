#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  AirSense — install/update on Luckfox Pico with ONE command (always the latest version)
#
#    wget -qO get.sh https://raw.githubusercontent.com/nikkpap/AirSense/main/luckfox/get.sh && sudo bash get.sh
#
#  Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM
# ═══════════════════════════════════════════════════════════════════════════
set -e
[ "$(id -u)" = 0 ] || exec sudo bash "$0" "$@"
mount -o remount,size=32M /run 2>/dev/null || true
U=${SUDO_USER:-pico}
H=$(getent passwd "$U" | cut -d: -f6); H=${H:-/root}
cd "$H"
echo "… tools (wget, unzip)"
command -v wget >/dev/null && command -v unzip >/dev/null || {
  apt-get -o DPkg::Lock::Timeout=600 update -qq && DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=600 install -y -qq wget unzip >/dev/null; }
echo "… downloading the latest AirSense"
rm -rf AirSense-Luckfox AirSense-Luckfox.zip
wget -q --show-progress -O AirSense-Luckfox.zip \
  https://github.com/nikkpap/AirSense/releases/latest/download/AirSense-Luckfox.zip
unzip -oq AirSense-Luckfox.zip
chown -R "$U": AirSense-Luckfox AirSense-Luckfox.zip 2>/dev/null || true
exec bash AirSense-Luckfox/airsense-setup.sh "$@"
