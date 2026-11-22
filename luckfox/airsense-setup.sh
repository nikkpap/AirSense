#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  AirSense — εγκατάσταση σε Luckfox Pico Pro/Max (Ubuntu 22.04 στην κάρτα SD)
#  Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM
#
#  Τρέχει ΜΙΑ φορά (μετά το φρέσκο Ubuntu):   sudo bash airsense-setup.sh
#  Μετά: σε κάθε εκκίνηση όλα γίνονται αυτόματα (airsense-boot.service).
# ═══════════════════════════════════════════════════════════════════════════
set -u
G='\033[1;32m'; Y='\033[1;33m'; R='\033[1;31m'; B='\033[1;36m'; N='\033[0m'
ok()   { echo -e "${G}✔${N} $*"; }
warn() { echo -e "${Y}⚠${N} $*"; }
die()  { echo -e "${R}✖ $*${N}"; exit 1; }
step() { echo -e "\n${B}━━ $* ━━${N}"; }
# Ερώτηση Y/N — Enter = η προεπιλογή (κεφαλαίο). Δέχεται y/yes/ν/ναι και n/no/ο/όχι.
ask()  {
  local a d=${2:-y} hint
  [[ "$d" =~ ^(y|Y|ν|Ν)$ ]] && hint="Y/n" || hint="y/N"
  while true; do
    read -r -p "$(echo -e "${Y}?${N} $1 (${hint}): ")" a
    a=${a:-$d}
    case "$a" in y|Y|yes|YES|Yes|ν|Ν|ναι|Ναι|ΝΑΙ) return 0 ;; n|N|no|NO|No|ο|Ο|όχι|οχι|Όχι|ΟΧΙ) return 1 ;; esac
    echo "   Γράψε Y (ναι) ή N (όχι) — ή Enter για ${hint%%/*}"
  done
}
# /run μικρό λόγω λίγης RAM → το systemd αρνείται daemon-reload (θέλει 16MB ελεύθερα)
grow_run() { mount -o remount,size=32M /run 2>/dev/null; }
# Όνομα συσκευής — απευθείας στα αρχεία (το hostnamectl αποτυγχάνει σε αυτή την εικόνα)
set_name() {
  local new=$1 old; old=$(hostname)
  [ "$new" = "$old" ] && return 0
  echo "$new" > /etc/hostname
  if grep -q "^127\.0\.1\.1" /etc/hosts; then sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t$new/" /etc/hosts
  else echo -e "127.0.1.1\t$new" >> /etc/hosts; fi
  sed -i "s/\b$old\b/$new/g" /etc/hosts
  hostname "$new" 2>/dev/null
  systemctl restart avahi-daemon 2>/dev/null
  [ "$(cat /etc/hostname)" = "$new" ]
}

[ "$(id -u)" = 0 ] || exec sudo bash "$0" "$@"
HERE=$(cd "$(dirname "$0")" && pwd)
USER_NAME=${SUDO_USER:-pico}
[ "$USER_NAME" = root ] && USER_NAME=$(ls /home | head -1)
USER_HOME=$(getent passwd "$USER_NAME" | cut -d: -f6); USER_HOME=${USER_HOME:-/root}
NONINTERACTIVE=0; [ -t 0 ] || NONINTERACTIVE=1
for a in "$@"; do [ "$a" = "-y" ] && NONINTERACTIVE=1; done
[ "$NONINTERACTIVE" = 1 ] && ask() { [[ "${2:-y}" =~ ^(ν|y|Y)$ ]]; }

echo -e "${B}"
echo "   🌬  AirSense — εγκατάσταση σε Luckfox Pico"
echo -e "${N}   Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM\n"

# ── 1. Έλεγχος ─────────────────────────────────────────────────────────────
step "1/6 Έλεγχος συστήματος"
command -v apt-get >/dev/null || die "Χρειάζεται Ubuntu (με apt). Δες ODIGIES_Luckfox.md → «Γράψιμο Ubuntu στην κάρτα»."
command -v systemctl >/dev/null || die "Χρειάζεται systemd (Ubuntu)."
MEM=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)
ok "$(. /etc/os-release; echo "$PRETTY_NAME") · $(uname -m) · RAM ${MEM}MB · χρήστης $USER_NAME"
APP_SRC=$(ls -1 "$HERE"/AirSense_v*.pyw "$HERE"/AirSense*.py "$HERE"/AirSense*.pyw 2>/dev/null | sort -V | tail -1)
[ -n "$APP_SRC" ] || die "Δεν βρέθηκε το AirSense_vX.pyw δίπλα στο script."
ok "Εφαρμογή: $(basename "$APP_SRC")"
timeout 8 bash -c 'exec 3<>/dev/tcp/ports.ubuntu.com/80' 2>/dev/null && ok "Internet OK" \
  || warn "Δεν φαίνεται internet — θα χρειαστεί για apt/Tailscale (καλώδιο Ethernet στο router;)"

# ── 2. Swap (η πλακέτα έχει λίγη RAM) ──────────────────────────────────────
step "2/6 Swap (μνήμη στην κάρτα SD)"
if [ "$(awk '/SwapTotal/{print $2}' /proc/meminfo)" -gt 100000 ]; then
  ok "Υπάρχει ήδη swap"
else
  SW=/swapfile; SZ=512
  [ "$(df -m / | awk 'NR==2{print $4}')" -lt 1500 ] && SZ=256
  fallocate -l ${SZ}M $SW 2>/dev/null || dd if=/dev/zero of=$SW bs=1M count=$SZ status=none
  chmod 600 $SW && mkswap $SW >/dev/null && swapon $SW
  grep -q "^$SW " /etc/fstab || echo "$SW none swap sw 0 0" >> /etc/fstab
  echo "vm.swappiness=20" > /etc/sysctl.d/90-airsense.conf; sysctl -q -p /etc/sysctl.d/90-airsense.conf
  ok "Swap ${SZ}MB"
fi

# ── 3. Πακέτα ──────────────────────────────────────────────────────────────
step "3/6 Πακέτα (python3, reportlab για PDF, γραμματοσειρές, avahi για airsense.local)"
export DEBIAN_FRONTEND=noninteractive
APT="apt-get -y -o DPkg::Lock::Timeout=600 -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold"
NEED=""
for pkg in python3 python3-reportlab fonts-dejavu-core avahi-daemon curl ca-certificates qrencode; do
  dpkg -s "$pkg" >/dev/null 2>&1 || NEED="$NEED $pkg"
done
if [ -z "$NEED" ]; then
  ok "Όλα τα πακέτα υπάρχουν ήδη"
else
  echo "   Χρειάζονται:$NEED  (σε αυτή την πλακέτα παίρνει 5–15 λεπτά — μην το κλείσεις)"
  pgrep -x apt-get >/dev/null || pgrep -x dpkg >/dev/null && echo "   … περιμένω να τελειώσει άλλη εγκατάσταση (apt/dpkg)"
  dpkg --configure -a >/dev/null 2>&1 || true
  timeout 1200 $APT update 2>&1 | grep -E "^(Get|Hit|Err|E:)" | sed 's/^/   /' || warn "apt update απέτυχε"
  timeout 1800 $APT install --no-install-recommends $NEED 2>&1 | grep -E "^(Get:|Setting up|Unpacking|E:)" | sed 's/^/   /' \
    || warn "Κάποια πακέτα δεν μπήκαν — θα ξαναδοκιμάσει στο boot"
fi
python3 -c "import reportlab" 2>/dev/null && ok "python3 $(python3 -V | cut -d' ' -f2) + reportlab" || warn "χωρίς reportlab (τα PDF θα δοκιμάσουν αργότερα)"
systemctl enable --now systemd-timesyncd >/dev/null 2>&1 && ok "Συγχρονισμός ώρας (NTP)"
timedatectl set-timezone Europe/Athens 2>/dev/null && ok "Ζώνη ώρας: Europe/Athens"

# ── 4. Αρχεία + υπηρεσία ──────────────────────────────────────────────────
step "4/6 AirSense + αυτόματη εκκίνηση"
install -d /opt/airsense /var/lib/airsense
install -m 755 "$HERE/airsense-boot.sh" /usr/local/sbin/airsense-boot
install -m 755 "$HERE/airsense-update.sh" /usr/local/sbin/airsense-update
install -m 755 "$HERE/airsense" /usr/local/bin/airsense
install -D -m 755 "$HERE/tailscale.sh" /usr/local/share/airsense/tailscale.sh
sed -i 's/\r$//' /usr/local/sbin/airsense-boot /usr/local/sbin/airsense-update /usr/local/bin/airsense "$HERE/post-update.sh"
# η εφαρμογή στον φάκελο του χρήστη (εκεί τη βρίσκει το boot — αντικατάστησέ τη για ενημέρωση)
rm -f "$USER_HOME"/AirSense_v*.pyw
cp -f "$APP_SRC" "$USER_HOME/$(basename "$APP_SRC")"
[ -f "$HERE/airsense-settings.txt" ] && [ ! -f "$USER_HOME/airsense-settings.txt" ] && cp "$HERE/airsense-settings.txt" "$USER_HOME/"
chown "$USER_NAME": "$USER_HOME"/AirSense_v*.pyw "$USER_HOME/airsense-settings.txt" 2>/dev/null
echo "$USER_NAME" > /var/lib/airsense/user
grow_run && ok "/run → 32MB (χώρος για το systemd)"
bash "$HERE/post-update.sh"     # υπηρεσίες: airsense-boot, airsense-run-size, airsense-update.timer
ok "Αυτόματη ενημέρωση από το GitHub: ON (10' μετά το boot και κάθε 6 ώρες · airsense autoupdate off)"
systemctl is-enabled airsense-boot >/dev/null 2>&1 || die "Η υπηρεσία δεν ενεργοποιήθηκε — στείλε screenshot"
systemctl enable systemd-networkd-wait-online >/dev/null 2>&1 || true
ok "Υπηρεσία airsense-boot (ξεκινά σε κάθε εκκίνηση, ξανανοίγει αν κλείσει)"

# ── 5. Όνομα στο δίκτυο ───────────────────────────────────────────────────
step "5/6 Όνομα στο δίκτυο"
if [ "$(hostname)" != "airsense" ] && ask "Όνομα συσκευής «airsense» (→ http://airsense.local:8765);" y; then
  set_name airsense || warn "Δεν άλλαξε το όνομα — μένει $(hostname)"
fi
ok "Όνομα: $(hostname) → http://$(hostname).local:8765"

# ── 6. Tailscale ───────────────────────────────────────────────────────────
step "6/6 Tailscale (πρόσβαση από παντού)"
echo "   Κανόνας: υπάρχει το ~/tailscale.sh → Tailscale ON σε κάθε boot · δεν υπάρχει → μόνο τοπικά."
if [ -f "$USER_HOME/tailscale.sh" ]; then
  ok "Υπάρχει ήδη το $USER_HOME/tailscale.sh (ON)"
elif ask "Θέλεις Tailscale (πρόσβαση από παντού);" y; then
  cp -f "$HERE/tailscale.sh" "$USER_HOME/tailscale.sh"; chown "$USER_NAME": "$USER_HOME/tailscale.sh"; chmod 755 "$USER_HOME/tailscale.sh"
  ok "Tailscale ON"
else
  ok "Μόνο τοπικά (Tailscale ενεργοποιείται αργότερα με: airsense tailscale on)"
fi
[ -f "$USER_HOME/tailscale.sh" ] && bash "$USER_HOME/tailscale.sh"

# ── Εκκίνηση ──────────────────────────────────────────────────────────────
grow_run
systemctl enable --now airsense-boot >/dev/null 2>&1
systemctl restart airsense-boot
echo -n "   Ξεκινά ο server"
for i in $(seq 1 60); do
  sleep 2; echo -n "."
  timeout 2 bash -c 'exec 3<>/dev/tcp/127.0.0.1/8765' 2>/dev/null && break
done
echo
IP=$(hostname -I | awk '{print $1}')
if timeout 2 bash -c 'exec 3<>/dev/tcp/127.0.0.1/8765' 2>/dev/null; then
  ok "Ο server τρέχει!"
else
  warn "Ο server αργεί — δες: airsense logs"
fi
echo -e "\n${G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
echo -e "  🏠 Τοπικά:   ${B}http://$IP:8765${N}   ή   ${B}http://$(hostname).local:8765${N}"
TSIP=$(tailscale ip -4 2>/dev/null | head -1); [ -n "$TSIP" ] && echo -e "  🌍 Tailscale: ${B}http://$TSIP:8765${N}"
echo -e "  📱 QR για το κινητό: ${B}airsense qr${N}     · κατάσταση: ${B}airsense${N}"
echo -e "  🔐 Κωδικός διαχειριστή: ${B}airsense set-admin${N} (ή ADMIN_PASSWORD στο ~/airsense-settings.txt)"
echo -e "  🔄 Ενημέρωση: ${B}αυτόματη${N} από το GitHub (κάθε 6 ώρες) · τώρα: ${B}airsense update${N}"
echo -e "${G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
command -v qrencode >/dev/null && qrencode -t ANSIUTF8 "http://$IP:8765"

echo
if ask "Επανεκκίνηση τώρα, για έλεγχο ότι όλα ξεκινούν μόνα τους;" y; then
  echo "   Επανεκκίνηση… σε 1–2 λεπτά: http://$(hostname).local:8765"
  sleep 2; reboot
fi
