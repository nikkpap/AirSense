#!/bin/bash
# AirSense (Luckfox) — system services. Runs from the installer and after every automatic update.
mount -o remount,size=32M /run 2>/dev/null

cat > /etc/systemd/system/airsense-run-size.service <<'EOF'
[Unit]
Description=AirSense — larger /run (low RAM)
DefaultDependencies=no
After=local-fs.target
Before=sysinit.target

[Service]
Type=oneshot
ExecStart=/bin/mount -o remount,size=32M /run

[Install]
WantedBy=sysinit.target
EOF

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

systemctl daemon-reload 2>/dev/null || { mount -o remount,size=32M /run; systemctl daemon-reload; }
systemctl enable airsense-run-size airsense-boot >/dev/null 2>&1
systemctl enable --now airsense-update.timer >/dev/null 2>&1
exit 0
