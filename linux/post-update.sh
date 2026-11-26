#!/bin/bash
# AirSense — system services. Runs from the installer and after every automatic update.
# Same for every board: Raspberry Pi · Luckfox Pico · other Debian/Ubuntu.
HERE=$(cd "$(dirname "$0")" && pwd)
DATA=/var/lib/airsense
mkdir -p "$DATA"
RUN_MB=$(df -m --output=size /run 2>/dev/null | tail -1 | tr -d ' ')
[ "${RUN_MB:-99}" -lt 32 ] && mount -o remount,size=32M /run 2>/dev/null

# ── board ──
MODEL=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null)
case "$MODEL" in
  *Raspberry*) BOARD=pi ;;
  *Luckfox*|*luckfox*|*LUCKFOX*) BOARD=luckfox ;;
  *) if [ -f /etc/rpi-issue ]; then BOARD=pi; elif grep -qi rv1106 /proc/device-tree/compatible 2>/dev/null; then BOARD=luckfox; else BOARD=linux; fi ;;
esac
echo "$BOARD" > "$DATA/board"
echo "${MODEL:-$(uname -m)}" > "$DATA/model"

# ── old Raspberry Pi install (install_pi.sh ≤ v1.6.13: service «airsense», data in ~/airsense-data) ──
for OLD in airsense hygrolink; do
  F=/etc/systemd/system/$OLD.service
  [ -f "$F" ] || continue
  OD=$(grep -m1 -oP -- '--data \K\S+' "$F")
  systemctl disable --now "$OLD" >/dev/null 2>&1
  rm -f "$F"
  if [ -n "$OD" ] && [ -d "$OD" ] && ! ls "$DATA"/*.db >/dev/null 2>&1; then
    cp -an "$OD"/. "$DATA"/ && echo "✔ Old data $OD → $DATA (the old folder is kept)"
  fi
  echo "✔ Old service «$OLD» replaced by airsense-boot"
done
systemctl disable --now hygrolink-bootwifi >/dev/null 2>&1; rm -f /etc/systemd/system/hygrolink-bootwifi.service
rm -f /opt/airsense/AirSense.pyw /opt/airsense/VERSION /usr/local/bin/hygrolink-wifi
[ -e /usr/local/bin/hygrolink ] && ln -sf /usr/local/bin/airsense /usr/local/bin/hygrolink   # old command still works

# ── helper tools ──
[ -f "$HERE/airsense-pwcheck.sh" ] && { sed 's/\r$//' "$HERE/airsense-pwcheck.sh" > /usr/local/sbin/airsense-pwcheck; chmod 755 /usr/local/sbin/airsense-pwcheck; }
[ -f "$HERE/airsense-password.sh" ] && { sed 's/\r$//' "$HERE/airsense-password.sh" > /etc/profile.d/airsense-password.sh; chmod 644 /etc/profile.d/airsense-password.sh; }
if [ -f "$HERE/airsense_wifi.py" ] && command -v nmcli >/dev/null; then
  sed 's/\r$//' "$HERE/airsense_wifi.py" > /usr/local/bin/airsense-wifi; chmod 755 /usr/local/bin/airsense-wifi
fi

# ── /run size: only on low-RAM boards (Luckfox) ──
if [ "${RUN_MB:-99}" -lt 32 ] || [ "$BOARD" = luckfox ]; then
cat > /etc/systemd/system/airsense-run-size.service <<'EOF'
[Unit]
Description=AirSense — larger /run (low RAM)
DefaultDependencies=no
After=local-fs.target
Before=sysinit.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c '[ "$(df -m --output=size /run | tail -1 | tr -d " ")" -lt 32 ] && mount -o remount,size=32M /run; true'

[Install]
WantedBy=sysinit.target
EOF
  RUNSIZE=1
else
  systemctl disable airsense-run-size >/dev/null 2>&1; rm -f /etc/systemd/system/airsense-run-size.service
  RUNSIZE=0
fi

cat > /etc/systemd/system/airsense-boot.service <<'EOF'
[Unit]
Description=AirSense server (BleBox humiditySensor) — autostart
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

cat > /etc/systemd/system/airsense-update.service <<'EOF'
[Unit]
Description=AirSense — check GitHub for a new version
Wants=network-online.target
After=network-online.target airsense-boot.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/airsense-update
Nice=10
EOF

cat > /etc/systemd/system/airsense-update.timer <<'EOF'
[Unit]
Description=AirSense — auto-update (10 min after boot and every 6 hours)

[Timer]
OnBootSec=10min
OnUnitActiveSec=6h
RandomizedDelaySec=15min
Persistent=true

[Install]
WantedBy=timers.target
EOF

# ── Raspberry Pi: WiFi from the SD card (airsense-wifi.txt on the boot partition) ──
if [ -x /usr/local/bin/airsense-wifi ]; then
cat > /etc/systemd/system/airsense-bootwifi.service <<'EOF'
[Unit]
Description=AirSense — WiFi from the SD card (airsense-wifi.txt on the boot partition)
After=NetworkManager.service
Wants=NetworkManager.service
Before=airsense-boot.service

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/local/bin/airsense-wifi bootfile

[Install]
WantedBy=multi-user.target
EOF
  BOOTWIFI=1
else
  BOOTWIFI=0
fi

# ── time zone: default Europe/Athens (until you choose another with: airsense clock Zone/City) ──
[ -s "$DATA/timezone" ] || echo "Europe/Athens" > "$DATA/timezone"
TZW=$(cat "$DATA/timezone" 2>/dev/null)
if [ -f "/usr/share/zoneinfo/$TZW" ] && [ "$(readlink -f /etc/localtime)" != "$(readlink -f "/usr/share/zoneinfo/$TZW")" ]; then
  timedatectl set-timezone "$TZW" 2>/dev/null || { ln -sf "/usr/share/zoneinfo/$TZW" /etc/localtime; echo "$TZW" > /etc/timezone; }
  echo "✔ time zone: $TZW (UTC$(TZ=$TZW date +%:z))"
fi

systemctl daemon-reload 2>/dev/null || { mount -o remount,size=32M /run; systemctl daemon-reload; }
[ "$RUNSIZE" = 1 ] && systemctl enable airsense-run-size >/dev/null 2>&1
[ "$BOOTWIFI" = 1 ] && systemctl enable airsense-bootwifi >/dev/null 2>&1
systemctl enable airsense-boot >/dev/null 2>&1
systemctl enable --now airsense-update.timer >/dev/null 2>&1
echo "✔ services ready (board: $BOARD)"
exit 0
