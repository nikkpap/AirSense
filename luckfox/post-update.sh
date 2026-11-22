#!/bin/bash
# AirSense (Luckfox) — υπηρεσίες συστήματος. Τρέχει από το setup και μετά από κάθε αυτόματη ενημέρωση.
mount -o remount,size=32M /run 2>/dev/null

cat > /etc/systemd/system/airsense-run-size.service <<'EOF'
[Unit]
Description=AirSense — μεγαλύτερο /run (λίγη RAM)
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

cat > /etc/systemd/system/airsense-update.service <<'EOF'
[Unit]
Description=AirSense — έλεγχος για νέα έκδοση στο GitHub
Wants=network-online.target
After=network-online.target airsense-boot.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/airsense-update
Nice=10
EOF

cat > /etc/systemd/system/airsense-update.timer <<'EOF'
[Unit]
Description=AirSense — αυτόματη ενημέρωση (10' μετά το boot και κάθε 6 ώρες)

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
