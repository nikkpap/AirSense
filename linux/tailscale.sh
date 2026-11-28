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
[ "$(df -m --output=size /run 2>/dev/null | tail -1 | tr -d ' ')" -lt 32 ] 2>/dev/null && mount -o remount,size=32M /run 2>/dev/null

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
trap 'printf "\r\033[K\033[?25h"' INT     # Ctrl+C stops only the current wait, the script continues

# only one Tailscale setup at a time (boot service + installer could start it together)
exec 9>/run/airsense-tailscale.lock
if ! flock -n 9; then
  echo "  ℹ Another Tailscale setup is already running (started at boot) — waiting for it"
  progress "Waiting for the other Tailscale setup" flock -w 1800 9 || { echo "  ✖ still busy — try later: airsense tailscale"; exit 1; }
fi

ts_state() { tailscale status --json 2>/dev/null | grep -m1 -oE '"BackendState": *"[A-Za-z]+"' | grep -oE '[A-Za-z]+"$' | tr -d '"'; }
wait_daemon() { for i in $(seq 1 30); do tailscale status --json >/dev/null 2>&1 && return 0; echo "waiting for tailscaled … $i"; sleep 2; done; return 1; }

# ── Install: official static package from pkgs.tailscale.com (NO apt → fast and light on 84MB RAM) ──
ts_arch() { case "$(uname -m)" in armv7*|armv6*|armhf) echo arm ;; aarch64|arm64) echo arm64 ;; x86_64) echo amd64 ;; i?86) echo 386 ;; *) echo "" ;; esac; }
cleanup_old() {
  # an older attempt (install.sh + apt) may still be running or half-finished → stop it and repair dpkg
  pkill -f "tailscale.com/install.sh" 2>/dev/null
  pkill -f "pkgs.tailscale.com" 2>/dev/null
  rm -f /etc/apt/sources.list.d/tailscale.list
  if pgrep -x apt-get >/dev/null || pgrep -x dpkg >/dev/null; then
    echo "an older install is still running — stopping it"; pkill -x apt-get; sleep 3
  fi
  dpkg --configure -a 2>&1 | tail -n 3
  return 0
}
install_static() {
  local A F V T=/tmp/ts-install
  A=$(ts_arch); [ -n "$A" ] || { echo "unsupported CPU $(uname -m)"; return 1; }
  echo "asking pkgs.tailscale.com for the latest version ($A)…"
  F=$(curl -fsSL --max-time 30 "https://pkgs.tailscale.com/stable/?mode=json" | grep -oE "\"$A\": *\"tailscale_[^\"]+\.tgz\"" | grep -oE 'tailscale_[^"]+\.tgz' | head -1)
  [ -n "$F" ] || { echo "could not read the version list (internet?)"; return 1; }
  rm -rf "$T"; mkdir -p "$T"
  echo "downloading $F …"
  ( curl -fsSL --max-time 900 -o "$T/ts.tgz" "https://pkgs.tailscale.com/stable/$F" ) &
  local cp=$!
  while kill -0 $cp 2>/dev/null; do echo "downloaded $(( $(stat -c %s "$T/ts.tgz" 2>/dev/null || echo 0) / 1048576 )) MB of $F"; sleep 2; done
  wait $cp || { echo "download failed"; return 1; }
  echo "unpacking…"; tar -xzf "$T/ts.tgz" -C "$T" || return 1
  local D; D=$(find "$T" -maxdepth 1 -type d -name 'tailscale_*' | head -1)
  echo "installing binaries…"
  install -m 755 "$D/tailscale"  /usr/bin/tailscale
  install -m 755 "$D/tailscaled" /usr/sbin/tailscaled
  install -m 644 "$D/systemd/tailscaled.service" /etc/systemd/system/tailscaled.service
  [ -f /etc/default/tailscaled ] || install -m 644 "$D/systemd/tailscaled.defaults" /etc/default/tailscaled
  mkdir -p /var/lib/tailscale
  systemctl daemon-reload 2>/dev/null || { mount -o remount,size=32M /run; systemctl daemon-reload; }
  rm -rf "$T"
  echo "tailscale $(tailscale version 2>/dev/null | head -1) installed"
}

if ! command -v tailscale >/dev/null || ! command -v tailscaled >/dev/null; then
  echo "  Installing Tailscale (official static package, ~30MB — 1–5 minutes)"
  progress "Cleaning up older attempts" cleanup_old
  if ! progress "Installing Tailscale" install_static; then
    echo "  ✖ Tailscale install failed (internet?) — see $PROG_LOG"
    exit 1
  fi
fi

# Luckfox: the kernel has no TUN device → run Tailscale in userspace mode (still reaches port 8765)
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

# Tailscale SSH: log in to this board from any of your Tailscale devices ("ssh USER@NAME"),
# no password, no open ports. Set TAILSCALE_SSH=off in airsense-settings.txt to keep it off.
enable_ssh() {
  if grep -qiE '^[[:space:]]*TAILSCALE_SSH[[:space:]]*=[[:space:]]*(off|no|0)' /var/lib/airsense/settings.applied 2>/dev/null; then
    tailscale set --ssh=false >/dev/null 2>&1; echo "  ℹ Tailscale SSH: OFF (TAILSCALE_SSH=off)"; return 0
  fi
  if tailscale set --ssh >/dev/null 2>&1; then echo "  ✔ Tailscale SSH: ON  →  ssh $(cat /var/lib/airsense/user 2>/dev/null || echo user)@$(hostname)  (from any device on your Tailscale)"
  else echo "  ⚠ Tailscale SSH could not be enabled (run: sudo tailscale set --ssh)"; fi
}
connected() {
  rm -f "$LOGIN_FILE"
  local T; T=$(tailscale ip -4 2>/dev/null | head -1)
  local DN; DN=$(tailscale status --peers=false --json 2>/dev/null | grep -m1 -oE '"DNSName": *"[^"]+"' | sed -E 's/.*"([^"]+)"$/\1/; s/\.$//')
  echo "  ✔ Tailscale connected · $T · http://$T:8765"
  [ -n "$DN" ] && echo "  ✔ MagicDNS: http://$DN:8765  (same, by name — never changes)"
  enable_ssh
}

if [ "$(ts_state)" = "Running" ]; then connected; exit 0; fi

if [ -n "$AUTHKEY" ]; then
  if progress "Tailscale login (auth key)" tailscale up --authkey="$AUTHKEY" --hostname="$(hostname)" --accept-dns=false; then connected; fi
  exit 0
fi

# Browser login: grab the link and keep it in tailscale-login.txt
OUT=$(mktemp)
( timeout 1200 tailscale up --hostname="$(hostname)" --accept-dns=false >"$OUT" 2>&1 & )
get_url() {
  for i in $(seq 1 30); do
    grep -q 'https://login\.tailscale\.com/' "$OUT" && return 0
    [ "$(ts_state)" = Running ] && return 0
    echo "asking Tailscale for a login link … $i"; sleep 1
  done
  return 1
}
wait_login() {
  for i in $(seq 1 300); do
    [ "$(ts_state)" = Running ] && return 0
    echo "open the link above and log in … (Ctrl+C = later)"; sleep 2
  done
  return 1
}
progress "Getting the login link" get_url
[ "$(ts_state)" = Running ] && { connected; exit 0; }
URL=$(grep -m1 -oE 'https://login\.tailscale\.com/[^ ]+' "$OUT")
if [ -n "$URL" ]; then
  echo "$URL" > "$LOGIN_FILE"
  echo
  echo "  🔑 Tailscale: open this link (on your phone or PC) and log in:"
  echo "     $URL"
  if [ -t 1 ] && command -v qrencode >/dev/null; then qrencode -t ANSIUTF8 "$URL"; fi
  echo "     (the link is also saved in $LOGIN_FILE · command: airsense tailscale)"
  if [ -t 1 ]; then
    echo
    if progress "Waiting for your Tailscale login (up to 10 min)" wait_login; then connected
    else echo "  ℹ Not logged in yet — log in any time; SSH + connection finish by themselves on the next boot (or: airsense tailscale)"; fi
  fi
else
  echo "  ⚠ No login link yet — try again: airsense tailscale"
fi
