#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  AirSense — is a login password still the factory default? (runs as root:
#  at the end of the setup and on every boot)
#  Default found → writes ~/.airsense-default-password (lines: user / root)
#  → on the next SSH login you are asked to change it (/etc/profile.d/airsense-password.sh).
#  Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM
# ═══════════════════════════════════════════════════════════════════════════
[ "$(id -u)" = 0 ] || exec sudo bash "$0" "$@"
U=$(cat /var/lib/airsense/user 2>/dev/null)
[ -n "$U" ] || U=$(getent passwd 1000 | cut -d: -f1)
[ -n "$U" ] || exit 0
UH=$(getent passwd "$U" | cut -d: -f6); [ -d "$UH" ] || exit 0
FLAG="$UH/.airsense-default-password"
command -v perl >/dev/null || exit 0

# well-known factory passwords of these boards / images
DEFAULTS="luckfox raspberry pico pi ubuntu root admin password orangepi linaro rockchip debian 1234 12345678"

is_default() {   # $1 = account → 0 if its password is one of the defaults (or the user name)
  local h p
  h=$(getent shadow "$1" | cut -d: -f2)
  case "$h" in ''|'!'*|'*'*) return 1 ;; esac    # no password / locked → nothing to change
  for p in $DEFAULTS "$1"; do
    perl -e 'exit(crypt($ARGV[0], $ARGV[1]) eq $ARGV[1] ? 0 : 1)' "$p" "$h" 2>/dev/null && return 0
  done
  return 1
}

OUT=""
is_default "$U"   && OUT="user"
is_default root   && OUT="${OUT:+$OUT
}root"
if [ -n "$OUT" ]; then
  printf '%s\n' "$OUT" > "$FLAG"; chown "$U": "$FLAG"; chmod 644 "$FLAG"
  echo "⚠ factory-default password: $(echo $OUT | sed "s/user/$U/") → you will be asked to change it at the next login (or: airsense password)"
else
  rm -f "$FLAG"
  [ "${1:-}" = "-v" ] && echo "✔ passwords are not the factory defaults"
fi
exit 0
