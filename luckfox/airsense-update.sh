#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  AirSense — automatic update from GitHub (Luckfox Pico)
#  Runs from airsense-update.timer (a few minutes after boot and every 6 hours)
#  or by hand:  airsense update      (or: sudo airsense-update --force)
#
#  Turn off:  airsense autoupdate off   (or AUTO_UPDATE=off in airsense-settings.txt)
#  Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM
# ═══════════════════════════════════════════════════════════════════════════
REPO=nikkpap/AirSense
APP=/opt/airsense/AirSense.py
DATA=/var/lib/airsense
LOG=$DATA/update.log
TMP=/tmp/airsense-update
FORCE=0; [ "${1:-}" = "--force" ] && FORCE=1
[ "$(id -u)" = 0 ] || exec sudo bash "$0" "$@"
mkdir -p "$DATA"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
[ "$(wc -c < "$LOG" 2>/dev/null || echo 0)" -gt 100000 ] && tail -c 40000 "$LOG" > "$LOG.t" && mv "$LOG.t" "$LOG"

# ── enabled? ──
if [ "$FORCE" = 0 ]; then
  [ -f "$DATA/autoupdate.off" ] && { log "Auto-update: OFF (airsense autoupdate on)"; exit 0; }
  if [ -f "$DATA/settings.applied" ] && grep -qiE '^[[:space:]]*AUTO_UPDATE[[:space:]]*=[[:space:]]*(off|no|0)' "$DATA/settings.applied"; then
    log "Auto-update: OFF (AUTO_UPDATE=off in settings)"; exit 0
  fi
fi

ver_of() { grep -m1 -oP '^APP_VERSION = "\K[^"]+' "$1" 2>/dev/null || echo 0; }
newer() { [ "$1" = "$2" ] && return 1; [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -1)" = "$1" ]; }

CUR=$(ver_of "$APP")
JSON=$(curl -fsSL --max-time 25 -H "Accept: application/vnd.github+json" \
       "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null) \
  || { log "✖ GitHub did not answer (internet?) — current v$CUR"; exit 0; }
LATEST=$(echo "$JSON" | grep -m1 -oE '"tag_name": *"v?[^"]+"' | grep -oE '[0-9][0-9.]*[0-9]')
[ -n "$LATEST" ] || { log "✖ No version found on GitHub"; exit 0; }

if ! newer "$LATEST" "$CUR"; then
  log "✔ Up to date: v$CUR (GitHub: v$LATEST)"
  exit 0
fi

log "⬇ New version v$LATEST (current v$CUR) — downloading…"
rm -rf "$TMP"; mkdir -p "$TMP"
if ! curl -fsSL --max-time 300 -o "$TMP/pkg.zip" \
     "https://github.com/$REPO/releases/download/v$LATEST/AirSense-Luckfox_v$LATEST.zip"; then
  curl -fsSL --max-time 300 -o "$TMP/pkg.zip" \
     "https://github.com/$REPO/releases/latest/download/AirSense-Luckfox.zip" \
    || { log "✖ Download failed"; exit 1; }
fi
command -v unzip >/dev/null || { apt-get install -y -qq unzip >/dev/null 2>&1 || python3 -c 1; }
if command -v unzip >/dev/null; then unzip -oq "$TMP/pkg.zip" -d "$TMP" || { log "✖ Broken zip"; exit 1; }
else python3 -m zipfile -e "$TMP/pkg.zip" "$TMP" || { log "✖ Broken zip"; exit 1; }; fi
P="$TMP/AirSense-Luckfox"
NEWAPP=$(ls -1 "$P"/AirSense_v*.pyw 2>/dev/null | sort -V | tail -1)
[ -n "$NEWAPP" ] && python3 -m py_compile "$NEWAPP" 2>/dev/null || { log "✖ The new app failed the check — nothing changed"; exit 1; }
sed -i 's/\r$//' "$P"/*.sh "$P"/airsense 2>/dev/null

# ── tools (scripts) ──
install -m 755 "$P/airsense-boot.sh"   /usr/local/sbin/airsense-boot
install -m 755 "$P/airsense-update.sh" /usr/local/sbin/airsense-update
install -m 755 "$P/airsense"           /usr/local/bin/airsense
install -D -m 755 "$P/tailscale.sh"    /usr/local/share/airsense/tailscale.sh
# the user's tailscale.sh (exists = ON) — updated, keeping its AUTHKEY
U=$(cat "$DATA/user" 2>/dev/null); [ -n "$U" ] || U=$(stat -c %U /home/* 2>/dev/null | grep -v root | head -1); UH=$(getent passwd "${U:-pico}" | cut -d: -f6); UH=${UH:-/home/pico}
if [ -f "$UH/tailscale.sh" ]; then
  K=$(grep -m1 -oP '^AUTHKEY="\K[^"]*' "$UH/tailscale.sh")
  cp -f "$P/tailscale.sh" "$UH/tailscale.sh"; [ -n "$K" ] && sed -i "s|^AUTHKEY=\"\"|AUTHKEY=\"$K\"|" "$UH/tailscale.sh"
  chown "${U:-pico}": "$UH/tailscale.sh" 2>/dev/null
fi
# optional steps of the new version (e.g. new services)
[ -f "$P/post-update.sh" ] && bash "$P/post-update.sh" >> "$LOG" 2>&1

# ── the app: in the user's home (the boot service finds it there) ──
rm -f "$UH"/AirSense_v*.pyw
cp -f "$NEWAPP" "$UH/"; chown "${U:-pico}": "$UH/$(basename "$NEWAPP")" 2>/dev/null
mount -o remount,size=32M /run 2>/dev/null
systemctl daemon-reload 2>/dev/null
systemctl restart airsense-boot
sleep 20
log "✔ Updated to v$(ver_of "$APP") ($(systemctl is-active airsense-boot))"
rm -rf "$TMP"
