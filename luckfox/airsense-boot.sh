#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  AirSense — start on boot (Luckfox Pico Pro/Max · Ubuntu)
#  Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM
#
#  On every boot:
#   1. looks for AirSense*.py / AirSense*.pyw on the SD card, USB sticks and the user's home
#   2. if it finds a newer (or changed) one, copies it to /opt/airsense
#   3. applies airsense-settings.txt (if it is next to the app)
#   3b. Tailscale: if «tailscale.sh» exists (next to the app / SD card root / USB) → runs it
#       automatically (install + login). If it does NOT exist → local only (Tailscale off).
#   4. checks/installs what is missing (python3, reportlab, fonts) when online
#   5. starts the server (systemd restarts it if it stops)
# ═══════════════════════════════════════════════════════════════════════════
APP_DIR=/opt/airsense
APP=$APP_DIR/AirSense.py
DATA=/var/lib/airsense
SCAN=/run/airsense-scan
LOG=$DATA/boot.log
mount -o remount,size=32M /run 2>/dev/null   # low RAM: room for systemd/apt (e.g. Tailscale install)
mkdir -p "$APP_DIR" "$DATA" "$SCAN"
exec > >(tee -a "$LOG") 2>&1
echo "──── $(date '+%F %T') · airsense-boot ────"
# keep boot.log small
[ "$(wc -c < "$LOG" 2>/dev/null || echo 0)" -gt 300000 ] && tail -c 100000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"

ver_of() { grep -m1 -oP '^APP_VERSION = "\K[^"]+' "$1" 2>/dev/null || echo 0; }
newer() { [ "$1" = "$2" ] && return 1; [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -1)" = "$1" ]; }

# ── 1. find the app ─────────────────────────────────────────────────────────
DIRS=(/ /root /boot /boot/firmware /mnt/sdcard /media /mnt /userdata /oem)
for h in /home/*; do [ -d "$h" ] && DIRS+=("$h"); done
# whatever is already mounted from SD card / USB
while read -r src tgt; do
  case "$src" in /dev/mmcblk*|/dev/sd*) DIRS+=("$tgt") ;; esac
done < <(findmnt -rn -o SOURCE,TARGET 2>/dev/null)
# partitions that are NOT mounted (e.g. a FAT partition or USB stick) → temporarily, read-only
MOUNTED_TMP=()
for dev in /dev/mmcblk*p* /dev/sd[a-z][0-9]* /dev/sd[a-z]; do
  [ -b "$dev" ] || continue
  findmnt -rn -S "$dev" >/dev/null 2>&1 && continue
  fs=$(blkid -o value -s TYPE "$dev" 2>/dev/null)
  case "$fs" in vfat|exfat|ntfs|ext2|ext3|ext4) ;; *) continue ;; esac
  mp="$SCAN/$(basename "$dev")"
  mkdir -p "$mp"
  if mount -o ro "$dev" "$mp" 2>/dev/null; then MOUNTED_TMP+=("$mp"); DIRS+=("$mp"); fi
done

BEST=""; BESTV=0; TS_SCRIPT=""
for d in "${DIRS[@]}"; do
  [ -z "$TS_SCRIPT" ] && [ -f "$d/tailscale.sh" ] && { cp -f "$d/tailscale.sh" /run/airsense-tailscale.sh; TS_SCRIPT="$d/tailscale.sh"; }
  for f in "$d"/AirSense*.py "$d"/AirSense*.pyw "$d"/ALU_AirSense*.pyw "$d"/ALU_HygroLink*.pyw; do
    [ -f "$f" ] || continue
    grep -q '^APP_VERSION = ' "$f" || continue
    v=$(ver_of "$f")
    if [ -z "$BEST" ] || newer "$v" "$BESTV"; then BEST="$f"; BESTV="$v"; fi
  done
done

if [ -n "$BEST" ]; then
  CURV=$(ver_of "$APP")
  if [ ! -f "$APP" ] || newer "$BESTV" "$CURV" || { [ "$BESTV" = "$CURV" ] && ! cmp -s "$BEST" "$APP"; }; then
    cp -f "$BEST" "$APP.new" && sed -i 's/\r$//' "$APP.new" && mv -f "$APP.new" "$APP"
    echo "✔ App: $BEST (v$BESTV) → $APP"
  else
    echo "✔ App: v$CURV (already installed · also found $BEST)"
  fi
  SRC_DIR=$(dirname "$BEST")
  # ── 3. settings from airsense-settings.txt ──────────────────────────────────
  SET="$SRC_DIR/airsense-settings.txt"
  [ -f "$SET" ] || SET=""
  if [ -n "$SET" ] && ! cmp -s "$SET" "$DATA/settings.applied" 2>/dev/null; then
    cp -f "$SET" "$DATA/settings.applied"
    echo "⚙ Settings from $SET"
  fi
else
  if [ -f "$APP" ]; then echo "ℹ No new version found — running v$(ver_of "$APP")"
  else echo "✖ No AirSense*.py on SD card / USB / /home — copy the file there and reboot"; fi
fi
for mp in "${MOUNTED_TMP[@]}"; do umount "$mp" 2>/dev/null; rmdir "$mp" 2>/dev/null; done
[ -f "$APP" ] || { sleep 60; exit 1; }

# ── 4. dependencies ──────────────────────────────────────────────────────────
online() { timeout 5 bash -c 'exec 3<>/dev/tcp/deb.debian.org/80' 2>/dev/null || timeout 5 getent hosts ports.ubuntu.com >/dev/null; }
if ! command -v python3 >/dev/null; then
  echo "… installing python3"; online && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 || true
fi
if ! python3 -c "import reportlab" 2>/dev/null || [ ! -f /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf ]; then
  if online; then
    echo "… installing reportlab + fonts (for PDF reports)"
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-reportlab fonts-dejavu-core >/dev/null 2>&1 \
      || python3 -m pip install -q reportlab 2>/dev/null || true
  fi
fi

# ── clock: wait for time sync (the board keeps no time without an RTC battery) ──
for i in $(seq 1 45); do
  [ "$(timedatectl show -p NTPSynchronized --value 2>/dev/null)" = "yes" ] && break
  [ "$(date +%Y)" -ge 2025 ] && [ "$i" -gt 10 ] && break
  sleep 2
done
echo "🕒 $(date '+%F %T %Z')"

# ── apply settings (once per change of the file) ──
if [ -f "$DATA/settings.applied" ] && ! cmp -s "$DATA/settings.applied" "$DATA/settings.done" 2>/dev/null; then
  get() { grep -m1 -E "^[[:space:]]*$1[[:space:]]*=" "$DATA/settings.applied" | sed -E "s/^[^=]*=[[:space:]]*//; s/[[:space:]]*$//; s/\r$//"; }
  A=$(get ADMIN_PASSWORD); P=$(get PIN); S=$(get SENSORS); C=$(get CITY); H=$(get HOSTNAME)
  run() { python3 "$APP" --data "$DATA" "$@" 2>&1 | sed 's/^/   /'; }
  [ -n "$A" ] && AIRSENSE_ADMIN_PW="$A" run --set-admin
  [ -n "$P" ] && run --set-pin "$P"
  if [ -n "$S" ]; then IFS=', ' read -ra L <<< "$S"; for ip in "${L[@]}"; do [ -n "$ip" ] && run --add "$ip"; done; fi
  [ -n "$C" ] && run --locate "$C"
  if [ -n "$H" ] && [ "$H" != "$(hostname)" ]; then
    O=$(hostname); echo "$H" > /etc/hostname
    if grep -q "^127\.0\.1\.1" /etc/hosts; then sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t$H/" /etc/hosts; else echo -e "127.0.1.1\t$H" >> /etc/hosts; fi
    sed -i "s/\b$O\b/$H/g" /etc/hosts; hostname "$H"; systemctl restart avahi-daemon 2>/dev/null; echo "   name: $H"
  fi
  cp -f "$DATA/settings.applied" "$DATA/settings.done"
  echo "✔ Settings applied"
fi

# ── Tailscale: tailscale.sh exists → ON · missing → local only ──
if [ -n "$TS_SCRIPT" ]; then
  echo "🌍 Found $TS_SCRIPT → Tailscale ON"
  sed -i 's/\r$//' /run/airsense-tailscale.sh
  # in the background, so the server starts right away (even if the internet is slow)
  ( online || sleep 20; bash /run/airsense-tailscale.sh 2>&1 | sed 's/^/   [tailscale] /' >> "$LOG" ) &
else
  if command -v tailscale >/dev/null && systemctl is-enabled tailscaled >/dev/null 2>&1; then
    tailscale down >/dev/null 2>&1
    systemctl disable --now tailscaled >/dev/null 2>&1
    echo "🏠 No tailscale.sh → local only (Tailscale OFF)"
  else
    echo "🏠 Local only (no tailscale.sh)"
  fi
fi

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo "▶ AirSense v$(ver_of "$APP") → http://${IP:-?}:8765"
exec python3 "$APP" --headless --data "$DATA"
