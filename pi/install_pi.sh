#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
#  ALU AirSense — εγκατάσταση σε Raspberry Pi (Zero 2 W / 3 / 4 / 5)
#  Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM
#  Χρήση:  bash install_pi.sh
# ═══════════════════════════════════════════════════════════════════════
set -euo pipefail
G='\033[1;32m'; Y='\033[1;33m'; R='\033[1;31m'; B='\033[1;36m'; N='\033[0m'
say()  { echo -e "\n${B}▶ $*${N}"; }
ok()   { echo -e "${G}✔${N} $*"; }
warn() { echo -e "${Y}⚠${N} $*"; }
die()  { echo -e "${R}✖ $*${N}"; exit 1; }
ask()  { # ask "ερώτηση" default(y/n)
  local a d="${2:-y}"
  if [ ! -t 0 ] && [ ! -e /dev/tty ]; then return 1; fi   # χωρίς τερματικό: παράλειψη ερωτήσεων
  read -r -p "$1 [$( [ "$d" = y ] && echo 'Ν/ο' || echo 'ν/Ο' )] " a </dev/tty || a=""
  a="${a:-$d}"; [[ "$a" =~ ^(y|Y|ν|Ν|yes|ναι|Ναι) ]]
}

if [ "$(id -u)" -ne 0 ]; then exec sudo bash "$0" "$@"; fi

RUN_USER="${SUDO_USER:-}"
if [ -z "$RUN_USER" ] || [ "$RUN_USER" = "root" ]; then RUN_USER="$(logname 2>/dev/null || echo root)"; fi
HOME_DIR="$(getent passwd "$RUN_USER" | cut -d: -f6)"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR=/opt/airsense
DATA_DIR="$HOME_DIR/airsense-data"
SRC="$(ls "$SRC_DIR"/ALU_AirSense_v*.pyw 2>/dev/null | sort -V | tail -1 || true)"
[ -n "$SRC" ] || die "Δεν βρέθηκε ALU_AirSense_v*.pyw δίπλα στο install_pi.sh"
VER="$(basename "$SRC" | sed -E 's/^ALU_AirSense_v(.*)\.pyw$/\1/')"

echo -e "${B}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   🌬 ALU AirSense v$VER — Raspberry Pi        "
echo "  ║   Nikolaos K. Paridis (aka nikkpap)           "
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${N}  Χρήστης: $RUN_USER · Δεδομένα: $DATA_DIR"

run_app() { sudo -u "$RUN_USER" python3 "$APP_DIR/ALU_AirSense.pyw" --data "$DATA_DIR" "$@"; }

# ── Μεταφορά από το παλιό όνομα (ALU HygroLink → ALU AirSense) ──
MIGRATED=0
if [ -f /etc/systemd/system/hygrolink.service ]; then
  echo -e "${G}Βρέθηκε το παλιό ALU HygroLink — μεταφέρεται στο νέο όνομα ALU AirSense (κρατάω όλα τα δεδομένα).${N}"
  systemctl disable --now hygrolink hygrolink-bootwifi >/dev/null 2>&1 || true
  rm -f /etc/systemd/system/hygrolink.service /etc/systemd/system/hygrolink-bootwifi.service
  systemctl daemon-reload
  if [ -d "$HOME_DIR/hygrolink-data" ] && [ ! -e "$DATA_DIR" ]; then
    mv "$HOME_DIR/hygrolink-data" "$DATA_DIR" && ok "Δεδομένα: ~/hygrolink-data → ~/airsense-data"
  fi
  rm -rf /opt/hygrolink
  rm -f /usr/local/bin/hygrolink /usr/local/bin/hygrolink-wifi
  MIGRATED=1
fi

UPDATE=0
if [ "$MIGRATED" = 1 ]; then UPDATE=1; ok "Μεταφορά — οι ρυθμίσεις μένουν (κωδικοί, PIN, πόλη, αισθητήρες, Tailscale)"
elif [ -f /etc/systemd/system/airsense.service ]; then
  echo -e "${G}Βρέθηκε ήδη εγκατάσταση AirSense σε αυτό το Pi.${N}"
  if ask "Μόνο ενημέρωση; (κρατάω κωδικούς, PIN, πόλη, αισθητήρες, Tailscale)" y; then UPDATE=1; fi
fi

# ── 1. Πακέτα ──
say "1/6  Πακέτα συστήματος (python3, curl, qrencode)…"
apt-get update -qq || warn "apt update απέτυχε — συνεχίζω"
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 curl ca-certificates qrencode >/dev/null \
  || warn "Κάποια πακέτα δεν εγκαταστάθηκαν — συνεχίζω"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || die "Χρειάζεται Python 3.9 ή νεότερη"
ok "Python $(python3 -c 'import platform; print(platform.python_version())')"

# ── 2. Εφαρμογή ──
say "2/6  Αντιγραφή εφαρμογής στο $APP_DIR…"
systemctl stop airsense 2>/dev/null || true
install -d -m 755 "$APP_DIR"
install -m 644 "$SRC" "$APP_DIR/ALU_AirSense.pyw"
if [ -f "$SRC_DIR/airsense_wifi.py" ]; then
  sed 's/\r$//' "$SRC_DIR/airsense_wifi.py" > /usr/local/bin/airsense-wifi && chmod 755 /usr/local/bin/airsense-wifi
  ok "Εργαλείο WiFi: airsense wifi"
else
  warn "Δεν βρέθηκε airsense_wifi.py — η εντολή «airsense wifi» δεν θα είναι διαθέσιμη"
fi
echo "$VER" > "$APP_DIR/VERSION"
install -d -o "$RUN_USER" -g "$(id -gn "$RUN_USER")" -m 750 "$DATA_DIR"
cat > /usr/local/bin/airsense <<EOF
#!/usr/bin/env bash
# ALU AirSense — εντολή διαχείρισης (Raspberry Pi)
APP=$APP_DIR/ALU_AirSense.pyw
DATA=$DATA_DIR
U=$RUN_USER
SVC=airsense
EOF
cat >> /usr/local/bin/airsense <<'EOF'
run() { if [ "$(id -un)" = "$U" ]; then python3 "$APP" --data "$DATA" "$@"; else sudo -u "$U" python3 "$APP" --data "$DATA" "$@"; fi; }
cfg() { sudo systemctl stop "$SVC"; run "$@"; sudo systemctl start "$SVC"; }
case "${1:-help}" in
  status)    systemctl --no-pager --lines=0 status "$SVC" | head -4; echo; run --status ;;
  url|qr)    run --status | grep -E '^Web' | while read -r a b url; do echo "$a $b $url"; command -v qrencode >/dev/null && qrencode -t ANSIUTF8 -m 1 "$url"; done ;;
  logs)      journalctl -u "$SVC" -n "${2:-80}" --no-pager -o cat ;;
  live)      journalctl -u "$SVC" -f -o cat ;;
  start|stop|restart) sudo systemctl "$1" "$SVC" && echo "✔ $1" ;;
  set-admin) cfg --set-admin ;;
  set-pin)   cfg --set-pin "${2:-}" ;;
  add)       [ -n "${2:-}" ] || { echo "Χρήση: airsense add 192.168.1.50"; exit 1; }; cfg --add "$2" ;;
  city)      cfg --locate "${2:-}" ;;
  update)
    NEW="${2:-$(ls ~/ALU_AirSense_v*.pyw 2>/dev/null | sort -V | tail -1)}"
    [ -f "$NEW" ] || { echo "Βάλε το νέο ALU_AirSense_vX.pyw στο ~ ή: airsense update /path/file.pyw"; exit 1; }
    sudo install -m 644 "$NEW" "$APP" && basename "$NEW" | sed -E 's/^ALU_AirSense_v(.*)\.pyw$/\1/' | sudo tee "$(dirname "$APP")/VERSION" >/dev/null
    sudo systemctl restart "$SVC" && echo "✔ Ενημερώθηκε σε $(cat "$(dirname "$APP")/VERSION")" ;;
  backup)
    F=~/airsense-backup-$(date +%Y%m%d_%H%M).tar.gz
    tar czf "$F" -C "$(dirname "$DATA")" "$(basename "$DATA")" && echo "✔ $F" ;;
  wifi)      sudo /usr/local/bin/airsense-wifi "${@:2}" ;;
  tailscale)
    command -v tailscale >/dev/null || curl -fsSL https://tailscale.com/install.sh | sudo sh
    sudo tailscale up && tailscale ip -4 ;;
  uninstall)
    read -r -p "Απεγκατάσταση; (τα δεδομένα στο $DATA ΜΕΝΟΥΝ) [ν/Ο] " a
    [[ "$a" =~ ^(y|Y|ν|Ν|yes|ναι|Ναι) ]] || exit 0
    sudo systemctl disable --now "$SVC" airsense-bootwifi 2>/dev/null
    sudo rm -f /etc/systemd/system/$SVC.service /etc/systemd/system/airsense-bootwifi.service; sudo systemctl daemon-reload
    sudo rm -rf "$(dirname "$APP")"; sudo rm -f /usr/local/bin/airsense /usr/local/bin/airsense-wifi /usr/local/bin/hygrolink; echo "✔ Απεγκαταστάθηκε" ;;
  version)   cat "$(dirname "$APP")/VERSION" ;;
  *)
    cat <<H
🌬 airsense — εντολές
  airsense status        κατάσταση, αισθητήρες, διευθύνσεις
  airsense qr            QR για το κινητό (στο τερματικό)
  airsense logs | live   καταγραφή (live = συνεχής, Ctrl+C έξοδος)
  airsense restart       επανεκκίνηση  (και start / stop)
  airsense set-admin     κωδικός διαχειριστή
  airsense set-pin 1234  PIN για web/κινητό  (χωρίς αριθμό = αφαίρεση)
  airsense add IP        προσθήκη αισθητήρα με IP
  airsense city "Πόλη"   τοποθεσία καιρού (Open-Meteo)
  airsense update [αρχ.] νέα έκδοση (ALU_AirSense_vX.pyw στο ~)
  airsense backup        αντίγραφο ασφαλείας δεδομένων
  airsense wifi          WiFi του Pi: σάρωση, νέο δίκτυο, αποθηκευμένα (μενού)
  airsense tailscale     εγκατάσταση/σύνδεση Tailscale
  airsense uninstall     απεγκατάσταση (κρατά τα δεδομένα)
H
    ;;
esac
EOF
chmod 755 /usr/local/bin/airsense
ln -sf /usr/local/bin/airsense /usr/local/bin/hygrolink      # η παλιά εντολή δουλεύει ακόμα
ok "Εφαρμογή v$VER και εντολή «airsense» εγκαταστάθηκαν"

# ── 3. Ρυθμίσεις ──
say "3/6  Ρυθμίσεις"
if [ "$UPDATE" = 1 ]; then ok "Ενημέρωση — οι ρυθμίσεις μένουν ως έχουν"; else
if ! run_app --status 2>/dev/null | grep -q 'Διαχειριστής: ναι'; then
  if ask "Ορισμός κωδικού διαχειριστή τώρα; (για τις ρυθμίσεις από web/κινητό)" y; then run_app --set-admin || warn "Παραλείφθηκε"; fi
else ok "Υπάρχει ήδη κωδικός διαχειριστή"; fi
if ask "Ορισμός PIN για πρόσβαση από web/κινητό; (προτείνεται)" y; then
  read -r -p "PIN: " PIN </dev/tty || PIN=""
  run_app --set-pin "$PIN" || true
fi
if ask "Ορισμός πόλης για τον καιρό (Open-Meteo); Αλλιώς θα βρεθεί αυτόματα από την IP" y; then
  read -r -p "Πόλη / χωριό: " CITY </dev/tty || CITY=""
  [ -n "$CITY" ] && { run_app --locate "$CITY" || warn "Δεν ορίστηκε — μπορείς αργότερα: airsense city \"Πόλη\""; }
fi

fi
if [ -x /usr/local/bin/airsense-wifi ] && ask "Θες να αποθηκεύσεις κι άλλο WiFi τώρα; (π.χ. του εργοταξίου — το Pi θα συνδέεται μόνο του όπου το βρει)" n; then
  /usr/local/bin/airsense-wifi </dev/tty || true
fi

# ── 4. Υπηρεσία ──
say "4/6  Υπηρεσία systemd (ξεκινά μόνη της σε κάθε εκκίνηση)…"
cat > /etc/systemd/system/airsense.service <<EOF
[Unit]
Description=ALU AirSense server (BleBox humiditySensor) — nikkpap
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 $APP_DIR/ALU_AirSense.pyw --headless --data $DATA_DIR
Restart=always
RestartSec=10
Nice=5

[Install]
WantedBy=multi-user.target
EOF
if [ -x /usr/local/bin/airsense-wifi ]; then
cat > /etc/systemd/system/airsense-bootwifi.service <<EOF
[Unit]
Description=AirSense: WiFi από την κάρτα SD (airsense-wifi.txt στο bootfs)
After=NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/local/bin/airsense-wifi bootfile

[Install]
WantedBy=multi-user.target
EOF
fi
systemctl daemon-reload
systemctl enable --now airsense >/dev/null 2>&1
if [ -f /etc/systemd/system/airsense-bootwifi.service ]; then
  systemctl enable airsense-bootwifi >/dev/null 2>&1
  systemctl start airsense-bootwifi >/dev/null 2>&1 || true
  ok "WiFi από κάρτα SD: ενεργό (αρχείο airsense-wifi.txt στο bootfs)"
fi
sleep 4
if systemctl is-active --quiet airsense; then ok "Ο server τρέχει"; else warn "Ο server δεν ξεκίνησε — δες: airsense logs"; fi

# ── 5. Tailscale ──
say "5/6  Tailscale (πρόσβαση από παντού, π.χ. 4G)"
if [ "$UPDATE" = 1 ]; then ok "Ενημέρωση — Tailscale ως έχει"
elif command -v tailscale >/dev/null && tailscale ip -4 >/dev/null 2>&1; then
  ok "Tailscale ήδη συνδεδεμένο: $(tailscale ip -4 | head -1)"
elif ask "Εγκατάσταση Tailscale;" y; then
  command -v tailscale >/dev/null || curl -fsSL https://tailscale.com/install.sh | sh
  echo -e "${Y}Άνοιξε τον σύνδεσμο που θα εμφανιστεί (από κινητό/υπολογιστή) και συνδέσου με τον ΙΔΙΟ λογαριασμό με το κινητό.${N}"
  tailscale up || warn "Το Tailscale δεν συνδέθηκε — αργότερα: airsense tailscale"
fi

# ── 6. Τέλος ──
say "6/6  Έτοιμο! 🎉"
systemctl restart airsense
sleep 3
PORT=8765
echo
for IP in $(hostname -I 2>/dev/null); do
  case "$IP" in *:*) continue ;; 100.*) LBL="Tailscale (από παντού)";; *) LBL="Ίδιο WiFi";; esac
  URL="http://$IP:$PORT"
  echo -e "${G}$LBL:${N}  $URL"
  command -v qrencode >/dev/null && qrencode -t ANSIUTF8 -m 1 "$URL"
done
echo -e "  Επίσης: ${G}http://$(hostname).local:$PORT${N}"
echo
echo "Σκάναρε το QR με το κινητό ή βάλε τη διεύθυνση στην εφαρμογή AirSense (Android)."
echo "Αισθητήρες: βρίσκονται αυτόματα. Δες τους με:  airsense status"
echo "Όλες οι εντολές:  airsense help"
