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
ask()  { local a; read -r -p "$(echo -e "${Y}?${N} $1 [${2:-ν}/ο]: ")" a; a=${a:-${2:-ν}}; [[ "$a" =~ ^(y|Y|ν|Ν|yes|ναι|Ναι)$ ]]; }

[ "$(id -u)" = 0 ] || exec sudo bash "$0" "$@"
HERE=$(cd "$(dirname "$0")" && pwd)
USER_NAME=${SUDO_USER:-pico}
[ "$USER_NAME" = root ] && USER_NAME=$(ls /home | head -1)
USER_HOME=$(getent passwd "$USER_NAME" | cut -d: -f6); USER_HOME=${USER_HOME:-/root}
NONINTERACTIVE=0; [ -t 0 ] || NONINTERACTIVE=1
for a in "$@"; do [ "$a" = "-y" ] && NONINTERACTIVE=1; done
[ "$NONINTERACTIVE" = 1 ] && ask() { [[ "${2:-ν}" =~ ^(ν|y)$ ]]; }

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
apt-get update -qq || warn "apt update απέτυχε"
apt-get install -y -qq --no-install-recommends python3 python3-reportlab fonts-dejavu-core avahi-daemon curl \
  ca-certificates qrencode util-linux >/dev/null 2>&1 \
  || apt-get install -y -qq python3 curl ca-certificates || warn "Κάποια πακέτα δεν μπήκαν — θα ξαναδοκιμάσει στο boot"
python3 -c "import reportlab" 2>/dev/null && ok "python3 $(python3 -V | cut -d' ' -f2) + reportlab" || warn "χωρίς reportlab (τα PDF θα δοκιμάσουν αργότερα)"
systemctl enable --now systemd-timesyncd >/dev/null 2>&1 && ok "Συγχρονισμός ώρας (NTP)"
timedatectl set-timezone Europe/Athens 2>/dev/null && ok "Ζώνη ώρας: Europe/Athens"

# ── 4. Αρχεία + υπηρεσία ──────────────────────────────────────────────────
step "4/6 AirSense + αυτόματη εκκίνηση"
install -d /opt/airsense /var/lib/airsense
install -m 755 "$HERE/airsense-boot.sh" /usr/local/sbin/airsense-boot
install -m 755 "$HERE/airsense" /usr/local/bin/airsense
install -D -m 755 "$HERE/tailscale.sh" /usr/local/share/airsense/tailscale.sh
sed -i 's/\r$//' /usr/local/sbin/airsense-boot /usr/local/bin/airsense
# η εφαρμογή στον φάκελο του χρήστη (εκεί τη βρίσκει το boot — αντικατάστησέ τη για ενημέρωση)
rm -f "$USER_HOME"/AirSense_v*.pyw
cp -f "$APP_SRC" "$USER_HOME/$(basename "$APP_SRC")"
[ -f "$HERE/airsense-settings.txt" ] && [ ! -f "$USER_HOME/airsense-settings.txt" ] && cp "$HERE/airsense-settings.txt" "$USER_HOME/"
chown "$USER_NAME": "$USER_HOME"/AirSense_v*.pyw "$USER_HOME/airsense-settings.txt" 2>/dev/null
cat > /etc/systemd/system/airsense-boot.service <<EOF
[Unit]
Description=AirSense server (BleBox humiditySensor) — αυτόματη εκκίνηση
Wants=network-online.target time-sync.target
After=network-online.target time-sync.target

[Service]
Type=simple
ExecStart=/usr/local/sbin/airsense-boot
Restart=always
RestartSec=10
TimeoutStartSec=infinity
Environment=PYTHONUNBUFFERED=1
Nice=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable airsense-boot >/dev/null 2>&1
systemctl enable systemd-networkd-wait-online >/dev/null 2>&1 || true
ok "Υπηρεσία airsense-boot (ξεκινά σε κάθε εκκίνηση, ξανανοίγει αν κλείσει)"

# ── 5. Όνομα στο δίκτυο ───────────────────────────────────────────────────
step "5/6 Όνομα στο δίκτυο"
if [ "$(hostname)" != "airsense" ] && ask "Όνομα συσκευής «airsense» (→ http://airsense.local:8765);" ν; then
  hostnamectl set-hostname airsense
  grep -q "127.0.1.1" /etc/hosts && sed -i "s/^127\.0\.1\.1.*/127.0.1.1\tairsense/" /etc/hosts || echo -e "127.0.1.1\tairsense" >> /etc/hosts
  systemctl restart avahi-daemon 2>/dev/null
fi
ok "Όνομα: $(hostname) → http://$(hostname).local:8765"

# ── 6. Tailscale ───────────────────────────────────────────────────────────
step "6/6 Tailscale (πρόσβαση από παντού)"
echo "   Κανόνας: υπάρχει το ~/tailscale.sh → Tailscale ON σε κάθε boot · δεν υπάρχει → μόνο τοπικά."
if [ -f "$USER_HOME/tailscale.sh" ]; then
  ok "Υπάρχει ήδη το $USER_HOME/tailscale.sh (ON)"
elif ask "Θέλεις Tailscale;" ν; then
  cp -f "$HERE/tailscale.sh" "$USER_HOME/tailscale.sh"; chown "$USER_NAME": "$USER_HOME/tailscale.sh"; chmod 755 "$USER_HOME/tailscale.sh"
  ok "Tailscale ON"
else
  ok "Μόνο τοπικά (Tailscale ενεργοποιείται αργότερα με: airsense tailscale on)"
fi
[ -f "$USER_HOME/tailscale.sh" ] && bash "$USER_HOME/tailscale.sh"

# ── Εκκίνηση ──────────────────────────────────────────────────────────────
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
echo -e "  🔄 Ενημέρωση: βάλε νέο AirSense_vX.pyw στο $USER_HOME (ή USB) και κάνε ${B}sudo reboot${N}"
echo -e "${G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
command -v qrencode >/dev/null && qrencode -t ANSIUTF8 "http://$IP:8765"
