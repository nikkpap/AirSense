#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  AirSense — αυτόματη ενημέρωση από το GitHub (Luckfox Pico)
#  Τρέχει από το airsense-update.timer (λίγα λεπτά μετά το boot και κάθε 6 ώρες)
#  ή με το χέρι:  airsense update      (ή: sudo airsense-update --force)
#
#  Απενεργοποίηση:  airsense autoupdate off   (ή AUTO_UPDATE=off στο airsense-settings.txt)
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

# ── ενεργό; ──
if [ "$FORCE" = 0 ]; then
  [ -f "$DATA/autoupdate.off" ] && { log "Αυτόματη ενημέρωση: OFF (airsense autoupdate on)"; exit 0; }
  if [ -f "$DATA/settings.applied" ] && grep -qiE '^[[:space:]]*AUTO_UPDATE[[:space:]]*=[[:space:]]*(off|no|0|όχι|οχι)' "$DATA/settings.applied"; then
    log "Αυτόματη ενημέρωση: OFF (AUTO_UPDATE=off στις ρυθμίσεις)"; exit 0
  fi
fi

ver_of() { grep -m1 -oP '^APP_VERSION = "\K[^"]+' "$1" 2>/dev/null || echo 0; }
newer() { [ "$1" = "$2" ] && return 1; [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -1)" = "$1" ]; }

CUR=$(ver_of "$APP")
JSON=$(curl -fsSL --max-time 25 -H "Accept: application/vnd.github+json" \
       "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null) \
  || { log "✖ Δεν απάντησε το GitHub (internet;) — τρέχουσα v$CUR"; exit 0; }
LATEST=$(echo "$JSON" | grep -m1 -oE '"tag_name": *"v?[^"]+"' | grep -oE '[0-9][0-9.]*[0-9]')
[ -n "$LATEST" ] || { log "✖ Δεν βρέθηκε έκδοση στο GitHub"; exit 0; }

if ! newer "$LATEST" "$CUR"; then
  log "✔ Ενημερωμένο: v$CUR (GitHub: v$LATEST)"
  exit 0
fi

log "⬇ Νέα έκδοση v$LATEST (τρέχουσα v$CUR) — κατέβασμα…"
rm -rf "$TMP"; mkdir -p "$TMP"
if ! curl -fsSL --max-time 300 -o "$TMP/pkg.zip" \
     "https://github.com/$REPO/releases/download/v$LATEST/AirSense-Luckfox_v$LATEST.zip"; then
  curl -fsSL --max-time 300 -o "$TMP/pkg.zip" \
     "https://github.com/$REPO/releases/latest/download/AirSense-Luckfox.zip" \
    || { log "✖ Το κατέβασμα απέτυχε"; exit 1; }
fi
command -v unzip >/dev/null || { apt-get install -y -qq unzip >/dev/null 2>&1 || python3 -c 1; }
if command -v unzip >/dev/null; then unzip -oq "$TMP/pkg.zip" -d "$TMP" || { log "✖ Χαλασμένο zip"; exit 1; }
else python3 -m zipfile -e "$TMP/pkg.zip" "$TMP" || { log "✖ Χαλασμένο zip"; exit 1; }; fi
P="$TMP/AirSense-Luckfox"
NEWAPP=$(ls -1 "$P"/AirSense_v*.pyw 2>/dev/null | sort -V | tail -1)
[ -n "$NEWAPP" ] && python3 -m py_compile "$NEWAPP" 2>/dev/null || { log "✖ Η νέα εφαρμογή δεν πέρασε τον έλεγχο — καμία αλλαγή"; exit 1; }
sed -i 's/\r$//' "$P"/*.sh "$P"/airsense 2>/dev/null

# ── εργαλεία (scripts) ──
install -m 755 "$P/airsense-boot.sh"   /usr/local/sbin/airsense-boot
install -m 755 "$P/airsense-update.sh" /usr/local/sbin/airsense-update
install -m 755 "$P/airsense"           /usr/local/bin/airsense
install -D -m 755 "$P/tailscale.sh"    /usr/local/share/airsense/tailscale.sh
# το tailscale.sh του χρήστη (αν υπάρχει = ON) — ενημέρωση κρατώντας το AUTHKEY του
U=$(cat "$DATA/user" 2>/dev/null); [ -n "$U" ] || U=$(stat -c %U /home/* 2>/dev/null | grep -v root | head -1); UH=$(getent passwd "${U:-pico}" | cut -d: -f6); UH=${UH:-/home/pico}
if [ -f "$UH/tailscale.sh" ]; then
  K=$(grep -m1 -oP '^AUTHKEY="\K[^"]*' "$UH/tailscale.sh")
  cp -f "$P/tailscale.sh" "$UH/tailscale.sh"; [ -n "$K" ] && sed -i "s|^AUTHKEY=\"\"|AUTHKEY=\"$K\"|" "$UH/tailscale.sh"
  chown "${U:-pico}": "$UH/tailscale.sh" 2>/dev/null
fi
# προαιρετικά βήματα της νέας έκδοσης (π.χ. νέες υπηρεσίες)
[ -f "$P/post-update.sh" ] && bash "$P/post-update.sh" >> "$LOG" 2>&1

# ── η εφαρμογή: στο /home του χρήστη (εκεί τη βρίσκει το boot) ──
rm -f "$UH"/AirSense_v*.pyw
cp -f "$NEWAPP" "$UH/"; chown "${U:-pico}": "$UH/$(basename "$NEWAPP")" 2>/dev/null
mount -o remount,size=32M /run 2>/dev/null
systemctl daemon-reload 2>/dev/null
systemctl restart airsense-boot
sleep 20
log "✔ Ενημερώθηκε σε v$(ver_of "$APP") ($(systemctl is-active airsense-boot))"
rm -rf "$TMP"
