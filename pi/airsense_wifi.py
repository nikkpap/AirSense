#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🌬 AirSense WiFi — easy connection of the Raspberry Pi to a new WiFi (NetworkManager / nmcli)
Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM

Menu:       sudo airsense-wifi          (or: airsense wifi)
Quick:      sudo airsense-wifi add "WiFi name" "password" [--now]
            sudo airsense-wifi list | scan | status | forget "Name"
SD card:    file airsense-wifi.txt on the card's boot partition (bootfs) → applied on boot
            (service airsense-bootwifi — runs: airsense-wifi bootfile)
"""
import configparser
import getpass
import os
import shutil
import subprocess
import sys
import time

VERSION = "1.3.0"
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
        raise RuntimeError((r.stderr or r.stdout).strip() or f"nmcli {' '.join(args)} failed")
    return r


def split_terse(line):
    """Split a «nmcli -t» line (a ':' inside a value is written as '\\:')."""
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
    """Save a network (without dropping the current one). An existing profile is replaced."""
    active_same = None
    for c in saved():
        if c["ssid"] == ssid or c["name"] == ssid:
            if c["active"]:
                active_same = c["name"]
            else:
                nm("con", "delete", "id", c["name"])     # old profile for the same network
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
    """Connect to the new WiFi in the background; if it fails within ~60 s, go back to the previous one."""
    old = active_wifi() or ""
    S, O = sh(ssid), sh(old)
    script = "\n".join([
        "sleep 4",
        f'echo "$(date) connecting to:" {S} "(previous:" {O}")"',
        f"if nmcli --wait 45 con up id {S}; then",
        "  sleep 15",
        f"  if nmcli -t -f GENERAL.STATE con show id {S} 2>/dev/null | grep -q activated; then",
        f'    echo "$(date) OK: connected to:" {S}; exit 0',
        "  fi",
        "fi",
        f'echo "$(date) FAILED — going back to:" {O}',
        f"nmcli --wait 45 con up id {O}" if old else "true",
        "",
    ])
    subprocess.Popen(["setsid", "bash", "-c", script], stdout=open(LOG, "a"), stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, close_fds=True)


def sh(s):
    return "'" + str(s).replace("'", "'\"'\"'") + "'"


# ── WiFi from the SD card (boot partition) ─────────────────────────────────
BOOT_DIRS = ("/boot/firmware", "/boot")
BOOT_FILE = "airsense-wifi.txt"
BOOT_DONE = "airsense-wifi.applied.txt"
BOOT_LOG = "airsense-wifi-log.txt"
BOOT_EXAMPLE = "airsense-wifi.example.txt"
BOOT_FILE_OLD = "hygrolink-wifi.txt"      # old name (ALU HygroLink) — also read
EXAMPLE_TEXT = """# ═══ AirSense — WiFi from the SD card ═══
# 1. Copy this file as:  airsense-wifi.txt   (same folder, bootfs)
# 2. Write the WiFi name and password. You can add many networks: [Office], [Home], [Site]…
# 3. Put the card in the Pi and power it on. In 1–2 minutes: ssh pi@airsense.local
# After applying, the password is removed from the file (it becomes airsense-wifi.applied.txt)
# and airsense-wifi-log.txt gets the result and the Pi's IP.
# 2.4 GHz WiFi only (the Pi Zero 2 W cannot see 5 GHz).

[Office]
ssid = Office-WiFi-name
password = wifi-password
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
    """[Section] with ssid/password/priority/hidden. A simple form without [section] works too."""
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
        if not ssid or ssid.startswith(("Όνομα-WiFi", "Office-WiFi-name")):
            continue
        try:
            prio = int((c.get("priority") or "50").strip())
        except ValueError:
            prio = 50
        hidden = (c.get("hidden") or "no").strip().lower() in ("yes", "true", "1", "ναι", "ν")
        nets.append({"section": sec, "ssid": ssid, "password": pw, "priority": prio, "hidden": hidden})
    return nets


def boot_apply():
    """Called on boot (airsense-bootwifi.service)."""
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
            os.remove(old_ex)        # the Pi now has the new installer (AirSense)
        except Exception:
            pass
    try:
        with open(src, encoding="utf-8-sig", errors="replace") as f:
            text = f.read()
        nets = parse_boot_file(text)
    except Exception as e:
        _boot_log(bd, [f"✖ Error in {BOOT_FILE}: {e}"])
        return 1
    log = [f"── Found {BOOT_FILE}: {len(nets)} network(s) ──"]
    added = []
    for n in nets:
        if n["password"] and not 8 <= len(n["password"]) <= 63:
            log.append(f"✖ {n['ssid']}: the password must have 8–63 characters — skipped")
            continue
        try:
            save_network(n["ssid"], n["password"], "WPA2" if n["password"] else "", n["hidden"], n["priority"])
            log.append(f"✔ Saved: {n['ssid']} (priority {n['priority']})")
            added.append(n["ssid"])
        except Exception as e:
            log.append(f"✖ {n['ssid']}: {e}")
    # remove passwords from the card (the file becomes .applied.txt without passwords)
    masked = []
    for line in text.lstrip("\ufeff").splitlines():
        k = line.split("=", 1)[0].strip().lower() if "=" in line else ""
        masked.append(f"{line.split('=', 1)[0].rstrip()} = ********" if k in ("password", "pass", "κωδικός") else line)
    try:
        with open(os.path.join(bd, BOOT_DONE), "w", encoding="utf-8", newline="\r\n") as f:
            f.write("# Applied " + time.strftime("%Y-%m-%d %H:%M") + " — passwords removed\n" + "\n".join(masked) + "\n")
        os.remove(src)
    except Exception as e:
        log.append(f"⚠ Could not remove {BOOT_FILE}: {e}")
    os.sync()
    _boot_log(bd, log)
    # if not connected, try now; then write which network it joined and the IP
    bg = "\n".join([
        "sleep 8",
        "if ! nmcli -t -f DEVICE,STATE dev | grep -q '^" + IFACE + ":connected'; then",
        "  nmcli dev wifi rescan >/dev/null 2>&1; sleep 6",
        *[f"  nmcli -t -f DEVICE,STATE dev | grep -q '^{IFACE}:connected' || nmcli --wait 40 con up id {sh(a)} >/dev/null 2>&1"
          for a in added],
        "fi",
        "for i in $(seq 1 30); do nmcli -t -f DEVICE,STATE dev | grep -q '^" + IFACE + ":connected' && break; sleep 3; done",
        f"S=$(nmcli -t -f ACTIVE,SSID dev wifi | grep '^yes:' | cut -d: -f2-)",
        f"echo \"$(date '+%Y-%m-%d %H:%M:%S') 📶 WiFi: ${{S:-NOT CONNECTED}} · IP: $(hostname -I) · ssh $(stat -c %U /home/* 2>/dev/null | head -1)@$(hostname).local\r\" >> {sh(os.path.join(bd, BOOT_LOG))}",
        "sync",
    ])
    subprocess.Popen(["setsid", "bash", "-c", bg], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, close_fds=True)
    return 0


# ── screens ──────────────────────────────────────────────────────────────
def header():
    os.system("clear")
    print(f"{B}╔══════════════════════════════════════════════╗")
    print(f"║  🌬 AirSense — Raspberry Pi WiFi  v{VERSION}     ║")
    print(f"╚══════════════════════════════════════════════╝{N}")
    c = active_conn()
    ips = [i for i in ip_addrs() if ":" not in i]
    print(f"  Now: {G + c['ssid'] + N if c else R + 'no WiFi' + N}   IP: {', '.join(ips) or '—'}\n")


def ask(prompt, default=""):
    try:
        v = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    except EOFError:
        v = ""
    return v or default


def yes(prompt, default=True):
    v = ask(prompt + (" (Y/n)" if default else " (y/N)")).lower()
    if not v:
        return default
    return v[0] in ("ν", "y")


def pause():
    try:
        input(f"\n{D}Press Enter to continue…{N}")
    except EOFError:
        pass


def choose_and_add():
    print("🔍 Scanning networks… (a few seconds)")
    try:
        nets = scan(True)
    except Exception as e:
        err(f"Scan failed: {e}")
        return
    if not nets:
        warn("No networks found. Is the router close? The Zero 2 W only sees 2.4 GHz.")
        return
    print()
    for i, n in enumerate(nets, 1):
        bars = "▂▄▆█"[:max(1, min(4, n["signal"] // 25 + 1))]
        lock = "🔓" if not key_mgmt(n["sec"]) else "🔒"
        here = f" {G}← now{N}" if n["inuse"] else ""
        print(f"  {B}{i:>2}{N}) {n['ssid']:<32} {bars:<4} {n['signal']:>3}%  {lock} {n['band']}{here}")
    print(f"   {B}0{N}) Back")
    k = ask("\nNetwork number")
    if not k.isdigit() or int(k) == 0 or int(k) > len(nets):
        return
    n = nets[int(k) - 1]
    add_flow(n["ssid"], n["sec"])


def add_flow(ssid, sec="WPA2", hidden=False):
    pw = ""
    if key_mgmt(sec) or hidden:
        while True:
            pw = getpass.getpass(f"Password for «{ssid}» (hidden while you type): ")
            if hidden and not pw:
                break
            if 8 <= len(pw) <= 63:
                break
            err("The WiFi password must have 8–63 characters.")
    try:
        save_network(ssid, pw, sec if not hidden else ("WPA2" if pw else ""), hidden)
    except Exception as e:
        err(f"Not saved: {e}")
        return
    ok(f"«{ssid}» saved. The Pi connects to it by itself whenever it finds it.")
    print(f"\n  {B}1{N}) Save only — it connects when it gets there {G}(safe, recommended){N}")
    print(f"  {B}2{N}) Connect NOW")
    if ask("Choice", "1") == "2":
        warn("Your SSH session may drop if the PC is not on the same WiFi.")
        warn("If the new WiFi does not work, the Pi goes back to the previous one by itself in ~1 minute.")
        connect_safely(ssid)
        ok(f"Connecting in the background. Result: {LOG}")


def add_hidden():
    ssid = ask("Hidden WiFi name (exactly, case-sensitive)")
    if ssid:
        add_flow(ssid, "WPA2", hidden=True)


def show_saved():
    cs = saved()
    if not cs:
        warn("No saved WiFi networks.")
        return cs
    print(f"  {'#':>2}  {'Network':<32} {'Priority':>8}  State")
    for i, c in enumerate(cs, 1):
        st = f"{G}● connected{N}" if c["active"] else ("auto-connect" if c["auto"] else f"{D}manual{N}")
        label = c["ssid"] if c["ssid"] == c["name"] else f"{c['ssid']} {D}({c['name']}){N}"
        print(f"  {B}{i:>2}{N}  {label:<32} {c['prio']:>8}  {st}")
    return cs


def set_priority():
    cs = show_saved()
    if not cs:
        return
    k = ask("\nNetwork number")
    if not k.isdigit() or not 1 <= int(k) <= len(cs):
        return
    p = ask("Priority (higher = preferred, e.g. 100)", "50")
    try:
        nm("con", "mod", "id", cs[int(k) - 1]["name"], "connection.autoconnect-priority", str(int(p)), check=True)
        ok("Saved.")
    except Exception as e:
        err(str(e))


def forget():
    cs = show_saved()
    if not cs:
        return
    k = ask("\nNetwork number to delete")
    if not k.isdigit() or not 1 <= int(k) <= len(cs):
        return
    c = cs[int(k) - 1]
    if c["active"]:
        warn("This is the current network! If you delete it, the Pi disconnects.")
        if len(cs) == 1:
            err("It is the only saved network — not deleted (the Pi would be lost).")
            return
    if yes(f"Delete «{c['ssid']}»?", False):
        try:
            nm("con", "delete", "id", c["name"], check=True)
            ok("Deleted.")
        except Exception as e:
            err(str(e))


def status():
    c = active_conn()
    print(f"  WiFi:  {c['ssid'] if c else '—'}")
    try:
        for n in scan(False):
            if n["inuse"]:
                print(f"  Signal: {n['signal']}%  ·  channel {n['chan']}  ·  {n['band']}")
    except Exception:
        pass
    for ip in ip_addrs():
        if ":" not in ip:
            print(f"  IP:    {ip}" + ("   (Tailscale)" if ip.startswith("100.") else ""))
    print(f"  Name:  {os.uname().nodename}.local")
    if os.path.exists(LOG):
        print(f"\n{D}Last actions ({LOG}):{N}")
        with open(LOG, encoding="utf-8", errors="replace") as f:
            for line in f.readlines()[-4:]:
                print("  " + line.rstrip())


def menu():
    while True:
        header()
        print(f"  {B}1{N}) 🔍 Scan & add a new WiFi")
        print(f"  {B}2{N}) 📋 Saved networks")
        print(f"  {B}3{N}) ⭐ Network priority")
        print(f"  {B}4{N}) 🗑  Delete a saved network")
        print(f"  {B}5{N}) ✍  Hidden network (type the name)")
        print(f"  {B}6{N}) 📶 Status / IP")
        print(f"  {B}0{N}) Exit\n")
        c = ask("Choice")
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
        err("nmcli (NetworkManager) not found. Raspberry Pi OS Bookworm/Trixie is required.")
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
            ok(f"Saved: {a[1]} (connects by itself)")
            if "--now" in a:
                connect_safely(a[1])
                ok(f"Connecting in the background — see {LOG}")
        elif a[0] == "list":
            show_saved()
        elif a[0] == "scan":
            for n in scan(True):
                print(f"{n['signal']:>3}%  {n['band']:<7} {'🔒' if key_mgmt(n['sec']) else '🔓'}  {n['ssid']}")
        elif a[0] == "forget" and len(a) >= 2:
            nm("con", "delete", "id", a[1], check=True)
            ok(f"Deleted: {a[1]}")
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
