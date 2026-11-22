#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  AirSense — installer for Luckfox Pico Pro/Max (Ubuntu 22.04 on the SD card)
#  Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM
#
#  Run ONCE on a fresh Ubuntu:   sudo bash airsense-setup.sh
#  After that everything starts by itself on every boot (airsense-boot.service)
#  and updates itself from GitHub (airsense-update.timer).
# ═══════════════════════════════════════════════════════════════════════════
set -u
G='\033[1;32m'; Y='\033[1;33m'; R='\033[1;31m'; B='\033[1;36m'; D='\033[2m'; N='\033[0m'
ok()   { echo -e "  ${G}✔${N} $*"; }
warn() { echo -e "  ${Y}⚠${N} $*"; }
die()  { echo -e "  ${R}✖ $*${N}"; printf '\033[?25h'; exit 1; }

TOTAL=6
# Overall progress: [##########..........] Step 3/6 — Packages
step() {
  local n=$1 title=$2 w=30 done bar
  done=$(( n * w / TOTAL ))
  bar=$(printf '%*s' "$done" '' | tr ' ' '#')$(printf '%*s' $((w - done)) '' | tr ' ' '.')
  echo -e "\n${B}[${bar}] Step ${n}/${TOTAL} — ${title}${N}"
}

# Y/N question — Enter = default (capital letter)
ask() {
  local a d=${2:-y} hint
  [[ "$d" =~ ^(y|Y)$ ]] && hint="Y/n" || hint="y/N"
  while true; do
    read -r -p "$(echo -e "  ${Y}?${N} $1 (${hint}): ")" a
    a=${a:-$d}
    case "$a" in y|Y|yes|YES|Yes) return 0 ;; n|N|no|NO|No) return 1 ;; esac
    echo "    Type Y (yes) or N (no) — or press Enter for ${hint%%/*}"
  done
}

# Live progress for every task: moving bar + elapsed time + what it is doing right now
PROG_LOG=/tmp/airsense-setup.log
progress() {
  local msg=$1; shift
  echo "──── $msg" >> "$PROG_LOG"
  if [ ! -t 1 ]; then "$@" >>"$PROG_LOG" 2>&1; return $?; fi
  ( "$@" >>"$PROG_LOG" 2>&1 ) &
  local pid=$! t0 el w=24 pos=0 dir=1 bar last cols
  t0=$(date +%s); cols=$(tput cols 2>/dev/null || echo 100)
  printf '\033[?25l'
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
  if [ $rc = 0 ]; then printf "  ${G}✔${N} %s  ${D}(%02d:%02d)${N}\n" "$msg" $((el / 60)) $((el % 60))
  else printf "  ${R}✖${N} %s  ${D}(%02d:%02d) — see %s${N}\n" "$msg" $((el / 60)) $((el % 60)) "$PROG_LOG"; fi
  return $rc
}
trap 'printf "\033[?25h"' EXIT

# /run is tiny on this board (little RAM) → systemd refuses daemon-reload (needs 16MB free)
grow_run() { mount -o remount,size=32M /run 2>/dev/null; }
# Device name — written directly (hostnamectl fails on this image)
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
make_swap() {
  local SW=/swapfile SZ=512
  [ "$(df -m / | awk 'NR==2{print $4}')" -lt 1500 ] && SZ=256
  fallocate -l ${SZ}M $SW 2>/dev/null || dd if=/dev/zero of=$SW bs=1M count=$SZ status=none
  chmod 600 $SW && mkswap $SW && swapon $SW || return 1
  grep -q "^$SW " /etc/fstab || echo "$SW none swap sw 0 0" >> /etc/fstab
  echo "vm.swappiness=20" > /etc/sysctl.d/90-airsense.conf; sysctl -q -p /etc/sysctl.d/90-airsense.conf
}
wait_server() {
  for i in $(seq 1 90); do
    timeout 2 bash -c 'exec 3<>/dev/tcp/127.0.0.1/8765' 2>/dev/null && return 0
    echo "waiting for http://127.0.0.1:8765 … ${i}"; sleep 2
  done
  return 1
}

[ "$(id -u)" = 0 ] || exec sudo bash "$0" "$@"
HERE=$(cd "$(dirname "$0")" && pwd)
USER_NAME=${SUDO_USER:-pico}
[ "$USER_NAME" = root ] && USER_NAME=$(ls /home | head -1)
USER_HOME=$(getent passwd "$USER_NAME" | cut -d: -f6); USER_HOME=${USER_HOME:-/root}
NONINTERACTIVE=0; [ -t 0 ] || NONINTERACTIVE=1
for a in "$@"; do [ "$a" = "-y" ] && NONINTERACTIVE=1; done
[ "$NONINTERACTIVE" = 1 ] && ask() { [[ "${2:-y}" =~ ^(y|Y)$ ]]; }
: > "$PROG_LOG"

echo -e "${B}"
echo "   🌬  AirSense — installer for Luckfox Pico"
echo -e "${N}   Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM"
echo -e "   ${D}Every task shows a moving bar + timer: moving = working, not stuck.${N}"

# ── 1. Check ───────────────────────────────────────────────────────────────
step 1 "System check"
command -v apt-get >/dev/null || die "Ubuntu (with apt) is required — see ODIGIES_Luckfox.md → step 1."
command -v systemctl >/dev/null || die "systemd (Ubuntu) is required."
MEM=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)
ok "$(. /etc/os-release; echo "$PRETTY_NAME") · $(uname -m) · RAM ${MEM}MB · user $USER_NAME"
APP_SRC=$(ls -1 "$HERE"/AirSense_v*.pyw "$HERE"/AirSense*.py "$HERE"/AirSense*.pyw 2>/dev/null | sort -V | tail -1)
[ -n "$APP_SRC" ] || die "AirSense_vX.pyw was not found next to this script."
ok "App: $(basename "$APP_SRC")"
progress "Internet check" timeout 10 bash -c 'exec 3<>/dev/tcp/ports.ubuntu.com/80' \
  || warn "No internet? — needed for packages / Tailscale / updates (Ethernet cable to the router?)"
progress "Free space for systemd (/run → 32MB)" grow_run || warn "Could not enlarge /run"

# ── 2. Swap ────────────────────────────────────────────────────────────────
step 2 "Swap (extra memory on the SD card)"
if [ "$(awk '/SwapTotal/{print $2}' /proc/meminfo)" -gt 100000 ]; then
  ok "Swap already exists ($(free -m | awk '/Swap:/{print $2}')MB)"
else
  progress "Creating swap file" make_swap || warn "Swap was not created"
fi

# ── 3. Packages ────────────────────────────────────────────────────────────
step 3 "Packages (python3, reportlab for PDF, fonts, avahi for airsense.local)"
export DEBIAN_FRONTEND=noninteractive
APT="apt-get -y -o DPkg::Lock::Timeout=600 -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold"
NEED=""
for pkg in python3 python3-reportlab fonts-dejavu-core avahi-daemon curl ca-certificates qrencode; do
  dpkg -s "$pkg" >/dev/null 2>&1 || NEED="$NEED $pkg"
done
if [ -z "$NEED" ]; then
  ok "All packages are already installed"
else
  echo -e "  ${D}Needed:$NEED — on this board 5–15 minutes, do not close the window${N}"
  progress "Checking dpkg" dpkg --configure -a || true
  progress "Package lists (apt update)" timeout 1200 $APT update || warn "apt update failed"
  progress "Installing packages" timeout 1800 $APT install --no-install-recommends $NEED \
    || warn "Some packages were not installed — will retry on boot"
fi
python3 -c "import reportlab" 2>/dev/null && ok "python3 $(python3 -V | cut -d' ' -f2) + reportlab" || warn "no reportlab (PDF reports will retry later)"
progress "Time sync (NTP)" systemctl enable --now systemd-timesyncd || true
progress "Time zone Europe/Athens" timedatectl set-timezone Europe/Athens || true

# ── 4. Files + services ────────────────────────────────────────────────────
step 4 "AirSense + autostart + auto-update"
install_files() {
  install -d /opt/airsense /var/lib/airsense
  install -m 755 "$HERE/airsense-boot.sh"   /usr/local/sbin/airsense-boot
  install -m 755 "$HERE/airsense-update.sh" /usr/local/sbin/airsense-update
  install -m 755 "$HERE/airsense"           /usr/local/bin/airsense
  install -D -m 755 "$HERE/tailscale.sh"    /usr/local/share/airsense/tailscale.sh
  sed -i 's/\r$//' /usr/local/sbin/airsense-boot /usr/local/sbin/airsense-update /usr/local/bin/airsense \
    /usr/local/share/airsense/tailscale.sh "$HERE/post-update.sh"
  # the app goes to the user's home (the boot service finds it there)
  rm -f "$USER_HOME"/AirSense_v*.pyw
  cp -f "$APP_SRC" "$USER_HOME/$(basename "$APP_SRC")"
  [ -f "$HERE/airsense-settings.txt" ] && [ ! -f "$USER_HOME/airsense-settings.txt" ] && cp "$HERE/airsense-settings.txt" "$USER_HOME/"
  chown "$USER_NAME": "$USER_HOME"/AirSense_v*.pyw "$USER_HOME/airsense-settings.txt" 2>/dev/null
  echo "$USER_NAME" > /var/lib/airsense/user
}
progress "Copying files" install_files || die "Copying files failed"
progress "System services (boot · /run · auto-update)" bash "$HERE/post-update.sh" || warn "Services: see $PROG_LOG"
systemctl is-enabled airsense-boot >/dev/null 2>&1 || die "The service was not enabled — send a screenshot"
systemctl enable systemd-networkd-wait-online >/dev/null 2>&1 || true
ok "airsense-boot: starts on every boot, restarts if it stops"
ok "Auto-update from GitHub: ON (10 min after boot and every 6 hours · airsense autoupdate off)"

# ── 5. Network name ────────────────────────────────────────────────────────
step 5 "Network name"
if [ "$(hostname)" != "airsense" ] && ask "Name this device «airsense» (→ http://airsense.local:8765)?" y; then
  progress "Renaming to airsense" set_name airsense || warn "Name not changed — stays $(hostname)"
fi
ok "Name: $(hostname) → http://$(hostname).local:8765"

# ── 6. Tailscale ───────────────────────────────────────────────────────────
step 6 "Tailscale (access from anywhere)"
echo -e "  ${D}Rule: ~/tailscale.sh exists → Tailscale ON on every boot · missing → local only.${N}"
if [ -f "$USER_HOME/tailscale.sh" ]; then
  ok "$USER_HOME/tailscale.sh already exists (ON)"
elif ask "Do you want Tailscale (access from anywhere)?" y; then
  cp -f "$HERE/tailscale.sh" "$USER_HOME/tailscale.sh"; chown "$USER_NAME": "$USER_HOME/tailscale.sh"; chmod 755 "$USER_HOME/tailscale.sh"
  ok "Tailscale ON"
else
  ok "Local only (turn Tailscale on later with: airsense tailscale on)"
fi
[ -f "$USER_HOME/tailscale.sh" ] && bash "$USER_HOME/tailscale.sh"

# ── Start ──────────────────────────────────────────────────────────────────
echo -e "\n${B}[$(printf '%*s' 30 '' | tr ' ' '#')] Done — starting the server${N}"
grow_run
systemctl enable --now airsense-boot >/dev/null 2>&1
systemctl restart airsense-boot
progress "Starting the AirSense server" wait_server && SRV=1 || SRV=0
IP=$(hostname -I | awk '{print $1}')
[ "$SRV" = 1 ] && ok "The server is running!" || warn "The server is slow to start — check: airsense logs"
echo -e "\n${G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
echo -e "  🏠 Local:     ${B}http://$IP:8765${N}   or   ${B}http://$(hostname).local:8765${N}"
TSIP=$(tailscale ip -4 2>/dev/null | head -1); [ -n "$TSIP" ] && echo -e "  🌍 Tailscale: ${B}http://$TSIP:8765${N}"
echo -e "  📱 QR for the phone: ${B}airsense qr${N}     · status: ${B}airsense${N}"
echo -e "  🔐 Admin password:   ${B}airsense set-admin${N}  (or ADMIN_PASSWORD in ~/airsense-settings.txt)"
echo -e "  🔄 Updates: ${B}automatic${N} from GitHub (every 6 hours) · now: ${B}airsense update${N}"
echo -e "${G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
command -v qrencode >/dev/null && qrencode -t ANSIUTF8 "http://$IP:8765"

echo
if ask "Reboot now, to check that everything starts by itself?" y; then
  echo "  Rebooting… in 1–2 minutes: http://$(hostname).local:8765"
  sleep 2; reboot
fi
