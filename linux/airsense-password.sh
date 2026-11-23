# AirSense — /etc/profile.d/airsense-password.sh
# On an SSH login: if the password is still the factory default (e.g. «luckfox»), ask to change it.
# Once changed this stays silent. Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM
_airsense_pw() {
  _f="$HOME/.airsense-default-password"
  [ -f "$_f" ] || return 0
  [ -t 0 ] && [ -t 1 ] || return 0
  case $- in *i*) ;; *) return 0 ;; esac
  [ "$(id -u)" = 0 ] && return 0
  if grep -q '^user$' "$_f"; then
    printf '\n\033[1;33m⚠  AirSense: the password of «%s» is still the factory default — anyone can log in!\033[0m\n' "$(id -un)"
    printf '   Change it now? (Y/n): '; read -r _a
    case "$_a" in
      n|N|no|NO|No) printf '   OK — I will ask again at the next login (or run: airsense password)\n\n'; return 0 ;;
    esac
    echo "   Type the CURRENT password first, then the NEW one twice (nothing shows while you type):"
    if passwd; then
      sed -i '/^user$/d' "$_f"
      printf '\033[1;32m   ✔ Password changed — use the new one from now on (ssh, sudo).\033[0m\n'
    else
      printf '\033[1;31m   ✖ Not changed\033[0m — I will ask again at the next login (or: airsense password)\n\n'; return 0
    fi
  fi
  if grep -q '^root$' "$_f"; then
    printf '\n\033[1;33m⚠  The «root» password is also the factory default.\033[0m Change it too? (Y/n): '; read -r _a
    case "$_a" in
      n|N|no|NO|No) printf '   OK — later: airsense password\n\n'; return 0 ;;
    esac
    echo "   (sudo asks for YOUR password first, then the new root password twice)"
    if sudo passwd root; then sed -i '/^root$/d' "$_f"; printf '\033[1;32m   ✔ root password changed.\033[0m\n'; fi
  fi
  [ -s "$_f" ] || rm -f "$_f"
  echo
}
_airsense_pw
unset -f _airsense_pw 2>/dev/null; unset _f _a
