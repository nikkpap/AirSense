#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  AirSense — Tailscale (access from anywhere: 4G/5G, other WiFi)
#
#  AS LONG AS this file exists (next to AirSense*.py, in the SD card root or on USB)
#  it runs automatically on every boot: installs / starts / logs in Tailscale.
#  DELETE it (or rename it) → on the next boot: local only (Tailscale OFF).
#
#  You can also run it by hand:   sudo bash tailscale.sh
# ═══════════════════════════════════════════════════════════════════════════

# Optional: auth key to log in WITHOUT a browser
# (tailscale.com → Settings → Keys → Generate auth key) e.g. AUTHKEY="tskey-auth-xxxxxxxx"
AUTHKEY=""
AUTHKEY=${AIRSENSE_TS_AUTHKEY:-$AUTHKEY}     # (the boot service / airsense command pass the key of your copy)

LOGIN_FILE=/var/lib/airsense/tailscale-login.txt
[ "$(id -u)" = 0 ] || exec sudo bash "$0" "$@"
mkdir -p /var/lib/airsense
mount -o remount,size=32M /run 2>/dev/null

# Live progress: moving bar + elapsed time + what it is doing right now
PROG_LOG=/tmp/tailscale-install.log
progress() {
  local msg=$1; shift
  echo "──── $msg" >> "$PROG_LOG"
  if [ ! -t 1 ]; then "$@" >>"$PROG_LOG" 2>&1; return $?; fi
  ( "$@" >>"$PROG_LOG" 2>&1 ) &
  local pid=$! t0 el w=24 pos=0 dir=1 bar line cols DASHES='------------------------'
  t0=$(date +%s); cols=$(tput cols 2>/dev/null); [ "${cols:-0}" -gt 20 ] 2>/dev/null || cols=$(stty size 2>/dev/null | awk '{print $2}'); [ "${cols:-0}" -gt 20 ] 2>/dev/null || cols=80
  printf '\033[?25l'
  while kill -0 "$pid" 2>/dev/null; do
    el=$(( $(date +%s) - t0 ))
    bar="${DASHES:0:pos}#####${DASHES:0:w-pos}"
    line=$(printf '  [%s] %s  %02d:%02d  %s' "$bar" "$msg" $((el / 60)) $((el % 60)) \
      "$(tail -n 1 "$PROG_LOG" 2>/dev/null | tr -d '\r\033' | LC_ALL=C sed 's/[[:cntrl:]]//g; s/[^ -~]/?/g')")
    printf '\r%s\033[K' "$(printf '%s' "$line" | LC_ALL=C cut -c1-$((cols > 20 ? cols - 2 : 78)))"
    pos=$((pos + dir)); { [ $pos -ge $w ] || [ $pos -le 0 ]; } && dir=$((-dir))
    sleep 0.4
  done
  wait "$pid"; local rc=$?
  el=$(( $(date +%s) - t0 ))
  printf '\r\033[K\033[?25h'
  if [ $rc = 0 ]; then printf '  \033[1;32m✔\033[0m %s  (%02d:%02d)\n' "$msg" $((el / 60)) $((el % 60))
  else printf '  \033[1;31m✖\033[0m %s  (%02d:%02d) — see %s\n' "$msg" $((el / 60)) $((el % 60)) "$PROG_LOG"; fi
  return $rc
}
trap 'printf "\033[?25h"' EXIT

ts_state() { tailscale status --json 2>/dev/null | grep -m1 -oE '"BackendState": *"[A-Za-z]+"' | grep -oE '[A-Za-z]+"$' | tr -d '"'; }
wait_daemon() { for i in $(seq 1 30); do tailscale status --json >/dev/null 2>&1 && return 0; echo "waiting for tailscaled … $i"; sleep 2; done; return 1; }

if ! command -v tailscale >/dev/null; then
  echo "  Installing Tailscale — on this board 5–15 minutes (moving bar = working)"
  if ! progress "Installing Tailscale" bash -c 'curl -fsSL --max-time 60 https://tailscale.com/install.sh | timeout 1200 sh'; then
    echo "  ✖ Tailscale install failed (internet?) — see $PROG_LOG"
    exit 1
  fi
fi

# This board's kernel may have no TUN device → run Tailscale in userspace mode (still reaches port 8765)
need_userspace() { [ -c /dev/net/tun ] && return 1; modprobe tun 2>/dev/null; [ -c /dev/net/tun ] && return 1; return 0; }
if need_userspace; then
  if ! grep -q "userspace-networking" /etc/default/tailscaled 2>/dev/null; then
    if grep -q '^FLAGS=' /etc/default/tailscaled 2>/dev/null; then
      sed -i 's/^FLAGS="\(.*\)"/FLAGS="\1 --tun=userspace-networking"/' /etc/default/tailscaled
    else
      echo 'FLAGS="--tun=userspace-networking"' >> /etc/default/tailscaled
    fi
    echo "  ℹ No TUN device on this kernel → Tailscale in userspace mode"
    systemctl restart tailscaled 2>/dev/null
  fi
fi
progress "Starting Tailscale" bash -c 'systemctl enable tailscaled; systemctl restart tailscaled; sleep 3; systemctl is-active tailscaled' 
progress "Waiting for Tailscale" wait_daemon || {
  echo "  ✖ tailscaled does not start:"; systemctl status tailscaled --no-pager 2>&1 | tail -n 6 | sed 's/^/     /'; exit 1; }

if [ "$(ts_state)" = "Running" ]; then
  rm -f "$LOGIN_FILE"
  T=$(tailscale ip -4 2>/dev/null | head -1)
  echo "  ✔ Tailscale connected · $T · http://$T:8765"
  exit 0
fi

if [ -n "$AUTHKEY" ]; then
  progress "Tailscale login (auth key)" tailscale up --authkey="$AUTHKEY" --hostname="$(hostname)" --accept-dns=false \
    && echo "  ✔ Tailscale connected · $(tailscale ip -4 2>/dev/null | head -1)"
  exit 0
fi

# Browser login: grab the link and keep it in tailscale-login.txt
OUT=$(mktemp)
( timeout 300 tailscale up --hostname="$(hostname)" --accept-dns=false >"$OUT" 2>&1 & )
get_url() {
  for i in $(seq 1 30); do
    grep -q 'https://login\.tailscale\.com/' "$OUT" && return 0
    [ "$(ts_state)" = Running ] && return 0
    echo "asking Tailscale for a login link … $i"; sleep 1
  done
  return 1
}
progress "Getting the login link" get_url
URL=$(grep -m1 -oE 'https://login\.tailscale\.com/[^ ]+' "$OUT")
if [ -n "$URL" ]; then
  echo "$URL" > "$LOGIN_FILE"
  echo
  echo "  🔑 Tailscale: open this link (on your phone or PC) and log in:"
  echo "     $URL"
  if [ -t 1 ] && command -v qrencode >/dev/null; then qrencode -t ANSIUTF8 "$URL"; fi
  echo "     (the link is also saved in $LOGIN_FILE · command: airsense tailscale)"
else
  [ "$(ts_state)" = Running ] && echo "  ✔ Tailscale connected · $(tailscale ip -4 2>/dev/null | head -1)"
fi
