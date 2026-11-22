#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  AirSense — εγκατάσταση/ενημέρωση σε Luckfox Pico με ΜΙΑ εντολή (πάντα η τελευταία έκδοση)
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
echo "… εργαλεία (wget, unzip)"
command -v wget >/dev/null && command -v unzip >/dev/null || {
  apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq wget unzip >/dev/null; }
echo "… κατέβασμα τελευταίας έκδοσης AirSense"
rm -rf AirSense-Luckfox AirSense-Luckfox.zip
wget -q --show-progress -O AirSense-Luckfox.zip \
  https://github.com/nikkpap/AirSense/releases/latest/download/AirSense-Luckfox.zip
unzip -oq AirSense-Luckfox.zip
chown -R "$U": AirSense-Luckfox AirSense-Luckfox.zip 2>/dev/null || true
exec bash AirSense-Luckfox/airsense-setup.sh "$@"
