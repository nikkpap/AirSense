#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  AirSense — installer for Raspberry Pi (Zero 2 W / 3 / 4 / 5 · Raspberry Pi OS)
#  and Luckfox Pico Pro/Max (Ubuntu 22.04) — also any Debian/Ubuntu board
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
  local n=$1 title=$2 w=30 dn bar
  dn=$(( n * w / TOTAL ))
  bar=$(printf '%*s' "$dn" '' | tr ' ' '#')$(printf '%*s' $((w - dn)) '' | tr ' ' '.')
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
  if [ $rc = 0 ]; then printf "  ${G}✔${N} %s  ${D}(%02d:%02d)${N}\n" "$msg" $((el / 60)) $((el % 60))
  else printf "  ${R}✖${N} %s  ${D}(%02d:%02d) — see %s${N}\n" "$msg" $((el / 60)) $((el % 60)) "$PROG_LOG"; fi
  return $rc
}
trap 'printf "\033[?25h"' EXIT
trap 'printf "\r\033[K\033[?25h"; kill $(jobs -p) 2>/dev/null; echo -e "\n  ${Y}⚠${N} Stopped (Ctrl+C). Run the same command again to continue."; exit 130' INT

# /run is tiny on low-RAM boards (Luckfox) → systemd refuses daemon-reload (needs 16MB free).
# Only ever ENLARGE it (on a Raspberry Pi /run is already bigger → nothing to do)
grow_run() {
  [ "$(df -m --output=size /run 2>/dev/null | tail -1 | tr -d ' ')" -lt 32 ] 2>/dev/null || { echo "/run is big enough"; return 0; }
  mount -o remount,size=32M /run 2>/dev/null
}
# Which board? → pi / luckfox / linux
MODEL=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null)
case "$MODEL" in
  *Raspberry*) BOARD=pi ;;
  *Luckfox*|*luckfox*|*LUCKFOX*) BOARD=luckfox ;;
  *) if [ -f /etc/rpi-issue ]; then BOARD=pi; elif grep -qi rv1106 /proc/device-tree/compatible 2>/dev/null; then BOARD=luckfox; else BOARD=linux; fi ;;
esac
MODEL=${MODEL:-$(uname -m) board}
# random MAC on every boot? (locally administered bit set: x2/x6/xA/xE) — Luckfox yes, Raspberry Pi no
mac_is_random() {
  local ifc mac
  ifc=$(ip -o link | awk -F': ' '/link\/ether/{print $2; exit}' | cut -d@ -f1)
  mac=$(cat /sys/class/net/$ifc/address 2>/dev/null)
  [ -n "$mac" ] && [ $(( 0x${mac:0:2} & 2 )) -ne 0 ]
}
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
# Fixed MAC: this board gets a random MAC (→ new IP) on every boot. A .link file keeps one MAC forever,
# derived from the machine-id, so the router always gives the same IP (or you can reserve it).
fixed_mac() {
  local ifc mac
  ifc=$(ip -o link | awk -F': ' '/link\/ether/{print $2; exit}' | cut -d@ -f1)
  [ -n "$ifc" ] || { echo "no Ethernet interface"; return 1; }
  if [ -f /etc/systemd/network/10-airsense-mac.link ]; then
    mac=$(grep -m1 '^MACAddress=' /etc/systemd/network/10-airsense-mac.link | cut -d= -f2)
  else
    mac=$(printf '02:%s:%s:%s:%s:%s' $(md5sum /etc/machine-id | cut -c1-10 | sed 's/../& /g'))
    mkdir -p /etc/systemd/network
    printf '[Match]\nOriginalName=%s\n\n[Link]\nMACAddress=%s\nNamePolicy=kernel\n' "$ifc" "$mac" > /etc/systemd/network/10-airsense-mac.link
  fi
  echo "$ifc $mac" > /var/lib/airsense/mac.txt
  echo "$ifc → $mac (active after reboot)"
}
wait_server() {
  for i in $(seq 1 90); do
    timeout 2 bash -c 'exec 3<>/dev/tcp/127.0.0.1/8765' 2>/dev/null && return 0
    echo "waiting for http://127.0.0.1:8765 … ${i}"; sleep 2
  done
  return 1
}

# ── Clock: time zone from a list + NTP servers of ntppool.org (zone by region, e.g. europe) ──
TZ_LIST="Europe/Athens Europe/Nicosia Europe/Istanbul Europe/London Europe/Lisbon Europe/Berlin Europe/Paris Europe/Rome Europe/Madrid Europe/Amsterdam Europe/Warsaw Europe/Bucharest Europe/Sofia Europe/Kyiv Europe/Moscow UTC America/New_York America/Chicago America/Los_Angeles Asia/Dubai Asia/Tokyo Australia/Sydney"
CUR_TZ=$(timedatectl show -p Timezone --value 2>/dev/null); case "$CUR_TZ" in ''|UTC|Etc/*|Asia/Shanghai) CUR_TZ=Europe/Athens ;; esac   # Luckfox factory = Asia/Shanghai
pick_tz() {
  local i=1 z def=1 a
  echo -e "  ${B}Time zone${N} (offset right now, summer/winter time included):"
  for z in $TZ_LIST; do
    [ "$z" = "$CUR_TZ" ] && def=$i
    printf "   %2d) %-22s UTC%s%s\n" "$i" "$z" "$(TZ=$z date +%:z)" "$([ "$z" = "$CUR_TZ" ] && echo '   ← suggested')"
    i=$((i + 1))
  done
  echo "    0) other — type the name (e.g. Asia/Nicosia, list: timedatectl list-timezones)"
  while true; do
    read -r -p "$(echo -e "  ${Y}?${N} Number (Enter = $def): ")" a; a=${a:-$def}
    if [ "$a" = 0 ]; then
      read -r -p "    Time zone name: " z
      [ -f "/usr/share/zoneinfo/$z" ] && { TZ_SEL=$z; return 0; }; echo "    ✖ unknown: $z"
    elif [[ "$a" =~ ^[0-9]+$ ]] && [ "$a" -ge 1 ] && [ "$a" -lt "$i" ]; then
      TZ_SEL=$(echo $TZ_LIST | cut -d' ' -f"$a"); return 0
    else echo "    Type a number from the list"; fi
  done
}
set_ntp() {   # $1 = time zone → pool zone of ntppool.org
  local Z
  case "$1" in Europe/*) Z=europe ;; Asia/*) Z=asia ;; Africa/*) Z=africa ;; Australia/*|Pacific/*) Z=oceania ;;
               America/Sao_Paulo|America/Argentina/*|America/Santiago|America/Bogota|America/Lima) Z=south-america ;;
               America/*) Z=north-america ;; *) Z="" ;; esac
  local P=${Z:+$Z.}pool.ntp.org
  mkdir -p /etc/systemd/timesyncd.conf.d /var/lib/airsense
  printf '[Time]\nNTP=0.%s 1.%s 2.%s 3.%s\nFallbackNTP=pool.ntp.org time.google.com time.cloudflare.com\n' "$P" "$P" "$P" "$P" \
    > /etc/systemd/timesyncd.conf.d/airsense.conf
  echo "$P" > /var/lib/airsense/ntp.txt
  timedatectl set-ntp true 2>/dev/null
  systemctl enable systemd-timesyncd >/dev/null 2>&1
  systemctl restart systemd-timesyncd
}
wait_sync() {
  for i in $(seq 1 45); do
    [ "$(timedatectl show -p NTPSynchronized --value 2>/dev/null)" = yes ] && return 0
    echo "waiting for the time servers … $i"; sleep 2
  done
  return 1
}

[ "$(id -u)" = 0 ] || exec sudo bash "$0" "$@"
HERE=$(cd "$(dirname "$0")" && pwd)
USER_NAME=${SUDO_USER:-root}
[ "$USER_NAME" = root ] && USER_NAME=$(getent passwd 1000 | cut -d: -f1)
USER_NAME=${USER_NAME:-root}
USER_HOME=$(getent passwd "$USER_NAME" | cut -d: -f6); USER_HOME=${USER_HOME:-/root}
NONINTERACTIVE=0; [ -t 0 ] || NONINTERACTIVE=1
for a in "$@"; do [ "$a" = "-y" ] && NONINTERACTIVE=1; done
[ "$NONINTERACTIVE" = 1 ] && ask() { [[ "${2:-y}" =~ ^(y|Y)$ ]]; }
: > "$PROG_LOG"
export DEBIAN_FRONTEND=noninteractive
APT="apt-get -y -o DPkg::Lock::Timeout=600 -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold"

echo -e "${B}"
echo "   🌬  AirSense — installer · $MODEL"
echo -e "${N}   Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM"
echo -e "   ${D}Every task shows a moving bar + timer: moving = working, not stuck.${N}"

# ── 1. Check ───────────────────────────────────────────────────────────────
step 1 "System check"
command -v apt-get >/dev/null || die "Debian / Ubuntu / Raspberry Pi OS (with apt) is required — see the ODIGIES file → step 1."
command -v systemctl >/dev/null || die "systemd (Ubuntu) is required."
MEM=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)
ok "$MODEL ($BOARD) · $(. /etc/os-release; echo "$PRETTY_NAME") · $(uname -m) · RAM ${MEM}MB · user $USER_NAME"
APP_SRC=$(ls -1 "$HERE"/AirSense_v*.pyw "$HERE"/AirSense*.py "$HERE"/AirSense*.pyw 2>/dev/null | sort -V | tail -1)
[ -n "$APP_SRC" ] || die "AirSense_vX.pyw was not found next to this script."
ok "App: $(basename "$APP_SRC")"
progress "Internet check" timeout 10 bash -c 'exec 3<>/dev/tcp/github.com/443' \
  || warn "No internet? — needed for packages / Tailscale / updates (Ethernet cable to the router?)"
progress "Free space for systemd (/run ≥ 32MB)" grow_run || warn "Could not enlarge /run"

# ── all questions NOW — after this it runs by itself (only the Tailscale login waits for you) ──
echo -e "\n  ${B}A few questions first — then it runs by itself${N}"
TZ_SEL=$CUR_TZ
[ "$NONINTERACTIVE" = 1 ] || pick_tz
DO_NAME=0; [ "$(hostname)" != "airsense" ] && ask "Name this device «airsense» (→ http://airsense.local:8765)? Now: $(hostname)" y && DO_NAME=1
DO_MAC=0
if [ -f /etc/systemd/network/10-airsense-mac.link ]; then DO_MAC=1
elif mac_is_random; then ask "This board gets a random MAC (→ new IP) on every boot. Keep the same one?" y && DO_MAC=1; fi
TS_RUNNING=0
command -v tailscale >/dev/null && tailscale status --json 2>/dev/null | grep -q '"BackendState": *"Running"' && TS_RUNNING=1
if [ -f "$USER_HOME/tailscale.sh" ]; then DO_TS=1
elif [ "$TS_RUNNING" = 1 ]; then DO_TS=1; ok "Tailscale is already connected → stays ON"
else DO_TS=0; ask "Tailscale — open AirSense from anywhere (4G, other WiFi)?" y && DO_TS=1; fi
DO_WIFI=0
if command -v nmcli >/dev/null && [ -f "$HERE/airsense_wifi.py" ]; then
  ask "Save another WiFi at the end (e.g. the site's / your phone hotspot)?" n && DO_WIFI=1
fi
ok "Answers saved — you can leave it running now"

# ── 2. Clock + swap ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
step 2 "Clock (time zone + NTP) and swap"
set_tz() {   # timedatectl is blocked on some images (Luckfox: "Access denied") → write it directly
  mkdir -p /var/lib/airsense; echo "$1" > /var/lib/airsense/timezone     # re-applied on every boot
  timedatectl set-timezone "$1" 2>/dev/null || { ln -sf "/usr/share/zoneinfo/$1" /etc/localtime && echo "$1" > /etc/timezone; }
  [ "$(readlink -f /etc/localtime)" = "$(readlink -f "/usr/share/zoneinfo/$1")" ]
}
progress "Time zone $TZ_SEL (UTC$(TZ=$TZ_SEL date +%:z))" set_tz "$TZ_SEL" || warn "Time zone not set"
if ! dpkg -s systemd-timesyncd >/dev/null 2>&1 && [ ! -x /lib/systemd/systemd-timesyncd ]; then
  progress "Installing systemd-timesyncd" timeout 900 $APT install --no-install-recommends systemd-timesyncd || true
fi
progress "Time sync (NTP) → $(case "$TZ_SEL" in Europe/*) echo europe.;; esac)pool.ntp.org" set_ntp "$TZ_SEL" || warn "NTP not set"
progress "Synchronising the clock (before apt — a wrong date breaks it)" wait_sync \
  && ok "Clock: $(date '+%F %T') $TZ_SEL UTC$(date +%:z) · NTP: $(cat /var/lib/airsense/ntp.txt 2>/dev/null)" \
  || warn "Clock not synced yet ($(date '+%F %T')) — continuing; it syncs by itself"
if [ "$(awk '/SwapTotal/{print $2}' /proc/meminfo)" -gt 100000 ]; then
  ok "Swap already exists ($(free -m | awk '/Swap:/{print $2}')MB)"
else
  progress "Creating swap file" make_swap || warn "Swap was not created"
fi

# ── 3. Packages ────────────────────────────────────────────────────────────
step 3 "Packages (python3, reportlab for PDF, fonts, avahi for airsense.local)"
NEED=""
for pkg in python3 python3-reportlab fonts-dejavu-core avahi-daemon curl ca-certificates qrencode unzip perl; do
  dpkg -s "$pkg" >/dev/null 2>&1 || NEED="$NEED $pkg"
done
if [ -z "$NEED" ]; then
  ok "All packages are already installed"
else
  echo -e "  ${D}Needed:$NEED — on a small board 5–15 minutes, do not close the window${N}"
  progress "Checking dpkg" dpkg --configure -a || true
  progress "Package lists (apt update)" timeout 1200 $APT update || warn "apt update failed"
  progress "Installing packages" timeout 1800 $APT install --no-install-recommends $NEED \
    || warn "Some packages were not installed — will retry on boot"
fi
python3 -c "import reportlab" 2>/dev/null && ok "python3 $(python3 -V | cut -d' ' -f2) + reportlab" || warn "no reportlab (PDF reports will retry later)"

# ── 4. Files + services ────────────────────────────────────────────────────
step 4 "AirSense + autostart + auto-update"
install_files() {
  install -d /opt/airsense /var/lib/airsense
  install -m 755 "$HERE/airsense-boot.sh"   /usr/local/sbin/airsense-boot
  install -m 755 "$HERE/airsense-update.sh" /usr/local/sbin/airsense-update
  install -m 755 "$HERE/airsense"           /usr/local/bin/airsense
  install -m 755 "$HERE/airsense-pwcheck.sh" /usr/local/sbin/airsense-pwcheck
  install -D -m 755 "$HERE/tailscale.sh"    /usr/local/share/airsense/tailscale.sh
  sed -i 's/\r$//' /usr/local/sbin/airsense-boot /usr/local/sbin/airsense-update /usr/local/bin/airsense /usr/local/sbin/airsense-pwcheck \
    /usr/local/share/airsense/tailscale.sh "$HERE/post-update.sh"
  # the app goes to the user's home (the boot service finds it there)
  rm -f "$USER_HOME"/AirSense_v*.pyw
  cp -f "$APP_SRC" "$USER_HOME/$(basename "$APP_SRC")"
  [ -f "$HERE/airsense-settings.txt" ] && [ ! -f "$USER_HOME/airsense-settings.txt" ] && cp "$HERE/airsense-settings.txt" "$USER_HOME/"
  chown "$USER_NAME": "$USER_HOME"/AirSense_v*.pyw "$USER_HOME/airsense-settings.txt" 2>/dev/null
  echo "$USER_NAME" > /var/lib/airsense/user
}
progress "Copying files" install_files || die "Copying files failed"
[ -f /etc/systemd/system/airsense.service ] || [ -f /etc/systemd/system/hygrolink.service ] && \
  echo -e "  ${D}Older AirSense/HygroLink install found → it is replaced, your data is copied to /var/lib/airsense${N}"
progress "System services (boot, auto-update$([ "$BOARD" = pi ] && echo ', WiFi from SD card'))" bash "$HERE/post-update.sh" || warn "Services: see $PROG_LOG"
systemctl is-enabled airsense-boot >/dev/null 2>&1 || die "The service was not enabled — send a screenshot"
# Luckfox/Ubuntu use systemd-networkd · Raspberry Pi OS uses NetworkManager (its own wait-online is already on)
systemctl is-active --quiet systemd-networkd && systemctl enable systemd-networkd-wait-online >/dev/null 2>&1 || true
ok "airsense-boot: starts on every boot, restarts if it stops"
ok "Auto-update from GitHub: ON (10 min after boot and every 6 hours · airsense autoupdate off)"

# ── 5. Network + start the server ──────────────────────────────────────────
step 5 "Network name, fixed address, start the server"
if [ "$DO_NAME" = 1 ]; then
  progress "Renaming to airsense" set_name airsense || warn "Name not changed — stays $(hostname)"
fi
ok "Name: $(hostname) → http://$(hostname).local:8765"
if ! mac_is_random && [ ! -f /etc/systemd/network/10-airsense-mac.link ]; then
  ok "MAC: $(ip -o link | awk '/link\/ether/{print $(NF-2); exit}') — fixed by the hardware (same IP every boot)"
elif [ "$DO_MAC" = 1 ]; then
  progress "Fixed network address (MAC)" fixed_mac && ok "MAC: $(cut -d' ' -f2 /var/lib/airsense/mac.txt) — the IP may change ONCE after the next reboot, then stays" \
    || warn "Fixed MAC not set"
else
  warn "MAC changes on every boot → the IP may change (later: run the installer again)"
fi
if [ -x /usr/local/bin/airsense-wifi ]; then
  ok "WiFi: $(nmcli -t -f NAME,TYPE connection show --active 2>/dev/null | awk -F: '/wireless/{print $1; exit}') · more networks: ${B}airsense wifi${N} or airsense-wifi.txt on the SD card"
fi
grow_run
systemctl enable airsense-boot >/dev/null 2>&1
systemctl restart airsense-boot
progress "Starting the AirSense server" wait_server && SRV=1 || SRV=0
[ "$SRV" = 1 ] && ok "The server is running: http://$(hostname -I | awk '{print $1}'):8765" || warn "The server is slow to start — check: airsense logs"

# ── 6. Tailscale ───────────────────────────────────────────────────────────
step 6 "Tailscale (access from anywhere)"
echo -e "  ${D}Rule: ~/tailscale.sh exists → Tailscale ON on every boot · missing → local only.${N}"
if [ -f "$USER_HOME/tailscale.sh" ]; then
  # refresh the user's copy to the new version, keeping its AUTHKEY (the file is the ON switch)
  TSK=$(grep -m1 -oP '^AUTHKEY="\K[^"]*' "$USER_HOME/tailscale.sh" 2>/dev/null)
  cp -f "$HERE/tailscale.sh" "$USER_HOME/tailscale.sh"; chown "$USER_NAME": "$USER_HOME/tailscale.sh"; chmod 755 "$USER_HOME/tailscale.sh"
  [ -n "$TSK" ] && sed -i "s|^AUTHKEY=\"\"|AUTHKEY=\"$TSK\"|" "$USER_HOME/tailscale.sh"
  ok "$USER_HOME/tailscale.sh exists (ON) — updated"
elif [ "$DO_TS" = 1 ]; then
  cp -f "$HERE/tailscale.sh" "$USER_HOME/tailscale.sh"; chown "$USER_NAME": "$USER_HOME/tailscale.sh"; chmod 755 "$USER_HOME/tailscale.sh"
  ok "Tailscale ON"
else
  ok "Local only (turn Tailscale on later with: airsense tailscale on)"
fi
if [ -f "$USER_HOME/tailscale.sh" ]; then
  echo -e "  ${D}(the server is already running — Ctrl+C here only stops the Tailscale setup; it retries on every boot)${N}"
  TSK=$(grep -m1 -oP '^AUTHKEY="\K[^"]*' "$USER_HOME/tailscale.sh" 2>/dev/null)
  trap 'echo' INT        # Ctrl+C during Tailscale = skip it, the installer continues
  AIRSENSE_TS_AUTHKEY="$TSK" timeout 1800 bash /usr/local/share/airsense/tailscale.sh || warn "Tailscale not ready yet — later: airsense tailscale"
  trap 'printf "\r\033[K\033[?25h"; kill $(jobs -p) 2>/dev/null; echo -e "\n  ${Y}⚠${N} Stopped (Ctrl+C). Run the same command again to continue."; exit 130' INT
fi

# ── Summary ────────────────────────────────────────────────────────────────
echo -e "\n${B}[$(printf '%*s' 30 '' | tr ' ' '#')] Done${N}"
IP=$(hostname -I | awk '{print $1}')
echo -e "\n${G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
echo -e "  🏠 Local:     ${B}http://$IP:8765${N}   or   ${B}http://$(hostname).local:8765${N}"
TSIP=$(tailscale ip -4 2>/dev/null | head -1); [ -n "$TSIP" ] && echo -e "  🌍 Tailscale: ${B}http://$TSIP:8765${N}"
echo -e "  📱 QR for the phone: ${B}airsense qr${N}     · status: ${B}airsense${N}"
echo -e "  🔐 Admin password:   ${B}airsense set-admin${N}  (or ADMIN_PASSWORD in ~/airsense-settings.txt)"
echo -e "  🔄 Updates: ${B}automatic${N} from GitHub (every 6 hours) · now: ${B}airsense update${N}"
[ "$BOARD" = pi ] && echo -e "  📶 WiFi:      ${B}airsense wifi${N}  (or airsense-wifi.txt on the SD card)"
if /usr/local/sbin/airsense-pwcheck >/dev/null 2>&1 && [ -f "$USER_HOME/.airsense-default-password" ]; then
  echo -e "  🔑 ${Y}The password is still the factory default${N} → after the reboot, on your first SSH login,"
  echo -e "     you will be asked to change it (or now: ${B}passwd${N})"
fi
echo -e "${G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
command -v qrencode >/dev/null && qrencode -t ANSIUTF8 "http://$IP:8765"

if [ "$DO_WIFI" = 1 ] && [ -x /usr/local/bin/airsense-wifi ]; then
  echo -e "\n  ${B}📶 Another WiFi${N} (it connects by itself wherever it finds it · 0 = exit the menu)"
  /usr/local/bin/airsense-wifi </dev/tty || true
fi

echo
if ask "Reboot now, to check that everything starts by itself?" y; then
  echo "  Rebooting… in 1–2 minutes: http://$(hostname).local:8765"
  [ -f "$USER_HOME/.airsense-default-password" ] && echo "  🔑 Log in again with ssh — you will be asked to change the factory password."
  sync; sleep 2; reboot
fi
