#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  AirSense — εκκίνηση στο boot (Luckfox Pico Pro/Max · Ubuntu)
#  Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM
#
#  Σε κάθε εκκίνηση:
#   1. ψάχνει το AirSense*.py / AirSense*.pyw στην κάρτα SD, σε USB στικάκια και στον φάκελο του χρήστη
#   2. αν βρει νεότερο (ή αλλαγμένο), το αντιγράφει στο /opt/airsense
#   3. εφαρμόζει το airsense-settings.txt (αν υπάρχει δίπλα στην εφαρμογή)
#   3b. Tailscale: αν υπάρχει το «tailscale.sh» (δίπλα στην εφαρμογή / στη ρίζα της κάρτας / USB) → τρέχει
#       αυτόματα (εγκατάσταση + σύνδεση Tailscale). Αν ΔΕΝ υπάρχει → μόνο τοπικά (το Tailscale σβήνει).
#   4. ελέγχει/εγκαθιστά ό,τι λείπει (python3, reportlab, γραμματοσειρές) όταν υπάρχει internet
#   5. ξεκινά τον server (το systemd τον ξανανοίγει αν κλείσει)
# ═══════════════════════════════════════════════════════════════════════════
APP_DIR=/opt/airsense
APP=$APP_DIR/AirSense.py
DATA=/var/lib/airsense
SCAN=/run/airsense-scan
LOG=$DATA/boot.log
mkdir -p "$APP_DIR" "$DATA" "$SCAN"
exec > >(tee -a "$LOG") 2>&1
echo "──── $(date '+%F %T') · airsense-boot ────"
# κρατά το boot.log μικρό
[ "$(wc -c < "$LOG" 2>/dev/null || echo 0)" -gt 300000 ] && tail -c 100000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"

ver_of() { grep -m1 -oP '^APP_VERSION = "\K[^"]+' "$1" 2>/dev/null || echo 0; }
newer() { [ "$1" = "$2" ] && return 1; [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -1)" = "$1" ]; }

# ── 1. αναζήτηση της εφαρμογής ──────────────────────────────────────────────
DIRS=(/ /root /boot /boot/firmware /mnt/sdcard /media /mnt /userdata /oem)
for h in /home/*; do [ -d "$h" ] && DIRS+=("$h"); done
# ό,τι είναι ήδη προσαρτημένο από κάρτα SD / USB
while read -r src tgt; do
  case "$src" in /dev/mmcblk*|/dev/sd*) DIRS+=("$tgt") ;; esac
done < <(findmnt -rn -o SOURCE,TARGET 2>/dev/null)
# κατατμήσεις που ΔΕΝ είναι προσαρτημένες (π.χ. FAT της κάρτας ή USB στικάκι) → προσωρινά, μόνο για ανάγνωση
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
    echo "✔ Εφαρμογή: $BEST (v$BESTV) → $APP"
  else
    echo "✔ Εφαρμογή: v$CURV (ήδη εγκατεστημένη · βρέθηκε και $BEST)"
  fi
  SRC_DIR=$(dirname "$BEST")
  # ── 3. ρυθμίσεις από airsense-settings.txt ─────────────────────────────────
  SET="$SRC_DIR/airsense-settings.txt"
  [ -f "$SET" ] || SET=""
  if [ -n "$SET" ] && ! cmp -s "$SET" "$DATA/settings.applied" 2>/dev/null; then
    cp -f "$SET" "$DATA/settings.applied"
    echo "⚙ Ρυθμίσεις από $SET"
  fi
else
  if [ -f "$APP" ]; then echo "ℹ Δεν βρέθηκε νέα έκδοση — τρέχει η v$(ver_of "$APP")"
  else echo "✖ Δεν βρέθηκε AirSense*.py σε κάρτα SD / USB / /home — βάλε το αρχείο και κάνε reboot"; fi
fi
for mp in "${MOUNTED_TMP[@]}"; do umount "$mp" 2>/dev/null; rmdir "$mp" 2>/dev/null; done
[ -f "$APP" ] || { sleep 60; exit 1; }

# ── 4. εξαρτήσεις ───────────────────────────────────────────────────────────
online() { timeout 5 bash -c 'exec 3<>/dev/tcp/deb.debian.org/80' 2>/dev/null || timeout 5 getent hosts ports.ubuntu.com >/dev/null; }
if ! command -v python3 >/dev/null; then
  echo "… εγκατάσταση python3"; online && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 || true
fi
if ! python3 -c "import reportlab" 2>/dev/null || [ ! -f /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf ]; then
  if online; then
    echo "… εγκατάσταση reportlab + γραμματοσειρών (για τις αναφορές PDF)"
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-reportlab fonts-dejavu-core >/dev/null 2>&1 \
      || python3 -m pip install -q reportlab 2>/dev/null || true
  fi
fi

# ── ρολόι: περιμένει συγχρονισμό ώρας (η πλακέτα δεν κρατά ώρα χωρίς μπαταρία RTC) ──
for i in $(seq 1 45); do
  [ "$(timedatectl show -p NTPSynchronized --value 2>/dev/null)" = "yes" ] && break
  [ "$(date +%Y)" -ge 2025 ] && [ "$i" -gt 10 ] && break
  sleep 2
done
echo "🕒 $(date '+%F %T %Z')"

# ── εφαρμογή ρυθμίσεων (μία φορά για κάθε αλλαγή του αρχείου) ──
if [ -f "$DATA/settings.applied" ] && ! cmp -s "$DATA/settings.applied" "$DATA/settings.done" 2>/dev/null; then
  get() { grep -m1 -E "^[[:space:]]*$1[[:space:]]*=" "$DATA/settings.applied" | sed -E "s/^[^=]*=[[:space:]]*//; s/[[:space:]]*$//; s/\r$//"; }
  A=$(get ADMIN_PASSWORD); P=$(get PIN); S=$(get SENSORS); C=$(get CITY); H=$(get HOSTNAME)
  run() { python3 "$APP" --data "$DATA" "$@" 2>&1 | sed 's/^/   /'; }
  [ -n "$A" ] && AIRSENSE_ADMIN_PW="$A" run --set-admin
  [ -n "$P" ] && run --set-pin "$P"
  if [ -n "$S" ]; then IFS=', ' read -ra L <<< "$S"; for ip in "${L[@]}"; do [ -n "$ip" ] && run --add "$ip"; done; fi
  [ -n "$C" ] && run --locate "$C"
  if [ -n "$H" ] && [ "$H" != "$(hostname)" ]; then hostnamectl set-hostname "$H" && sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t$H/" /etc/hosts && echo "   όνομα: $H"; fi
  cp -f "$DATA/settings.applied" "$DATA/settings.done"
  echo "✔ Ρυθμίσεις εφαρμόστηκαν"
fi

# ── Tailscale: υπάρχει tailscale.sh → ON · δεν υπάρχει → μόνο τοπικά ──
if [ -n "$TS_SCRIPT" ]; then
  echo "🌍 Βρέθηκε $TS_SCRIPT → Tailscale ON"
  sed -i 's/\r$//' /run/airsense-tailscale.sh
  # στο παρασκήνιο, ώστε ο server να ξεκινά αμέσως (ακόμα κι αν αργεί το internet)
  ( online || sleep 20; bash /run/airsense-tailscale.sh 2>&1 | sed 's/^/   [tailscale] /' >> "$LOG" ) &
else
  if command -v tailscale >/dev/null && systemctl is-enabled tailscaled >/dev/null 2>&1; then
    tailscale down >/dev/null 2>&1
    systemctl disable --now tailscaled >/dev/null 2>&1
    echo "🏠 Δεν υπάρχει tailscale.sh → μόνο τοπικά (Tailscale OFF)"
  else
    echo "🏠 Μόνο τοπικά (χωρίς tailscale.sh)"
  fi
fi

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo "▶ AirSense v$(ver_of "$APP") → http://${IP:-?}:8765"
exec python3 "$APP" --headless --data "$DATA"
