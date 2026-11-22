#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  AirSense — Tailscale (πρόσβαση από παντού: 4G/5G, άλλο WiFi)
#
#  ΟΣΟ ΥΠΑΡΧΕΙ αυτό το αρχείο (δίπλα στο AirSense*.py, στη ρίζα της κάρτας ή σε USB),
#  τρέχει αυτόματα σε κάθε εκκίνηση: εγκαθιστά/ξεκινά/συνδέει το Tailscale.
#  Αν το ΣΒΗΣΕΙΣ (ή το μετονομάσεις) → στο επόμενο boot μόνο τοπικά (Tailscale OFF).
#
#  Μπορείς να το τρέξεις και με το χέρι:   sudo bash tailscale.sh
# ═══════════════════════════════════════════════════════════════════════════

# Προαιρετικό: κλειδί σύνδεσης για σύνδεση ΧΩΡΙΣ browser
# (tailscale.com → Settings → Keys → Generate auth key) π.χ. AUTHKEY="tskey-auth-xxxxxxxx"
AUTHKEY=""

LOGIN_FILE=/var/lib/airsense/tailscale-login.txt
[ "$(id -u)" = 0 ] || exec sudo bash "$0" "$@"
mkdir -p /var/lib/airsense
PROG_LOG=/tmp/tailscale-install.log
# ── Ένδειξη προόδου: γραμμή που κινείται + χρόνος + τι κάνει τώρα (για να φαίνεται ότι δεν κόλλησε) ──
# χρήση: progress "Μήνυμα" εντολή ορίσματα…   (η έξοδος της εντολής πάει στο $PROG_LOG)
PROG_LOG=${PROG_LOG:-/tmp/airsense-progress.log}
progress() {
  local msg=$1; shift
  : > "$PROG_LOG"
  if [ ! -t 1 ]; then "$@" >>"$PROG_LOG" 2>&1; return $?; fi      # χωρίς οθόνη (boot): απλά τρέχει
  ( "$@" >>"$PROG_LOG" 2>&1 ) &
  local pid=$! t0 el w=24 pos=0 dir=1 bar last cols
  t0=$(date +%s)
  cols=$(tput cols 2>/dev/null || echo 100)
  printf '\033[?25l'                                               # κρύβει τον κέρσορα
  while kill -0 "$pid" 2>/dev/null; do
    el=$(( $(date +%s) - t0 ))
    bar=$(printf '%*s' "$pos" '' | tr ' ' '-')'#####'$(printf '%*s' $((w - pos)) '' | tr ' ' '-')
    last=$(tail -n 1 "$PROG_LOG" 2>/dev/null | tr -d '\r\033' | sed 's/[[:cntrl:]]//g' | cut -c1-$((cols - ${#msg} - 45)))
    printf '\r  [%s] %s  %02d:%02d  %s\033[K' "$bar" "$msg" $((el / 60)) $((el % 60)) "$last"
    pos=$((pos + dir)); { [ $pos -ge $w ] || [ $pos -le 0 ]; } && dir=$((-dir))
    sleep 0.4
  done
  wait "$pid"; local rc=$?
  el=$(( $(date +%s) - t0 ))
  printf '\r\033[K\033[?25h'
  if [ $rc = 0 ]; then printf '  \033[1;32m✔\033[0m %s  (%02d:%02d)\n' "$msg" $((el / 60)) $((el % 60))
  else printf '  \033[1;31m✖\033[0m %s  (%02d:%02d) — δες %s\n' "$msg" $((el / 60)) $((el % 60)) "$PROG_LOG"; fi
  return $rc
}

if ! command -v tailscale >/dev/null; then
  echo "  Εγκατάσταση Tailscale — σε αυτή την πλακέτα 5–15 λεπτά (η γραμμή κινείται = δουλεύει)"
  if ! progress "Tailscale" bash -c 'curl -fsSL --max-time 60 https://tailscale.com/install.sh | timeout 1200 sh'; then
    echo "✖ Η εγκατάσταση Tailscale απέτυχε (internet;) — δες /tmp/tailscale-install.log"
    exit 1
  fi
fi

systemctl enable --now tailscaled >/dev/null 2>&1
for i in 1 2 3 4 5; do tailscale status --json >/dev/null 2>&1 && break; sleep 2; done

STATE=$(tailscale status --json 2>/dev/null | grep -m1 -oE '"BackendState": *"[A-Za-z]+"' | grep -oE '[A-Za-z]+"$' | tr -d '"')
if [ "$STATE" = "Running" ]; then
  rm -f "$LOGIN_FILE"
  echo "✔ Tailscale συνδεδεμένο · $(tailscale ip -4 2>/dev/null | head -1) · http://$(tailscale ip -4 2>/dev/null | head -1):8765"
  exit 0
fi

if [ -n "$AUTHKEY" ]; then
  tailscale up --authkey="$AUTHKEY" --hostname="$(hostname)" --accept-dns=false && \
    echo "✔ Tailscale συνδέθηκε με κλειδί · $(tailscale ip -4 2>/dev/null | head -1)"
  exit 0
fi

# σύνδεση με browser: παίρνει το link και το κρατά στο tailscale-login.txt
OUT=$(mktemp)
( tailscale up --hostname="$(hostname)" --accept-dns=false >"$OUT" 2>&1 & )
URL=""
for i in $(seq 1 20); do
  URL=$(grep -m1 -oE 'https://login\.tailscale\.com/[^ ]+' "$OUT")
  [ -n "$URL" ] && break
  tailscale status >/dev/null 2>&1 && break
  sleep 1
done
if [ -n "$URL" ]; then
  echo "$URL" > "$LOGIN_FILE"
  echo "🔑 Tailscale: άνοιξε αυτό το link (στο κινητό ή στον υπολογιστή) και συνδέσου:"
  echo "   $URL"
  if [ -t 1 ] && command -v qrencode >/dev/null; then qrencode -t ANSIUTF8 "$URL"; fi
  echo "   (το link είναι και στο $LOGIN_FILE · εντολή: airsense tailscale)"
else
  tailscale status >/dev/null 2>&1 && echo "✔ Tailscale συνδεδεμένο · $(tailscale ip -4 2>/dev/null | head -1)"
fi
