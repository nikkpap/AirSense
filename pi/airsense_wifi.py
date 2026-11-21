#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🌬 AirSense WiFi — εύκολη σύνδεση του Raspberry Pi σε νέο WiFi (NetworkManager / nmcli)
Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM

Μενού:      sudo airsense-wifi          (ή: airsense wifi)
Γρήγορα:    sudo airsense-wifi add "Όνομα WiFi" "κωδικός"
            sudo airsense-wifi list | scan | status | forget "Όνομα"
Κάρτα SD:   αρχείο airsense-wifi.txt στο boot (bootfs) της κάρτας → εφαρμόζεται στην εκκίνηση
            (υπηρεσία airsense-bootwifi — καλεί: airsense-wifi bootfile)
"""
import configparser
import getpass
import os
import shutil
import subprocess
import sys
import time

VERSION = "1.2.0"
IFACE = os.environ.get("HYGROLINK_WIFI_IFACE", "wlan0")
LOG = "/tmp/airsense-wifi.log"

G, Y, R, B, D, N = "\033[1;32m", "\033[1;33m", "\033[1;31m", "\033[1;36m", "\033[2m", "\033[0m"


def ok(m):
    print(f"{G}✔{N} {m}")


def warn(m):
    print(f"{Y}⚠{N} {m}")


def err(m):
    print(f"{R}✖{N} {m}")


# ── nmcli ────────────────────────────────────────────────────────────────
def nm(*args, check=False, timeout=40):
    r = subprocess.run(["nmcli", *args], capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip() or f"nmcli {' '.join(args)} απέτυχε")
    return r


def split_terse(line):
    """Διαχωρισμός γραμμής «nmcli -t» (το ':' μέσα σε τιμή γίνεται '\\:')."""
    out, cur, esc = [], [], False
    for ch in line:
        if esc:
            cur.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out


def parse_scan(text):
    nets = {}
    for line in text.splitlines():
        f = split_terse(line)
        if len(f) < 6 or not f[1].strip():
            continue
        inuse, ssid, sig, chan, freq, sec = f[:6]
        sig = int(sig) if sig.isdigit() else 0
        band = "5 GHz" if freq.strip().startswith("5") else "2.4 GHz"
        n = nets.get(ssid)
        if n is None or sig > n["signal"]:
            nets[ssid] = {"ssid": ssid, "signal": sig, "chan": chan, "band": band,
                          "sec": sec.strip() or "", "inuse": inuse.strip() == "*" or (n or {}).get("inuse", False)}
        elif inuse.strip() == "*":
            n["inuse"] = True
    return sorted(nets.values(), key=lambda n: (not n["inuse"], -n["signal"]))


def scan(rescan=True):
    r = nm("-t", "-f", "IN-USE,SSID,SIGNAL,CHAN,FREQ,SECURITY", "dev", "wifi", "list",
           "--rescan", "yes" if rescan else "no", timeout=60)
    return parse_scan(r.stdout)


def saved():
    r = nm("-t", "-f", "NAME,TYPE,AUTOCONNECT,AUTOCONNECT-PRIORITY,ACTIVE", "con", "show")
    out = []
    for line in r.stdout.splitlines():
        f = split_terse(line)
        if len(f) >= 5 and f[1] in ("802-11-wireless", "wifi"):
            ssid = nm("-g", "802-11-wireless.ssid", "con", "show", "id", f[0]).stdout.strip() or f[0]
            out.append({"name": f[0], "ssid": ssid, "auto": f[2] == "yes",
                        "prio": int(f[3]) if f[3].lstrip("-").isdigit() else 0, "active": f[4] == "yes"})
    return sorted(out, key=lambda c: (not c["active"], -c["prio"], c["name"].lower()))


def active_conn():
    for c in saved():
        if c["active"]:
            return c
    return None


def active_wifi():
    c = active_conn()
    return c["name"] if c else None


def ip_addrs():
    try:
        return subprocess.run(["hostname", "-I"], capture_output=True, text=True).stdout.split()
    except Exception:
        return []


def key_mgmt(sec):
    s = sec.upper()
    if not s or s in ("--", "NONE"):
        return None
    if "WPA3" in s and "WPA2" not in s and "WPA1" not in s:
        return "sae"
    return "wpa-psk"


def save_network(ssid, password="", sec="WPA2", hidden=False, priority=10):
    """Αποθήκευση δικτύου (χωρίς να κοπεί το τωρινό). Αν υπάρχει ήδη, αντικαθίσταται."""
    active_same = None
    for c in saved():
        if c["ssid"] == ssid or c["name"] == ssid:
            if c["active"]:
                active_same = c["name"]
            else:
                nm("con", "delete", "id", c["name"])     # παλιό προφίλ για το ίδιο δίκτυο
    km = None
    if password:
        km = "sae" if key_mgmt(sec) == "sae" else "wpa-psk"
    if active_same:
        args = ["con", "mod", "id", active_same]
    else:
        args = ["con", "add", "type", "wifi", "con-name", ssid, "ifname", IFACE, "ssid", ssid]
    args += ["connection.autoconnect", "yes", "connection.autoconnect-priority", str(priority)]
    if hidden:
        args += ["802-11-wireless.hidden", "yes"]
    if km and password:
        args += ["wifi-sec.key-mgmt", km, "wifi-sec.psk", password]
    nm(*args, check=True)


def connect_safely(ssid):
    """Σύνδεση στο νέο WiFi στο παρασκήνιο· αν δεν πετύχει σε ~60″ επιστρέφει στο προηγούμενο."""
    old = active_wifi() or ""
    S, O = sh(ssid), sh(old)
    script = "\n".join([
        "sleep 4",
        f'echo "$(date) σύνδεση στο:" {S} "(προηγούμενο:" {O}")"',
        f"if nmcli --wait 45 con up id {S}; then",
        "  sleep 15",
        f"  if nmcli -t -f GENERAL.STATE con show id {S} 2>/dev/null | grep -q activated; then",
        f'    echo "$(date) OK: συνδέθηκε στο:" {S}; exit 0',
        "  fi",
        "fi",
        f'echo "$(date) ΑΠΟΤΥΧΙΑ — επιστροφή στο:" {O}',
        f"nmcli --wait 45 con up id {O}" if old else "true",
        "",
    ])
    subprocess.Popen(["setsid", "bash", "-c", script], stdout=open(LOG, "a"), stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, close_fds=True)


def sh(s):
    return "'" + str(s).replace("'", "'\"'\"'") + "'"


# ── WiFi από την κάρτα SD (boot partition) ────────────────────────────────
BOOT_DIRS = ("/boot/firmware", "/boot")
BOOT_FILE = "airsense-wifi.txt"
BOOT_DONE = "airsense-wifi.applied.txt"
BOOT_LOG = "airsense-wifi-log.txt"
BOOT_EXAMPLE = "airsense-wifi.example.txt"
BOOT_FILE_OLD = "hygrolink-wifi.txt"      # παλιό όνομα (ALU HygroLink) — διαβάζεται κι αυτό
EXAMPLE_TEXT = """# ═══ AirSense — WiFi από την κάρτα SD ═══
# 1. Αντίγραψε αυτό το αρχείο ως:  airsense-wifi.txt   (στον ίδιο φάκελο, bootfs)
# 2. Γράψε όνομα WiFi και κωδικό. Μπορείς να βάλεις πολλά δίκτυα: [Γραφείο], [Σπίτι], [Εργοτάξιο]…
# 3. Βάλε την κάρτα στο Pi και άναψέ το. Σε 1–2 λεπτά: ssh pi@airsense.local
# Μετά την εφαρμογή ο κωδικός σβήνεται από το αρχείο (γίνεται airsense-wifi.applied.txt)
# και στο airsense-wifi-log.txt γράφεται το αποτέλεσμα και η IP του Pi.
# Μόνο WiFi 2.4 GHz (το Pi Zero 2 W δεν βλέπει 5 GHz).

[Γραφείο]
ssid = Όνομα-WiFi-γραφείου
password = κωδικός-WiFi
priority = 50
hidden = no
"""


def boot_dir():
    for d in BOOT_DIRS:
        if os.path.isfile(os.path.join(d, "config.txt")) or os.path.isfile(os.path.join(d, "cmdline.txt")):
            return d
    return None


def _boot_log(bd, lines):
    try:
        with open(os.path.join(bd, BOOT_LOG), "a", encoding="utf-8") as f:
            for l in lines:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + l + "\r\n")
        os.sync()
    except Exception:
        pass


def parse_boot_file(text):
    """[Ενότητα] με ssid/password/priority/hidden. Δέχεται και απλή μορφή χωρίς [ενότητα]."""
    text = text.lstrip("\ufeff")
    if not any(l.strip().startswith("[") for l in text.splitlines()):
        text = "[wifi]\n" + text
    cp = configparser.ConfigParser(interpolation=None, strict=False, comment_prefixes=("#", ";"),
                                   inline_comment_prefixes=None)
    cp.optionxform = str.lower
    cp.read_string(text)
    nets = []
    for sec in cp.sections():
        c = cp[sec]
        ssid = (c.get("ssid") or c.get("name") or c.get("όνομα") or "").strip()
        pw = (c.get("password") or c.get("pass") or c.get("κωδικός") or "").strip()
        if not ssid or ssid.startswith("Όνομα-WiFi"):
            continue
        try:
            prio = int((c.get("priority") or "50").strip())
        except ValueError:
            prio = 50
        hidden = (c.get("hidden") or "no").strip().lower() in ("yes", "true", "1", "ναι", "ν")
        nets.append({"section": sec, "ssid": ssid, "password": pw, "priority": prio, "hidden": hidden})
    return nets


def boot_apply():
    """Καλείται στην εκκίνηση (airsense-bootwifi.service)."""
    bd = boot_dir()
    if not bd:
        return 0
    ex = os.path.join(bd, BOOT_EXAMPLE)
    if not os.path.exists(ex):
        try:
            with open(ex, "w", encoding="utf-8", newline="\r\n") as f:
                f.write(EXAMPLE_TEXT)
        except Exception:
            pass
    src = os.path.join(bd, BOOT_FILE)
    if not os.path.isfile(src) and os.path.isfile(os.path.join(bd, BOOT_FILE_OLD)):
        src = os.path.join(bd, BOOT_FILE_OLD)
    if not os.path.isfile(src):
        return 0
    old_ex = os.path.join(bd, "hygrolink-wifi.example.txt")
    if os.path.exists(old_ex):
        try:
            os.remove(old_ex)        # το Pi έχει πλέον τον νέο installer (AirSense)
        except Exception:
            pass
    try:
        with open(src, encoding="utf-8-sig", errors="replace") as f:
            text = f.read()
        nets = parse_boot_file(text)
    except Exception as e:
        _boot_log(bd, [f"✖ Λάθος στο {BOOT_FILE}: {e}"])
        return 1
    log = [f"── Βρέθηκε {BOOT_FILE}: {len(nets)} δίκτυα ──"]
    added = []
    for n in nets:
        if n["password"] and not 8 <= len(n["password"]) <= 63:
            log.append(f"✖ {n['ssid']}: ο κωδικός πρέπει να έχει 8–63 χαρακτήρες — παραλείφθηκε")
            continue
        try:
            save_network(n["ssid"], n["password"], "WPA2" if n["password"] else "", n["hidden"], n["priority"])
            log.append(f"✔ Αποθηκεύτηκε: {n['ssid']} (προτεραιότητα {n['priority']})")
            added.append(n["ssid"])
        except Exception as e:
            log.append(f"✖ {n['ssid']}: {e}")
    # αφαίρεση κωδικών από την κάρτα (το αρχείο γίνεται .applied.txt χωρίς κωδικούς)
    masked = []
    for line in text.lstrip("\ufeff").splitlines():
        k = line.split("=", 1)[0].strip().lower() if "=" in line else ""
        masked.append(f"{line.split('=', 1)[0].rstrip()} = ********" if k in ("password", "pass", "κωδικός") else line)
    try:
        with open(os.path.join(bd, BOOT_DONE), "w", encoding="utf-8", newline="\r\n") as f:
            f.write("# Εφαρμόστηκε " + time.strftime("%Y-%m-%d %H:%M") + " — οι κωδικοί σβήστηκαν\n" + "\n".join(masked) + "\n")
        os.remove(src)
    except Exception as e:
        log.append(f"⚠ Δεν σβήστηκε το {BOOT_FILE}: {e}")
    os.sync()
    _boot_log(bd, log)
    # αν δεν είναι συνδεδεμένο, δοκίμασε τώρα· μετά γράψε σε ποιο δίκτυο μπήκε και την IP
    bg = "\n".join([
        "sleep 8",
        "if ! nmcli -t -f DEVICE,STATE dev | grep -q '^" + IFACE + ":connected'; then",
        "  nmcli dev wifi rescan >/dev/null 2>&1; sleep 6",
        *[f"  nmcli -t -f DEVICE,STATE dev | grep -q '^{IFACE}:connected' || nmcli --wait 40 con up id {sh(a)} >/dev/null 2>&1"
          for a in added],
        "fi",
        "for i in $(seq 1 30); do nmcli -t -f DEVICE,STATE dev | grep -q '^" + IFACE + ":connected' && break; sleep 3; done",
        f"S=$(nmcli -t -f ACTIVE,SSID dev wifi | grep '^yes:' | cut -d: -f2-)",
        f"echo \"$(date '+%Y-%m-%d %H:%M:%S') 📶 WiFi: ${{S:-ΧΩΡΙΣ ΣΥΝΔΕΣΗ}} · IP: $(hostname -I) · ssh $(stat -c %U /home/* 2>/dev/null | head -1)@$(hostname).local\r\" >> {sh(os.path.join(bd, BOOT_LOG))}",
        "sync",
    ])
    subprocess.Popen(["setsid", "bash", "-c", bg], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, close_fds=True)
    return 0


# ── οθόνες ───────────────────────────────────────────────────────────────
def header():
    os.system("clear")
    print(f"{B}╔══════════════════════════════════════════════╗")
    print(f"║  🌬 AirSense — WiFi του Raspberry Pi  v{VERSION}  ║")
    print(f"╚══════════════════════════════════════════════╝{N}")
    c = active_conn()
    ips = [i for i in ip_addrs() if ":" not in i]
    print(f"  Τώρα: {G + c['ssid'] + N if c else R + 'χωρίς WiFi' + N}   IP: {', '.join(ips) or '—'}\n")


def ask(prompt, default=""):
    try:
        v = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    except EOFError:
        v = ""
    return v or default


def yes(prompt, default=True):
    v = ask(prompt + (" (Ν/ο)" if default else " (ν/Ο)")).lower()
    if not v:
        return default
    return v[0] in ("ν", "y")


def pause():
    try:
        input(f"\n{D}Enter για συνέχεια…{N}")
    except EOFError:
        pass


def choose_and_add():
    print("🔍 Σάρωση δικτύων… (λίγα δευτερόλεπτα)")
    try:
        nets = scan(True)
    except Exception as e:
        err(f"Η σάρωση απέτυχε: {e}")
        return
    if not nets:
        warn("Δεν βρέθηκαν δίκτυα. Είναι κοντά το router; Το Zero 2 W βλέπει μόνο 2.4 GHz.")
        return
    print()
    for i, n in enumerate(nets, 1):
        bars = "▂▄▆█"[:max(1, min(4, n["signal"] // 25 + 1))]
        lock = "🔓" if not key_mgmt(n["sec"]) else "🔒"
        here = f" {G}← τώρα{N}" if n["inuse"] else ""
        print(f"  {B}{i:>2}{N}) {n['ssid']:<32} {bars:<4} {n['signal']:>3}%  {lock} {n['band']}{here}")
    print(f"   {B}0{N}) Πίσω")
    k = ask("\nΑριθμός δικτύου")
    if not k.isdigit() or int(k) == 0 or int(k) > len(nets):
        return
    n = nets[int(k) - 1]
    add_flow(n["ssid"], n["sec"])


def add_flow(ssid, sec="WPA2", hidden=False):
    pw = ""
    if key_mgmt(sec) or hidden:
        while True:
            pw = getpass.getpass(f"Κωδικός για «{ssid}» (δεν φαίνεται όσο γράφεις): ")
            if hidden and not pw:
                break
            if 8 <= len(pw) <= 63:
                break
            err("Ο κωδικός WiFi πρέπει να έχει 8–63 χαρακτήρες.")
    try:
        save_network(ssid, pw, sec if not hidden else ("WPA2" if pw else ""), hidden)
    except Exception as e:
        err(f"Δεν αποθηκεύτηκε: {e}")
        return
    ok(f"Το «{ssid}» αποθηκεύτηκε. Το Pi θα συνδέεται μόνο του όταν το βρίσκει.")
    print(f"\n  {B}1{N}) Μόνο αποθήκευση — θα συνδεθεί όταν πάει εκεί {G}(ασφαλές, προτείνεται){N}")
    print(f"  {B}2{N}) Σύνδεση ΤΩΡΑ")
    if ask("Επιλογή", "1") == "2":
        warn("Η σύνδεση SSH μπορεί να κοπεί αν ο υπολογιστής δεν είναι στο ίδιο WiFi.")
        warn("Αν το νέο WiFi δεν δουλέψει, το Pi επιστρέφει μόνο του στο προηγούμενο σε ~1 λεπτό.")
        connect_safely(ssid)
        ok(f"Η σύνδεση ξεκίνησε στο παρασκήνιο. Αποτέλεσμα: {LOG}")


def add_hidden():
    ssid = ask("Όνομα κρυφού WiFi (ακριβώς, με κεφαλαία/μικρά)")
    if ssid:
        add_flow(ssid, "WPA2", hidden=True)


def show_saved():
    cs = saved()
    if not cs:
        warn("Δεν υπάρχουν αποθηκευμένα WiFi.")
        return cs
    print(f"  {'#':>2}  {'Δίκτυο':<32} {'Προτερ.':>7}  Κατάσταση")
    for i, c in enumerate(cs, 1):
        st = f"{G}● συνδεδεμένο{N}" if c["active"] else ("αυτόματη σύνδεση" if c["auto"] else f"{D}χειροκίνητο{N}")
        label = c["ssid"] if c["ssid"] == c["name"] else f"{c['ssid']} {D}({c['name']}){N}"
        print(f"  {B}{i:>2}{N}  {label:<32} {c['prio']:>7}  {st}")
    return cs


def set_priority():
    cs = show_saved()
    if not cs:
        return
    k = ask("\nΑριθμός δικτύου")
    if not k.isdigit() or not 1 <= int(k) <= len(cs):
        return
    p = ask("Προτεραιότητα (μεγαλύτερο = προτιμάται, π.χ. 100)", "50")
    try:
        nm("con", "mod", "id", cs[int(k) - 1]["name"], "connection.autoconnect-priority", str(int(p)), check=True)
        ok("Αποθηκεύτηκε.")
    except Exception as e:
        err(str(e))


def forget():
    cs = show_saved()
    if not cs:
        return
    k = ask("\nΑριθμός δικτύου για διαγραφή")
    if not k.isdigit() or not 1 <= int(k) <= len(cs):
        return
    c = cs[int(k) - 1]
    if c["active"]:
        warn("Αυτό είναι το τωρινό δίκτυο! Αν το σβήσεις, το Pi θα αποσυνδεθεί.")
        if len(cs) == 1:
            err("Είναι το μόνο αποθηκευμένο δίκτυο — δεν σβήνεται (θα χανόταν το Pi).")
            return
    if yes(f"Διαγραφή «{c['ssid']}»;", False):
        try:
            nm("con", "delete", "id", c["name"], check=True)
            ok("Διαγράφηκε.")
        except Exception as e:
            err(str(e))


def status():
    c = active_conn()
    print(f"  WiFi:  {c['ssid'] if c else '—'}")
    try:
        for n in scan(False):
            if n["inuse"]:
                print(f"  Σήμα:  {n['signal']}%  ·  κανάλι {n['chan']}  ·  {n['band']}")
    except Exception:
        pass
    for ip in ip_addrs():
        if ":" not in ip:
            print(f"  IP:    {ip}" + ("   (Tailscale)" if ip.startswith("100.") else ""))
    print(f"  Όνομα: {os.uname().nodename}.local")
    if os.path.exists(LOG):
        print(f"\n{D}Τελευταίες ενέργειες ({LOG}):{N}")
        with open(LOG, encoding="utf-8", errors="replace") as f:
            for line in f.readlines()[-4:]:
                print("  " + line.rstrip())


def menu():
    while True:
        header()
        print(f"  {B}1{N}) 🔍 Σάρωση & προσθήκη νέου WiFi")
        print(f"  {B}2{N}) 📋 Αποθηκευμένα δίκτυα")
        print(f"  {B}3{N}) ⭐ Προτεραιότητα δικτύου")
        print(f"  {B}4{N}) 🗑  Διαγραφή αποθηκευμένου δικτύου")
        print(f"  {B}5{N}) ✍  Κρυφό δίκτυο (γράφω το όνομα)")
        print(f"  {B}6{N}) 📶 Κατάσταση / IP")
        print(f"  {B}0{N}) Έξοδος\n")
        c = ask("Επιλογή")
        print()
        if c == "1":
            choose_and_add()
        elif c == "2":
            show_saved()
        elif c == "3":
            set_priority()
        elif c == "4":
            forget()
        elif c == "5":
            add_hidden()
        elif c == "6":
            status()
        elif c in ("0", "q", ""):
            return
        pause()


def main():
    if not shutil.which("nmcli"):
        err("Δεν βρέθηκε το nmcli (NetworkManager). Χρειάζεται Raspberry Pi OS Bookworm/Trixie.")
        return 1
    if os.geteuid() != 0:
        os.execvp("sudo", ["sudo", sys.executable, os.path.abspath(__file__), *sys.argv[1:]])
    a = sys.argv[1:]
    try:
        if not a:
            menu()
        elif a[0] == "add" and len(a) >= 2:
            pw = a[2] if len(a) >= 3 else ""
            save_network(a[1], pw, "WPA2" if pw else "")
            ok(f"Αποθηκεύτηκε: {a[1]} (θα συνδέεται μόνο του)")
            if "--now" in a:
                connect_safely(a[1])
                ok(f"Σύνδεση στο παρασκήνιο — δες {LOG}")
        elif a[0] == "list":
            show_saved()
        elif a[0] == "scan":
            for n in scan(True):
                print(f"{n['signal']:>3}%  {n['band']:<7} {'🔒' if key_mgmt(n['sec']) else '🔓'}  {n['ssid']}")
        elif a[0] == "forget" and len(a) >= 2:
            nm("con", "delete", "id", a[1], check=True)
            ok(f"Διαγράφηκε: {a[1]}")
        elif a[0] == "status":
            status()
        elif a[0] == "bootfile":
            return boot_apply()
        else:
            print(__doc__)
    except KeyboardInterrupt:
        print()
    except Exception as e:
        err(str(e))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
