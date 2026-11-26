#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AirSense (πρώην ALU HygroLink) — BleBox humiditySensor monitor, logger & mobile web server
---------------------------------------------------------------------------
* Σάρωση δικτύου (LAN) για συσκευές BleBox + σάρωση WiFi για νέους αισθητήρες
* Ρύθμιση WiFi νέου αισθητήρα (Access Point mode 192.168.4.1)
* Συνεχής καταγραφή θερμοκρασίας / υγρασίας / σημείου δρόσου σε SQLite
* Γραφήματα στην εφαρμογή + web εφαρμογή για κινητό (τοπικά & Tailscale)
* Αποθήκευση CSV + XML (ημερήσια αρχεία & εξαγωγή κατ' επιλογή)
* Email: ημερήσια αναφορά με συνημμένα CSV/XML + ειδοποιήσεις ορίων

Developer : Nikolaos K. Paridis (aka nikkpap) — ALU DEV TEAM
"""
APP_NAME = "AirSense"
OLD_APP_NAMES = ("ALU HygroLink", "ALU AirSense")   # παλιά ονόματα (μεταφορά δεδομένων/ρυθμίσεων)
OLD_APP_NAME = OLD_APP_NAMES[0]
APP_VERSION = "1.6.22"
AUTHOR = "Nikolaos K. Paridis (aka nikkpap)"
TEAM = "ALU DEV TEAM"

import os
import re
import sys
import time
import subprocess
import importlib
import importlib.util

# ═══════════════════════════════════════════════════════════════════════════
# 1) Αυτόματη εγκατάσταση βιβλιοθηκών (πρώτη εκκίνηση)
# ═══════════════════════════════════════════════════════════════════════════
REQUIRED = [("PyQt6", "PyQt6"), ("pyqtgraph", "pyqtgraph"), ("numpy", "numpy"), ("qrcode", "qrcode"),
            ("reportlab", "reportlab")]


LOG_FILE = os.path.join(os.environ.get("TEMP") or os.path.expanduser("~"), "AirSense_log.txt")


for _st in (sys.stdout, sys.stderr):          # console in UTF-8 (Greek instead of ������)
    try:
        _st.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _log(msg):
    try:
        new = not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0
        with open(LOG_FILE, "a", encoding="utf-8-sig" if new else "utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass
    try:
        print(msg, flush=True)
    except Exception:
        pass


def _popup(msg, error=True):
    try:
        import tkinter as tk
        from tkinter import messagebox
        rt = tk.Tk()
        rt.withdraw()
        (messagebox.showerror if error else messagebox.showinfo)(APP_NAME, msg)
        rt.destroy()
    except Exception:
        print(msg)


def _probe_python(exe):
    """→ (bits, major, minor, has_pyqt6) ή None."""
    code = ("import struct,sys,importlib.util as u;"
            "print(struct.calcsize('P')*8,sys.version_info[0],sys.version_info[1],int(u.find_spec('PyQt6') is not None))")
    try:
        r = subprocess.run([exe, "-c", code], capture_output=True, text=True, timeout=20,
                           creationflags=0x08000000 if os.name == "nt" else 0)
        b, ma, mi, q = r.stdout.split()
        return int(b), int(ma), int(mi), q == "1"
    except Exception:
        return None


def _find_better_python():
    """Βρίσκει εγκατεστημένη Python 64-bit (3.9–3.14) για αυτόματη επανεκκίνηση."""
    cands = []
    try:
        r = subprocess.run(["py", "-0p"], capture_output=True, text=True, timeout=20, creationflags=0x08000000)
        cands += re.findall(r"([A-Za-z]:\\[^\r\n*]*?python(?:w)?\.exe)", r.stdout + r.stderr, re.I)
    except Exception:
        pass
    for d in (os.environ.get("PATH") or "").split(os.pathsep):
        exe = os.path.join(d.strip('"'), "python.exe")
        if os.path.isfile(exe) and "WindowsApps" not in exe:
            cands.append(exe)
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python")
    if os.path.isdir(base):
        for n in os.listdir(base):
            cands.append(os.path.join(base, n, "python.exe"))
    best = None
    me = os.path.normcase(os.path.abspath(sys.executable))
    for exe in dict.fromkeys(os.path.normcase(os.path.abspath(c.strip())) for c in cands):
        if exe == me or not os.path.isfile(exe):
            continue
        info = _probe_python(exe)
        if not info:
            continue
        bits, ma, mi, has_qt = info
        if bits != 64 or ma != 3 or not (9 <= mi <= 14):
            continue
        score = (has_qt, mi)
        if best is None or score > best[0]:
            best = (score, exe, f"{ma}.{mi}")
    return (best[1], best[2]) if best else (None, None)


def _relaunch(exe, ver):
    w = exe[:-len("python.exe")] + "pythonw.exe" if exe.lower().endswith("python.exe") else exe
    if os.path.isfile(w):
        exe = w
    _log(f"Επανεκκίνηση με Python {ver}: {exe}")
    env = dict(os.environ, HYGROLINK_RELAUNCHED="1")
    subprocess.Popen([exe, os.path.abspath(sys.argv[0])] + sys.argv[1:], env=env, close_fds=True)
    sys.exit(0)


def _ensure_deps():
    import struct
    missing = [pip for mod, pip in REQUIRED if importlib.util.find_spec(mod) is None]
    if not missing:
        return
    bits = struct.calcsize("P") * 8
    _log(f"Python {sys.version.split()[0]} {bits}-bit ({sys.executable}) — λείπουν: {', '.join(missing)}")
    relaunched = os.environ.get("HYGROLINK_RELAUNCHED") == "1"
    unsupported = bits != 64 or sys.version_info >= (3, 15) or sys.version_info < (3, 9)
    if unsupported and not relaunched and os.name == "nt":
        exe, ver = _find_better_python()
        if exe:
            _relaunch(exe, ver)
        if bits != 64:
            _popup(f"Αυτή η Python είναι 32-bit ({sys.version.split()[0]}) και το PyQt6 δεν υποστηρίζεται.\n\n"
                   "Εγκαταστήστε Python 3.13 64-bit από python.org (Windows installer 64-bit) "
                   "και ξανανοίξτε την εφαρμογή — θα τη βρει αυτόματα.")
            webbrowser_open("https://www.python.org/downloads/windows/")
            sys.exit(1)
    py = sys.executable
    if py.lower().endswith("pythonw.exe"):
        cand = py[: -len("pythonw.exe")] + "python.exe"
        if os.path.exists(cand):
            py = cand
    win = None
    try:
        import tkinter as tk
        win = tk.Tk()
        win.title(APP_NAME)
        win.geometry("480x140")
        tk.Label(win, text="Πρώτη εκκίνηση — εγκατάσταση βιβλιοθηκών…\n\n" + ", ".join(missing)
                 + "\n\nΠαρακαλώ περιμένετε (1–3 λεπτά).", padx=20, pady=15).pack()
        win.update()
    except Exception:
        win = None
    flags = 0x08000000 if os.name == "nt" else 0
    base = [py, "-m", "pip", "install", "--upgrade", "--disable-pip-version-check", "--only-binary=:all:"]
    ok, last = False, ""
    for extra in ([], ["--user"], ["--break-system-packages"], ["--user", "--break-system-packages"]):
        try:
            r = subprocess.run(base + extra + missing, capture_output=True, text=True, creationflags=flags, timeout=900)
            last = (r.stdout or "")[-1500:] + (r.stderr or "")[-1500:]
            if r.returncode == 0:
                ok = True
                break
        except Exception as e:
            last = str(e)
    if win:
        try:
            win.destroy()
        except Exception:
            pass
    importlib.invalidate_caches()
    if not ok:
        _log("pip απέτυχε:\n" + last)
        try:
            import site
            importlib.reload(site)
        except Exception:
            pass
        still = [pip for mod, pip in REQUIRED if importlib.util.find_spec(mod) is None]
        if still:
            if not relaunched and os.name == "nt":
                exe, ver = _find_better_python()
                if exe:
                    _relaunch(exe, ver)
            tail = "\n".join(last.strip().splitlines()[-6:])
            _popup("Δεν ήταν δυνατή η αυτόματη εγκατάσταση:\n" + ", ".join(still) +
                   f"\n\nPython: {sys.version.split()[0]} ({sys.executable})\n\n{tail}\n\n"
                   f"Λεπτομέρειες: {LOG_FILE}")
            sys.exit(1)


def webbrowser_open(url):
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass


CLI_FLAGS = ("--headless", "--set-admin", "--set-pin", "--status", "--add", "--scan", "--locate", "--help-cli")
HEADLESS = any(a in sys.argv for a in CLI_FLAGS) or (
    os.name != "nt" and sys.platform != "darwin" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"))
if not HEADLESS:
    _ensure_deps()   # ο headless server (π.χ. Raspberry Pi) χρειάζεται μόνο Python — καμία εξωτερική βιβλιοθήκη

# ═══════════════════════════════════════════════════════════════════════════
# 2) Imports
# ═══════════════════════════════════════════════════════════════════════════
import base64
import bisect
import calendar
import csv
import hmac
import io
import ipaddress
import json
import math
import re
import shutil
import smtplib
import socket
import sqlite3
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ═══════════════════════════════════════════════════════════════════════════
# 3) Διαδρομές / ρυθμίσεις
# ═══════════════════════════════════════════════════════════════════════════
def _docs_dir():
    home = os.path.expanduser("~")
    d = os.path.join(home, "Documents")
    return d if os.path.isdir(d) else home


def _arg_value(flag):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return None


def _migrate_old_data():
    """Μεταφορά από ALU HygroLink → AirSense: φάκελος δεδομένων + βάση (μία φορά, χωρίς απώλειες)."""
    new_d = os.path.join(_docs_dir(), APP_NAME)
    old_d = next((os.path.join(_docs_dir(), n) for n in reversed(OLD_APP_NAMES)
                  if os.path.isdir(os.path.join(_docs_dir(), n))), "")
    if not os.path.exists(new_d) and old_d:
        try:
            os.rename(old_d, new_d)
        except Exception:
            try:
                import shutil
                shutil.copytree(old_d, new_d)
            except Exception:
                return old_d                      # αποτυχία → συνεχίζει με τον παλιό φάκελο
    return new_d


DATA_DIR = (_arg_value("--data") or os.environ.get("AIRSENSE_DATA") or os.environ.get("HYGROLINK_DATA")
            or (None if "--help-cli" in sys.argv else _migrate_old_data()) or os.path.join(_docs_dir(), APP_NAME))
DAILY_DIR = os.path.join(DATA_DIR, "daily")
EXPORT_DIR = os.path.join(DATA_DIR, "exports")
CFG_PATH = os.path.join(DATA_DIR, "config.json")
DB_PATH = os.path.join(DATA_DIR, "airsense.db")
if not os.path.exists(DB_PATH) and os.path.exists(os.path.join(DATA_DIR, "hygrolink.db")):
    try:   # παλιά βάση ALU HygroLink (μαζί με τα -wal/-shm)
        for _ext in ("", "-wal", "-shm"):
            if os.path.exists(os.path.join(DATA_DIR, "hygrolink.db" + _ext)):
                os.rename(os.path.join(DATA_DIR, "hygrolink.db" + _ext), DB_PATH + _ext)
    except Exception:
        DB_PATH = os.path.join(DATA_DIR, "hygrolink.db")

DEFAULT_CFG = {
    "devices": [],                       # [{id,name,ip,type,product,fv,apiLevel,enabled}]
    "poll_seconds": 60,
    "subnets": "",                       # επιπλέον δίκτυα π.χ. "192.168.2.0/24"
    "auto_add_sensors": True,
    "server": {"enabled": True, "port": 8765, "pin": ""},
    "email": {
        "enabled": False, "host": "smtp.gmail.com", "port": 587, "security": "STARTTLS",
        "user": "", "password": "", "sender": "", "to": "",
        "daily_report": True, "report_time": "08:00", "alarm_mails": True, "attach_pdf": True,
    },
    "alarms": {
        "enabled": False, "temp_min": 5.0, "temp_max": 35.0, "hum_min": 20.0, "hum_max": 80.0,
        "offline": True, "cooldown_min": 60,
    },
    "export": {"greek_excel": True, "daily_files": True},
    "ui": {"minimize_to_tray": True, "start_minimized": False, "tray_hint_shown": False, "theme": "auto"},
    "last_report_date": "",
    "labels": {"inside": "Μέσα", "outside": "Έξω"},
    "weather": {"enabled": False, "lat": None, "lon": None, "place": "", "interval_min": 15, "auto": False,
                "auto_tried": False},
}

SENSOR_TYPES = {"humiditysensor", "multisensor", "tempsensor"}
SENSOR_PATHS = ["/state/extended", "/state", "/api/tempsensor/state", "/api/multisensor/state"]


def ensure_dirs():
    for d in (DATA_DIR, DAILY_DIR, EXPORT_DIR):
        os.makedirs(d, exist_ok=True)


def _merge(dst, src):
    for k, v in src.items():
        if k in dst and isinstance(dst[k], dict) and isinstance(v, dict):
            _merge(dst[k], v)
        else:
            dst[k] = v
    return dst


def load_cfg():
    cfg = json.loads(json.dumps(DEFAULT_CFG))
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            _merge(cfg, json.load(f))
    except Exception:
        pass
    return cfg


# ── Προστασία κωδικού email (Windows DPAPI, αλλιώς base64) ─────────────────
def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes
    import ctypes.wintypes as wt

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    inb = BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    if not fn(ctypes.byref(inb), None, None, None, None, 0, ctypes.byref(out)):
        raise OSError("DPAPI failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def enc_secret(s: str) -> str:
    if not s:
        return ""
    if os.name == "nt":
        try:
            return "dpapi:" + base64.b64encode(_dpapi(s.encode("utf-8"), True)).decode()
        except Exception:
            pass
    return "b64:" + base64.b64encode(s.encode("utf-8")).decode()


def dec_secret(s: str) -> str:
    if not s:
        return ""
    try:
        if s.startswith("dpapi:"):
            return _dpapi(base64.b64decode(s[6:]), False).decode("utf-8")
        if s.startswith("b64:"):
            return base64.b64decode(s[4:]).decode("utf-8")
    except Exception:
        return ""
    return s


# ═══════════════════════════════════════════════════════════════════════════
# 4) BleBox API
# ═══════════════════════════════════════════════════════════════════════════
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # χωρίς proxy στο LAN


def parse_host(addr: str):
    addr = addr.strip().replace("http://", "").replace("https://", "").strip("/")
    if ":" in addr:
        h, p = addr.rsplit(":", 1)
        try:
            return h, int(p)
        except ValueError:
            return addr, 80
    return addr, 80


def http_json(addr, path, timeout=3.0, method="GET", body=None):
    host, port = parse_host(addr)
    url = f"http://{host}:{port}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", "User-Agent": APP_NAME})
    with _OPENER.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace") or "{}")


def blebox_info(addr, timeout=2.5):
    """Επιστρέφει dict 'device' (deviceName, type, product, id, fv, apiLevel) ή None."""
    for p in ("/info", "/api/device/state"):
        try:
            js = http_json(addr, p, timeout)
        except Exception:
            continue
        dev = js.get("device") if isinstance(js, dict) else None
        if isinstance(dev, dict) and ("type" in dev or "id" in dev):
            return dev
    return None


def _collect_sensors(js, out):
    if isinstance(js, dict):
        t, v = js.get("type"), js.get("value")
        if isinstance(t, str) and isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append(js)
        for vv in js.values():
            if isinstance(vv, (dict, list)):
                _collect_sensors(vv, out)
    elif isinstance(js, list):
        for i in js:
            _collect_sensors(i, out)


def dew_point(t, rh):
    if t is None or rh is None or rh <= 0:
        return None
    a, b = 17.62, 243.12
    g = math.log(rh / 100.0) + a * t / (b + t)
    return round(b * g / (a - g), 2)


def abs_humidity(t, rh):
    if t is None or rh is None:
        return None
    return round(6.112 * math.exp(17.67 * t / (t + 243.5)) * rh * 2.1674 / (273.15 + t), 2)


DEFAULT_LABELS = {"inside": "Μέσα", "outside": "Έξω"}


def labels(cfg):
    """Τα λεκτικά «Μέσα» / «Έξω» όπως τα όρισε ο χρήστης στις Ρυθμίσεις."""
    lb = dict(DEFAULT_LABELS)
    for k, v in (cfg.get("labels") or {}).items():
        if k in lb and str(v).strip():
            lb[k] = str(v).strip()[:30]
    return lb


def inout_diff(t_in, h_in, t_out, h_out, lb=None):
    """Διαφορά μέσα–έξω + τι θα γίνει αν αεριστεί ο χώρος (με βάση την απόλυτη υγρασία)."""
    lb = lb or DEFAULT_LABELS
    li, lo = lb["inside"], lb["outside"]
    if None in (t_in, h_in, t_out, h_out):
        return None
    ah_in, ah_out = abs_humidity(t_in, h_in), abs_humidity(t_out, h_out)
    d = {"dt": round(t_in - t_out, 1), "dh": round(h_in - h_out, 1), "ah_in": ah_in, "ah_out": ah_out,
         "dah": round(ah_in - ah_out, 2)}
    if abs(d["dah"]) < 0.5:
        d["vent"], d["vent_txt"] = 0, "Ο αερισμός δεν αλλάζει σχεδόν την υγρασία"
    elif d["dah"] > 0:
        d["vent"], d["vent_txt"] = 1, f"Ο αερισμός θα ΜΕΙΩΣΕΙ την υγρασία ({li}) — ο αέρας ({lo}) είναι πιο ξερός"
    else:
        d["vent"], d["vent_txt"] = -1, f"Ο αερισμός θα ΑΥΞΗΣΕΙ την υγρασία ({li}) — ο αέρας ({lo}) έχει περισσότερο νερό"
    return d


def parse_sensors(js):
    items = []
    _collect_sensors(js, items)
    t = h = None
    extra = {}

    def sid(s):
        return s.get("id") if isinstance(s.get("id"), int) else 0

    for s in sorted(items, key=sid):
        typ = str(s.get("type", "")).lower()
        raw = s.get("value")
        if typ in ("temperature", "temp"):
            v = raw if (isinstance(raw, float) and not raw.is_integer()) else raw / 100.0
            if t is None and -60 <= v <= 150:
                t = round(v, 2)
        elif typ in ("humidity", "hum", "relativehumidity"):
            if isinstance(raw, float) and not raw.is_integer():
                v = raw
            else:
                v = raw / 100.0 if raw > 100 else float(raw)
            if h is None and 0 <= v <= 100:
                h = round(v, 2)
        else:
            extra[typ] = raw
    return {"t": t, "h": h, "dp": dew_point(t, h), "ah": abs_humidity(t, h), "extra": extra}


def read_sensors(addr, cache, timeout=4.0):
    paths = list(SENSOR_PATHS)
    if cache.get(addr) in paths:
        paths.remove(cache[addr])
        paths.insert(0, cache[addr])
    last = None
    for p in paths:
        try:
            js = http_json(addr, p, timeout)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code} στο {p}"
            continue
        except Exception as e:
            last = f"Χωρίς απόκριση ({e.__class__.__name__})"
            break
        r = parse_sensors(js)
        if r["t"] is not None or r["h"] is not None:
            cache[addr] = p
            return r
        last = f"Δεν βρέθηκαν μετρήσεις στο {p}"
    raise RuntimeError(last or "Αποτυχία ανάγνωσης")


# ═══════════════════════════════════════════════════════════════════════════
# 5) Δίκτυο: σάρωση LAN, WiFi, Tailscale
# ═══════════════════════════════════════════════════════════════════════════
TS_NET = ipaddress.ip_network("100.64.0.0/10")


def local_ipv4s():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except Exception:
        pass
    return sorted(i for i in ips if not i.startswith("127.") and not i.startswith("169.254."))


def lan_ipv4s():
    return [i for i in local_ipv4s() if ipaddress.ip_address(i) not in TS_NET]


def build_networks(extra_text=""):
    nets = []
    for ip in lan_ipv4s():
        n = ipaddress.ip_network(ip + "/24", strict=False)
        if n not in nets:
            nets.append(n)
    for part in re.split(r"[,\s;]+", extra_text or ""):
        part = part.strip()
        if not part:
            continue
        try:
            if "/" not in part:
                part += "/24"
            n = ipaddress.ip_network(part, strict=False)
            if n.prefixlen < 22:
                n = ipaddress.ip_network(f"{n.network_address}/22", strict=False)
            if n not in nets:
                nets.append(n)
        except ValueError:
            pass
    return nets


def probe_host(h):
    try:
        with socket.create_connection((h, 80), timeout=0.6):
            pass
    except Exception:
        return None
    dev = blebox_info(h, 2.5)
    if dev:
        return {"ip": h, "blebox": True, "mac": "", "id": str(dev.get("id", "")), "name": dev.get("deviceName", ""),
                "type": dev.get("type", ""), "product": dev.get("product", ""),
                "fv": dev.get("fv", ""), "apiLevel": str(dev.get("apiLevel", ""))}
    name = ""
    try:
        name = socket.gethostbyaddr(h)[0]
    except Exception:
        pass
    return {"ip": h, "blebox": False, "mac": "", "id": "", "name": name, "type": "HTTP (όχι BleBox)",
            "product": "", "fv": "", "apiLevel": ""}


NOWIN = 0x08000000 if os.name == "nt" else 0
BLEBOX_SSID_RE = re.compile(r"(humiditysensor|tempsensor|multisensor|airsensor|blebox|switchbox|shutterbox|"
                            r"wlightbox|dimmerbox|gatebox|saunabox|thermobox|floodsensor|rainsensor|windsensor|luxsensor)", re.I)
SSID_ID_RE = re.compile(r"[-_]([0-9a-f]{12})$", re.I)


def _run(cmd, timeout=15):
    """Εκτέλεση εντολής συστήματος → (returncode, κείμενο)."""
    r = subprocess.run(cmd, capture_output=True, creationflags=NOWIN, timeout=timeout)
    raw = (r.stdout or b"") + (r.stderr or b"")
    for enc in (["oem", "utf-8"] if os.name == "nt" else ["utf-8"]):
        try:
            return r.returncode, raw.decode(enc, "replace")
        except LookupError:
            continue
    return r.returncode, raw.decode("utf-8", "replace")


def _wlan_force_scan():
    """Ζητά από τα Windows νέα (φρέσκια) σάρωση WiFi μέσω wlanapi."""
    if os.name != "nt":
        return
    try:
        import ctypes
        import ctypes.wintypes as wt
        wl = ctypes.windll.wlanapi
        h, ver = wt.HANDLE(), wt.DWORD()
        if wl.WlanOpenHandle(2, None, ctypes.byref(ver), ctypes.byref(h)) != 0:
            return
        lst = ctypes.c_void_p()
        try:
            if wl.WlanEnumInterfaces(h, None, ctypes.byref(lst)) == 0 and lst.value:
                n = ctypes.c_uint32.from_address(lst.value).value
                for i in range(n):  # WLAN_INTERFACE_INFO = GUID(16)+WCHAR[256](512)+state(4)
                    wl.WlanScan(h, ctypes.c_void_p(lst.value + 8 + i * 532), None, None, None)
                wl.WlanFreeMemory(lst)
        finally:
            wl.WlanCloseHandle(h, None)
    except Exception:
        pass


def wifi_scan(force=True):
    """Σάρωση WiFi → (rows, error). Αν δεν φανεί BleBox, ξαναδοκιμάζει μία φορά."""
    rows, err = _wifi_scan_once(force)
    if force and not err and not any(r["blebox"] for r in rows):
        rows2, err2 = _wifi_scan_once(True)
        if len(rows2) >= len(rows):
            rows, err = rows2, err2
    return rows, err


def _wifi_scan_once(force=True):
    if force:
        _wlan_force_scan()
        time.sleep(3.5)
    rows, err = [], ""
    try:
        if os.name == "nt":
            rc, out = _run(["netsh", "wlan", "show", "networks", "mode=bssid"])
            base = cur = None
            for line in out.splitlines():
                ls = line.strip()
                m = re.match(r"^SSID\s+\d+\s*:\s*(.*)$", ls)
                if m:
                    base = {"ssid": m.group(1).strip() or "(κρυφό)", "auth": "", "enc": ""}
                    cur = None
                    continue
                if base is None or ":" not in ls:
                    continue
                m = re.match(r"^BSSID\s+\d+\s*:\s*((?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2})", ls)
                if m:
                    cur = dict(base, bssid=m.group(1).upper().replace("-", ":"), signal=0, radio="", band="", channel="")
                    rows.append(cur)
                    continue
                key, val = [x.strip() for x in ls.split(":", 1)]
                kl = key.lower()
                if cur is None:
                    if "authentication" in kl or "ταυτότητ" in kl:
                        base["auth"] = val
                    elif "encryption" in kl or "κρυπτογρ" in kl:
                        base["enc"] = val
                    continue
                if re.fullmatch(r"\d+\s*%", val):
                    cur["signal"] = int(val.rstrip("% "))
                elif "802.11" in val:
                    cur["radio"] = val
                elif "ghz" in val.lower():
                    cur["band"] = val
                elif ("channel" in kl or "κανάλι" in kl) and val.isdigit():
                    cur["channel"] = val
            if not rows:
                low = out.lower()
                if "location" in low or "τοποθεσ" in low:
                    err = "LOCATION"
                elif "wlansvc" in low or "not running" in low or "δεν εκτελείται" in low or "no wireless" in low:
                    err = "Δεν βρέθηκε κάρτα WiFi ή η υπηρεσία WLAN AutoConfig δεν τρέχει."
                elif rc != 0:
                    err = out.strip()[:300]
        else:
            rc, out = _run(["nmcli", "-t", "-f", "SSID,BSSID,SIGNAL,CHAN,FREQ,SECURITY", "dev", "wifi", "list",
                            "--rescan", "yes" if force else "no"], 30)
            for line in out.splitlines():
                p = [x.replace("\\:", ":") for x in re.split(r"(?<!\\):", line)]
                if len(p) >= 6:
                    rows.append({"ssid": p[0] or "(κρυφό)", "bssid": p[1].upper(), "signal": int(p[2] or 0),
                                 "channel": p[3], "band": ("5 GHz" if p[4].startswith("5") else "2.4 GHz"),
                                 "radio": "", "auth": p[5] or "Open", "enc": ""})
            if not rows and rc != 0:
                err = out.strip()[:300]
    except Exception as e:
        err = str(e)
    for r in rows:
        s = r["ssid"]
        r["blebox"] = bool(BLEBOX_SSID_RE.search(s))
        m = SSID_ID_RE.search(s)
        r["dev_id"] = m.group(1).lower() if m else ""
        r["model"] = re.split(r"[-]", s)[0] if r["blebox"] else ""
        a, e = r.get("auth", "").lower(), r.get("enc", "").lower()
        r["open"] = a in ("open", "ανοιχτό", "ανοικτό", "") and e in ("none", "κανένα", "καμία", "")
        if not r["band"] and r["channel"].isdigit():
            r["band"] = "2.4 GHz" if int(r["channel"]) <= 14 else "5 GHz"
    rows.sort(key=lambda r: (not r["blebox"], -r["signal"]))
    return rows, err


def wifi_current():
    """Τρέχον WiFi του υπολογιστή → {ssid, profile, bssid}."""
    info = {"ssid": "", "profile": "", "bssid": ""}
    try:
        if os.name == "nt":
            _, out = _run(["netsh", "wlan", "show", "interfaces"])
            for line in out.splitlines():
                if ":" not in line:
                    continue
                k, v = [x.strip() for x in line.split(":", 1)]
                kl = k.lower()
                if kl == "ssid":
                    info["ssid"] = v
                elif kl in ("profile", "προφίλ"):
                    info["profile"] = v
                elif kl in ("bssid", "ap bssid"):
                    info["bssid"] = v.upper()
        else:
            _, out = _run(["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"])
            for line in out.splitlines():
                if line.startswith("yes:"):
                    info["ssid"] = info["profile"] = line[4:]
    except Exception:
        pass
    return info


def _xml_esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def wifi_connect(ssid, password=""):
    """Σύνδεση του υπολογιστή σε WiFi (π.χ. το ανοιχτό WiFi του αισθητήρα)."""
    if os.name != "nt":
        rc, out = _run(["nmcli", "dev", "wifi", "connect", ssid] + (["password", password] if password else []), 45)
        return rc == 0, out
    import tempfile
    if password:
        sec = ("<authEncryption><authentication>WPA2PSK</authentication><encryption>AES</encryption>"
               "<useOneX>false</useOneX></authEncryption><sharedKey><keyType>passPhrase</keyType>"
               f"<protected>false</protected><keyMaterial>{_xml_esc(password)}</keyMaterial></sharedKey>")
    else:
        sec = ("<authEncryption><authentication>open</authentication><encryption>none</encryption>"
               "<useOneX>false</useOneX></authEncryption>")
    x = _xml_esc(ssid)
    xml = ('<?xml version="1.0"?><WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">'
           f"<name>{x}</name><SSIDConfig><SSID><name>{x}</name></SSID></SSIDConfig>"
           "<connectionType>ESS</connectionType><connectionMode>manual</connectionMode>"
           f"<MSM><security>{sec}</security></MSM></WLANProfile>")
    path = os.path.join(tempfile.gettempdir(), "airsense_wifi.xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)
    try:
        _run(f'netsh wlan add profile filename="{path}" user=current')
    finally:
        try:
            os.remove(path)
        except Exception:
            pass
    rc, out = _run(f'netsh wlan connect name="{ssid}" ssid="{ssid}"')
    return rc == 0, out


def wifi_reconnect(profile):
    if not profile:
        return False
    if os.name == "nt":
        return _run(f'netsh wlan connect name="{profile}"')[0] == 0
    return _run(["nmcli", "con", "up", "id", profile], 45)[0] == 0


def wifi_forget(ssid):
    if os.name == "nt" and ssid:
        _run(f'netsh wlan delete profile name="{ssid}"')


# ── Raspberry Pi: WiFi στην κάρτα SD (airsense-wifi.txt στο bootfs) ──
PI_BOOT_FILE = "airsense-wifi.txt"
PI_BOOT_LOG = "airsense-wifi-log.txt"
PI_BOOT_EXAMPLE = "airsense-wifi.example.txt"


def pi_boot_names(card):
    """Ονόματα αρχείων για την κάρτα: νέο (airsense-*) ή παλιό (hygrolink-*) αν το Pi έχει παλιό installer."""
    if (card and not os.path.exists(os.path.join(card, PI_BOOT_EXAMPLE))
            and os.path.exists(os.path.join(card, "hygrolink-wifi.example.txt"))):
        return "hygrolink-wifi.txt", "hygrolink-wifi-log.txt", "hygrolink-wifi.example.txt"
    return PI_BOOT_FILE, PI_BOOT_LOG, PI_BOOT_EXAMPLE


def is_pi_boot_dir(path):
    return os.path.isfile(os.path.join(path, "config.txt")) and os.path.isfile(os.path.join(path, "cmdline.txt"))


def find_pi_boot_drives():
    out = []
    if os.name == "nt":
        import string
        for L in string.ascii_uppercase:
            root = f"{L}:\\"
            try:
                if os.path.exists(root) and is_pi_boot_dir(root):
                    out.append(root)
            except OSError:
                pass
    else:
        for base in ("/media", "/run/media", "/Volumes"):
            if os.path.isdir(base):
                for dp, dirs, _ in os.walk(base):
                    if is_pi_boot_dir(dp):
                        out.append(dp)
                    if dp.count(os.sep) - base.count(os.sep) >= 2:
                        dirs[:] = []
    return out


def win_wifi_profiles():
    if os.name != "nt":
        return []
    _, out = _run(["netsh", "wlan", "show", "profiles"])
    names = []
    for line in out.splitlines():
        if ":" in line and ("profile" in line.lower() or "προφίλ" in line.lower()):
            v = line.split(":", 1)[1].strip()
            if v:
                names.append(v)
    return names


def win_wifi_password(name):
    if os.name != "nt" or not name:
        return ""
    _, out = _run(f'netsh wlan show profile name="{name}" key=clear')
    for line in out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip().lower()
            if k.startswith("key content") or k.startswith("περιεχόμενο κλειδιού") or k.startswith("περιεχόμενα κλειδιού"):
                return v.strip()
    return ""


def build_pi_wifi_file(nets):
    lines = [f"# AirSense — WiFi για το Raspberry Pi (από {APP_NAME} v{APP_VERSION})",
             "# Το Pi το διαβάζει στην εκκίνηση· μετά ο κωδικός σβήνεται από την κάρτα.", ""]
    for i, n in enumerate(nets, 1):
        sec = re.sub(r"[\[\]]", "", n["ssid"]) or f"WiFi {i}"
        lines += [f"[{i}. {sec}]", f"ssid = {n['ssid']}", f"password = {n['password']}",
                  f"priority = {n['priority']}", f"hidden = {'yes' if n['hidden'] else 'no'}", ""]
    return "\r\n".join(lines)


def arp_table():
    """IP → MAC από τον πίνακα ARP του υπολογιστή."""
    m = {}
    try:
        _, out = _run(["arp", "-a"] if os.name == "nt" else ["ip", "neigh"], 10)
        for line in out.splitlines():
            mm = re.search(r"(\d+\.\d+\.\d+\.\d+)\D+?((?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2})", line)
            if mm:
                mac = mm.group(2).upper().replace("-", ":")
                if mac not in ("FF:FF:FF:FF:FF:FF",) and not mac.startswith("01:00:5E"):
                    m[mm.group(1)] = mac
    except Exception:
        pass
    return m


def tailscale_info():
    exe = shutil.which("tailscale")
    if not exe and os.name == "nt":
        for c in (r"C:\Program Files\Tailscale\tailscale.exe", r"C:\Program Files (x86)\Tailscale\tailscale.exe"):
            if os.path.exists(c):
                exe = c
                break
    ip = dns = None
    state = ""
    if exe:
        try:
            r = subprocess.run([exe, "status", "--json"], capture_output=True, text=True, timeout=5,
                               creationflags=0x08000000 if os.name == "nt" else 0)
            js = json.loads(r.stdout or "{}")
            state = js.get("BackendState") or ""
            me = js.get("Self") or {}
            for x in me.get("TailscaleIPs") or []:
                if "." in x:
                    ip = x
                    break
            dns = (me.get("DNSName") or "").rstrip(".") or None
        except Exception:
            pass
    if not ip:
        for x in local_ipv4s():
            if ipaddress.ip_address(x) in TS_NET:
                ip = x
                break
    return {"installed": bool(exe) or ip is not None, "ip": ip, "dns": dns, "state": state, "exe": exe}


def tailscale_login(exe):
    """Σύνδεση Tailscale: «up» (αν είναι σταματημένο) ή login → επιστρέφει URL σύνδεσης (αν χρειάζεται)."""
    if not exe:
        raise RuntimeError("Το Tailscale δεν είναι εγκατεστημένο")
    flags = 0x08000000 if os.name == "nt" else 0
    p = subprocess.Popen([exe, "up"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         creationflags=flags, errors="replace")
    url, lines, t_end = None, [], time.time() + 25
    while time.time() < t_end:
        line = p.stdout.readline()
        if not line:
            if p.poll() is not None:
                break
            continue
        lines.append(line.strip())
        m = re.search(r"https://login\.tailscale\.com/\S+", line)
        if m:
            url = m.group(0)
            break
    if url:
        return url, "Άνοιξε η σελίδα σύνδεσης Tailscale στον browser"
    if p.poll() is None:
        return None, "Η σύνδεση συνεχίζεται…"
    if p.returncode == 0:
        return None, "Το Tailscale συνδέθηκε"
    raise RuntimeError(" ".join(lines[-3:]) or f"tailscale up: κωδικός {p.returncode}")


# ═══════════════════════════════════════════════════════════════════════════
# 5b) Open-Meteo — εξωτερικός καιρός
# ═══════════════════════════════════════════════════════════════════════════
OM_FORECAST = "https://api.open-meteo.com/v1/forecast"
OM_GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
OM_CURRENT = ("temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,rain,showers,snowfall,"
              "weather_code,cloud_cover,pressure_msl,wind_speed_10m,wind_direction_10m,wind_gusts_10m")
OM_HOURLY = ("temperature_2m,relative_humidity_2m,precipitation,rain,snowfall,weather_code,cloud_cover,"
             "sunshine_duration,is_day,wind_speed_10m")
OM_DAILY = ("weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,rain_sum,snowfall_sum,"
            "sunshine_duration,sunrise,sunset,precipitation_probability_max,wind_speed_10m_max,uv_index_max")
WMO = {0: ("☀️", "Αίθριος"), 1: ("🌤", "Κυρίως αίθριος"), 2: ("⛅", "Μερική νέφωση"), 3: ("☁️", "Συννεφιά"),
       45: ("🌫", "Ομίχλη"), 48: ("🌫", "Παγωμένη ομίχλη"), 51: ("🌦", "Ελαφρύ ψιχάλισμα"), 53: ("🌦", "Ψιχάλισμα"),
       55: ("🌧", "Πυκνό ψιχάλισμα"), 56: ("🌧", "Παγωμένο ψιχάλισμα"), 57: ("🌧", "Πυκνό παγωμένο ψιχάλισμα"),
       61: ("🌦", "Ελαφριά βροχή"), 63: ("🌧", "Βροχή"), 65: ("🌧", "Δυνατή βροχή"), 66: ("🌧", "Παγωμένη βροχή"),
       67: ("🌧", "Δυνατή παγωμένη βροχή"), 71: ("🌨", "Ελαφριά χιονόπτωση"), 73: ("🌨", "Χιονόπτωση"),
       75: ("❄️", "Πυκνή χιονόπτωση"), 77: ("🌨", "Χιονόκοκκοι"), 80: ("🌦", "Ελαφριές μπόρες"), 81: ("🌧", "Μπόρες"),
       82: ("⛈", "Ισχυρές μπόρες"), 85: ("🌨", "Ελαφριές χιονοπτώσεις"), 86: ("❄️", "Ισχυρές χιονοπτώσεις"),
       95: ("⛈", "Καταιγίδα"), 96: ("⛈", "Καταιγίδα με χαλάζι"), 97: ("⛈", "Ισχυρή καταιγίδα"),
       99: ("⛈", "Καταιγίδα με ισχυρό χαλάζι")}
GR_DAYS = ["Δευ", "Τρί", "Τετ", "Πέμ", "Παρ", "Σάβ", "Κυρ"]
WX_KEYS = ("ts", "temp", "hum", "feels", "precip", "rain", "snow", "code", "cloud", "pressure", "wind", "gust",
           "sunshine", "is_day", "status")


def _web_json(url, params, timeout=20):
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def geocode(name, lang="el"):
    js = _web_json(OM_GEOCODE, {"name": name, "count": 10, "language": lang, "format": "json"})
    out = []
    for r in js.get("results") or []:
        label = ", ".join(x for x in (r.get("name"), r.get("admin2") or r.get("admin1"), r.get("country")) if x)
        out.append({"label": label, "lat": r["latitude"], "lon": r["longitude"], "elev": r.get("elevation")})
    return out


PS_LOCATE = r"""
Add-Type -AssemblyName System.Device
$w = New-Object System.Device.Location.GeoCoordinateWatcher('High')
$null = $w.TryStart($false, [TimeSpan]::FromSeconds(10))
$t = 0
while (($w.Status -ne 'Ready') -and ($w.Permission -ne 'Denied') -and ($t -lt 120)) { Start-Sleep -Milliseconds 100; $t++ }
$c = $w.Position.Location
$ic = [System.Globalization.CultureInfo]::InvariantCulture
if ($c.IsUnknown) { 'UNKNOWN ' + $w.Permission + ' ' + $w.Status } else { 'LOC;' + $c.Latitude.ToString($ic) + ';' + $c.Longitude.ToString($ic) + ';' + $c.HorizontalAccuracy.ToString($ic) }
$w.Stop()
"""


def locate_pc():
    """Τοποθεσία υπολογιστή: 1) Windows Location (WiFi/GPS)  2) IP (κατά προσέγγιση)."""
    errs = []
    if os.name == "nt":
        try:
            _, out = _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", PS_LOCATE], 30)
            m = re.search(r"LOC;(-?\d+(?:\.\d+)?);(-?\d+(?:\.\d+)?);([\d.]+|NaN)", out)
            if m:
                acc = None if m.group(3) == "NaN" else float(m.group(3))
                return {"lat": float(m.group(1)), "lon": float(m.group(2)), "accuracy": acc,
                        "source": "Windows τοποθεσία (WiFi/GPS)"}
            errs.append("Windows: " + (out.strip().splitlines() or ["—"])[-1][:120])
        except Exception as e:
            errs.append(f"Windows: {e}")
    try:
        js = _web_json("http://ip-api.com/json/", {"fields": "status,message,lat,lon,city,regionName,country", "lang": "el"})
        if js.get("status") == "success":
            label = ", ".join(x for x in (js.get("city"), js.get("regionName"), js.get("country")) if x)
            return {"lat": float(js["lat"]), "lon": float(js["lon"]), "accuracy": None, "label": label,
                    "source": "Διεύθυνση IP (κατά προσέγγιση)"}
        errs.append("IP: " + str(js.get("message", "")))
    except Exception as e:
        errs.append(f"IP: {e}")
    raise RuntimeError("Δεν βρέθηκε τοποθεσία — " + " · ".join(errs))


def reverse_name(lat, lon):
    try:
        js = _web_json("https://nominatim.openstreetmap.org/reverse",
                       {"format": "jsonv2", "lat": lat, "lon": lon, "zoom": 12, "accept-language": "el"}, 15)
        a = js.get("address") or {}
        name = a.get("village") or a.get("town") or a.get("city") or a.get("municipality") or js.get("name")
        region = a.get("state") or a.get("county") or a.get("region")
        label = ", ".join(x for x in (name, region, a.get("country")) if x)
        if label:
            return label
    except Exception:
        pass
    return f"{lat:.4f}, {lon:.4f}"


def _om_epoch(iso, off):
    return int(calendar.timegm(datetime.fromisoformat(iso).timetuple()) - off)


def wx_info(code, is_day=1):
    c = -1 if code is None else int(code)
    icon, txt = WMO.get(c, ("🌡", "—"))
    if c in (0, 1) and not is_day:
        icon = "🌙"
    return icon, txt


def wx_status(code, rain=0, snow=0, is_day=1):
    """Απλή κατάσταση για την καταγραφή: Καταιγίδα / Χιόνι / Βροχή / Ομίχλη / Συννεφιά / Ηλιοφάνεια / Νύχτα."""
    c = -1 if code is None else int(code)
    if c >= 95:
        return "Καταιγίδα"
    if (snow or 0) > 0 or c in (71, 73, 75, 77, 85, 86):
        return "Χιόνι"
    if (rain or 0) > 0 or 51 <= c <= 67 or 80 <= c <= 82:
        return "Βροχή"
    if c in (45, 48):
        return "Ομίχλη"
    if is_day == 0:
        return "Νύχτα"
    if c == 3:
        return "Συννεφιά"
    return "Ηλιοφάνεια"


def fetch_weather(lat, lon):
    js = _web_json(OM_FORECAST, {"latitude": lat, "longitude": lon, "current": OM_CURRENT, "hourly": OM_HOURLY,
                                 "daily": OM_DAILY, "timezone": "auto", "past_days": 1, "forecast_days": 7})
    off = int(js.get("utc_offset_seconds", 0))
    c = js.get("current") or {}
    cur = {"ts": _om_epoch(c["time"], off) if c.get("time") else int(time.time()),
           "temp": c.get("temperature_2m"), "hum": c.get("relative_humidity_2m"), "feels": c.get("apparent_temperature"),
           "is_day": c.get("is_day", 1), "precip": c.get("precipitation"),
           "rain": (c.get("rain") or 0) + (c.get("showers") or 0), "snow": c.get("snowfall"),
           "code": c.get("weather_code"), "cloud": c.get("cloud_cover"), "pressure": c.get("pressure_msl"),
           "wind": c.get("wind_speed_10m"), "wdir": c.get("wind_direction_10m"), "gust": c.get("wind_gusts_10m")}

    def col(block, key, i):
        arr = block.get(key) or []
        return arr[i] if i < len(arr) else None
    h = js.get("hourly") or {}
    hourly = []
    for i, t in enumerate(h.get("time") or []):
        x = {"ts": _om_epoch(t, off), "temp": col(h, "temperature_2m", i), "hum": col(h, "relative_humidity_2m", i),
             "precip": col(h, "precipitation", i), "rain": col(h, "rain", i), "snow": col(h, "snowfall", i),
             "code": col(h, "weather_code", i), "cloud": col(h, "cloud_cover", i),
             "sunshine": col(h, "sunshine_duration", i), "is_day": col(h, "is_day", i), "wind": col(h, "wind_speed_10m", i)}
        x["status"] = wx_status(x["code"], x["rain"], x["snow"], x["is_day"])
        hourly.append(x)
    now = time.time()
    past = [x for x in hourly if x["ts"] <= now]
    cur["sunshine"] = past[-1]["sunshine"] if past else None          # δευτερόλεπτα ηλιοφάνειας στην τρέχουσα ώρα
    d = js.get("daily") or {}
    daily = []
    for i, t in enumerate(d.get("time") or []):
        x = {"date": t, "code": col(d, "weather_code", i), "tmax": col(d, "temperature_2m_max", i),
             "tmin": col(d, "temperature_2m_min", i), "precip": col(d, "precipitation_sum", i),
             "rain": col(d, "rain_sum", i), "snow": col(d, "snowfall_sum", i), "sunshine": col(d, "sunshine_duration", i),
             "sunrise": col(d, "sunrise", i), "sunset": col(d, "sunset", i),
             "prob": col(d, "precipitation_probability_max", i), "wind": col(d, "wind_speed_10m_max", i),
             "uv": col(d, "uv_index_max", i)}
        x["icon"], x["text"] = wx_info(x["code"], 1)
        try:
            dd = datetime.strptime(t, "%Y-%m-%d").date()
            x["day"] = ("Σήμερα" if dd == datetime.now().date() else "Αύριο" if dd == datetime.now().date() + timedelta(days=1)
                        else f"{GR_DAYS[dd.weekday()]} {dd.day}/{dd.month}")
        except Exception:
            x["day"] = t
        daily.append(x)
    cur["icon"], cur["text"] = wx_info(cur["code"], cur["is_day"])
    cur["status"] = wx_status(cur["code"], cur["rain"], cur["snow"], cur["is_day"])
    return {"current": cur, "hourly": hourly, "daily": [x for x in daily if x["date"] >= datetime.now().strftime("%Y-%m-%d")]}


# ═══════════════════════════════════════════════════════════════════════════
# 6) Βάση δεδομένων
# ═══════════════════════════════════════════════════════════════════════════
class Store:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        with self._c() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""CREATE TABLE IF NOT EXISTS readings(
                ts INTEGER NOT NULL, device_id TEXT NOT NULL, name TEXT, ip TEXT,
                temperature REAL, humidity REAL, dew_point REAL, abs_humidity REAL)""")
            c.execute("CREATE INDEX IF NOT EXISTS ix_dev_ts ON readings(device_id, ts)")
            c.execute("""CREATE TABLE IF NOT EXISTS weather(
                ts INTEGER PRIMARY KEY, temp REAL, hum REAL, feels REAL, precip REAL, rain REAL, snow REAL,
                code INTEGER, cloud REAL, pressure REAL, wind REAL, gust REAL, sunshine REAL, is_day INTEGER, status TEXT)""")
            cols = [r[1] for r in c.execute("PRAGMA table_info(readings)")]
            for col in ("raw_t", "raw_h"):
                if col not in cols:
                    c.execute(f"ALTER TABLE readings ADD COLUMN {col} REAL")

    def _c(self):
        return sqlite3.connect(self.path, timeout=15)

    def insert(self, ts, did, name, ip, r):
        with self.lock, self._c() as c:
            c.execute("INSERT INTO readings(ts,device_id,name,ip,temperature,humidity,dew_point,abs_humidity,raw_t,raw_h)"
                      " VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (int(ts), did, name, ip, r["t"], r["h"], r["dp"], r["ah"], r.get("raw_t", r["t"]), r.get("raw_h", r["h"])))

    def history(self, did, t0, t1, max_points=900):
        bucket = max(1, int((t1 - t0) / max_points))
        with self._c() as c:
            return c.execute(
                """SELECT (ts/?)*? AS b, AVG(temperature), AVG(humidity), AVG(dew_point)
                   FROM readings WHERE device_id=? AND ts BETWEEN ? AND ? GROUP BY b ORDER BY b""",
                (bucket, bucket, did, int(t0), int(t1))).fetchall(), bucket

    def rows(self, dids, t0, t1):
        q = ("SELECT ts,device_id,name,ip,temperature,humidity,dew_point,abs_humidity,raw_t,raw_h "
             "FROM readings WHERE ts BETWEEN ? AND ?")
        args = [int(t0), int(t1)]
        if dids:
            q += " AND device_id IN (%s)" % ",".join("?" * len(dids))
            args += list(dids)
        q += " ORDER BY device_id, ts"
        with self._c() as c:
            return c.execute(q, args).fetchall()

    def stats(self, did, t0, t1):
        with self._c() as c:
            return c.execute(
                """SELECT COUNT(*), MIN(temperature), AVG(temperature), MAX(temperature),
                          MIN(humidity), AVG(humidity), MAX(humidity)
                   FROM readings WHERE device_id=? AND ts BETWEEN ? AND ?""",
                (did, int(t0), int(t1))).fetchone()

    def count(self):
        with self._c() as c:
            return c.execute("SELECT COUNT(*) FROM readings").fetchone()[0]

    def insert_weather(self, rows, replace=True):
        if not rows:
            return
        verb = "INSERT OR REPLACE" if replace else "INSERT OR IGNORE"
        with self.lock, self._c() as c:
            c.executemany(f"{verb} INTO weather({','.join(WX_KEYS)}) VALUES({','.join('?' * len(WX_KEYS))})",
                          [tuple(r.get(k) for k in WX_KEYS) for r in rows])

    def weather_rows(self, t0, t1):
        with self._c() as c:
            return c.execute(f"SELECT {','.join(WX_KEYS)} FROM weather WHERE ts BETWEEN ? AND ? ORDER BY ts",
                             (int(t0), int(t1))).fetchall()

    def weather_history(self, t0, t1, max_points=900):
        bucket = max(1, int((t1 - t0) / max_points))
        with self._c() as c:
            return c.execute("""SELECT (ts/?)*? AS b, AVG(temp), AVG(hum), MAX(precip), MAX(snow), MAX(code),
                                       AVG(sunshine), AVG(cloud), AVG(wind)
                                FROM weather WHERE ts BETWEEN ? AND ? GROUP BY b ORDER BY b""",
                             (bucket, bucket, int(t0), int(t1))).fetchall(), bucket

    def count_range(self, did, t0, t1):
        q, a = "SELECT COUNT(*) FROM readings WHERE ts BETWEEN ? AND ?", [int(t0), int(t1)]
        if did:
            q += " AND device_id=?"
            a.append(did)
        with self._c() as c:
            return c.execute(q, a).fetchone()[0]

    def recalibrate(self, did, t0, cal):
        """Ξαναϋπολογίζει τις τιμές από τις αρχικές (raw) με νέα βαθμονόμηση."""
        with self.lock, self._c() as c:
            rows = c.execute("SELECT rowid, COALESCE(raw_t, temperature), COALESCE(raw_h, humidity) FROM readings "
                             "WHERE device_id=? AND ts>=?", (did, int(t0))).fetchall()
            upd = []
            for rid, rt, rh in rows:
                t, h = calibrate_values(rt, rh, cal)
                upd.append((t, h, dew_point(t, h), abs_humidity(t, h), rt, rh, rid))
            c.executemany("UPDATE readings SET temperature=?, humidity=?, dew_point=?, abs_humidity=?, raw_t=?, raw_h=? "
                          "WHERE rowid=?", upd)
            return len(upd)

    def delete(self, did, t0, t1):
        q, a = "DELETE FROM readings WHERE ts BETWEEN ? AND ?", [int(t0), int(t1)]
        if did:
            q += " AND device_id=?"
            a.append(did)
        with self.lock, self._c() as c:
            return c.execute(q, a).rowcount


def calibrate_values(rt, rh, cal):
    t = None if rt is None else round(rt * float(cal.get("t_mul", 1)) + float(cal.get("t_off", 0)), 2)
    h = None if rh is None else round(min(100.0, max(0.0, rh * float(cal.get("h_mul", 1)) + float(cal.get("h_off", 0)))), 2)
    return t, h


def _pw_hash(pw, salt=None):
    import hashlib
    import secrets
    salt = salt or secrets.token_hex(16)
    return salt, hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt), 200_000).hex()


# ═══════════════════════════════════════════════════════════════════════════
# 7) CSV / XML
# ═══════════════════════════════════════════════════════════════════════════
CSV_HEAD = ["Ημερομηνία/Ώρα", "Epoch", "ID συσκευής", "Όνομα", "IP",
            "Θερμοκρασία (°C)", "Υγρασία (%RH)", "Σημείο δρόσου (°C)", "Απόλυτη υγρασία (g/m³)",
            "Εξωτ. θερμοκρασία (°C)", "Εξωτ. υγρασία (%)", "Καιρός", "Κατάσταση", "Βροχή (mm)", "Χιόνι (cm)",
            "Νέφωση (%)", "Άνεμος (km/h)", "Ηλιοφάνεια (λεπτά/ώρα)"]


def _num(v, greek):
    if v is None:
        return ""
    s = f"{v:.2f}"
    return s.replace(".", ",") if greek else s


def _tstr(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def csv_row(row, greek, w=None):
    ts, did, name, ip, t, h, dp, ah = row[:8]
    out = [_tstr(ts), ts, did, name, ip, _num(t, greek), _num(h, greek), _num(dp, greek), _num(ah, greek)]
    if w:
        sun = None if w.get("sunshine") is None else w["sunshine"] / 60.0
        out += [_num(w.get("temp"), greek), _num(w.get("hum"), greek), wx_info(w.get("code"), w.get("is_day", 1))[1],
                w.get("status") or "", _num(w.get("rain") if w.get("rain") is not None else w.get("precip"), greek),
                _num(w.get("snow"), greek), _num(w.get("cloud"), greek), _num(w.get("wind"), greek), _num(sun, greek)]
    else:
        out += [""] * 9
    return out


def csv_bytes(rows, greek=True, wxf=None):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";" if greek else ",", lineterminator="\r\n")
    w.writerow(CSV_HEAD)
    for r in rows:
        w.writerow(csv_row(r, greek, wxf(r[0]) if wxf else None))
    return buf.getvalue().encode("utf-8-sig")


def xml_bytes(rows, t0=None, t1=None, wxf=None, place=None):
    root = ET.Element("AirSenseLog", {
        "app": APP_NAME, "version": APP_VERSION, "author": AUTHOR,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "from": datetime.fromtimestamp(t0).isoformat(timespec="seconds") if t0 else "",
        "to": datetime.fromtimestamp(t1).isoformat(timespec="seconds") if t1 else ""})
    if place and place.get("lat") is not None:
        ET.SubElement(root, "WeatherSource", {"provider": "Open-Meteo", "place": place.get("place", ""),
                                              "lat": str(place["lat"]), "lon": str(place["lon"])})
    devs = {}
    for row in rows:
        ts, did, name, ip, t, h, dp, ah = row[:8]
        rt, rh = (row[8], row[9]) if len(row) >= 10 else (None, None)
        d = devs.get(did)
        if d is None:
            d = devs[did] = ET.SubElement(root, "Device", {"id": did, "name": name or "", "ip": ip or ""})
        a = {"time": datetime.fromtimestamp(ts).isoformat(timespec="seconds"), "epoch": str(ts)}
        for k, v in (("temperature", t), ("humidity", h), ("dewPoint", dp), ("absHumidity", ah)):
            if v is not None:
                a[k] = f"{v:.2f}"
        for k, raw, v in (("sensorTemperature", rt, t), ("sensorHumidity", rh, h)):
            if raw is not None and v is not None and abs(raw - v) > 0.001:
                a[k] = f"{raw:.2f}"   # αρχική τιμή αισθητήρα πριν τη βαθμονόμηση
        w = wxf(ts) if wxf else None
        if w:
            a["weather"] = wx_info(w.get("code"), w.get("is_day", 1))[1]
            a["weatherStatus"] = w.get("status") or ""
            for k, v in (("outTemp", w.get("temp")), ("outHumidity", w.get("hum")), ("weatherCode", w.get("code")),
                         ("rainMm", w.get("rain")), ("snowCm", w.get("snow")), ("cloudPct", w.get("cloud")),
                         ("windKmh", w.get("wind")),
                         ("sunshineMinPerHour", None if w.get("sunshine") is None else w["sunshine"] / 60.0)):
                if v is not None:
                    a[k] = f"{v:.2f}" if isinstance(v, float) else str(v)
        ET.SubElement(d, "Reading", a)
    for did, d in devs.items():
        d.set("count", str(len(d)))
    ET.indent(root, space="  ")
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# 7b) Αναφορά PDF (reportlab — όμορφη αναφορά με κάρτες, γραφήματα και πίνακα ημερών)
# ═══════════════════════════════════════════════════════════════════════════
def _need_reportlab():
    """Φορτώνει το reportlab· αν λείπει (π.χ. headless/Pi), το εγκαθιστά μόνο του."""
    if importlib.util.find_spec("reportlab") is None:
        _log("Λείπει το reportlab — εγκατάσταση…")
        flags = 0x08000000 if os.name == "nt" else 0
        py = sys.executable
        if py.lower().endswith("pythonw.exe") and os.path.exists(py[:-len("pythonw.exe")] + "python.exe"):
            py = py[:-len("pythonw.exe")] + "python.exe"
        for extra in ([], ["--user"], ["--break-system-packages"], ["--user", "--break-system-packages"]):
            try:
                r = subprocess.run([py, "-m", "pip", "install", "--disable-pip-version-check", "reportlab"] + extra,
                                   capture_output=True, text=True, timeout=600, creationflags=flags)
                if r.returncode == 0:
                    break
            except Exception:
                pass
        importlib.invalidate_caches()
        try:
            import site
            importlib.reload(site)
        except Exception:
            pass
    if importlib.util.find_spec("reportlab") is None:
        raise RuntimeError("Για PDF χρειάζεται η βιβλιοθήκη reportlab (pip install reportlab"
                           + (" ή sudo apt install python3-reportlab" if sys.platform.startswith("linux") else "") + ")")


_PDF_FONTS = {}


def _pdf_fonts():
    """Γραμματοσειρές με ελληνικά: Segoe UI / Arial (Windows), DejaVu (Linux/Pi), Arial (macOS)."""
    if _PDF_FONTS:
        return _PDF_FONTS["r"], _PDF_FONTS["b"]
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    win = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    cands = [
        (os.path.join(win, "segoeui.ttf"), os.path.join(win, "segoeuib.ttf")),
        (os.path.join(win, "arial.ttf"), os.path.join(win, "arialbd.ttf")),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ]
    for reg, bold in cands:
        if os.path.exists(reg):
            pdfmetrics.registerFont(TTFont("ASans", reg))
            pdfmetrics.registerFont(TTFont("ASans-B", bold if os.path.exists(bold) else reg))
            from reportlab.lib.fonts import addMapping
            addMapping("ASans", 0, 0, "ASans")
            addMapping("ASans", 1, 0, "ASans-B")
            addMapping("ASans", 0, 1, "ASans")
            addMapping("ASans", 1, 1, "ASans-B")
            _PDF_FONTS.update(r="ASans", b="ASans-B")
            return "ASans", "ASans-B"
    raise RuntimeError("Δεν βρέθηκε γραμματοσειρά με ελληνικά (π.χ. sudo apt install fonts-dejavu-core)")


def _stats(vals):
    v = [x for x in vals if x is not None]
    if not v:
        return None, None, None
    return min(v), sum(v) / len(v), max(v)


def _downsample(pts, n=360):
    """(ts, v) → έως n σημεία (μέσος όρος ανά «κουβά»), με κενά όπου λείπουν δεδομένα."""
    pts = [(t, v) for t, v in pts if v is not None]
    if len(pts) <= n:
        return pts
    t0, t1 = pts[0][0], pts[-1][0]
    step = max(1.0, (t1 - t0) / n)
    out, cur, acc = [], None, []
    for t, v in pts:
        b = int((t - t0) / step)
        if b != cur and acc:
            out.append((sum(a[0] for a in acc) / len(acc), sum(a[1] for a in acc) / len(acc)))
            acc = []
        cur = b
        acc.append((t, v))
    if acc:
        out.append((sum(a[0] for a in acc) / len(acc), sum(a[1] for a in acc) / len(acc)))
    return out


def _nice_range(lo, hi, ticks=5):
    if lo is None:
        return 0, 1, 0.2
    if hi - lo < 1e-6:
        lo, hi = lo - 1, hi + 1
    span = hi - lo
    raw = span / ticks
    mag = 10 ** math.floor(math.log10(raw))
    step = min((s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw), default=raw)
    return math.floor(lo / step) * step, math.ceil(hi / step) * step, step


def build_setup_pdf(urls, has_pin=False, version=""):
    """Οδηγός σύνδεσης κινητού (σελίδα 1 Ελληνικά, σελίδα 2 English) με QR για εφαρμογή, server, Tailscale → bytes.
    urls: [(label, url)] όπως server_urls()."""
    _need_reportlab()
    import io
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.barcode.qr import QrCodeWidget

    FR, FB = _pdf_fonts()
    BLUE, DARK, GREY, LIGHT, WARNBG, OKBG = (colors.HexColor("#2b6cff"), colors.HexColor("#1b2433"), colors.HexColor("#5b6678"),
                                            colors.HexColor("#eef3ff"), colors.HexColor("#fff4e0"), colors.HexColor("#e8f8ef"))
    APK = "https://github.com/nikkpap/AirSense/releases/latest"
    TSAPP = "https://play.google.com/store/apps/details?id=com.tailscale.ipn"
    lan = next((u for _l, u in urls if re.match(r"^http://(192\.168|10\.|172\.(1[6-9]|2\d|3[01]))", u)), "")
    ts = next((u for _l, u in urls if re.match(r"^http://100\.\d+\.\d+\.\d+:", u)), "")
    st = {
        "t": ParagraphStyle("t", fontName=FB, fontSize=18, leading=22, textColor=DARK),
        "s": ParagraphStyle("s", fontName=FR, fontSize=10, leading=13, textColor=GREY),
        "h": ParagraphStyle("h", fontName=FB, fontSize=12.5, leading=16, textColor=colors.white),
        "b": ParagraphStyle("b", fontName=FR, fontSize=10, leading=13.2, textColor=DARK),
        "c": ParagraphStyle("c", fontName=FB, fontSize=9, leading=11, textColor=DARK, alignment=1),
        "u": ParagraphStyle("u", fontName=FR, fontSize=8, leading=10, textColor=GREY, alignment=1),
        "sm": ParagraphStyle("sm", fontName=FR, fontSize=8.5, leading=11, textColor=GREY),
    }

    def link(u, txt=None):
        return f'<link href="{u}" color="#2b6cff"><u>{txt or u}</u></link>'

    def qr(url, size=29 * mm):
        w = QrCodeWidget(url)
        w.barLevel = "M"
        x1, y1, x2, y2 = w.getBounds()
        d = Drawing(size, size, transform=[size / (x2 - x1), 0, 0, size / (y2 - y1), 0, 0])
        d.add(w)
        return d

    def qr_cell(url, title):
        if not url:
            return [Paragraph(title, st["c"]), Spacer(1, 2 * mm), Paragraph("—", st["u"])]
        return [qr(url), Paragraph(title, st["c"]), Paragraph(link(url, url.replace("https://", "").replace("play.google.com/store/apps/details?id=", "Play: ")[:40]), st["u"])]

    def step(n, word, title, items):
        head = Table([[Paragraph(f"{word} {n} — {title}", st["h"])]], colWidths=[170 * mm])
        head.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BLUE), ("LEFTPADDING", (0, 0), (-1, -1), 9),
                                  ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        body = Table([[Paragraph("• " + x, st["b"])] for x in items], colWidths=[170 * mm])
        body.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("LEFTPADDING", (0, 0), (-1, -1), 9),
                                  ("TOPPADDING", (0, 0), (-1, -1), 1.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8)]))
        return KeepTogether([head, body, Spacer(1, 2.6 * mm)])

    def box(items, bg):
        t = Table([[x] for x in items], colWidths=[170 * mm])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("LEFTPADDING", (0, 0), (-1, -1), 9),
                               ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        return t

    T = {
        "el": dict(
            title="AirSense — σύνδεση κινητού (Android)",
            sub=f"Οδηγός που έφτιαξε ο server σου · {datetime.now():%d/%m/%Y %H:%M} · AirSense v{version} · 4 βήματα, ~5 λεπτά",
            q=["① Εφαρμογή AirSense", "② Στο ίδιο WiFi", "③ Από παντού (Tailscale)", "Εφαρμογή Tailscale"],
            step="Βήμα",
            s1=("Εφαρμογή AirSense", ["Σκάναρε το QR ① (ή " + link(APK, "GitHub Releases") + ") → κατέβασε το <b>AirSense-Android_vX.apk</b>.",
                "Άνοιξέ το · αν πει «Για την ασφάλειά σας…» → <b>Ρυθμίσεις</b> → <b>Να επιτρέπεται από αυτή την πηγή</b> → πίσω → <b>Εγκατάσταση</b>.",
                "Οι επόμενες ενημερώσεις έρχονται μόνες τους μέσα από την εφαρμογή."]),
            s2=("Σύνδεση (στο ίδιο WiFi)", ["Το κινητό στο <b>ίδιο WiFi</b> με τον server.",
                "AirSense → <b>«Βρες αυτόματα»</b> — βρίσκει τον server και αποθηκεύει μόνο του. (Ή «Σκανάρισμα QR» → QR ②.)",
                "Αν ζητήσει <b>PIN</b>, γράψ' το και πάτα «Δοκιμή & αποθήκευση»."]),
            s3=("Από παντού (4G, άλλο WiFi)", ["Εγκατάστησε το <b>Tailscale</b> (QR «Εφαρμογή Tailscale») → login.",
                "Ίδιος λογαριασμός με τον server — ή πάτα την <b>πρόσκληση</b> που σου έστειλε ο διαχειριστής (άνοιξέ τη στο <b>Chrome</b>) → Accept.",
                "Tailscale <b>ON</b>. Η εφαρμογή AirSense ξέρει ήδη τη διεύθυνση (QR ③) — δεν γράφεις τίποτα."]),
            s4=("Έξτρα", ["<b>Widget:</b> παρατεταμένο πάτημα στην αρχική οθόνη → Widgets → AirSense.",
                "<b>Θέμα:</b> το εικονίδιο πάνω δεξιά — Αυτόματο / Με την ώρα / Σκούρο / Φωτεινό.",
                "<b>Ειδοποιήσεις:</b> καρτέλα Ειδοποιήσεις — όρια θερμοκρασίας/υγρασίας, αισθητήρας εκτός, παγετός."]),
            pin="<b>PIN:</b> ____________  (ζήτα το από τον διαχειριστή)",
            nopin="Ο server <b>δεν</b> ζητά PIN.",
            trouble="<b>Αν κάτι δεν πάει:</b> «Βρες αυτόματα» δεν βρίσκει → ίδιο WiFi; server αναμμένος; · "
                    "Δεν συνδέεται από 4G → Tailscale <b>ON</b> στο κινητό · «Failed to accept invitation» → άνοιξε τον σύνδεσμο στο <b>Chrome</b> · "
                    "Λάθος PIN → ζήτα το σωστό.",
            notail="(Ο server δεν έχει ακόμα Tailscale — μόνο στο ίδιο WiFi.)"),
        "en": dict(
            title="AirSense — connect your phone (Android)",
            sub=f"Guide made by your server · {datetime.now():%Y-%m-%d %H:%M} · AirSense v{version} · 4 steps, ~5 minutes",
            q=["① AirSense app", "② On the same WiFi", "③ From anywhere (Tailscale)", "Tailscale app"],
            step="Step",
            s1=("AirSense app", ["Scan QR ① (or " + link(APK, "GitHub Releases") + ") → download <b>AirSense-Android_vX.apk</b>.",
                "Open it · if it says \"For your security…\" → <b>Settings</b> → <b>Allow from this source</b> → back → <b>Install</b>.",
                "Later updates arrive by themselves inside the app."]),
            s2=("Connect (same WiFi)", ["Phone on the <b>same WiFi</b> as the server.",
                "AirSense → <b>\"Find automatically\"</b> — it finds the server and saves it. (Or \"Scan QR\" → QR ②.)",
                "If it asks for a <b>PIN</b>, type it and tap \"Test & save\"."]),
            s3=("From anywhere (4G, other WiFi)", ["Install <b>Tailscale</b> (QR \"Tailscale app\") → sign in.",
                "Same account as the server — or tap the <b>invitation</b> the admin sent you (open it in <b>Chrome</b>) → Accept.",
                "Tailscale <b>ON</b>. The AirSense app already knows the address (QR ③) — nothing to type."]),
            s4=("Extras", ["<b>Widget:</b> long-press the home screen → Widgets → AirSense.",
                "<b>Theme:</b> the icon at the top right — Auto / By time / Dark / Light.",
                "<b>Alerts:</b> tab Alerts — temperature/humidity limits, sensor offline, frost."]),
            pin="<b>PIN:</b> ____________  (ask the admin)",
            nopin="The server does <b>not</b> ask for a PIN.",
            trouble="<b>If something goes wrong:</b> \"Find automatically\" finds nothing → same WiFi? server on? · "
                    "No connection on 4G → Tailscale <b>ON</b> on the phone · \"Failed to accept invitation\" → open the link in <b>Chrome</b> · "
                    "Wrong PIN → ask for the right one.",
            notail="(The server has no Tailscale yet — same WiFi only.)"),
    }
    story = []
    for i, lang in enumerate(("el", "en")):
        L = T[lang]
        if i:
            story.append(PageBreak())
        story += [Paragraph(L["title"], st["t"]), Spacer(1, 1.5 * mm), Paragraph(L["sub"], st["s"]), Spacer(1, 4 * mm)]
        cells = [qr_cell(APK, L["q"][0]), qr_cell(lan, L["q"][1]), qr_cell(ts, L["q"][2]), qr_cell(TSAPP, L["q"][3])]
        qt = Table([cells], colWidths=[42.5 * mm] * 4)
        qt.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#c9d6f5")),
                                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dfe6f5")),
                                ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        story += [qt, Spacer(1, 3 * mm)]
        story += [box([Paragraph(L["pin"] if has_pin else L["nopin"], st["b"])] + ([] if ts else [Paragraph(L["notail"], st["sm"])]), OKBG),
                  Spacer(1, 3 * mm)]
        for n, key in enumerate(("s1", "s2", "s3", "s4"), 1):
            title, items = L[key]
            story.append(step(n, L["step"], title, items))
        story += [box([Paragraph(L["trouble"], st["b"])], WARNBG), Spacer(1, 3 * mm),
                  Paragraph(f"{APP_NAME} · {AUTHOR} · ALU DEV TEAM · " + link("https://github.com/nikkpap/AirSense", "github.com/nikkpap/AirSense"), st["sm"])]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=11 * mm, bottomMargin=9 * mm,
                      title="AirSense — Phone setup / Σύνδεση κινητού", author=AUTHOR).build(story)
    return buf.getvalue()


def build_pdf_report(info):
    """Φτιάχνει την αναφορά PDF. info: dict με app, period, devices, weather, labels κ.λπ. → bytes"""
    _need_reportlab()
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
                                    KeepTogether, PageBreak)
    from reportlab.graphics.shapes import Drawing, Rect, Line, PolyLine, String, Polygon, Circle, Group
    from reportlab.pdfgen import canvas as rl_canvas

    FR, FB = _pdf_fonts()
    C = lambda h, a=1.0: colors.Color(int(h[1:3], 16) / 255, int(h[3:5], 16) / 255, int(h[5:7], 16) / 255, alpha=a)
    NAVY, BLUE, ORANGE, SKY, PURPLE, GREEN, GREY, LIGHT, LINE, TXT, RED, AMBER = (
        C("#141b2d"), C("#2b6cff"), C("#ff8a1f"), C("#1f8fff"), C("#8b5cf6"), C("#1e9e55"), C("#6b7588"),
        C("#f3f5f9"), C("#dfe4ec"), C("#1a1f2b"), C("#d93636"), C("#d08700"))
    W, H = A4
    M = 15 * mm
    CW = W - 2 * M
    lb = info["labels"]
    li, lo = lb["inside"], lb["outside"]

    st = {
        "h1": ParagraphStyle("h1", fontName=FB, fontSize=15, leading=19, textColor=TXT, spaceBefore=4, spaceAfter=6),
        "h2": ParagraphStyle("h2", fontName=FB, fontSize=12, leading=15, textColor=TXT, spaceBefore=6, spaceAfter=4),
        "p": ParagraphStyle("p", fontName=FR, fontSize=9, leading=12.5, textColor=TXT),
        "mut": ParagraphStyle("mut", fontName=FR, fontSize=8, leading=11, textColor=GREY),
        "cell": ParagraphStyle("cell", fontName=FR, fontSize=7.6, leading=9.5, textColor=TXT),
        "cellb": ParagraphStyle("cellb", fontName=FB, fontSize=7.6, leading=9.5, textColor=TXT),
        "th": ParagraphStyle("th", fontName=FB, fontSize=7.4, leading=9, textColor=colors.white),
    }
    f1 = lambda v, d=1: "–" if v is None else (f"{v:.{d}f}")
    span_s = info["t1"] - info["t0"]
    dfmt = "%d/%m/%Y %H:%M"
    period = f"{datetime.fromtimestamp(info['t0']).strftime(dfmt)} — {datetime.fromtimestamp(info['t1']).strftime(dfmt)}"

    # ── σελίδα: κεφαλίδα + υποσέλιδο με «Σελίδα Χ / Υ»
    class NumCanvas(rl_canvas.Canvas):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._pages = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            n = len(self._pages)
            for p in self._pages:
                self.__dict__.update(p)
                self._decor(n)
                super().showPage()
            super().save()

        def _logo(self, x, y, s):
            self.setFillColor(BLUE)
            self.roundRect(x, y, s, s, s * 0.22, stroke=0, fill=1)
            self.setStrokeColor(colors.white)
            self.setLineWidth(s * 0.075)
            self.setLineCap(1)
            for i, (w_, dy) in enumerate(((0.62, 0.68), (0.46, 0.50), (0.56, 0.32))):
                p = self.beginPath()
                p.moveTo(x + s * 0.2, y + s * dy)
                p.curveTo(x + s * (0.2 + w_ * 0.4), y + s * (dy + 0.09), x + s * (0.2 + w_ * 0.7), y + s * (dy - 0.06),
                          x + s * (0.2 + w_), y + s * dy)
                self.drawPath(p, stroke=1, fill=0)

        def _decor(self, n):
            pg = self._pageNumber
            if pg == 1:
                self.setFillColor(NAVY)
                self.rect(0, H - 40 * mm, W, 40 * mm, stroke=0, fill=1)
                self.setFillColor(BLUE)
                self.rect(0, H - 40 * mm, W, 1.4 * mm, stroke=0, fill=1)
                self._logo(M, H - 29 * mm, 15 * mm)
                self.setFillColor(colors.white)
                self.setFont(FB, 24)
                self.drawString(M + 19 * mm, H - 21.5 * mm, info["app"])
                self.setFont(FR, 10.5)
                self.setFillColor(C("#aeb9cf"))
                self.drawString(M + 19 * mm, H - 28 * mm, "Αναφορά μετρήσεων θερμοκρασίας & υγρασίας")
                self.setFont(FB, 10)
                self.setFillColor(colors.white)
                self.drawRightString(W - M, H - 18 * mm, period)
                self.setFont(FR, 8.5)
                self.setFillColor(C("#aeb9cf"))
                if info.get("place"):
                    self.drawRightString(W - M, H - 23.5 * mm, info["place"][:80])
                self.drawRightString(W - M, H - 28.5 * mm,
                                     "Δημιουργήθηκε " + datetime.now().strftime("%d/%m/%Y %H:%M"))
            else:
                self.setFillColor(NAVY)
                self.rect(0, H - 12 * mm, W, 12 * mm, stroke=0, fill=1)
                self._logo(M, H - 9.6 * mm, 7 * mm)
                self.setFillColor(colors.white)
                self.setFont(FB, 10)
                self.drawString(M + 9.5 * mm, H - 7.4 * mm, info["app"])
                self.setFont(FR, 8)
                self.setFillColor(C("#aeb9cf"))
                self.drawRightString(W - M, H - 7.4 * mm, period)
            self.setStrokeColor(LINE)
            self.setLineWidth(0.6)
            self.line(M, 12 * mm, W - M, 12 * mm)
            self.setFont(FR, 7.5)
            self.setFillColor(GREY)
            self.drawString(M, 8 * mm, f"{info['app']} v{info['version']} · {info['author']} · {info['team']}")
            self.drawRightString(W - M, 8 * mm, f"Σελίδα {pg} / {n}")

    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=M, rightMargin=M, topMargin=18 * mm, bottomMargin=16 * mm,
                          title=f"{info['app']} — Αναφορά", author=info["author"], subject=period,
                          creator=f"{info['app']} v{info['version']}")
    first = Frame(M, 16 * mm, CW, H - 16 * mm - 46 * mm, id="first", leftPadding=0, rightPadding=0, topPadding=0)
    later = Frame(M, 16 * mm, CW, H - 16 * mm - 18 * mm, id="later", leftPadding=0, rightPadding=0, topPadding=0)
    doc.addPageTemplates([PageTemplate("first", [first], autoNextPageTemplate="later"),
                          PageTemplate("later", [later])])

    # ── δομικά στοιχεία
    from reportlab.pdfbase.pdfmetrics import stringWidth as SW

    def fit(text, font, size, maxw, min_size=6.0):
        """Μικραίνει τη γραμματοσειρά ή κόβει με «…» ώστε το κείμενο να χωράει."""
        while size > min_size and SW(text, font, size) > maxw:
            size -= 0.3
        while text and SW(text, font, size) > maxw:
            text = text[:-2] + "…"
        return text, size

    def tile(title, big, unit, sub, accent, w):
        d = Drawing(w, 23 * mm)
        d.add(Rect(0, 0, w, 23 * mm, rx=3 * mm, ry=3 * mm, fillColor=LIGHT, strokeColor=None))
        d.add(Rect(0, 0, 1.6 * mm, 23 * mm, fillColor=accent, strokeColor=None))
        inner = w - 7 * mm
        t_, ts_ = fit(title, FR, 7.8, inner)
        d.add(String(4.5 * mm, 17 * mm, t_, fontName=FR, fontSize=ts_, fillColor=GREY))
        d.add(String(4.5 * mm, 8.6 * mm, big, fontName=FB, fontSize=17, fillColor=accent))
        d.add(String(4.5 * mm + SW(big, FB, 17) + 1.0 * mm, 8.8 * mm, unit, fontName=FR, fontSize=8.5, fillColor=GREY))
        s_, ss_ = fit(sub, FR, 7, inner)
        d.add(String(4.5 * mm, 3.2 * mm, s_, fontName=FR, fontSize=ss_, fillColor=GREY))
        return d

    def tiles_row(items):
        gap = 3 * mm
        w = (CW - gap * (len(items) - 1)) / len(items)
        t = Table([[tile(*it, w) for it in items]], colWidths=[w + (gap if i < len(items) - 1 else 0)
                                                                for i in range(len(items))])
        t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                               ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    def chart(series, title, unit, height=62 * mm, band=None):
        """series: [(pts[(ts,v)], color, dashed, name, fill)]  band: (lo, hi, color) ζώνη ορίων"""
        w, h = CW, height
        d = Drawing(w, h)
        d.add(Rect(0, 0, w, h, rx=3 * mm, ry=3 * mm, fillColor=colors.white, strokeColor=LINE, strokeWidth=0.6))
        pl, pr, pt, pb = 13 * mm, 5 * mm, 10 * mm, 9 * mm
        x0, x1, y0, y1 = pl, w - pr, pb, h - pt
        allv = [v for s in series for _, v in s[0]]
        d.add(String(4 * mm, h - 6.3 * mm, title, fontName=FB, fontSize=9.5, fillColor=TXT))
        lx = w - 4 * mm
        for pts, col, dashed, name, _fill in reversed(series):
            if not pts:
                continue
            tw = SW(name, FR, 7.4)
            d.add(String(lx - tw, h - 6.1 * mm, name, fontName=FR, fontSize=7.4, fillColor=GREY))
            ln = Line(lx - tw - 8 * mm, h - 5.2 * mm, lx - tw - 2 * mm, h - 5.2 * mm, strokeColor=col, strokeWidth=1.8)
            if dashed:
                ln.strokeDashArray = [2.2, 1.6]
            d.add(ln)
            lx -= tw + 12 * mm
        if not allv:
            d.add(String(w / 2, h / 2, "Δεν υπάρχουν δεδομένα", fontName=FR, fontSize=9, fillColor=GREY, textAnchor="middle"))
            return d
        lo_, hi_, step = _nice_range(min(allv), max(allv))
        t0, t1 = info["t0"], info["t1"]
        X = lambda t: x0 + (t - t0) / max(1, (t1 - t0)) * (x1 - x0)
        Y = lambda v: y0 + (v - lo_) / max(1e-9, (hi_ - lo_)) * (y1 - y0)
        if band:
            b0, b1 = max(lo_, band[0]), min(hi_, band[1])
            if b1 > b0:
                d.add(Rect(x0, Y(b0), x1 - x0, Y(b1) - Y(b0), fillColor=band[2], strokeColor=None))
        v = lo_
        while v <= hi_ + step / 2:
            yy = Y(v)
            d.add(Line(x0, yy, x1, yy, strokeColor=LINE, strokeWidth=0.4))
            d.add(String(x0 - 1.6 * mm, yy - 2.4, (f"{v:.0f}" if step >= 1 else f"{v:.1f}") + unit, fontName=FR,
                         fontSize=6.8, fillColor=GREY, textAnchor="end"))
            v += step
        nt = 6
        tf = "%H:%M" if span_s <= 36 * 3600 else ("%d/%m %H:%M" if span_s <= 4 * 86400 else "%d/%m")
        for i in range(nt + 1):
            tt = t0 + (t1 - t0) * i / nt
            xx = X(tt)
            d.add(Line(xx, y0, xx, y0 - 1.2 * mm, strokeColor=LINE, strokeWidth=0.5))
            d.add(String(xx, y0 - 4.6 * mm, datetime.fromtimestamp(tt).strftime(tf), fontName=FR, fontSize=6.6,
                         fillColor=GREY, textAnchor="middle"))
        for pts, col, dashed, name, fill in series:
            if len(pts) < 1:
                continue
            gaps = sorted(b[0] - a[0] for a, b in zip(pts, pts[1:]))
            gap_lim = max(3 * (gaps[len(gaps) // 2] if gaps else 0), 2 * 3600 if dashed else 1800)
            segs, cur = [], [pts[0]]
            for a, b in zip(pts, pts[1:]):
                if b[0] - a[0] > gap_lim:
                    segs.append(cur)
                    cur = []
                cur.append(b)
            segs.append(cur)
            for sg in segs:
                xy = []
                for t, v in sg:
                    xy += [X(t), Y(v)]
                if fill and len(sg) > 1:
                    d.add(Polygon([X(sg[0][0]), y0] + xy + [X(sg[-1][0]), y0],
                                  fillColor=colors.Color(col.red, col.green, col.blue, alpha=0.10), strokeColor=None))
                if len(sg) == 1:
                    d.add(Circle(xy[0], xy[1], 1.1, fillColor=col, strokeColor=None))
                    continue
                pl_ = PolyLine(xy, strokeColor=col, strokeWidth=1.5 if not dashed else 1.2)
                pl_.strokeLineJoin = 1
                if dashed:
                    pl_.strokeDashArray = [2.2, 1.6]
                d.add(pl_)
        return d

    def table(head, rows, widths, zebra=True, aligns=None):
        data = [[Paragraph(h, st["th"]) for h in head]] + [
            [c if not isinstance(c, str) else Paragraph(c, st["cell"]) for c in r] for r in rows]
        t = Table(data, colWidths=widths, repeatRows=1)
        sty = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
               ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
               ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
               ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINE)]
        if zebra:
            for i in range(1, len(data)):
                if i % 2 == 0:
                    sty.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
        t.setStyle(TableStyle(sty))
        return t

    story = []
    devs = info["devices"]
    wx = info.get("weather") or []
    wxf = info.get("wxf")
    hum_lo, hum_hi = info.get("hum_band", (30.0, 60.0))

    # ── 1. Σύνοψη
    story.append(Paragraph("Σύνοψη", st["h1"]))
    hours = span_s / 3600
    intro = (f"Περίοδος <b>{period}</b> ({f1(hours, 0) + ' ώρες' if hours <= 72 else f1(hours / 24, 0) + ' ημέρες'}) · "
             f"αισθητήρες: <b>{len(devs)}</b> · μετρήσεις: <b>{sum(len(d['rows']) for d in devs):,}</b>".replace(",", "."))
    if info.get("place"):
        intro += f" · καιρός ({lo}): <b>{info['place']}</b> (Open-Meteo)"
    story.append(Paragraph(intro, st["p"]))
    story.append(Spacer(1, 4 * mm))

    for di, dv in enumerate(devs):
        rows = dv["rows"]
        T = [r[4] for r in rows]
        Hh = [r[5] for r in rows]
        DP = [r[6] for r in rows]
        AH = [r[7] for r in rows]
        tmn, tav, tmx = _stats(T)
        hmn, hav, hmx = _stats(Hh)
        dmn, dav, dmx = _stats(DP)
        amn, aav, amx = _stats(AH)
        head = (f"<font name='{FB}' size='11.5'>{dv['name']}</font>  "
                f"<font color='#6b7588' size='8'>{dv['ip']} · {len(rows)} μετρήσεις · {li}</font>")
        block = [Paragraph(head, st["p"]), Spacer(1, 2 * mm),
                 tiles_row([("Θερμοκρασία (μέση)", f1(tav), "°C", f"min {f1(tmn)} · max {f1(tmx)} °C", ORANGE),
                            ("Υγρασία (μέση)", f1(hav), "%", f"min {f1(hmn)} · max {f1(hmx)} %", SKY),
                            ("Σημείο δρόσου", f1(dav), "°C", f"min {f1(dmn)} · max {f1(dmx)} °C", PURPLE),
                            ("Απόλυτη υγρασία", f1(aav), "g/m³", f"min {f1(amn)} · max {f1(amx)}", GREEN)])]
        # ποσοστά χρόνου σε ζώνες υγρασίας
        hv = [x for x in Hh if x is not None]
        if hv:
            n = len(hv)
            p_lo = 100 * sum(1 for x in hv if x < hum_lo) / n
            p_hi = 100 * sum(1 for x in hv if x > hum_hi) / n
            p_ok = 100 - p_lo - p_hi
            p_mold = 100 * sum(1 for x in hv if x >= 70) / n
            bar = Drawing(CW, 13 * mm)
            bar.add(String(0, 9.6 * mm, f"Χρόνος ανά ζώνη υγρασίας ({li})", fontName=FB, fontSize=8, fillColor=TXT))
            x = 0
            for pc, col, lab in ((p_lo, AMBER, f"ξηρή <{hum_lo:.0f}%"), (p_ok, GREEN, f"άνετη {hum_lo:.0f}–{hum_hi:.0f}%"),
                                 (p_hi, SKY, f"υγρή >{hum_hi:.0f}%")):
                ww = CW * pc / 100
                if ww > 0.2:
                    bar.add(Rect(x, 3.6 * mm, ww, 4.2 * mm, fillColor=col, strokeColor=colors.white, strokeWidth=0.8))
                    if ww > 26 * mm:
                        bar.add(String(x + 2 * mm, 4.9 * mm, f"{lab}: {pc:.0f}%", fontName=FB, fontSize=6.8,
                                       fillColor=colors.white))
                x += ww
            note = f"Κίνδυνος μούχλας (υγρασία ≥ 70%): {p_mold:.0f}% του χρόνου"
            bar.add(String(0, 0, note, fontName=FR, fontSize=7, fillColor=RED if p_mold >= 10 else GREY))
            block += [Spacer(1, 2.5 * mm), bar]
        # μέσα–έξω
        if wxf and rows:
            dts, dhs, vent = [], [], {1: 0, -1: 0, 0: 0}
            for r in rows[:: max(1, len(rows) // 3000)]:
                w_ = wxf(r[0])
                if not w_ or r[4] is None or r[5] is None or w_.get("temp") is None or w_.get("hum") is None:
                    continue
                df = inout_diff(r[4], r[5], w_["temp"], w_["hum"], lb)
                dts.append(df["dt"])
                dhs.append(df["dh"])
                vent[df["vent"]] += 1
            if dts:
                n = sum(vent.values())
                block += [Spacer(1, 2.5 * mm), tiles_row([
                    (f"Θερμοκρασία {li} − {lo}", ("+" if sum(dts) > 0 else "") + f1(sum(dts) / len(dts)), "°C",
                     f"εύρος {f1(min(dts))} … {f1(max(dts))} °C", ORANGE),
                    (f"Υγρασία {li} − {lo}", ("+" if sum(dhs) > 0 else "") + f1(sum(dhs) / len(dhs)), "%",
                     f"εύρος {f1(min(dhs))} … {f1(max(dhs))} %", SKY),
                    ("Αερισμός ξεραίνει", f"{100 * vent[1] / n:.0f}", "%", f"του χρόνου ({lo}: πιο ξερός αέρας)", GREEN),
                    ("Αερισμός υγραίνει", f"{100 * vent[-1] / n:.0f}", "%", f"του χρόνου ({lo}: πιο υγρός αέρας)", AMBER)])]
        block.append(Spacer(1, 5 * mm))
        story.append(KeepTogether(block))

    # ── καιρός (έξω)
    if wx:
        wT = [r["temp"] for r in wx]
        wH = [r["hum"] for r in wx]
        rain = sum((r.get("rain") if r.get("rain") is not None else (r.get("precip") or 0)) or 0 for r in wx)
        snow = sum(r.get("snow") or 0 for r in wx)
        sun_h = sum(r.get("sunshine") or 0 for r in wx) / 3600
        wmn, wav, wmx = _stats(wT)
        _, whav, _ = _stats(wH)
        stat = {}
        for r in wx:
            if r.get("status"):
                stat[r["status"]] = stat.get(r["status"], 0) + 1
        blk = [Paragraph(f"Καιρός — {lo}" + (f" <font color='#6b7588' size='8'>({info['place']}, Open-Meteo)</font>"
                                               if info.get("place") else ""), st["h2"]),
               tiles_row([("Θερμοκρασία (μέση)", f1(wav), "°C", f"min {f1(wmn)} · max {f1(wmx)} °C", ORANGE),
                          ("Υγρασία (μέση)", f1(whav), "%", f"{len(wx)} ωριαίες τιμές", SKY),
                          ("Βροχή / χιόνι", f1(rain), "mm", f"χιόνι {f1(snow)} cm", BLUE),
                          ("Ηλιοφάνεια", f1(sun_h), "ώρες", "σύνολο διαστήματος", AMBER)])]
        if stat:
            tot = sum(stat.values())
            pal = {"Ηλιοφάνεια": C("#f5b400"), "Συννεφιά": C("#8b96ab"), "Βροχή": C("#1f8fff"), "Χιόνι": C("#9fc0ff"),
                   "Καταιγίδα": C("#7c3aed"), "Ομίχλη": C("#b8c0cc"), "Νύχτα": C("#33405c")}
            bar = Drawing(CW, 12 * mm)
            bar.add(String(0, 8.6 * mm, "Καταστάσεις καιρού (ώρες)", fontName=FB, fontSize=8, fillColor=TXT))
            x = 0
            leg = []
            for k, v in sorted(stat.items(), key=lambda kv: -kv[1]):
                ww = CW * v / tot
                col = pal.get(k, GREY)
                bar.add(Rect(x, 3 * mm, ww, 4 * mm, fillColor=col, strokeColor=colors.white, strokeWidth=0.8))
                x += ww
                leg.append((k, v, col))
            lx = 0
            for k, v, col in leg:
                bar.add(Rect(lx, 0, 2.2 * mm, 2.2 * mm, fillColor=col, strokeColor=None))
                txt = f"{k} {v}"
                bar.add(String(lx + 3 * mm, 0.3 * mm, txt, fontName=FR, fontSize=6.8, fillColor=GREY))
                lx += 3 * mm + SW(txt, FR, 6.8) + 4 * mm
            blk += [Spacer(1, 2.5 * mm), bar]
        story.append(KeepTogether(blk + [Spacer(1, 4 * mm)]))

    # ── 2. Ανά αισθητήρα: γραφήματα + πίνακας ανά ημέρα (κάθε αισθητήρας σε νέα σελίδα)
    out_t = _downsample([(r["ts"], r["temp"]) for r in wx], 240) if wx else []
    out_h = _downsample([(r["ts"], r["hum"]) for r in wx], 240) if wx else []
    WD = ["Δευ", "Τρί", "Τετ", "Πέμ", "Παρ", "Σάβ", "Κυρ"]
    wdays = {}
    for r in wx:
        wdays.setdefault(datetime.fromtimestamp(r["ts"]).date(), []).append(r)
    for dv in devs:
        rows = dv["rows"]
        story.append(PageBreak())
        story.append(Paragraph(f"{dv['name']} <font color='#6b7588' size='9'>· {dv['ip']} · {li}</font>", st["h1"]))
        pt_t = _downsample([(r[0], r[4]) for r in rows])
        pt_h = _downsample([(r[0], r[5]) for r in rows])
        pt_d = _downsample([(r[0], r[6]) for r in rows])
        story.append(chart([(pt_t, ORANGE, False, f"{li}", True), (pt_d, PURPLE, False, "σημείο δρόσου", False),
                            (out_t, GREEN, True, f"{lo} (Open-Meteo)", False)], "Θερμοκρασία", "°", height=56 * mm))
        story.append(Spacer(1, 3.5 * mm))
        story.append(chart([(pt_h, SKY, False, f"{li}", True), (out_h, GREEN, True, f"{lo} (Open-Meteo)", False)],
                           f"Σχετική υγρασία  ·  πράσινη ζώνη = άνετη {hum_lo:.0f}–{hum_hi:.0f}%", "%", height=56 * mm,
                           band=(hum_lo, hum_hi, C("#1e9e55", 0.08))))
        story.append(Spacer(1, 5 * mm))
        days = {}
        for r in rows:
            days.setdefault(datetime.fromtimestamp(r[0]).date(), []).append(r)
        trs = []
        for k in sorted(days):
            rr = days[k]
            tmn, tav, tmx = _stats([r[4] for r in rr])
            hmn, hav, hmx = _stats([r[5] for r in rr])
            _, dav, _ = _stats([r[6] for r in rr])
            ww = wdays.get(k, [])
            _, wta, _ = _stats([r["temp"] for r in ww])
            _, wha, _ = _stats([r["hum"] for r in ww])
            rn = sum((r.get("rain") if r.get("rain") is not None else (r.get("precip") or 0)) or 0 for r in ww) if ww else None
            sc = {}
            for r in ww:
                if r.get("status") and r["status"] != "Νύχτα":
                    sc[r["status"]] = sc.get(r["status"], 0) + 1
            dom = max(sc.items(), key=lambda kv: kv[1])[0] if sc else ("Νύχτα" if ww else "")
            hcol = "#d93636" if (hmx or 0) >= 70 else ("#d08700" if (hmn if hmn is not None else 100) < hum_lo else "#1a1f2b")
            trs.append([f"<b>{WD[k.weekday()]} {k.strftime('%d/%m')}</b>",
                        f"{f1(tmn)} / <b>{f1(tav)}</b> / {f1(tmx)}",
                        f"<font color='{hcol}'>{f1(hmn, 0)} / <b>{f1(hav, 0)}</b> / {f1(hmx, 0)}</font>",
                        f1(dav), f1(wta), f1(wha, 0), "" if rn is None else f1(rn), dom, str(len(rr))])
        story.append(Paragraph("Ανά ημέρα", st["h2"]))
        story.append(table(["Ημέρα", f"{li} °C<br/>min / μέση / max", f"{li} %RH<br/>min / μέση / max", "Δρόσος °C",
                            f"{lo} °C", f"{lo} %", "Βροχή mm", "Καιρός", "Μετρ."],
                           trs, [18 * mm, 31 * mm, 28 * mm, 15 * mm, 14 * mm, 13 * mm, 15 * mm, 26 * mm, 20 * mm]))
        story.append(Paragraph("<font color='#d93636'>κόκκινο</font> = υγρασία έφτασε ≥ 70% (κίνδυνος μούχλας) · "
                               f"<font color='#d08700'>πορτοκαλί</font> = έπεσε κάτω από {hum_lo:.0f}%", st["mut"]))
        story.append(Spacer(1, 5 * mm))

    story.append(Paragraph(
        f"Σημειώσεις: η απόλυτη υγρασία (g/m³) δείχνει πόσο νερό έχει πραγματικά ο αέρας — αν «{lo}» είναι μικρότερη από "
        f"«{li}», ο αερισμός ξεραίνει τον χώρο, ακόμα κι αν το ποσοστό (%RH) έξω φαίνεται μεγαλύτερο. "
        "Καιρός: Open-Meteo.com (CC BY 4.0). Αισθητήρες: BleBox humiditySensor.", st["mut"]))
    doc.build(story, canvasmaker=NumCanvas)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════
# 8) Email
# ═══════════════════════════════════════════════════════════════════════════
# ── Γρήγορη σύνδεση Microsoft (Outlook / Hotmail / Live / Microsoft 365) ──
# Τα λογαριασμοί Outlook.com δεν δέχονται πια κωδικό στο SMTP (ούτε κωδικό εφαρμογής) → σύνδεση OAuth2
# με «κωδικό συσκευής»: δείχνουμε έναν κωδικό, ο χρήστης μπαίνει στο microsoft.com/link από όποια συσκευή
# θέλει (PC ή κινητό) και πατάει «Αποδοχή». Δουλεύει και στην πλακέτα (χωρίς οθόνη).
# MS_CLIENT_ID = «Application (client) ID» μιας δωρεάν καταχώρισης στο portal.azure.com (δημόσιο, όχι μυστικό).
MS_CLIENT_ID = ""
MS_AUTH = "https://login.microsoftonline.com/common/oauth2/v2.0/"
MS_SCOPE = "https://outlook.office.com/SMTP.Send offline_access openid email profile"
MS_PERSONAL = ("outlook.", "hotmail.", "live.", "msn.", "passport.", "windowslive.")
GMAIL_APP_PW = "https://myaccount.google.com/apppasswords"
MS_APP_GUIDE = "https://github.com/nikkpap/AirSense#-email-quick-login"
_MAIL_SAVE = None            # Engine.save_cfg → σώζει το νέο refresh token της Microsoft
_MS_TOK = {}                 # refresh(enc) → (access token, λήξη)


def ms_client_id(e):
    return (e.get("ms_client_id") or MS_CLIENT_ID or "").strip()


def ms_smtp_host(email):
    dom = email.split("@")[-1].lower()
    return "smtp-mail.outlook.com" if dom.startswith(MS_PERSONAL) else "smtp.office365.com"


def _form_post(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        try:
            return json.loads(ex.read().decode("utf-8"))
        except Exception:
            raise RuntimeError(f"HTTP {ex.code}")


def _jwt_claims(tok):
    try:
        part = tok.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    except Exception:
        return {}


def ms_access_token(e):
    rt_enc = e.get("oauth_refresh", "")
    rt = dec_secret(rt_enc)
    if not rt:
        raise RuntimeError("Δεν υπάρχει σύνδεση Microsoft — πατήστε «Σύνδεση Outlook»")
    tok = _MS_TOK.get(rt_enc)
    if tok and tok[1] > time.time() + 120:
        return tok[0]
    j = _form_post(MS_AUTH + "token", {"client_id": ms_client_id(e), "grant_type": "refresh_token",
                                       "refresh_token": rt, "scope": MS_SCOPE})
    if "access_token" not in j:
        raise RuntimeError("Η σύνδεση Microsoft έληξε — πατήστε ξανά «Σύνδεση Outlook» "
                           f"({j.get('error_description', j.get('error', ''))[:120]})")
    if j.get("refresh_token") and j["refresh_token"] != rt:      # η Microsoft αλλάζει το refresh token
        e["oauth_refresh"] = enc_secret(j["refresh_token"])
        if _MAIL_SAVE:
            try:
                _MAIL_SAVE()
            except Exception:
                pass
    _MS_TOK[e.get("oauth_refresh", "")] = (j["access_token"], time.time() + int(j.get("expires_in", 3600)))
    return j["access_token"]


def _smtp_open(e):
    """Σύνδεση + είσοδος στον SMTP (κωδικός ή Microsoft OAuth2)."""
    port = int(e.get("port") or 587)
    sec = e.get("security", "STARTTLS")
    ctx = ssl.create_default_context()
    if sec == "SSL":
        srv = smtplib.SMTP_SSL(e["host"], port, context=ctx, timeout=25)
    else:
        srv = smtplib.SMTP(e["host"], port, timeout=25)
        if sec == "STARTTLS":
            srv.starttls(context=ctx)
    try:
        if e.get("auth") == "oauth_ms":
            tok = ms_access_token(e)
            user = e.get("user", "")
            srv.ehlo()
            srv.auth("XOAUTH2", lambda challenge=None: f"user={user}\x01auth=Bearer {tok}\x01\x01",
                     initial_response_ok=True)
        elif e.get("user"):
            srv.login(e["user"], dec_secret(e.get("password", "")))
    except smtplib.SMTPAuthenticationError as ex:
        try:
            srv.quit()
        except Exception:
            pass
        txt = (ex.smtp_error or b"").decode("utf-8", "replace")
        if "basic authentication is disabled" in txt.lower():
            raise RuntimeError("Η Microsoft δεν δέχεται κωδικό → πατήστε «🟦 Σύνδεση Outlook» (γρήγορη σύνδεση).")
        if "gmail" in e.get("host", "") or "Application-specific" in txt:
            raise RuntimeError("Η Google δεν δέχτηκε τον κωδικό → χρειάζεται «Κωδικός εφαρμογής» 16 γραμμάτων "
                               "(πατήστε «🔵 Σύνδεση Google»).")
        raise RuntimeError(f"Λάθος χρήστης / κωδικός ({ex.smtp_code})")
    except Exception:
        try:
            srv.quit()
        except Exception:
            pass
        raise
    return srv


def smtp_check(e):
    srv = _smtp_open(e)
    try:
        srv.noop()
    finally:
        try:
            srv.quit()
        except Exception:
            pass


def send_mail(e, subject, body, attachments=()):
    to = [x.strip() for x in re.split(r"[,;]", e.get("to", "")) if x.strip()]
    if not e.get("host") or not to:
        raise RuntimeError("Συμπληρώστε SMTP server και παραλήπτη")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = e.get("sender") or e.get("user")
    msg["To"] = ", ".join(to)
    msg.set_content(body)
    for fname, data, maintype, subtype in attachments:
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=fname)
    srv = _smtp_open(e)
    try:
        srv.send_message(msg)
    finally:
        try:
            srv.quit()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
# 9) Engine (καταγραφή, σάρωση, server) — χωρίς GUI
# ═══════════════════════════════════════════════════════════════════════════
class Engine:
    def __init__(self):
        ensure_dirs()
        self.cfg = load_cfg()
        self.lock = threading.RLock()
        self.ms_flow = {}
        global _MAIL_SAVE
        _MAIL_SAVE = self.save_cfg
        self.store = Store(DB_PATH)
        self.live = {}
        self.events = deque(maxlen=500)
        self.poll_counter = 0
        self.stop_ev = threading.Event()
        self.wake_ev = threading.Event()
        self.scan = {"running": False, "done": 0, "total": 0, "results": [], "finished": None, "auto": False}
        self.scan_stop = threading.Event()
        self.alarm_last = {}
        self.httpd = None
        self.server_error = ""
        self._path_cache = {}
        self._last_xml = 0
        self._last_rescan = 0
        self._cur_date = datetime.now().strftime("%Y-%m-%d")
        self._ts_cache = (0, None)
        self.wx = None
        self.wx_err = ""
        self.wx_wake = threading.Event()
        self.wx_counter = 0

    # ── βοηθητικά ──
    def log(self, msg, level="info"):
        with self.lock:
            self.events.append((time.time(), level, msg))
        if HEADLESS:
            print(f"{datetime.now():%Y-%m-%d %H:%M:%S} [{level}] {msg}", flush=True)

    def save_cfg(self):
        with self.lock:
            tmp = CFG_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, ensure_ascii=False, indent=2)
            os.replace(tmp, CFG_PATH)
            if os.name != "nt":
                try:
                    os.chmod(CFG_PATH, 0o600)   # περιέχει κωδικό email
                except Exception:
                    pass

    def devices(self):
        with self.lock:
            return [dict(d) for d in self.cfg["devices"]]

    def device(self, did):
        with self.lock:
            for d in self.cfg["devices"]:
                if d["id"] == did:
                    return d
        return None

    def set_device_field(self, did, key, val):
        with self.lock:
            d = self.device(did)
            if d is not None:
                d[key] = val
                self.save_cfg()

    def remove_device(self, did):
        with self.lock:
            self.cfg["devices"] = [d for d in self.cfg["devices"] if d["id"] != did]
            self.live.pop(did, None)
            self.save_cfg()
        self.log(f"Αφαιρέθηκε η συσκευή {did}")

    def add_from_info(self, ip, info):
        did = str(info.get("id") or ip)
        with self.lock:
            ex = self.device(did)
            if ex:
                ex["ip"] = ip
                self.save_cfg()
                return False
            self.cfg["devices"].append({
                "id": did, "name": info.get("deviceName") or info.get("name") or f"Αισθητήρας {ip}",
                "ip": ip, "type": info.get("type", ""), "product": info.get("product", ""),
                "fv": info.get("fv", ""), "apiLevel": str(info.get("apiLevel", "")), "mac": info.get("mac", ""),
                "enabled": True})
            self.save_cfg()
        self.log(f"Προστέθηκε: {info.get('deviceName') or did} ({ip})")
        self.wake_ev.set()
        return True

    def add_scan_result(self, r):
        return self.add_from_info(r["ip"], {"id": r["id"], "deviceName": r["name"], "type": r["type"],
                                            "product": r["product"], "fv": r["fv"], "apiLevel": r["apiLevel"],
                                            "mac": r.get("mac", "")})

    def add_manual(self, addr):
        addr = addr.strip()
        info = blebox_info(addr, 4.0)
        if not info:
            return False, f"Δεν βρέθηκε συσκευή BleBox στη διεύθυνση {addr}"
        self.add_from_info(addr, info)
        return True, f"OK: {info.get('deviceName', '')} [{info.get('type', '')}]"

    # ── εκκίνηση / τερματισμός ──
    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="poller").start()
        threading.Thread(target=self._wx_loop, daemon=True, name="weather").start()
        self.start_server()
        if not self.cfg["devices"]:
            self.log("Δεν υπάρχουν συσκευές — αυτόματη σάρωση δικτύου…")
            self.start_scan(auto=True)

    # ── καιρός (Open-Meteo) ──
    def auto_locate(self):
        loc = locate_pc()
        label = loc.get("label") if loc["source"].startswith("Διεύθυνση IP") else None
        label = label or reverse_name(loc["lat"], loc["lon"])
        self.set_weather_location(label, loc["lat"], loc["lon"], True)
        acc = f" ±{loc['accuracy']:.0f} m" if loc.get("accuracy") else ""
        self.log(f"Αυτόματη τοποθεσία ({loc['source']}{acc}): {label}")
        return dict(loc, label=label)

    def _wx_loop(self):
        w0 = self.cfg.get("weather") or {}
        if w0.get("auto") or (w0.get("lat") is None and not w0.get("auto_tried")):
            w0["auto_tried"] = True
            self.save_cfg()
            try:
                self.auto_locate()
            except Exception as e:
                self.log(f"Αυτόματη τοποθεσία: {e}", "warn")
        while not self.stop_ev.is_set():
            w = self.cfg.get("weather") or {}
            if w.get("enabled") and w.get("lat") is not None:
                try:
                    self.update_weather()
                except Exception as e:
                    if str(e) != self.wx_err:
                        self.log(f"Open-Meteo: {e}", "warn")
                    self.wx_err = str(e)
            self.wx_wake.wait(max(5, int(w.get("interval_min", 15))) * 60)
            self.wx_wake.clear()

    def update_weather(self):
        w = self.cfg["weather"]
        data = fetch_weather(w["lat"], w["lon"])
        cur = data["current"]
        self.store.insert_weather([cur], replace=True)
        self.store.insert_weather([x for x in data["hourly"] if x["ts"] <= time.time()], replace=False)
        prev = ((self.wx or {}).get("current") or {}).get("status")
        with self.lock:
            self.wx = dict(data, place=w.get("place", ""), updated=time.time())
            self.wx_err = ""
            self.wx_counter += 1
        if prev != cur["status"]:
            self.log(f"Καιρός {w.get('place', '')}: {cur['icon']} {cur['text']} · {_fmt(cur['temp'])}°C · "
                     f"{cur['status']}")

    def set_weather_location(self, place, lat, lon, enabled=True):
        with self.lock:
            self.cfg["weather"].update(place=place, lat=float(lat), lon=float(lon), enabled=bool(enabled))
            self.save_cfg()
        self.log(f"Τοποθεσία καιρού: {place} ({float(lat):.4f}, {float(lon):.4f})")
        self.wx_wake.set()

    def wx_snapshot(self):
        with self.lock:
            if self.wx and time.time() - self.wx["updated"] < 3 * 3600:
                return dict(self.wx["current"])
        return None

    def wx_lookup(self, t0, t1):
        rows = self.store.weather_rows(t0 - 7200, t1)
        keys = [r[0] for r in rows]

        def f(ts):
            i = bisect.bisect_right(keys, ts) - 1
            if i >= 0 and ts - keys[i] <= 7200:
                return dict(zip(WX_KEYS, rows[i]))
            return None
        return f

    def wx_place(self):
        return dict(self.cfg.get("weather") or {})

    def weather_points(self, hours):
        t1 = time.time()
        rows, bucket = self.store.weather_history(t1 - hours * 3600, t1)
        return [[b, _r(t), _r(h), _r(p), _r(sn), None if c is None else int(c), _r(sun), _r(cl), _r(wd)]
                for b, t, h, p, sn, c, sun, cl, wd in rows]

    def weather_dict(self):
        w = self.cfg.get("weather") or {}
        with self.lock:
            wx = self.wx
            out = {"labels": labels(self.cfg), "enabled": bool(w.get("enabled")), "place": w.get("place", ""), "lat": w.get("lat"),
                   "lon": w.get("lon"), "error": self.wx_err, "updated": wx["updated"] if wx else None,
                   "current": wx["current"] if wx else None, "daily": wx["daily"] if wx else []}
            if wx:
                now = time.time()
                out["next_hours"] = [x for x in wx["hourly"] if now - 3600 <= x["ts"] <= now + 24 * 3600]
        return out

    def pdf_bytes(self, dids, t0, t1):
        """Όμορφη αναφορά PDF για τις συσκευές dids (None = όλες) στο διάστημα t0..t1."""
        known = {d["id"]: d for d in self.devices()}
        by = {}
        for r in self.store.rows(list(dids) if dids else None, t0, t1):
            by.setdefault(r[1], []).append(r)
        order = [i for i in known if i in by] + sorted(i for i in by if i not in known)   # και αισθητήρες που αφαιρέθηκαν
        devs = []
        for i in order:
            rows = by[i]
            d = known.get(i, {})
            devs.append({"id": i, "name": d.get("name") or rows[-1][2] or i, "ip": d.get("ip") or rows[-1][3] or "",
                         "rows": rows})
        if not devs:
            raise RuntimeError("Δεν υπάρχουν μετρήσεις στο διάστημα")
        wx = [dict(zip(WX_KEYS, r)) for r in self.store.weather_rows(t0, t1)]
        al = self.cfg.get("alarms") or {}
        lo_, hi_ = float(al.get("hum_min", 30) or 30), float(al.get("hum_max", 60) or 60)
        if not al.get("enabled") or hi_ - lo_ < 5:
            lo_, hi_ = 30.0, 60.0
        info = {"app": APP_NAME, "version": APP_VERSION, "author": AUTHOR, "team": TEAM, "t0": t0, "t1": t1,
                "devices": devs, "weather": wx, "wxf": self.wx_lookup(t0, t1) if wx else None,
                "place": (self.cfg.get("weather") or {}).get("place", "") if wx else "",
                "labels": labels(self.cfg), "hum_band": (lo_, hi_)}
        return build_pdf_report(info)

    def export_bytes(self, kind, rows, t0, t1):
        if kind == "pdf":
            ids = sorted({r[1] for r in rows})
            return self.pdf_bytes(ids or None, t0, t1)
        wxf = self.wx_lookup(t0, t1)
        if kind == "csv":
            return csv_bytes(rows, self.cfg["export"].get("greek_excel", True), wxf)
        return xml_bytes(rows, t0, t1, wxf, self.wx_place())

    def shutdown(self):
        self.stop_ev.set()
        self.wx_wake.set()
        self.wake_ev.set()
        self.scan_stop.set()
        self.stop_server()

    def poll_now(self):
        self.wake_ev.set()

    # ── κύκλος καταγραφής ──
    def _loop(self):
        while not self.stop_ev.is_set():
            try:
                self.poll_once()
            except Exception as e:
                self.log(f"Σφάλμα καταγραφής: {e}", "err")
            try:
                self._daily_tasks()
            except Exception as e:
                self.log(f"Σφάλμα εργασιών: {e}", "err")
            try:
                self._guide_watch()
            except Exception as e:
                self.log(f"Οδηγός κινητού PDF: {e}", "warn")
            secs = max(2, int(self.cfg.get("poll_seconds", 60)))
            self.wake_ev.wait(secs)
            self.wake_ev.clear()

    # ── 📄 phone guide PDF: made again by itself whenever the server's addresses change (new WiFi / place / Tailscale) ──
    GUIDE_NAME = "AirSense_Phone_Setup_GR_EN.pdf"

    def guide_paths(self):
        paths = [os.path.join(EXPORT_DIR, self.GUIDE_NAME)]
        try:                                       # board: also in the user's home folder (scp / AirSense Remote)
            u = open("/var/lib/airsense/user").read().strip() if os.path.exists("/var/lib/airsense/user") else ""
            if u:
                import pwd
                home = pwd.getpwnam(u).pw_dir
                if os.path.isdir(home):
                    paths.append(os.path.join(home, self.GUIDE_NAME))
        except Exception:
            pass
        return paths

    def _guide_watch(self, force=False):
        now = time.time()
        if not force and now - getattr(self, "_guide_checked", 0) < 60:
            return
        self._guide_checked = now
        urls = [(l, u) for l, u in self.server_urls() if "127.0.0.1" not in u]
        if not urls:
            return
        sig = json.dumps([u for _l, u in urls] + [bool(self.cfg["server"].get("pin"))], sort_keys=True)
        main = self.guide_paths()[0]
        if not force and sig == self.cfg.get("guide_sig") and os.path.exists(main):
            return
        try:
            data = build_setup_pdf(urls, bool(self.cfg["server"].get("pin")), APP_VERSION)
        except Exception as e:
            if sig != getattr(self, "_guide_err_sig", None):
                self._guide_err_sig = sig
                self.log(f"Οδηγός κινητού PDF: δεν έγινε ({e})", "warn")
            return
        saved = []
        for fn in self.guide_paths():
            try:
                os.makedirs(os.path.dirname(fn), exist_ok=True)
                with open(fn, "wb") as f:
                    f.write(data)
                if fn.startswith("/home/") and os.path.exists("/var/lib/airsense/user"):
                    import pwd
                    pw = pwd.getpwnam(open("/var/lib/airsense/user").read().strip())
                    os.chown(fn, pw.pw_uid, pw.pw_gid)
                saved.append(fn)
            except Exception:
                pass
        first = "guide_sig" not in self.cfg
        self.cfg["guide_sig"] = sig
        self.save_cfg()
        self.guide_ready = (now, saved[0] if saved else "")
        self.log(("📄 Οδηγός κινητού PDF έτοιμος: " if first else "📄 Νέο δίκτυο → νέος οδηγός κινητού PDF: ")
                 + " · ".join(saved) + " — " + ", ".join(u for _l, u in urls), "info")

    def calib(self, did):
        c = (self.cfg.get("calib") or {}).get(did) or {}
        return {"t_off": float(c.get("t_off", 0)), "h_off": float(c.get("h_off", 0)),
                "t_mul": float(c.get("t_mul", 1)), "h_mul": float(c.get("h_mul", 1))}

    def apply_calib(self, did, raw):
        t, h = calibrate_values(raw["t"], raw["h"], self.calib(did))
        return {"t": t, "h": h, "dp": dew_point(t, h), "ah": abs_humidity(t, h),
                "raw_t": raw["t"], "raw_h": raw["h"], "extra": raw.get("extra", {})}

    def _read_dev(self, d):
        try:
            return True, self.apply_calib(d["id"], read_sensors(d["ip"], self._path_cache)), ""
        except Exception as e:
            return False, None, str(e)

    def poll_once(self):
        devs = [d for d in self.devices() if d.get("enabled", True)]
        if not devs:
            # no sensor yet (e.g. it was not on the WiFi at the first start) → keep looking every 5 minutes
            now = time.time()
            if self.cfg.get("auto_add_sensors", True) and now - self._last_rescan > 300:
                self._last_rescan = now
                self.log("Δεν υπάρχει αισθητήρας ακόμα — αυτόματη αναζήτηση στο δίκτυο…")
                self.start_scan(auto=True)
            return
        with ThreadPoolExecutor(max_workers=min(8, len(devs))) as ex:
            results = list(ex.map(self._read_dev, devs))
        now = time.time()
        need_rescan = False
        for d, (ok, data, err) in zip(devs, results):
            did, name = d["id"], d.get("name", d["id"])
            with self.lock:
                st = self.live.setdefault(did, {"fails": 0})
                was_off = st.get("online") is False
                if ok:
                    st.update(online=True, error="", fails=0, ts=now, t=data["t"], h=data["h"],
                              dp=data["dp"], ah=data["ah"], raw_t=data["raw_t"], raw_h=data["raw_h"])
                else:
                    st["fails"] = st.get("fails", 0) + 1
                    st["error"] = err
                    if st["fails"] >= 2:
                        st["online"] = False
                fails = st["fails"]
            if ok:
                self.store.insert(now, did, name, d["ip"], data)
                self._append_daily_csv(now, did, name, d["ip"], data)
                self._check_alarms(d, data)
                if was_off:
                    self.log(f"{name}: ξανά online")
            else:
                if fails == 3:
                    self.log(f"{name} ({d['ip']}): εκτός σύνδεσης — {err}", "warn")
                    self._offline_alarm(d)
                if fails >= 3:
                    need_rescan = True
        self.poll_counter += 1
        if need_rescan and now - self._last_rescan > 600:          # a sensor is lost → look every 10 min
            self._last_rescan = now
            self.log("Αναζήτηση συσκευών που άλλαξαν IP…")
            self.start_scan(auto=True)

    # ── ημερήσια αρχεία ──
    def _append_daily_csv(self, ts, did, name, ip, r):
        if not self.cfg["export"].get("daily_files", True):
            return
        greek = self.cfg["export"].get("greek_excel", True)
        path = os.path.join(DAILY_DIR, datetime.fromtimestamp(ts).strftime("%Y-%m-%d") + ".csv")
        new = not os.path.exists(path)
        try:
            with open(path, "a", newline="", encoding="utf-8-sig" if new else "utf-8") as f:
                w = csv.writer(f, delimiter=";" if greek else ",", lineterminator="\r\n")
                if new:
                    w.writerow(CSV_HEAD)
                w.writerow(csv_row((int(ts), did, name, ip, r["t"], r["h"], r["dp"], r["ah"]), greek, self.wx_snapshot()))
        except Exception as e:
            self.log(f"CSV: {e}", "err")

    def _write_daily_xml(self, date_str):
        d0 = datetime.strptime(date_str, "%Y-%m-%d")
        t0, t1 = d0.timestamp(), (d0 + timedelta(days=1)).timestamp() - 1
        rows = self.store.rows(None, t0, t1)
        if rows:
            with open(os.path.join(DAILY_DIR, date_str + ".xml"), "wb") as f:
                f.write(self.export_bytes("xml", rows, t0, t1))

    def _daily_tasks(self):
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        if self.cfg["export"].get("daily_files", True):
            if today != self._cur_date:
                self._write_daily_xml(self._cur_date)
                self._cur_date = today
            if time.time() - self._last_xml > 900:
                self._last_xml = time.time()
                self._write_daily_xml(today)
        e = self.cfg["email"]
        if e.get("enabled") and e.get("daily_report") and self.cfg.get("last_report_date") != today:
            try:
                hh, mm = [int(x) for x in e.get("report_time", "08:00").split(":")[:2]]
            except Exception:
                hh, mm = 8, 0
            if (now.hour, now.minute) >= (hh, mm):
                self.cfg["last_report_date"] = today
                self.save_cfg()
                threading.Thread(target=self.send_report, kwargs={"hours": 24}, daemon=True).start()

    # ── ειδοποιήσεις ──
    def _alarm(self, key, subject, body):
        a = self.cfg["alarms"]
        now = time.time()
        if now - self.alarm_last.get(key, 0) < float(a.get("cooldown_min", 60)) * 60:
            return
        self.alarm_last[key] = now
        self.log("⚠ " + subject, "warn")
        e = self.cfg["email"]
        if e.get("enabled") and e.get("alarm_mails", True):
            def run():
                try:
                    send_mail(e, f"[{APP_NAME}] {subject}", body)
                    self.log("Στάλθηκε email ειδοποίησης")
                except Exception as ex:
                    self.log(f"Email ειδοποίησης απέτυχε: {ex}", "err")
            threading.Thread(target=run, daemon=True).start()

    def _check_alarms(self, d, r):
        a = self.cfg["alarms"]
        if not a.get("enabled"):
            return
        name = d.get("name", d["id"])
        stamp = datetime.now().strftime("%d/%m/%Y %H:%M")
        checks = [
            ("t_low", r["t"] is not None and r["t"] < float(a["temp_min"]),
             f"{name}: Χαμηλή θερμοκρασία {r['t']:.1f}°C (όριο {a['temp_min']}°C)" if r["t"] is not None else ""),
            ("t_high", r["t"] is not None and r["t"] > float(a["temp_max"]),
             f"{name}: Υψηλή θερμοκρασία {r['t']:.1f}°C (όριο {a['temp_max']}°C)" if r["t"] is not None else ""),
            ("h_low", r["h"] is not None and r["h"] < float(a["hum_min"]),
             f"{name}: Χαμηλή υγρασία {r['h']:.1f}% (όριο {a['hum_min']}%)" if r["h"] is not None else ""),
            ("h_high", r["h"] is not None and r["h"] > float(a["hum_max"]),
             f"{name}: Υψηλή υγρασία {r['h']:.1f}% (όριο {a['hum_max']}%)" if r["h"] is not None else ""),
        ]
        for key, hit, text in checks:
            if hit:
                body = (f"{text}\n\nΣυσκευή: {name} ({d['ip']})\nΏρα: {stamp}\n"
                        f"Θερμοκρασία: {_fmt(r['t'])} °C\nΥγρασία: {_fmt(r['h'])} %RH\n"
                        f"Σημείο δρόσου: {_fmt(r['dp'])} °C\n\n— {APP_NAME}")
                self._alarm(f"{d['id']}:{key}", text, body)

    def _offline_alarm(self, d):
        a = self.cfg["alarms"]
        if a.get("enabled") and a.get("offline", True):
            name = d.get("name", d["id"])
            self._alarm(f"{d['id']}:offline", f"{name}: εκτός σύνδεσης",
                        f"Η συσκευή {name} ({d['ip']}) δεν απαντά από "
                        f"{datetime.now().strftime('%d/%m/%Y %H:%M')}.\n\n— {APP_NAME}")

    # ── αναφορές email ──
    def report_text(self, hours=24):
        t1 = time.time()
        t0 = t1 - hours * 3600
        lines = [f"{APP_NAME} — Αναφορά τελευταίων {hours} ωρών",
                 f"Από {_tstr(t0)} έως {_tstr(t1)}", ""]
        wd = self.weather_dict()
        if wd.get("current"):
            c = wd["current"]
            lines += [f"Καιρός ({wd['place']}, Open-Meteo): {c['text']} · {_fmt(c['temp'])}°C · υγρασία {_fmt(c['hum'], 0)}% · "
                      f"{c['status']}"]
            stat = {}
            for r in self.store.weather_rows(t0, t1):
                stat[r[14]] = stat.get(r[14], 0) + 1
            if stat:
                lines.append("   Καταστάσεις διαστήματος: " + ", ".join(f"{k}: {v}" for k, v in sorted(stat.items(), key=lambda x: -x[1])))
            for dd in wd["daily"][:3]:
                lines.append(f"   {dd['day']}: {dd['text']} {_fmt(dd['tmin'])}…{_fmt(dd['tmax'])}°C, βροχή {_fmt(dd['precip'])} mm"
                             f" ({_fmt(dd['prob'], 0)}%)")
            lines.append("")
        for d in self.devices():
            c, tmin, tavg, tmax, hmin, havg, hmax = self.store.stats(d["id"], t0, t1)
            st = self.live.get(d["id"], {})
            lines += [f"■ {d.get('name')}  ({d['ip']})",
                      f"   Μετρήσεις: {c}",
                      f"   Θερμοκρασία  min/μέση/max: {_fmt(tmin)} / {_fmt(tavg)} / {_fmt(tmax)} °C",
                      f"   Υγρασία      min/μέση/max: {_fmt(hmin)} / {_fmt(havg)} / {_fmt(hmax)} %RH",
                      f"   Τελευταία: {_fmt(st.get('t'))} °C, {_fmt(st.get('h'))} %RH"
                      f" ({'online' if st.get('online') else 'offline'})", ""]
        lines.append(f"— {APP_NAME} v{APP_VERSION} · {AUTHOR}")
        return "\n".join(lines), t0, t1

    def send_report(self, hours=24):
        try:
            body, t0, t1 = self.report_text(hours)
            rows = self.store.rows(None, t0, t1)
            stamp = datetime.now().strftime("%Y%m%d_%H%M")
            att = []
            if self.cfg["email"].get("attach_pdf", True) and rows:
                try:
                    att.append((f"AirSense_{stamp}.pdf", self.pdf_bytes(None, t0, t1), "application", "pdf"))
                except Exception as e:
                    self.log(f"PDF αναφορά δεν δημιουργήθηκε: {e}", "warn")
            att += [(f"AirSense_{stamp}.csv", self.export_bytes("csv", rows, t0, t1), "text", "csv"),
                    (f"AirSense_{stamp}.xml", self.export_bytes("xml", rows, t0, t1), "application", "xml")]
            send_mail(self.cfg["email"], f"[{APP_NAME}] Αναφορά {datetime.now().strftime('%d/%m/%Y')}", body, att)
            self.log("Στάλθηκε email αναφοράς")
            return True, "Η αναφορά στάλθηκε"
        except Exception as e:
            self.log(f"Αποστολή αναφοράς απέτυχε: {e}", "err")
            return False, f"Σφάλμα: {e}"

    # ── γρήγορη σύνδεση email ──
    def _mail_ready(self, e):
        if not e.get("to"):
            e["to"] = e.get("user", "")
        if not e.get("enabled"):
            self.cfg["last_report_date"] = datetime.now().strftime("%Y-%m-%d")   # πρώτη αναφορά αύριο
        e["enabled"] = True

    def gmail_login(self, user, app_pw, to=""):
        """Google: email + κωδικός εφαρμογής → έλεγχος σύνδεσης → αποθήκευση."""
        user = user.strip()
        app_pw = re.sub(r"\s+", "", app_pw)
        if "@" not in user or len(app_pw) < 8:
            return False, "Γράψτε το email και τον κωδικό εφαρμογής (16 γράμματα)"
        e = dict(self.cfg["email"], host="smtp.gmail.com", port=587, security="STARTTLS", auth="password",
                 user=user, password=enc_secret(app_pw))
        try:
            smtp_check(e)
        except Exception as ex:
            return False, str(ex)
        with self.lock:
            e["oauth_refresh"] = ""
            if to.strip():
                e["to"] = to.strip()
            self._mail_ready(e)
            self.cfg["email"].clear()
            self.cfg["email"].update(e)
            self.save_cfg()
        self.log(f"✉ Συνδέθηκε Google: {user}")
        return True, f"✔ Συνδέθηκε: {user}"

    def ms_login_start(self, client_id=""):
        """Microsoft: ξεκινά σύνδεση με κωδικό συσκευής· η πρόοδος στο self.ms_flow."""
        e = self.cfg["email"]
        if client_id.strip():
            e["ms_client_id"] = client_id.strip()
            self.save_cfg()
        cid = ms_client_id(e)
        if not cid:
            self.ms_flow = {"stage": "need_id", "msg": "Χρειάζεται Microsoft App ID (μία φορά)"}
            return self.ms_flow
        try:
            j = _form_post(MS_AUTH + "devicecode", {"client_id": cid, "scope": MS_SCOPE})
        except Exception as ex:
            self.ms_flow = {"stage": "error", "msg": f"Χωρίς internet; ({ex})"}
            return self.ms_flow
        if "user_code" not in j:
            self.ms_flow = {"stage": "error", "msg": j.get("error_description", str(j))[:300]}
            return self.ms_flow
        flow = {"stage": "wait", "code": j["user_code"], "url": j.get("verification_uri", "https://microsoft.com/devicelogin"),
                "msg": "Ανοίξτε τη σελίδα, γράψτε τον κωδικό και πατήστε «Αποδοχή»", "id": time.time()}
        self.ms_flow = flow

        def poll():
            dl = time.time() + int(j.get("expires_in", 900))
            iv = int(j.get("interval", 5))
            while time.time() < dl and self.ms_flow is flow:
                time.sleep(iv)
                try:
                    t = _form_post(MS_AUTH + "token", {"client_id": cid, "device_code": j["device_code"],
                                                       "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
                except Exception:
                    continue
                err = t.get("error")
                if err == "authorization_pending":
                    continue
                if err == "slow_down":
                    iv += 5
                    continue
                if err or "refresh_token" not in t:
                    flow.update(stage="error", msg={"authorization_declined": "Ακυρώθηκε από τον χρήστη",
                                                    "expired_token": "Ο κωδικός έληξε — ξαναδοκιμάστε"}.get(
                        err, t.get("error_description", str(err))[:300]))
                    return
                c = _jwt_claims(t.get("id_token", ""))
                user = c.get("email") or c.get("preferred_username") or ""
                with self.lock:
                    e = self.cfg["email"]
                    e.update(auth="oauth_ms", oauth_refresh=enc_secret(t["refresh_token"]), user=user,
                             host=ms_smtp_host(user), port=587, security="STARTTLS", password="", sender="")
                    _MS_TOK[e["oauth_refresh"]] = (t["access_token"], time.time() + int(t.get("expires_in", 3600)))
                    self._mail_ready(e)
                    self.save_cfg()
                self.log(f"✉ Συνδέθηκε Microsoft: {user}")
                flow.update(stage="ok", user=user, msg=f"✔ Συνδέθηκε: {user}")
                return
            if self.ms_flow is flow and flow["stage"] == "wait":
                flow.update(stage="error", msg="Ο κωδικός έληξε — ξαναδοκιμάστε")
        threading.Thread(target=poll, daemon=True).start()
        return flow

    def mail_logout(self):
        with self.lock:
            e = self.cfg["email"]
            e.update(auth="password", oauth_refresh="", password="", enabled=False)
            self.save_cfg()
        self.ms_flow = {}
        self.log("✉ Αποσύνδεση email")

    def send_test(self):
        try:
            send_mail(self.cfg["email"], f"[{APP_NAME}] Δοκιμαστικό email",
                      f"Το email λειτουργεί σωστά.\n\n{datetime.now():%d/%m/%Y %H:%M}\n— {APP_NAME}")
            self.log("Δοκιμαστικό email: OK")
            return True, "Στάλθηκε!"
        except Exception as e:
            self.log(f"Δοκιμαστικό email απέτυχε: {e}", "err")
            return False, str(e)

    # ── σάρωση ──
    def start_scan(self, subnets_text=None, auto=False):
        with self.lock:
            if self.scan["running"]:
                return False
            self.scan.update(running=True, done=0, total=0, results=[], auto=auto, finished=None)
        self.scan_stop.clear()
        threading.Thread(target=self._scan_worker, args=(subnets_text, auto), daemon=True).start()
        return True

    def _scan_worker(self, subnets_text, auto):
        try:
            nets = build_networks(self.cfg.get("subnets", "") if subnets_text is None else subnets_text)
            hosts = []
            for n in nets:
                hosts += [str(h) for h in n.hosts()]
            hosts = list(dict.fromkeys(hosts))
            with self.lock:
                self.scan["total"] = len(hosts)
            self.log("Σάρωση: " + (", ".join(str(n) for n in nets) or "κανένα δίκτυο") + f" ({len(hosts)} διευθύνσεις)")
            ex = ThreadPoolExecutor(max_workers=128)
            futs = [ex.submit(probe_host, h) for h in hosts]
            for f in as_completed(futs):
                if self.scan_stop.is_set():
                    break
                r = f.result()
                with self.lock:
                    self.scan["done"] += 1
                    if r:
                        self.scan["results"].append(r)
            ex.shutdown(wait=False, cancel_futures=True)
            arp = arp_table()
            with self.lock:
                for r in self.scan["results"]:
                    r["mac"] = arp.get(r["ip"], "")
            self._apply_scan(list(self.scan["results"]))
        except Exception as e:
            self.log(f"Σφάλμα σάρωσης: {e}", "err")
        finally:
            with self.lock:
                self.scan["running"] = False
                self.scan["finished"] = time.time()
                self.scan["results"].sort(key=lambda r: (not r["blebox"], ipaddress.ip_address(r["ip"])))

    def _apply_scan(self, results):
        bb = [r for r in results if r["blebox"]]
        changed = False
        for r in bb:
            ex = self.device(r["id"]) if r["id"] else None
            if ex:
                if r.get("mac") and ex.get("mac") != r["mac"]:
                    ex["mac"] = r["mac"]
                    changed = True
                if ex["ip"] != r["ip"] and ":" not in ex["ip"]:
                    self.log(f"{ex['name']}: νέα IP {ex['ip']} → {r['ip']}")
                    with self.lock:
                        ex["ip"] = r["ip"]
                    changed = True
            elif self.cfg.get("auto_add_sensors", True) and r["type"].lower() in SENSOR_TYPES:
                self.add_scan_result(r)
        if changed:
            self.save_cfg()
            self.wake_ev.set()
        self.log(f"Σάρωση ολοκληρώθηκε: {len(bb)} BleBox, {len(results) - len(bb)} άλλες συσκευές HTTP")

    # ── δεδομένα για γραφήματα ──
    def history_points(self, did, hours):
        t1 = time.time()
        t0 = t1 - hours * 3600
        rows, bucket = self.store.history(did, t0, t1)
        gap = max(3 * bucket, 3 * int(self.cfg.get("poll_seconds", 60)) + 5)
        pts, prev = [], None
        for b, t, h, dp in rows:
            if prev is not None and b - prev > gap:
                pts.append([prev + 1, None, None, None])
            pts.append([b, _r(t), _r(h), _r(dp)])
            prev = b
        return pts

    # ── web server ──
    def start_server(self):
        self.stop_server()
        s = self.cfg["server"]
        if not s.get("enabled", True):
            self.server_error = ""
            return
        try:
            self.httpd = ThreadingHTTPServer(("0.0.0.0", int(s.get("port", 8765))), make_handler(self))
            self.httpd.daemon_threads = True
            threading.Thread(target=self.httpd.serve_forever, daemon=True, name="web").start()
            self.server_error = ""
            self.log(f"Web server ενεργός στη θύρα {s.get('port')}")
        except OSError as e:
            self.httpd = None
            self.server_error = str(e)
            self.log(f"Ο web server δεν ξεκίνησε: {e}", "err")

    def stop_server(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
            self.httpd = None

    def tailscale(self, force=False):
        if force or time.time() - self._ts_cache[0] > 60:
            self._ts_cache = (time.time(), tailscale_info())
        return self._ts_cache[1]

    def server_urls(self, force=False):
        port = self.cfg["server"].get("port", 8765)
        urls = [("Αυτός ο υπολογιστής", f"http://127.0.0.1:{port}")]
        for ip in lan_ipv4s():
            urls.append(("Τοπικό δίκτυο (WiFi/LAN)", f"http://{ip}:{port}"))
        ts = self.tailscale(force)
        if ts and ts.get("ip"):
            urls.append(("Tailscale (από παντού)", f"http://{ts['ip']}:{port}"))
        if ts and ts.get("dns"):
            urls.append(("Tailscale MagicDNS", f"http://{ts['dns']}:{port}"))
        return urls

    def status_dict(self):
        with self.lock:
            devs = []
            for d in self.cfg["devices"]:
                st = self.live.get(d["id"], {})
                devs.append({"id": d["id"], "name": d.get("name"), "ip": d["ip"], "type": d.get("type"),
                             "product": d.get("product"), "fv": d.get("fv"), "enabled": d.get("enabled", True),
                             "online": st.get("online"), "t": st.get("t"), "h": st.get("h"),
                             "dp": st.get("dp"), "ah": st.get("ah"), "ts": st.get("ts"), "error": st.get("error", "")})
            ev = [{"ts": t, "level": l, "msg": m} for t, l, m in list(self.events)[-40:]]
            sc = {k: self.scan[k] for k in ("running", "done", "total")}
            sc["found"] = len([r for r in self.scan["results"] if r["blebox"]])
        return {"app": APP_NAME, "version": APP_VERSION, "time": time.time(),
                "poll_seconds": self.cfg.get("poll_seconds", 60), "devices": devs, "log": ev, "scan": sc,
                "alarms": self.cfg["alarms"], "email_enabled": bool(self.cfg["email"].get("enabled")),
                "admin_set": bool((self.cfg.get("admin") or {}).get("hash")),
                # addresses of this server → the phone app fills the Tailscale address by itself
                "urls": [{"label": l, "url": u} for l, u in self.server_urls() if "127.0.0.1" not in u]}

    # ── API για την εφαρμογή Android ──
    def events_since(self, since):
        with self.lock:
            return [{"ts": t, "level": l, "msg": m} for t, l, m in self.events if t > since][-100:]

    def config_dict(self):
        e = self.cfg["email"]
        return {"poll_seconds": int(self.cfg.get("poll_seconds", 60)), "alarms": dict(self.cfg["alarms"]),
                "email": {"enabled": bool(e.get("enabled")), "daily_report": bool(e.get("daily_report")),
                          "report_time": e.get("report_time", "08:00"), "alarm_mails": bool(e.get("alarm_mails", True)),
                          "configured": bool(e.get("host") and e.get("to"))},
                "auto_add_sensors": bool(self.cfg.get("auto_add_sensors", True))}

    def update_config(self, b):
        with self.lock:
            if "poll_seconds" in b:
                self.cfg["poll_seconds"] = max(2, min(3600, int(b["poll_seconds"])))
            a = b.get("alarms") or {}
            for k in ("enabled", "offline"):
                if k in a:
                    self.cfg["alarms"][k] = bool(a[k])
            for k in ("temp_min", "temp_max", "hum_min", "hum_max"):
                if k in a:
                    self.cfg["alarms"][k] = float(a[k])
            if "cooldown_min" in a:
                self.cfg["alarms"]["cooldown_min"] = max(5, min(1440, int(a["cooldown_min"])))
            e = b.get("email") or {}
            for k in ("enabled", "daily_report", "alarm_mails"):
                if k in e:
                    self.cfg["email"][k] = bool(e[k])
            if re.fullmatch(r"\d{2}:\d{2}", str(e.get("report_time", ""))):
                self.cfg["email"]["report_time"] = e["report_time"]
            if "auto_add_sensors" in b:
                self.cfg["auto_add_sensors"] = bool(b["auto_add_sensors"])
            self.save_cfg()
        self.log("Οι ρυθμίσεις άλλαξαν από το κινητό")
        self.wake_ev.set()

    def update_device(self, b):
        did = str(b.get("id", ""))
        d = self.device(did)
        if not d:
            return False, "Η συσκευή δεν βρέθηκε"
        if b.get("remove"):
            self.remove_device(did)
            return True, "Αφαιρέθηκε"
        with self.lock:
            if str(b.get("name", "")).strip():
                d["name"] = str(b["name"]).strip()[:60]
            if "enabled" in b:
                d["enabled"] = bool(b["enabled"])
            self.save_cfg()
        self.log(f"Συσκευή {d['name']} ενημερώθηκε από το κινητό")
        return True, "Αποθηκεύτηκε"

    def admin_ok(self, pw):
        a = self.cfg.get("admin") or {}
        return bool(a.get("hash")) and hmac.compare_digest(_pw_hash(str(pw), a["salt"])[1], a["hash"])

    def set_calib(self, did, b):
        if not self.device(did):
            raise ValueError("Η συσκευή δεν βρέθηκε")
        vals = {"t_off": max(-20.0, min(20.0, float(b.get("t_off", 0)))),
                "t_mul": max(0.5, min(1.5, float(b.get("t_mul", 1)))),
                "h_off": max(-40.0, min(40.0, float(b.get("h_off", 0)))),
                "h_mul": max(0.5, min(1.5, float(b.get("h_mul", 1))))}
        with self.lock:
            self.cfg.setdefault("calib", {})[did] = vals
            self.save_cfg()
        name = (self.device(did) or {}).get("name", did)
        self.log(f"Βαθμονόμηση {name} (από κινητό): θερμ. ×{vals['t_mul']:.3f} {vals['t_off']:+.2f}°C, "
                 f"υγρ. ×{vals['h_mul']:.3f} {vals['h_off']:+.2f}%")
        n = 0
        if b.get("recalc_hours"):
            n = self.store.recalibrate(did, time.time() - float(b["recalc_hours"]) * 3600, vals)
            self.log(f"Επανυπολογίστηκαν {n} παλιές μετρήσεις")
        self.poll_counter += 1
        self.wake_ev.set()
        return n


def _r(v):
    return None if v is None else round(v, 2)


def _fmt(v, d=1):
    return "—" if v is None else f"{v:.{d}f}"


# ═══════════════════════════════════════════════════════════════════════════
# 10) Web εφαρμογή (κινητό)
# ═══════════════════════════════════════════════════════════════════════════
ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#0f131a"/>
<path d="M32 8C32 8 14 30 14 40a18 18 0 0 0 36 0C50 30 32 8 32 8z" fill="#3fa7ff"/>
<path d="M24 41a8 8 0 0 0 8 8" stroke="#fff" stroke-width="4" fill="none" stroke-linecap="round"/></svg>"""

INDEX_HTML = r"""<!doctype html><html lang="el"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0f131a" media="(prefers-color-scheme: dark)"><meta name="theme-color" content="#f4f6fa" media="(prefers-color-scheme: light)"><link rel="manifest" href="/manifest.json">
<link rel="icon" href="/icon.svg"><link rel="apple-touch-icon" href="/icon.svg">
<meta name="apple-mobile-web-app-capable" content="yes"><title>AirSense</title>
<style>
:root{--bg:#0f131a;--card:#171c26;--line:#262d3b;--txt:#e6ebf5;--mut:#8b96ab;--t:#ff9f43;--h:#3fa7ff;--d:#a78bfa;--ok:#2ecc71;--bad:#ff5c5c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header{position:sticky;top:0;background:rgba(15,19,26,.93);backdrop-filter:blur(8px);padding:12px 16px;padding-top:max(12px,env(safe-area-inset-top));display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--line);z-index:5}
header h1{font-size:17px;margin:0;flex:1}.dot{width:10px;height:10px;border-radius:50%;background:var(--mut)}
main{padding:14px;max-width:1100px;margin:auto}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px}
.dev{cursor:pointer}.dev.sel{border-color:#2b6cff}
.nm{font-weight:600;display:flex;justify-content:space-between;gap:8px;align-items:center}
.vals{display:flex;gap:22px;margin:12px 0 8px}
.big{font-size:36px;font-weight:700;line-height:1}.big small{font-size:15px;color:var(--mut);font-weight:500}
.t{color:var(--t)}.h{color:var(--h)}.d{color:var(--d)}.mut{color:var(--mut);font-size:13px}
.badge{font-size:12px;padding:2px 9px;border-radius:99px;background:#232a38;color:var(--mut)}
.badge.ok{background:rgba(46,204,113,.15);color:var(--ok)}.badge.bad{background:rgba(255,92,92,.15);color:var(--bad)}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
select,button{font:inherit;color:var(--txt);background:#1e2533;border:1px solid var(--line);border-radius:10px;padding:9px 12px}
button{cursor:pointer}button.pri{background:#2b6cff;border-color:#2b6cff}button.on{background:#2b6cff33;border-color:#2b6cff}
canvas{width:100%;height:320px;display:block;touch-action:pan-y;margin-top:6px}
h2{font-size:13px;margin:20px 0 10px;color:var(--mut);font-weight:600;text-transform:uppercase;letter-spacing:.07em}
.log{font-family:ui-monospace,Consolas,monospace;font-size:12px;max-height:260px;overflow:auto;white-space:pre-wrap;line-height:1.5}
.warn{color:#ffc04d}.err{color:var(--bad)}
input{font:inherit;color:var(--txt);background:#1e2533;border:1px solid var(--line);border-radius:10px;padding:9px 12px;min-width:0}
.sec{border-top:1px solid var(--line);padding:12px 0}.sec .row{margin-top:8px}
.frm{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px;margin-top:8px}
.frm label{display:flex;flex-direction:column;font-size:12px;color:var(--mut);gap:4px}
#locRes button{display:block;width:100%;text-align:left;margin-top:6px}
footer{text-align:center;color:var(--mut);font-size:12px;padding:24px}
#toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#2b6cff;padding:10px 16px;border-radius:12px;display:none;z-index:9;max-width:90%}
.legend span{margin-right:14px}.o{color:#2ecc71}
.wxnow{display:flex;align-items:center;gap:14px;flex-wrap:wrap}.wxi{font-size:46px;line-height:1}
.wxt{font-size:30px;font-weight:700}.fc{display:flex;gap:8px;overflow-x:auto;margin-top:12px;padding-bottom:4px}
.fd{min-width:86px;background:#1e2533;border-radius:12px;padding:8px;text-align:center;font-size:12px}
@media (prefers-color-scheme: light){
:root{--bg:#f4f6fa;--card:#ffffff;--line:#d9dee8;--txt:#1a1f2b;--mut:#5d6778;--t:#e07b00;--h:#1a73e8;--d:#7c5ce0;--ok:#1e9e55;--bad:#d93636}
header{background:rgba(244,246,250,.93)!important}select,button,input,.fd{background:#eef1f6!important}
button.pri{background:#2b6cff!important;color:#fff}.badge{background:#e6eaf2}.warn{color:#b07800}.o{color:#1e9e55}
.pill{color:#1a56c4}#toast{color:#fff}}
.fd .i{font-size:26px}.pill{display:inline-block;padding:2px 10px;border-radius:99px;background:#2b6cff33;color:#9fc0ff;font-size:12px}.empty{color:var(--mut);text-align:center;padding:30px}
</style></head><body>
<header><div class="dot" id="dot"></div><h1>🌬 AirSense</h1><span class="mut" id="hdr"></span></header>
<main>
<div class="card" id="wx" style="display:none;margin-bottom:12px"></div>
<div class="grid" id="devs"><div class="card empty">Φόρτωση…</div></div>
<h2>Γράφημα</h2>
<div class="card">
 <div class="row"><select id="sel"></select><span id="ranges" class="row"></span></div>
 <div class="legend mut" style="margin-top:10px"><span class="t">● Θερμοκρασία °C</span><span class="h">● Υγρασία %RH</span><span class="d">┄ Σημ. δρόσου</span><span class="o" id="lgOut">┄ Έξω (Open-Meteo)</span><span style="color:#5aa9ff">▮ Βροχή</span></div>
 <div class="mut" id="stats" style="margin-top:4px"></div>
 <canvas id="cv"></canvas>
</div>
<h2>Ενέργειες</h2>
<div class="card row">
 <button class="pri" onclick="act('poll')">⟳ Μέτρηση τώρα</button>
 <button onclick="act('scan')">📡 Σάρωση δικτύου</button>
 <button onclick="dl('csv')">⬇ CSV</button>
 <button onclick="dl('xml')">⬇ XML</button>
 <button class="pri" onclick="dl('pdf')">📄 PDF αναφορά</button>
 <button onclick="act('report')">✉ Email αναφορά</button>
</div>
<h2>Διαχείριση</h2>
<div class="card">
 <button onclick="admOpen()">🔐 Ρυθμίσεις διαχειριστή</button> <span class="mut" id="admMsg"></span>
 <div id="adm" style="display:none;margin-top:12px">
  <div class="sec"><b>📍 Τοποθεσία καιρού</b> <span class="mut" id="admPlace"></span>
   <div class="row"><input id="locQ" placeholder="Πόλη / χωριό"><button onclick="locFind()">🔍</button><button onclick="post('/api/weather/auto',{}).then(admLoad)">🛰 Αυτόματα</button></div>
   <div id="locRes"></div></div>
  <div class="sec"><b>🏷 Λεκτικά</b> <span class="mut">π.χ. Σαλόνι / Αυλή</span>
   <div class="row"><input id="lbIn" placeholder="Μέσα" maxlength="30"><input id="lbOut" placeholder="Έξω" maxlength="30">
   <button onclick="post('/api/admin/labels',{admin:ADM,inside:$('lbIn').value,outside:$('lbOut').value}).then(()=>loadWx())">💾</button></div></div>
  <div class="sec"><b>➕ Προσθήκη αισθητήρα με IP</b>
   <div class="row"><input id="addIp" placeholder="192.168.1.50"><button onclick="post('/api/device/add',{ip:$('addIp').value}).then(loadStatus)">Προσθήκη</button></div></div>
  <div class="sec"><b>⏱ Μέτρηση κάθε (δευτ.)</b>
   <div class="row"><input id="poll" type="number" min="2" style="width:110px"><button onclick="post('/api/config',{poll_seconds:+$('poll').value})">💾</button></div></div>
  <div class="sec"><b>✉ Email (SMTP)</b>
   <div class="row"><button class="pri" onclick="gOpen()">🔵 Σύνδεση Google</button><button class="pri" onclick="msGo()">🟦 Σύνδεση Outlook</button>
    <button onclick="if(confirm('Αποσύνδεση email;'))post('/api/admin/email/logout',{admin:ADM}).then(admLoad)">⏏</button></div>
   <div id="eStat" class="mut"></div>
   <div id="gBox" style="display:none" class="frm">
    <div class="mut">1) Βάλτε το Gmail σας · 2) πατήστε 🔑 και φτιάξτε «Κωδικό εφαρμογής» (όνομα: AirSense) · 3) επικολλήστε τον.</div>
    <label>Gmail<input id="gUser" placeholder="you@gmail.com"></label>
    <label>Κωδικός εφαρμογής <a href="https://myaccount.google.com/apppasswords" target="_blank">🔑 άνοιγμα</a><input id="gPw" placeholder="abcd efgh ijkl mnop"></label>
    <div class="row"><button class="pri" onclick="gLogin()">✔ Σύνδεση & έλεγχος</button></div></div>
   <div id="msBox" style="display:none;text-align:center">
    <div class="mut">Ανοίξτε <a id="msUrl" target="_blank" href="https://microsoft.com/devicelogin">microsoft.com/devicelogin</a> και γράψτε:</div>
    <div id="msCode" style="font-size:28px;font-weight:800;letter-spacing:3px;margin:6px 0">…</div>
    <div class="row" style="justify-content:center"><button onclick="navigator.clipboard&&navigator.clipboard.writeText($('msCode').textContent)">📋 Αντιγραφή</button></div>
    <div id="msMsg" class="mut"></div></div>
   <div id="msId" style="display:none" class="frm"><div class="mut">Μία φορά: Microsoft App (client) ID — <a href="https://github.com/nikkpap/AirSense#-email-quick-login" target="_blank">οδηγίες</a></div>
    <label>App ID<input id="msCid" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"></label>
    <div class="row"><button class="pri" onclick="msGo($('msCid').value)">✔ Συνέχεια</button></div></div>
   <details><summary class="mut">⚙ Χειροκίνητες ρυθμίσεις</summary>
   <div class="frm">
    <label>Πάροχος<select id="eprov" onchange="eProv()"><option value="">—</option><option>Gmail</option><option>Outlook</option><option>Yahoo</option></select></label>
    <label>SMTP server<input id="ehost"></label><label>Θύρα<input id="eport" type="number"></label>
    <label>Ασφάλεια<select id="esec"><option>STARTTLS</option><option>SSL</option><option>Κανένα</option></select></label>
    <label>Χρήστης<input id="euser"></label><label>Κωδικός <span class="mut" id="epwh"></span><input id="epw" type="password" placeholder="(αμετάβλητος)"></label>
    <label>Αποστολέας<input id="efrom"></label><label>Παραλήπτες<input id="eto" placeholder="a@x.gr, b@y.gr"></label>
    <label>Ώρα αναφοράς<input id="etime" placeholder="08:00"></label>
   </div>
   <div class="row"><label><input type="checkbox" id="een"> Ενεργό</label><label><input type="checkbox" id="edaily"> Ημερήσια αναφορά</label><label><input type="checkbox" id="ealarm"> Email σε ειδοποίηση</label></div>
   <div class="row"><button class="pri" onclick="eSave()">💾 Αποθήκευση</button><button onclick="post('/api/admin/email/test',{admin:ADM})">✉ Δοκιμή</button></div>
   <div class="mut">Gmail: χρειάζεται «Κωδικός εφαρμογής» (App Password). Outlook/Hotmail: μόνο με «Σύνδεση Outlook».</div></details></div>
  <div class="sec"><b>🔑 PIN για web/κινητό</b>
   <div class="row"><input id="pin" placeholder="κενό = χωρίς PIN"><button onclick="pinSave()">💾</button></div></div>
  <div class="sec"><b>🔐 Νέος κωδικός διαχειριστή</b>
   <div class="row"><input id="npw" type="password"><button onclick="post('/api/admin/password',{admin:ADM,new:$('npw').value}).then(j=>{if(j.ok)ADM=$('npw').value;})">💾</button></div></div>
  <div class="mut" id="admInfo"></div>
 </div>
</div>
<h2>Καταγραφή συμβάντων</h2>
<div class="card log" id="log"></div>
</main>
<footer><a href="/setup.pdf" target="_blank" style="color:inherit">📄 Οδηγός κινητού (PDF) · Phone guide</a><br>AirSense v__VER__ · Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM</footer>
<div id="toast"></div>
<script>
let WX=null,WXP=[];
let PIN=localStorage.getItem('hl_pin')||'',S=null,cur=localStorage.getItem('hl_dev')||'',hours=+(localStorage.getItem('hl_h')||24),pts=[],hov=-1;
const RANGES=[[1,'1ώ'],[6,'6ώ'],[24,'24ώ'],[168,'7 ημ'],[720,'30 ημ']];
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(path,opt={}){opt.headers=Object.assign({'X-PIN':PIN},opt.headers||{});const r=await fetch(path,opt);
 if(r.status==401){const p=prompt('PIN πρόσβασης:');if(p===null)throw new Error('auth');PIN=p;localStorage.setItem('hl_pin',p);return api(path,opt);}
 return r.json();}
function toast(m){const t=$('toast');t.textContent=m;t.style.display='block';clearTimeout(t._h);t._h=setTimeout(()=>t.style.display='none',3500);}
const f=(v,d=1)=>v==null?'—':(+v).toFixed(d);
function ago(ts){if(!ts)return'ποτέ';const s=Math.round(Date.now()/1000-ts);if(s<60)return s+' δευτ. πριν';if(s<3600)return Math.round(s/60)+' λεπτά πριν';return new Date(ts*1000).toLocaleString('el-GR');}
async function loadWx(){try{WX=await api('/api/weather');$('lgOut').textContent='┄ '+LB().outside+' (Open-Meteo)';renderWx();if(S)render();}catch(e){}}
function ahum(t,rh){return 6.112*Math.exp(17.67*t/(t+243.5))*rh*2.1674/(273.15+t);}
function LB(){return (WX&&WX.labels)||{inside:'Μέσα',outside:'Έξω'};}
function diffHtml(d){const c=WX&&WX.enabled&&WX.current;if(!c||d.t==null||d.h==null||c.temp==null||c.hum==null)return'';
 const li=esc(LB().inside),lo=esc(LB().outside);
 const sg=(x,n=1)=>(x>0?'+':'')+x.toFixed(n),ai=ahum(d.t,d.h),ao=ahum(c.temp,c.hum),da=ai-ao;
 const v=Math.abs(da)<0.5?['mut','Ο αερισμός δεν αλλάζει σχεδόν την υγρασία']:(da>0?['o',`Αερισμός → ΜΕΙΩΝΕΙ την υγρασία (${li})`]:['warn',`Αερισμός → ΑΥΞΑΝΕΙ την υγρασία (${li})`]);
 return `<div class="mut" style="margin-top:6px">↕ ${li} − ${lo}: <b class="t">${sg(d.t-c.temp)}°C</b> · <b class="h">${sg(d.h-c.hum)}%</b> · απόλυτη ${ai.toFixed(1)} / ${ao.toFixed(1)} g/m³ (${li} / ${lo})</div><div class="${v[0]}" style="font-size:13px">💨 ${v[1]}</div>`;}
function renderWx(){const el=$('wx');if(!WX||!WX.enabled||!WX.current){el.style.display='none';return;}
 const c=WX.current;el.style.display='block';
 el.innerHTML=`<div class="wxnow"><div class="wxi">${c.icon}</div><div><div class="wxt">${f(c.temp)}°C</div>
 <div>${esc(c.text)} <span class="pill">${esc(c.status)}</span></div></div>
 <div class="mut" style="flex:1;min-width:200px">📍 ${esc(WX.place)} · αίσθηση ${f(c.feels)}°C<br>💧 ${f(c.hum,0)}% · 🌬 ${f(c.wind,0)} km/h · ☁ ${f(c.cloud,0)}%<br>
 🌧 ${f(c.rain)} mm · ❄ ${f(c.snow)} cm · ☀ ${c.sunshine==null?'—':Math.round(c.sunshine/60)+' λεπτά/ώρα'}</div></div>
 <div class="fc">${WX.daily.map(d=>`<div class="fd"><b>${esc(d.day)}</b><div class="i">${d.icon}</div>${f(d.tmin,0)}° / <b>${f(d.tmax,0)}°</b><br>
 🌧 ${f(d.precip)} mm ${d.prob==null?'':'· '+d.prob+'%'}<br>☀ ${d.sunshine==null?'—':(d.sunshine/3600).toFixed(1)+' ώρ.'}</div>`).join('')}</div>`;}
async function loadStatus(){try{S=await api('/api/status');render();$('dot').style.background='var(--ok)';}catch(e){$('dot').style.background='var(--bad)';}}
function render(){
 const D=S.devices;if(!cur&&D.length){cur=D[0].id;loadHist();}
 $('devs').innerHTML=D.length?D.map(d=>`<div class="card dev ${d.id==cur?'sel':''}" onclick="pick('${esc(d.id)}')">
  <div class="nm"><span>${esc(d.name)}</span><span class="badge ${d.online?'ok':(d.online===false?'bad':'')}">${d.online?'online':(d.online===false?'offline':'…')}</span></div>
  <div class="vals"><div class="big t">${f(d.t)}<small> °C</small></div><div class="big h">${f(d.h)}<small> %</small></div></div>
  <div class="mut">Σημείο δρόσου <b class="d">${f(d.dp)} °C</b> · Απόλυτη ${f(d.ah)} g/m³</div>${diffHtml(d)}
  <div class="mut">${esc(d.ip)} · ${ago(d.ts)}</div>${d.error&&!d.online?`<div class="mut err">${esc(d.error)}</div>`:''}</div>`).join('')
  :'<div class="card empty">Δεν υπάρχουν συσκευές.<br>Πατήστε «Σάρωση δικτύου».</div>';
 $('sel').innerHTML=D.map(d=>`<option value="${esc(d.id)}" ${d.id==cur?'selected':''}>${esc(d.name)}</option>`).join('');
 $('log').innerHTML=S.log.slice().reverse().map(e=>`<div class="${e.level}">${new Date(e.ts*1000).toLocaleTimeString('el-GR')}  ${esc(e.msg)}</div>`).join('');
 $('hdr').textContent=S.scan.running?`Σάρωση ${S.scan.done}/${S.scan.total}`:'κάθε '+S.poll_seconds+'″';
}
function pick(id){cur=id;localStorage.setItem('hl_dev',id);render();loadHist();}
$('sel').onchange=e=>pick(e.target.value);
function renderRanges(){$('ranges').innerHTML=RANGES.map(([h,l])=>`<button class="${h==hours?'on':''}" onclick="setH(${h})">${l}</button>`).join('');}
function setH(h){hours=h;localStorage.setItem('hl_h',h);renderRanges();loadHist();}
async function loadHist(){if(!cur){pts=[];draw();return;}
 try{const j=await api(`/api/history?id=${encodeURIComponent(cur)}&hours=${hours}`);pts=j.points;WXP=j.wx||[];}catch(e){pts=[];WXP=[];}
 const T=pts.map(p=>p[1]).filter(v=>v!=null),H=pts.map(p=>p[2]).filter(v=>v!=null);
 $('stats').textContent=T.length?`Θερμ. ${f(Math.min(...T))}…${f(Math.max(...T))} °C · Υγρ. ${f(Math.min(...H))}…${f(Math.max(...H))} % · ${pts.length} σημεία`:'';
 hov=-1;draw();}
function rng(a){if(!a.length)return[0,1];let lo=Math.min(...a),hi=Math.max(...a);if(hi-lo<1){lo-=.5;hi+=.5;}const p=(hi-lo)*.1;return[lo-p,hi+p];}
const LT=()=>matchMedia('(prefers-color-scheme: light)').matches;
matchMedia('(prefers-color-scheme: light)').addEventListener?.('change',()=>draw());
function draw(){const cv=$('cv'),dpr=devicePixelRatio||1,W=cv.clientWidth,H=cv.clientHeight;cv.width=W*dpr;cv.height=H*dpr;
 const c=cv.getContext('2d');c.scale(dpr,dpr);c.clearRect(0,0,W,H);c.font='11px system-ui';
 const P=pts.filter(p=>p[1]!=null||p[2]!=null);
 if(!P.length){c.fillStyle='#8b96ab';c.textAlign='center';c.fillText('Δεν υπάρχουν δεδομένα για το διάστημα',W/2,H/2);return;}
 const L=40,R=40,T=10,B=26,pw=W-L-R,ph=H-T-B;let x0=P[0][0],x1=P[P.length-1][0];if(x1==x0){x0-=60;x1+=60;}
 const tv=[],hv=[];P.forEach(p=>{if(p[1]!=null)tv.push(p[1]);if(p[3]!=null)tv.push(p[3]);if(p[2]!=null)hv.push(p[2]);});
 const WP=WXP.filter(w=>w[0]>=x0&&w[0]<=x1);WP.forEach(w=>{if(w[1]!=null)tv.push(w[1]);if(w[2]!=null)hv.push(w[2]);});
 const [t0,t1]=rng(tv),[h0,h1]=rng(hv);
 const X=x=>L+(x-x0)/(x1-x0)*pw,YT=v=>T+ph-(v-t0)/(t1-t0)*ph,YH=v=>T+ph-(v-h0)/(h1-h0)*ph;
 const lt=LT(),CT=lt?'#e07b00':'#ff9f43',CH=lt?'#1a73e8':'#3fa7ff',CM=lt?'#5d6778':'#8b96ab';
 c.strokeStyle=lt?'#e3e7ef':'#262d3b';c.lineWidth=1;
 for(let i=0;i<=5;i++){const y=T+ph*i/5;c.beginPath();c.moveTo(L,y);c.lineTo(L+pw,y);c.stroke();
  c.fillStyle=CT;c.textAlign='right';c.fillText((t1-(t1-t0)*i/5).toFixed(1),L-5,y+4);
  c.fillStyle=CH;c.textAlign='left';c.fillText((h1-(h1-h0)*i/5).toFixed(0),L+pw+5,y+4);}
 const span=x1-x0;c.fillStyle=CM;c.textAlign='center';
 for(let i=0;i<=4;i++){const x=x0+span*i/4,d=new Date(x*1000);
  const s=span<=172800?d.toLocaleTimeString('el-GR',{hour:'2-digit',minute:'2-digit',hour12:false}):d.toLocaleDateString('el-GR',{day:'2-digit',month:'2-digit'});
  c.fillText(s,X(x),H-8);}
 function line(idx,Y,col,dash){c.strokeStyle=col;c.lineWidth=dash?1.3:2.2;c.setLineDash(dash?[4,4]:[]);c.beginPath();let pen=false;
  pts.forEach(p=>{const v=p[idx];if(v==null){pen=false;return;}const x=X(p[0]),y=Y(v);if(!pen){c.moveTo(x,y);pen=true;}else c.lineTo(x,y);});c.stroke();c.setLineDash([]);}
 const pmax=Math.max(1,...WP.map(w=>Math.max(w[3]||0,w[4]||0)));
 WP.forEach(w=>{const v=Math.max(w[3]||0,w[4]||0);if(v<=0)return;const bh=v/pmax*ph*0.35;c.fillStyle=(w[4]||0)>0?(lt?'rgba(120,140,175,.45)':'rgba(230,240,255,.55)'):'rgba(90,169,255,.45)';c.fillRect(X(w[0])-2,T+ph-bh,4,bh);});
 function wline(idx,Y,col){c.strokeStyle=col;c.lineWidth=1.6;c.setLineDash([6,4]);c.beginPath();let pen=false;
  WP.forEach(w=>{const v=w[idx];if(v==null){pen=false;return;}const x=X(w[0]),y=Y(v);if(!pen){c.moveTo(x,y);pen=true;}else c.lineTo(x,y);});c.stroke();c.setLineDash([]);}
 wline(1,YT,'#2ecc71');wline(2,YH,'#1abc9c');
 line(3,YT,lt?'#7c5ce0':'#a78bfa',true);line(2,YH,CH);line(1,YT,CT);
 if(hov>=0&&pts[hov]){const p=pts[hov],x=X(p[0]);c.strokeStyle=lt?'#00000040':'#ffffff55';c.beginPath();c.moveTo(x,T);c.lineTo(x,T+ph);c.stroke();
  const lines=[new Date(p[0]*1000).toLocaleString('el-GR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}),`🌡 ${f(p[1])} °C`,`💧 ${f(p[2])} %`,`Δρόσος ${f(p[3])} °C`];
  const bw=130,bh=lines.length*16+10;let bx=x+10;if(bx+bw>W)bx=x-bw-10;c.fillStyle=lt?'rgba(255,255,255,.97)':'rgba(23,28,38,.95)';c.strokeStyle='#2b6cff';
  c.beginPath();c.roundRect?c.roundRect(bx,T+4,bw,bh,8):c.rect(bx,T+4,bw,bh);c.fill();c.stroke();
  c.fillStyle=lt?'#1a1f2b':'#e6ebf5';c.textAlign='left';lines.forEach((l,i)=>c.fillText(l,bx+8,T+20+i*16));}
}
function hoverAt(ev){if(!pts.length)return;const r=$('cv').getBoundingClientRect(),cx=(ev.touches?ev.touches[0].clientX:ev.clientX)-r.left;
 const P=pts.filter(p=>p[1]!=null);if(!P.length)return;const L=40,pw=r.width-80;let x0=pts[0][0],x1=pts[pts.length-1][0];if(x1==x0)x1=x0+1;
 const xt=x0+(cx-L)/pw*(x1-x0);let bi=-1,bd=1e18;pts.forEach((p,i)=>{if(p[1]==null&&p[2]==null)return;const d=Math.abs(p[0]-xt);if(d<bd){bd=d;bi=i;}});hov=bi;draw();}
$('cv').addEventListener('mousemove',hoverAt);$('cv').addEventListener('touchstart',hoverAt,{passive:true});$('cv').addEventListener('touchmove',hoverAt,{passive:true});
$('cv').addEventListener('mouseleave',()=>{hov=-1;draw();});
async function act(k){try{const j=await api('/api/'+k,{method:'POST'});toast(j.msg||'OK');setTimeout(()=>{loadStatus();loadHist();},2500);}catch(e){toast('Σφάλμα: '+e.message);}}
let ADM='';
async function post(path,obj){const j=await api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(obj)});toast(j.msg||(j.ok?'OK':'Σφάλμα'));return j;}
async function admOpen(){
 let st=await api('/api/admin/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({admin:ADM})});
 if(!st.ok&&st.admin_set===false){const a=prompt('Ορίστε νέο κωδικό διαχειριστή (4+ χαρακτήρες):');if(!a)return;
  const b=prompt('Επανάληψη κωδικού:');if(a!==b){toast('Δεν ταιριάζουν');return;}
  const j=await post('/api/admin/init',{new:a});if(!j.ok)return;ADM=a;}
 else if(!st.ok){const a=prompt('Κωδικός διαχειριστή:');if(a===null)return;ADM=a;}
 await admLoad();}
async function admLoad(){
 const st=await api('/api/admin/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({admin:ADM})});
 if(!st.ok){toast(st.msg||'Λάθος κωδικός');ADM='';return;}
 $('adm').style.display='block';const e=st.email;$('lbIn').value=LB().inside;$('lbOut').value=LB().outside;
 $('ehost').value=e.host||'';$('eport').value=e.port||587;$('esec').value=e.security||'STARTTLS';$('euser').value=e.user||'';
 $('efrom').value=e.sender||'';$('eto').value=e.to||'';$('etime').value=e.report_time||'08:00';$('een').checked=!!e.enabled;
 $('edaily').checked=!!e.daily_report;$('ealarm').checked=!!e.alarm_mails;$('epwh').textContent=e.has_password?'(αποθηκευμένος)':'';
 $('eStat').textContent=e.user?((e.enabled?'✅ ':'⏸ ')+e.user+(e.auth==='oauth_ms'?' · Microsoft':(e.host||'').includes('gmail')?' · Google':'')):'Δεν έχει οριστεί email — πατήστε Σύνδεση Google ή Outlook';
 $('pin').value=st.pin||'';$('poll').value=st.config.poll_seconds;$('admPlace').textContent=st.weather.place||'—';
 $('admInfo').textContent=`v${st.version} · δεδομένα: ${st.data_dir}`;}
let msT=null;
function gOpen(){$('gBox').style.display='';$('msBox').style.display='none';$('msId').style.display='none';}
async function gLogin(){$('eStat').textContent='⏳ Έλεγχος…';const j=await post('/api/admin/email/gmail',{admin:ADM,user:$('gUser').value,app_pw:$('gPw').value});
 $('eStat').textContent=j.msg||'';if(j.ok){$('gBox').style.display='none';$('gPw').value='';admLoad();}}
async function msGo(cid){$('gBox').style.display='none';const j=await post('/api/admin/email/ms_start',{admin:ADM,client_id:cid||''});
 if(j.stage==='need_id'){$('msId').style.display='';return;} $('msId').style.display='none';
 if(j.stage!=='wait'){$('eStat').textContent='✖ '+(j.msg||'');return;}
 $('msBox').style.display='';$('msCode').textContent=j.code;$('msUrl').href=j.url;$('msUrl').textContent=j.url.replace('https://','');$('msMsg').textContent=j.msg;
 try{navigator.clipboard.writeText(j.code);}catch(e){} window.open(j.url,'_blank');
 clearInterval(msT);msT=setInterval(async()=>{const s=await post('/api/admin/email/ms_state',{admin:ADM});$('msMsg').textContent=s.msg||'';
  if(s.stage!=='wait'){clearInterval(msT);$('eStat').textContent=s.msg||'';if(s.stage==='ok'){$('msBox').style.display='none';admLoad();}}},3000);}
function eProv(){const m={Gmail:['smtp.gmail.com',587,'STARTTLS'],Outlook:['smtp-mail.outlook.com',587,'STARTTLS'],Yahoo:['smtp.mail.yahoo.com',465,'SSL']}[$('eprov').value];
 if(m){$('ehost').value=m[0];$('eport').value=m[1];$('esec').value=m[2];}}
function eSave(){post('/api/admin/email',{admin:ADM,host:$('ehost').value,port:+$('eport').value,security:$('esec').value,user:$('euser').value,
 password:$('epw').value,sender:$('efrom').value,to:$('eto').value,report_time:$('etime').value,enabled:$('een').checked,
 daily_report:$('edaily').checked,alarm_mails:$('ealarm').checked}).then(()=>{$('epw').value='';admLoad();});}
async function pinSave(){const p=$('pin').value.trim();const j=await post('/api/admin/pin',{admin:ADM,pin:p});if(j.ok){PIN=p;localStorage.setItem('hl_pin',p);}}
async function locFind(){const q=$('locQ').value.trim();if(!q)return;const j=await api('/api/geocode?name='+encodeURIComponent(q));
 $('locRes').innerHTML=(j.results||[]).map((r,i)=>`<button onclick='locSet(${JSON.stringify(r).replace(/'/g,"&#39;")})'>📍 ${esc(r.label)}</button>`).join('')||'<div class="mut">Δεν βρέθηκε</div>';}
async function locSet(r){await post('/api/weather/location',{place:r.label,lat:r.lat,lon:r.lon,enabled:true});$('locRes').innerHTML='';admLoad();setTimeout(loadWx,4000);}
function dl(k){location.href=`/api/export.${k}?hours=${hours}&id=all&pin=${encodeURIComponent(PIN)}`;}
window.addEventListener('resize',draw);renderRanges();loadWx();loadStatus().then(loadHist);setInterval(loadWx,300000);
setInterval(loadStatus,10000);setInterval(loadHist,60000);
</script></body></html>"""


def make_handler(engine):
    class H(BaseHTTPRequestHandler):
        server_version = "AirSense/" + APP_VERSION

        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _auth(self, qs):
            pin = str(engine.cfg["server"].get("pin") or "")
            if not pin:
                return True
            given = self.headers.get("X-PIN") or qs.get("pin", [""])[0]
            return hmac.compare_digest(given.encode(), pin.encode())

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(u.query)
            p = u.path
            try:
                if p in ("/", "/index.html"):
                    return self._send(200, INDEX_HTML.replace("__VER__", APP_VERSION), "text/html; charset=utf-8")
                if p == "/manifest.json":
                    return self._send(200, {"name": APP_NAME, "short_name": "AirSense", "start_url": "/",
                                            "display": "standalone", "background_color": "#0f131a",
                                            "theme_color": "#0f131a",
                                            "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}]})
                if p == "/icon.svg":
                    return self._send(200, ICON_SVG, "image/svg+xml")
                if p in ("/setup.pdf", "/api/setup.pdf"):        # phone guide (addresses + QR only, no secrets)
                    data = build_setup_pdf(engine.server_urls(), bool(engine.cfg["server"].get("pin")), APP_VERSION)
                    return self._send(200, data, "application/pdf",
                                      {"Content-Disposition": 'inline; filename="AirSense_Phone_Setup_GR_EN.pdf"'})
                if not p.startswith("/api/"):
                    return self._send(404, {"error": "not found"})
                if not self._auth(qs):
                    return self._send(401, {"error": "PIN"})
                if p == "/api/status":
                    return self._send(200, engine.status_dict())
                if p == "/api/weather":
                    return self._send(200, engine.weather_dict())
                if p == "/api/geocode":
                    return self._send(200, {"results": geocode(qs.get("name", [""])[0], qs.get("lang", ["el"])[0])})
                if p == "/api/events":
                    return self._send(200, {"time": time.time(),
                                            "events": engine.events_since(float(qs.get("since", ["0"])[0] or 0))})
                if p == "/api/config":
                    return self._send(200, engine.config_dict())
                if p == "/api/calib":
                    did = qs.get("id", [""])[0]
                    st = engine.live.get(did, {})
                    return self._send(200, {"id": did, "calib": engine.calib(did), "raw_t": st.get("raw_t"),
                                            "raw_h": st.get("raw_h"), "t": st.get("t"), "h": st.get("h")})
                if p == "/api/device/wifiscan":
                    d = engine.device(qs.get("id", [""])[0])
                    if not d:
                        return self._send(404, {"error": "Η συσκευή δεν βρέθηκε"})
                    found = []

                    def walk(o):
                        if isinstance(o, dict):
                            if isinstance(o.get("ssid"), str) and o["ssid"]:
                                found.append(o["ssid"])
                            for x in o.values():
                                walk(x)
                        elif isinstance(o, list):
                            for x in o:
                                walk(x)
                    walk(http_json(d["ip"], "/api/wifi/scan", 20))
                    return self._send(200, {"ssids": list(dict.fromkeys(found))})
                if p == "/api/history":
                    did = qs.get("id", [""])[0]
                    hours = min(24 * 366, max(0.1, float(qs.get("hours", ["24"])[0])))
                    return self._send(200, {"id": did, "hours": hours, "points": engine.history_points(did, hours),
                                            "wx": engine.weather_points(hours)})
                if p in ("/api/export.csv", "/api/export.xml", "/api/export.pdf"):
                    hours = min(24 * 3660, max(0.1, float(qs.get("hours", ["24"])[0])))
                    did = qs.get("id", ["all"])[0]
                    t1 = time.time()
                    t0 = t1 - hours * 3600
                    rows = engine.store.rows(None if did == "all" else [did], t0, t1)
                    stamp = datetime.now().strftime("%Y%m%d_%H%M")
                    if p.endswith("pdf"):
                        if not rows:
                            return self._send(404, {"error": "Δεν υπάρχουν μετρήσεις στο διάστημα"})
                        data, ct, fn = engine.export_bytes("pdf", rows, t0, t1), "application/pdf", f"AirSense_{stamp}.pdf"
                        return self._send(200, data, ct, {"Content-Disposition": f'inline; filename="{fn}"'})
                    if p.endswith("csv"):
                        data, ct, fn = engine.export_bytes("csv", rows, t0, t1), "text/csv; charset=utf-8", f"AirSense_{stamp}.csv"
                    else:
                        data, ct, fn = engine.export_bytes("xml", rows, t0, t1), "application/xml", f"AirSense_{stamp}.xml"
                    return self._send(200, data, ct, {"Content-Disposition": f'attachment; filename="{fn}"'})
                return self._send(404, {"error": "not found"})
            except Exception as e:
                return self._send(500, {"error": str(e)})

        def do_POST(self):
            u = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(u.query)
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(min(n, 65536)) if n else b""
            try:
                body = json.loads(raw.decode("utf-8")) if raw else {}
                if not isinstance(body, dict):
                    body = {}
            except Exception:
                body = {}
            if not self._auth(qs):
                return self._send(401, {"error": "PIN"})
            p = u.path
            try:
                if p == "/api/config":
                    engine.update_config(body)
                    return self._send(200, {"ok": True, "msg": "Αποθηκεύτηκε στον υπολογιστή", "config": engine.config_dict()})
                if p == "/api/device":
                    ok, msg = engine.update_device(body)
                    return self._send(200, {"ok": ok, "msg": msg})
                if p == "/api/device/wifi":
                    d = engine.device(str(body.get("id", "")))
                    ssid = str(body.get("ssid", "")).strip()
                    if not d or not ssid:
                        return self._send(400, {"ok": False, "msg": "Λείπει συσκευή ή SSID"})
                    note = ""
                    try:
                        http_json(d["ip"], "/api/wifi/connect", 15, "POST", {"ssid": ssid, "pwd": str(body.get("pwd", ""))})
                    except urllib.error.HTTPError as e:
                        return self._send(200, {"ok": False, "msg": f"Ο αισθητήρας απέρριψε (HTTP {e.code})"})
                    except Exception as e:
                        note = f" (η σύνδεση έκλεισε: {e.__class__.__name__})"
                    engine.log(f"{d['name']}: μεταφέρεται στο WiFi «{ssid}» (από κινητό)")
                    return self._send(200, {"ok": True, "msg": "Στάλθηκε στον αισθητήρα" + note})
                if p == "/api/weather/location":
                    if body.get("lat") is None or body.get("lon") is None:
                        return self._send(400, {"ok": False, "msg": "Λείπουν συντεταγμένες"})
                    engine.set_weather_location(str(body.get("place", "")), body["lat"], body["lon"], body.get("enabled", True))
                    return self._send(200, {"ok": True, "msg": "Η τοποθεσία καιρού αποθηκεύτηκε"})
                if p == "/api/weather/auto":
                    loc = engine.auto_locate()
                    return self._send(200, {"ok": True, "msg": f"📍 {loc['label']} ({loc['source']})", "location": loc})
                if p == "/api/weather/refresh":
                    engine.wx_wake.set()
                    return self._send(200, {"ok": True, "msg": "Ανανέωση καιρού…"})
                if p == "/api/device/add":
                    ok, msg = engine.add_manual(str(body.get("ip", "")).strip())
                    return self._send(200, {"ok": ok, "msg": msg})
                if p == "/api/admin/init":
                    if (engine.cfg.get("admin") or {}).get("hash"):
                        return self._send(403, {"ok": False, "msg": "Υπάρχει ήδη κωδικός διαχειριστή"})
                    new = str(body.get("new", ""))
                    if len(new) < 4:
                        return self._send(400, {"ok": False, "msg": "Τουλάχιστον 4 χαρακτήρες"})
                    salt, h = _pw_hash(new)
                    engine.cfg["admin"] = {"salt": salt, "hash": h}
                    engine.save_cfg()
                    engine.log("Ορίστηκε κωδικός διαχειριστή (web)")
                    return self._send(200, {"ok": True, "msg": "Ο κωδικός διαχειριστή ορίστηκε"})
                if p.startswith("/api/admin/") and p not in ("/api/admin/check", "/api/admin/calib"):
                    if not engine.admin_ok(body.get("admin", "")):
                        if body.get("admin"):
                            engine.log("Λάθος κωδικός διαχειριστή (web)", "warn")
                        return self._send(403, {"ok": False, "msg": "Λάθος κωδικός διαχειριστή",
                                                "admin_set": bool((engine.cfg.get("admin") or {}).get("hash"))})
                    if p == "/api/admin/state":
                        e = engine.cfg["email"]
                        return self._send(200, {"ok": True, "email": {k: e.get(k) for k in (
                            "enabled", "host", "port", "security", "user", "sender", "to", "daily_report", "report_time",
                            "alarm_mails")} | {"has_password": bool(e.get("password")), "auth": e.get("auth", "password"),
                                                "ms_id": bool(ms_client_id(e))},
                            "pin": engine.cfg["server"].get("pin", ""), "config": engine.config_dict(),
                            "weather": engine.wx_place(), "data_dir": DATA_DIR, "version": APP_VERSION})
                    if p == "/api/admin/email":
                        e = engine.cfg["email"]
                        with engine.lock:
                            for k in ("host", "security", "user", "sender", "to", "report_time"):
                                if k in body:
                                    e[k] = str(body[k]).strip()
                            if body.get("enabled") and not e.get("enabled"):
                                engine.cfg["last_report_date"] = datetime.now().strftime("%Y-%m-%d")  # πρώτη αναφορά αύριο
                            for k in ("enabled", "daily_report", "alarm_mails"):
                                if k in body:
                                    e[k] = bool(body[k])
                            if body.get("port"):
                                e["port"] = int(body["port"])
                            if body.get("password"):
                                e["password"] = enc_secret(str(body["password"]))
                            engine.save_cfg()
                        engine.log("Ρυθμίσεις email άλλαξαν (web)")
                        return self._send(200, {"ok": True, "msg": "Οι ρυθμίσεις email αποθηκεύτηκαν"})
                    if p == "/api/admin/email/gmail":
                        ok, msg = engine.gmail_login(str(body.get("user", "")), str(body.get("app_pw", "")),
                                                     str(body.get("to", "")))
                        return self._send(200, {"ok": ok, "msg": msg})
                    if p == "/api/admin/email/ms_start":
                        f = engine.ms_login_start(str(body.get("client_id", "")))
                        return self._send(200, {"ok": f.get("stage") == "wait", **f})
                    if p == "/api/admin/email/ms_state":
                        return self._send(200, {"ok": True, **(engine.ms_flow or {"stage": ""})})
                    if p == "/api/admin/email/logout":
                        engine.mail_logout()
                        return self._send(200, {"ok": True, "msg": "Αποσυνδέθηκε"})
                    if p == "/api/admin/email/test":
                        ok, msg = engine.send_test()
                        return self._send(200, {"ok": ok, "msg": "Στάλθηκε δοκιμαστικό email ✔" if ok else f"Σφάλμα: {msg}"})
                    if p == "/api/admin/pin":
                        engine.cfg["server"]["pin"] = str(body.get("pin", "")).strip()
                        engine.save_cfg()
                        engine.log("Το PIN άλλαξε (web)")
                        return self._send(200, {"ok": True, "msg": "Το PIN αποθηκεύτηκε — ξαναμπείτε με το νέο PIN"})
                    if p == "/api/admin/password":
                        new = str(body.get("new", ""))
                        if len(new) < 4:
                            return self._send(400, {"ok": False, "msg": "Τουλάχιστον 4 χαρακτήρες"})
                        salt, h = _pw_hash(new)
                        engine.cfg["admin"] = {"salt": salt, "hash": h}
                        engine.save_cfg()
                        engine.log("Αλλαγή κωδικού διαχειριστή (web)")
                        return self._send(200, {"ok": True, "msg": "Ο κωδικός άλλαξε"})
                    return self._send(404, {"ok": False, "msg": "not found"})
                if p == "/api/admin/check":
                    ok = engine.admin_ok(body.get("admin", ""))
                    if not ok:
                        engine.log("Λάθος κωδικός διαχειριστή από κινητό", "warn")
                    return self._send(200, {"ok": ok, "set": bool((engine.cfg.get("admin") or {}).get("hash")),
                                            "msg": "OK" if ok else "Λάθος κωδικός ή δεν έχει οριστεί στον υπολογιστή"})
                if p == "/api/admin/labels":
                    if not engine.admin_ok(body.get("admin", "")):
                        return self._send(403, {"ok": False, "msg": "Λάθος κωδικός διαχειριστή"})
                    engine.cfg["labels"] = {k: (str(body.get(k, "")).strip()[:30] or DEFAULT_LABELS[k]) for k in DEFAULT_LABELS}
                    engine.save_cfg()
                    engine.log(f"Λεκτικά (από κινητό): {engine.cfg['labels']['inside']} / {engine.cfg['labels']['outside']}")
                    return self._send(200, {"ok": True, "msg": "Τα λεκτικά αποθηκεύτηκαν"})
                if p == "/api/admin/calib":
                    if not engine.admin_ok(body.get("admin", "")):
                        return self._send(403, {"ok": False, "msg": "Λάθος κωδικός διαχειριστή"})
                    n = engine.set_calib(str(body.get("id", "")), body)
                    return self._send(200, {"ok": True, "msg": "Η βαθμονόμηση εφαρμόστηκε" +
                                            (f" · επανυπολογίστηκαν {n} μετρήσεις" if n else "")})
            except Exception as e:
                return self._send(500, {"ok": False, "msg": str(e)})
            if p == "/api/poll":
                engine.poll_now()
                return self._send(200, {"ok": True, "msg": "Νέα μέτρηση σε εξέλιξη…"})
            if p == "/api/scan":
                ok = engine.start_scan()
                return self._send(200, {"ok": ok, "msg": "Η σάρωση ξεκίνησε" if ok else "Σάρωση ήδη σε εξέλιξη"})
            if p == "/api/report":
                if not engine.cfg["email"].get("enabled"):
                    return self._send(200, {"ok": False, "msg": "Το email δεν είναι ενεργό (ρυθμίστε το στον υπολογιστή)"})
                ok, msg = engine.send_report(24)
                return self._send(200, {"ok": ok, "msg": msg})
            return self._send(404, {"error": "not found"})

        do_HEAD = do_GET

    return H


if not HEADLESS:
    # ═══════════════════════════════════════════════════════════════════════════
    # 11) GUI (PyQt6)
    # ═══════════════════════════════════════════════════════════════════════════
    import numpy as np
    import pyqtgraph as pg
    import qrcode
    from PyQt6.QtCore import Qt, QTimer, QDateTime, QTime, QUrl
    from PyQt6.QtGui import QShortcut, QKeySequence, QAction, QColor, QDesktopServices, QFont, QIcon, QPainter, QPixmap, QPainterPath, QBrush, QPalette
    from PyQt6.QtNetwork import QLocalServer, QLocalSocket
    from PyQt6.QtWidgets import (
        QAbstractItemView, QApplication, QCheckBox, QComboBox, QDateTimeEdit, QDialog, QDialogButtonBox,
        QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView,
        QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressBar,
        QPushButton, QScrollArea, QSpinBox, QStackedWidget, QListWidget, QListWidgetItem, QSystemTrayIcon, QTableWidget, QTableWidgetItem, QTabWidget,
        QTextBrowser, QTimeEdit, QToolButton, QLayout, QVBoxLayout, QWidget,
    )

    QSS = """
    QWidget{background:#11151c;color:#e6ebf5;font-family:'Segoe UI',sans-serif;font-size:10pt}
    QTabWidget::pane{border:1px solid #262d3b;border-radius:8px;top:-1px}
    QTabBar::tab{background:#171c26;padding:8px 14px;border:1px solid #262d3b;border-bottom:none;border-top-left-radius:8px;border-top-right-radius:8px;margin-right:2px}
    QTabBar::tab:selected{background:#2b6cff}
    QPushButton{background:#1e2533;border:1px solid #2f3747;border-radius:8px;padding:7px 14px}
    QPushButton:hover{background:#273042}QPushButton:disabled{color:#5b6475}
    QPushButton#pri{background:#2b6cff;border-color:#2b6cff;font-weight:600}
    QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox,QDateTimeEdit,QTimeEdit,QPlainTextEdit,QTextBrowser,QTableWidget{background:#171c26;border:1px solid #2f3747;border-radius:6px;padding:4px}
    QTableWidget{gridline-color:#262d3b;selection-background-color:#2b6cff55}
    QHeaderView::section{background:#1e2533;padding:6px;border:none;font-weight:600}
    QGroupBox{border:1px solid #262d3b;border-radius:10px;margin-top:14px;padding:10px}
    QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 4px;color:#8b96ab}
    QFrame#card{background:#171c26;border:1px solid #262d3b;border-radius:14px}
    QFrame#card QLabel{background:transparent}
    QProgressBar{border:1px solid #2f3747;border-radius:6px;text-align:center;background:#171c26;height:18px}
    QProgressBar::chunk{background:#2b6cff;border-radius:6px}
    QScrollArea{border:none}
    QCheckBox::indicator{width:18px;height:18px;border:2px solid #5b6475;border-radius:4px;background:#171c26}
    QCheckBox::indicator:checked{background:#2b6cff;border-color:#2b6cff;image:url(@CHECK@)}
    QCheckBox::indicator:hover{border-color:#2b6cff}
    QPushButton#tile{font-size:13pt;min-height:86px;border-radius:14px;background:#1b2130}
    QPushButton#tile:hover{background:#2b6cff}
    QMenu{background:#171c26;border:1px solid #2f3747}QMenu::item:selected{background:#2b6cff}
    QPushButton#pri,QTabBar::tab:selected,QMenu::item:selected{color:#ffffff}
    QPushButton#tile:hover{color:#ffffff}
    QToolTip{background:#171c26;color:#e6ebf5;border:1px solid #2f3747;padding:4px}
    """

    def _check_svg():
        """Μικρό εικονίδιο ✓ για τα τσεκαρισμένα κουτάκια (αλλιώς δεν φαίνεται η διαφορά)."""
        fp = os.path.join(DATA_DIR, "check.svg")
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            if not os.path.exists(fp):
                with open(fp, "w", encoding="utf-8") as fh:
                    fh.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 18"><path d="M4 9.5l3.2 3.2L14 5.8" '
                             'fill="none" stroke="#ffffff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>')
        except Exception:
            return "none"
        return fp.replace("\\", "/")
    _CK = _check_svg()
    QSS = QSS.replace("url(@CHECK@)", "none" if _CK == "none" else "url(%s)" % _CK)

    # ── Θέμα: σκούρο / ανοιχτό / αυτόματο (όπως τα Windows) ──
    THEME = {"light": False}
    _LIGHT_MAP = {
        "#11151c": "#f4f6fa", "#141821": "#ffffff", "#151a24": "#ffffff", "#171c26": "#ffffff",
        "#1b2130": "#e9edf5", "#1e2533": "#eef1f6", "#222938": "#e6eaf2", "#222a38": "#e6eaf2",
        "#232a38": "#e6eaf2", "#262d3b": "#d9dee8", "#273042": "#dde3ee", "#2a3242": "#e1e6ef",
        "#2f3747": "#c9d0dc", "#5b6475": "#8a93a3", "#6b7588": "#9aa3b2", "#8b96ab": "#5d6778",
        "#c8d0e0": "#3a4252", "#dbe3f0": "#2a3242", "#e6ebf5": "#1a1f2b", "#3fa7ff": "#1a73e8",
        "#2ecc71": "#1e9e55", "#ffc04d": "#a86f00", "#ff9f43": "#d97100", "#ff5c5c": "#d93636",
        "#5aa9ff": "#1a73e8", "#9fc0ff": "#1a56c4", "#a78bfa": "#7c5ce0", "#1abc9c": "#12927a",
        "#18233a": "#e8f0ff", "#cfe0ff": "#1d3d7a", "#2b4a8a": "#a9c2f5",
        "#14281c": "#e6f6ec", "#bff5cf": "#1b5e35", "#2c6b43": "#9fd7b4",
        "#2e1719": "#fdeaea", "#ffc9c9": "#8a1f1f", "#7a2c31": "#f0b3b3",
        "#2d2414": "#fff5dc", "#ffe2a8": "#6b4a00", "#6e5320": "#e8cf8f",
        "#1f3b26": "#dff3e6", "#5be38a": "#1e8a4a", "#3b2a1a": "#fdebd3", "#ffb84d": "#a35f00",
        "#1d3a2a": "#dff3e6", "#3a1d22": "#fde3e3",
    }
    _HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")

    def tc(text):
        """Μετατρέπει τα χρώματα του σκούρου θέματος στο ανοιχτό (όταν είναι ενεργό)."""
        if not THEME["light"] or not isinstance(text, str) or "#" not in text:
            return text
        return _HEX_RE.sub(lambda m: _LIGHT_MAP.get(m.group(0).lower(), m.group(0)), text)

    def tcol(hexcol):
        return QColor(tc(hexcol))

    def system_is_light():
        try:
            sch = QApplication.styleHints().colorScheme()
            if sch == Qt.ColorScheme.Light:
                return True
            if sch == Qt.ColorScheme.Dark:
                return False
        except Exception:
            pass
        if os.name == "nt":
            try:
                import winreg
                k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                   r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
                return bool(winreg.QueryValueEx(k, "AppsUseLightTheme")[0])
            except Exception:
                pass
        return False

    def theme_wants_light(mode):
        return {"light": True, "dark": False}.get(mode, None) if mode in ("light", "dark") else system_is_light()

    def apply_theme(app, mode):
        """Ορίζει το θέμα σε όλη την εφαρμογή. Επιστρέφει True αν άλλαξε."""
        light = theme_wants_light(mode)
        changed = light != THEME["light"]
        THEME["light"] = light
        pal = QPalette()
        base = {"win": "#11151c", "base": "#171c26", "alt": "#1e2533", "txt": "#e6ebf5", "btn": "#1e2533",
                "mut": "#8b96ab"}
        for role, key in ((QPalette.ColorRole.Window, "win"), (QPalette.ColorRole.Base, "base"),
                          (QPalette.ColorRole.AlternateBase, "alt"), (QPalette.ColorRole.Text, "txt"),
                          (QPalette.ColorRole.WindowText, "txt"), (QPalette.ColorRole.Button, "btn"),
                          (QPalette.ColorRole.ButtonText, "txt"), (QPalette.ColorRole.ToolTipBase, "base"),
                          (QPalette.ColorRole.ToolTipText, "txt"), (QPalette.ColorRole.PlaceholderText, "mut")):
            pal.setColor(role, tcol(base[key]))
        pal.setColor(QPalette.ColorRole.Highlight, QColor("#2b6cff"))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        pal.setColor(QPalette.ColorRole.Link, tcol("#3fa7ff"))
        app.setPalette(pal)
        app.setStyleSheet(QSS)
        try:
            pg.setConfigOptions(antialias=True, background=tc("#141821"), foreground=tc("#c8d0e0"))
        except Exception:
            pass
        return changed

    # Αυτόματη μετατροπή χρωμάτων σε stylesheets και κείμενα (rich text) όταν είναι ενεργό το ανοιχτό θέμα
    _orig_setss = QWidget.setStyleSheet
    QWidget.setStyleSheet = lambda self, css: _orig_setss(self, tc(css))
    _orig_appss = QApplication.setStyleSheet
    QApplication.setStyleSheet = lambda self, css: _orig_appss(self, tc(css))

    class QLabel(QLabel):                          # noqa: F811 — θεματική εκδοχή
        def __init__(self, *a, **k):
            if a and isinstance(a[0], str):
                a = (tc(a[0]),) + a[1:]
            super().__init__(*a, **k)

        def setText(self, t):
            super().setText(tc(t))

    class QTextBrowser(QTextBrowser):              # noqa: F811
        def setHtml(self, t):
            super().setHtml(tc(t))


    def app_icon():
        pm = QPixmap(64, 64)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#0f131a"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, 64, 64, 14, 14)
        path = QPainterPath()
        path.moveTo(32, 8)
        path.cubicTo(32, 8, 14, 30, 14, 40)
        path.arcTo(14, 22, 36, 36, 180, 180)
        path.cubicTo(50, 30, 32, 8, 32, 8)
        p.setBrush(QColor("#3fa7ff"))
        p.drawPath(path)
        p.end()
        return QIcon(pm)


    def qr_pixmap(text, size=170):
        q = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
        q.add_data(text)
        q.make(fit=True)
        m = q.get_matrix()
        n = len(m)
        sc = max(2, size // n)
        pm = QPixmap(n * sc, n * sc)
        pm.fill(QColor("white"))
        p = QPainter(pm)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("black"))
        for y, row in enumerate(m):
            for x, v in enumerate(row):
                if v:
                    p.drawRect(x * sc, y * sc, sc, sc)
        p.end()
        return pm


    def _btn(text, slot=None, primary=False):
        b = QPushButton(text)
        if primary:
            b.setObjectName("pri")
        if slot:
            b.clicked.connect(slot)
        return b


    class DeviceCard(QFrame):
        def __init__(self, on_click):
            super().__init__()
            self.setObjectName("card")
            self.setMinimumWidth(250)
            self.did = None
            self._on_click = on_click
            lay = QVBoxLayout(self)
            top = QHBoxLayout()
            self.name = QLabel()
            self.name.setStyleSheet("font-weight:600;font-size:11pt")
            self.badge = QLabel()
            self.badge.setMaximumHeight(24)
            top.addWidget(self.name, 1)
            top.addWidget(self.badge)
            lay.addLayout(top)
            vals = QHBoxLayout()
            self.t = QLabel()
            self.h = QLabel()
            for w, col in ((self.t, "#ff9f43"), (self.h, "#3fa7ff")):
                w.setStyleSheet(f"color:{col};font-size:24pt;font-weight:700")
                vals.addWidget(w)
            vals.addStretch()
            lay.addLayout(vals)
            self.sub = QLabel()
            self.sub.setStyleSheet("color:#8b96ab")
            self.sub.setWordWrap(True)
            lay.addWidget(self.sub)

        def mousePressEvent(self, e):
            if self.did:
                self._on_click(self.did)

        def set_data(self, d, st, selected):
            self.did = d["id"]
            self.name.setText(d.get("name") or d["id"])
            on = st.get("online")
            self.badge.setText("online" if on else ("offline" if on is False else "…"))
            self.badge.setStyleSheet("padding:2px 8px;border-radius:9px;" +
                                     ("color:#2ecc71;background:#1d3a2a" if on else
                                      "color:#ff5c5c;background:#3a1d22" if on is False else "color:#8b96ab"))
            self.t.setText(f"{_fmt(st.get('t'))}<span style='font-size:11pt;color:#8b96ab'> °C</span>")
            self.h.setText(f"{_fmt(st.get('h'))}<span style='font-size:11pt;color:#8b96ab'> %</span>")
            ts = st.get("ts")
            last = datetime.fromtimestamp(ts).strftime("%H:%M:%S") if ts else "—"
            extra = f"<br><span style='color:#ff5c5c'>{st.get('error')}</span>" if on is False and st.get("error") else ""
            if not d.get("enabled", True):
                extra += "<br><i>απενεργοποιημένη</i>"
            self.sub.setText(f"Σημείο δρόσου <b style='color:#a78bfa'>{_fmt(st.get('dp'))} °C</b> · "
                             f"Απόλυτη {_fmt(st.get('ah'))} g/m³<br>{d['ip']} · τελευταία {last}{extra}")
            self.setStyleSheet("QFrame#card{border:1px solid %s}" % ("#2b6cff" if selected else "#262d3b"))


    class Bg:
        """Τρέχει μια αργή εργασία στο παρασκήνιο και καλεί done(res, err) στο GUI thread."""
        _alive = []

        def __init__(self, parent, fn, done):
            self.fn, self.done, self.res, self.err = fn, done, None, None
            self.t = threading.Thread(target=self._run, daemon=True)
            self.t.start()
            self.tm = QTimer(parent)
            self.tm.timeout.connect(self._chk)
            self.tm.start(120)
            Bg._alive.append(self)

        def _run(self):
            try:
                self.res = self.fn()
            except Exception as e:
                self.err = e

        def _chk(self):
            if self.t.is_alive():
                return
            self.tm.stop()
            if self in Bg._alive:
                Bg._alive.remove(self)
            try:
                self.done(self.res, self.err)
            except RuntimeError:
                pass


    def wifi_row_text(r):
        sec = "🔓 ανοιχτό" if r["open"] else "🔒 με κωδικό"
        bars = "▂▄▆█"[:max(1, min(4, r["signal"] // 25 + 1))]
        line1 = f"📡  {r['ssid']}" if r["blebox"] else f"     {r['ssid']}"
        line2 = (f"      MAC {r['bssid']}  ·  σήμα {bars} {r['signal']}%  ·  κανάλι {r['channel'] or '?'}  ·  "
                 f"{r['band'] or '?'}  ·  {sec}")
        if r["blebox"] and r["dev_id"]:
            line2 += f"\n      BleBox {r['model']}  ·  ID συσκευής {r['dev_id']}"
        return line1 + "\n" + line2


    WIZ_QSS = """
    QLabel#h1{font-size:19pt;font-weight:700}
    QLabel#big{font-size:12pt}
    QDialog QPushButton{font-size:11.5pt;min-height:40px}
    QPushButton#choice{font-size:14pt;min-height:92px;text-align:left;padding:14px 22px;border-radius:14px;background:#1b2130}
    QPushButton#choice:hover{background:#2b6cff}
    QListWidget{font-size:11.5pt;background:#171c26;border:1px solid #2f3747;border-radius:8px}
    QListWidget::item{padding:8px;border-bottom:1px solid #222a38}
    QListWidget::item:selected{background:#2b6cff}
    """
    P_WELCOME, P_POWER, P_AP, P_HOME, P_FIND, P_PHONE, P_DONE = range(7)
    WIZ_TITLES = ["Καλώς ήρθες", "Άναψε τον αισθητήρα", "Σύνδεση στο WiFi του αισθητήρα", "Το δικό σου WiFi",
                  "Εύρεση στο δίκτυο", "Κινητό", "Τέλος"]
    AP_ADDR = "192.168.4.1"


    class SetupWizard(QDialog):
        def __init__(self, win, start=P_WELCOME, preselect=None):
            super().__init__(win)
            self.win, self.engine = win, win.engine
            self.setWindowTitle(f"🧙 Οδηγός εγκατάστασης — {APP_NAME}")
            self.resize(900, 680)
            self.setStyleSheet(WIZ_QSS)
            self.hist = []
            self.home = {"ssid": "", "profile": ""}
            self.ap = None              # επιλεγμένη γραμμή WiFi αισθητήρα
            self.ap_connected = False
            self.home_sent = False
            self.preselect = preselect
            self.find_tries = 0
            self.find_auto_retry = False
            self.wifi_rows = []
            lay = QVBoxLayout(self)
            self.steps = QLabel()
            self.steps.setStyleSheet("color:#8b96ab;font-size:10.5pt")
            lay.addWidget(self.steps)
            self.stack = QStackedWidget()
            for f in (self._p_welcome, self._p_power, self._p_ap, self._p_home, self._p_find, self._p_phone, self._p_done):
                self.stack.addWidget(f())
            lay.addWidget(self.stack, 1)
            nav = QHBoxLayout()
            self.back_b = _btn("◀ Πίσω", self._back)
            self.next_b = _btn("Επόμενο ▶", self._next, True)
            nav.addWidget(self.back_b)
            nav.addStretch()
            nav.addWidget(QLabel(f"<span style='color:#5b6475'>{AUTHOR}</span>"))
            nav.addStretch()
            nav.addWidget(self.next_b)
            lay.addLayout(nav)
            self.find_timer = QTimer(self)
            self.find_timer.timeout.connect(self._find_tick)
            self.go(start, push=False)

        # ── βοηθητικά σελίδων ──
        def _page(self, title, text=""):
            w = QWidget()
            v = QVBoxLayout(w)
            t = QLabel(title)
            t.setObjectName("h1")
            v.addWidget(t)
            if text:
                l = QLabel(text)
                l.setObjectName("big")
                l.setWordWrap(True)
                l.setTextFormat(Qt.TextFormat.RichText)
                l.setOpenExternalLinks(True)
                v.addWidget(l)
            return w, v

        def _status(self):
            l = QLabel("")
            l.setWordWrap(True)
            l.setTextFormat(Qt.TextFormat.RichText)
            l.setStyleSheet("font-size:12pt;padding:8px;border-radius:8px;background:#171c26")
            return l

        def go(self, page, push=True):
            if push and self.stack.currentIndex() != page:
                self.hist.append(self.stack.currentIndex())
            self.stack.setCurrentIndex(page)
            n = page if page else 0
            self.steps.setText("Οδηγός εγκατάστασης" if page == P_WELCOME else
                               f"Βήμα {n} από {len(WIZ_TITLES) - 1}  —  {WIZ_TITLES[page]}")
            self.back_b.setEnabled(bool(self.hist))
            self.next_b.setVisible(page != P_WELCOME)
            self.next_b.setText("Τέλος ✔" if page == P_DONE else "Επόμενο ▶")
            if page == P_AP and not self.wifi_rows:
                self.do_wifi_scan()
            elif page == P_HOME:
                self.enter_home()
            elif page == P_FIND:
                self.start_find(auto_retry=self.home_sent)
            elif page == P_PHONE:
                self.refresh_phone()

        def _back(self):
            if self.hist:
                self.find_timer.stop()
                self.stack.setCurrentIndex(self.hist.pop())
                self.go(self.stack.currentIndex(), push=False)

        def _next(self):
            p = self.stack.currentIndex()
            if p == P_POWER:
                self.go(P_AP)
            elif p == P_AP:
                if not self.ap_connected and QMessageBox.question(
                        self, APP_NAME, "Δεν έχει γίνει σύνδεση στον αισθητήρα.\nΣυνέχεια παρόλα αυτά;") \
                        != QMessageBox.StandardButton.Yes:
                    return
                self.go(P_HOME)
            elif p == P_HOME:
                self.go(P_FIND)
            elif p == P_FIND:
                if not self.engine.devices() and QMessageBox.question(
                        self, APP_NAME, "Δεν βρέθηκε ακόμα αισθητήρας.\nΣυνέχεια παρόλα αυτά;") \
                        != QMessageBox.StandardButton.Yes:
                    return
                self.go(P_PHONE)
            elif p == P_PHONE:
                self.go(P_DONE)
            elif p == P_DONE:
                self.finish()

        # ── 0. Καλωσόρισμα ──
        def _p_welcome(self):
            w, v = self._page("👋 Καλώς ήρθες!",
                              "Θα σε βοηθήσω να συνδέσεις τον αισθητήρα <b>BleBox humiditySensor</b> και να βλέπεις "
                              "θερμοκρασία και υγρασία στον υπολογιστή και στο κινητό. Διάλεξε τι θέλεις:")
            for text, page in (("🆕   Καινούριος αισθητήρας\n        Δεν έχει συνδεθεί ακόμα στο WiFi μου", P_POWER),
                               ("✅   Ο αισθητήρας είναι ήδη στο WiFi μου\n        Απλώς βρες τον", P_FIND),
                               ("📱   Θέλω μόνο να δω τις μετρήσεις στο κινητό", P_PHONE),
                               ("🔁   Μεταφορά αισθητήρα σε άλλο WiFi / Reset", -1)):
                b = _btn(text, (lambda _=False, pg_=page: self.go(pg_)) if page >= 0 else self._move)
                b.setObjectName("choice")
                v.addWidget(b)
            v.addStretch()
            return w

        def _move(self):
            self.reject()
            self.win.open_move()

        # ── 1. Τροφοδοσία ──
        def _p_power(self):
            w, v = self._page("🔌 Άναψε τον αισθητήρα", """
    <ol style='line-height:160%'>
    <li>Σύνδεσε τον αισθητήρα σε <b>φορτιστή USB 5V</b> (καλώδιο micro USB).</li>
    <li>Περίμενε περίπου <b>30 δευτερόλεπτα</b>.</li>
    <li>Ο αισθητήρας ανοίγει δικό του WiFi με όνομα σαν<br>
    <code style='font-size:13pt;color:#2ecc71'>humiditySensor_v2-8e4f00527ebf</code></li>
    <li>Ο υπολογιστής χρειάζεται <b>WiFi</b> (laptop ή USB WiFi stick).</li>
    </ol>
    <p style='color:#8b96ab'>Αν ο αισθητήρας είχε ρυθμιστεί παλιότερα σε άλλο WiFi, μπορεί να μην εμφανίζεται —
    κάνε επαναφορά σύμφωνα με το <a style='color:#3fa7ff' href='https://blebox.eu/wp-content/uploads/humiditySensor_v2_Manual_EN.pdf'>εγχειρίδιο</a>.</p>
    <p>Πάτα <b>Επόμενο</b> όταν είσαι έτοιμος.</p>""")
            v.addStretch()
            return w

        # ── 2. Σάρωση WiFi & σύνδεση στον αισθητήρα ──
        def _p_ap(self):
            w, v = self._page("📶 Βρες το WiFi του αισθητήρα",
                              "Διάλεξε τον αισθητήρα (📡, πράσινο) και πάτα <b>«Σύνδεση στον αισθητήρα»</b>. "
                              "Ο υπολογιστής συνδέεται μόνος του.")
            r = QHBoxLayout()
            self.scan_b = _btn("🔍 Αναζήτηση WiFi", self.do_wifi_scan)
            self.only_bb = QCheckBox("Μόνο συσκευές BleBox")
            self.only_bb.toggled.connect(self.fill_wifi_list)
            r.addWidget(self.scan_b)
            r.addWidget(self.only_bb)
            r.addStretch()
            v.addLayout(r)
            self.ap_list = QListWidget()
            self.ap_list.itemDoubleClicked.connect(lambda _: self.connect_ap())
            v.addWidget(self.ap_list, 1)
            r2 = QHBoxLayout()
            self.ap_pwd_cb = QCheckBox("Το WiFi του αισθητήρα έχει κωδικό:")
            self.ap_pwd = QLineEdit()
            self.ap_pwd.setEchoMode(QLineEdit.EchoMode.Password)
            self.ap_pwd.setEnabled(False)
            self.ap_pwd_cb.toggled.connect(self.ap_pwd.setEnabled)
            r2.addWidget(self.ap_pwd_cb)
            r2.addWidget(self.ap_pwd, 1)
            v.addLayout(r2)
            r3 = QHBoxLayout()
            self.conn_b = _btn("🔗 Σύνδεση στον αισθητήρα", self.connect_ap, True)
            self.check_b = _btn("Συνδέθηκα μόνος μου — Έλεγχος", self.check_ap)
            self.loc_b = _btn("📍 Άνοιγμα ρυθμίσεων Τοποθεσίας", self.open_location)
            self.loc_b.hide()
            r3.addWidget(self.conn_b)
            r3.addWidget(self.check_b)
            r3.addWidget(self.loc_b)
            r3.addStretch()
            v.addLayout(r3)
            self.ap_status = self._status()
            v.addWidget(self.ap_status)
            return w

        def open_location(self):
            try:
                os.startfile("ms-settings:privacy-location")
            except Exception:
                pass

        def do_wifi_scan(self):
            self.scan_b.setEnabled(False)
            self.ap_status.setText("🔍 Αναζήτηση δικτύων WiFi… (περίπου 5 δευτερόλεπτα)")
            Bg(self, lambda: wifi_scan(True), self._wifi_done)

        def _wifi_done(self, res, err):
            self.scan_b.setEnabled(True)
            rows, e = res if res else ([], str(err))
            self.wifi_rows = rows
            self.loc_b.setVisible(e == "LOCATION")
            if e == "LOCATION":
                self.ap_status.setText("⚠ Τα Windows χρειάζονται <b>άδεια Τοποθεσίας</b> για να δείξουν τα δίκτυα WiFi.<br>"
                                       "Πάτα «📍 Άνοιγμα ρυθμίσεων Τοποθεσίας» → ενεργοποίησε την Τοποθεσία και το "
                                       "«Να επιτρέπεται στις εφαρμογές υπολογιστή…» → ξανά «Αναζήτηση WiFi».")
            elif e:
                self.ap_status.setText(f"❌ {e}")
            else:
                bb = [r for r in rows if r["blebox"]]
                self.ap_status.setText(f"✅ Βρέθηκαν {len(rows)} σημεία WiFi — <b style='color:#2ecc71'>{len(bb)} {'αισθητήρας' if len(bb) == 1 else 'αισθητήρες'} BleBox</b>."
                                       if bb else f"Βρέθηκαν {len(rows)} δίκτυα, κανένας αισθητήρας. Είναι αναμμένος; "
                                                  "Περίμενε 30″ και ξαναπάτα «Αναζήτηση WiFi».")
            self.fill_wifi_list()

        def fill_wifi_list(self):
            self.ap_list.clear()
            sel = None
            for r in self.wifi_rows:
                if self.only_bb.isChecked() and not r["blebox"]:
                    continue
                it = QListWidgetItem(wifi_row_text(r))
                it.setData(Qt.ItemDataRole.UserRole, r)
                it.setForeground(tcol("#2ecc71" if r["blebox"] else "#8b96ab"))
                self.ap_list.addItem(it)
                if sel is None and r["blebox"] and (not self.preselect or r["ssid"] == self.preselect):
                    sel = it
            if sel:
                self.ap_list.setCurrentItem(sel)

        def connect_ap(self):
            it = self.ap_list.currentItem()
            if not it:
                return self.ap_status.setText("Διάλεξε πρώτα τον αισθητήρα από τη λίστα.")
            r = it.data(Qt.ItemDataRole.UserRole)
            if not r["blebox"] and QMessageBox.question(self, APP_NAME, f"Το «{r['ssid']}» δεν μοιάζει με αισθητήρα BleBox.\n"
                                                        "Σύνδεση παρόλα αυτά;") != QMessageBox.StandardButton.Yes:
                return
            self.ap = r
            pwd = self.ap_pwd.text() if self.ap_pwd_cb.isChecked() else ""
            self.conn_b.setEnabled(False)
            self.ap_status.setText(f"🔗 Σύνδεση στο <b>{r['ssid']}</b>… (έως 40 δευτερόλεπτα)<br>"
                                   "<span style='color:#8b96ab'>Το Internet του υπολογιστή θα κοπεί προσωρινά — είναι φυσιολογικό.</span>")

            def job():
                cur = wifi_current()
                if cur["ssid"] and not BLEBOX_SSID_RE.search(cur["ssid"]):
                    self.home = {"ssid": cur["ssid"], "profile": cur["profile"] or cur["ssid"]}
                ok, out = wifi_connect(r["ssid"], pwd)
                t_end = time.time() + 40
                while time.time() < t_end:
                    info = blebox_info(AP_ADDR, 2)
                    if info:
                        return info
                    time.sleep(2)
                raise RuntimeError(out.strip()[:200] if not ok else "Ο αισθητήρας δεν απάντησε στη διεύθυνση 192.168.4.1")
            Bg(self, job, self._ap_done)

        def check_ap(self):
            self.ap_status.setText("Έλεγχος 192.168.4.1…")
            Bg(self, lambda: blebox_info(AP_ADDR, 4) or (_ for _ in ()).throw(RuntimeError("Δεν απαντά")), self._ap_done)

        def _ap_done(self, info, err):
            self.conn_b.setEnabled(True)
            if info:
                self.ap_connected = True
                self.engine.log(f"Σύνδεση στο WiFi του αισθητήρα: {info.get('deviceName')} ({info.get('id')})")
                self.ap_status.setText(f"✅ <b>Συνδέθηκε!</b> {info.get('deviceName', '')} · τύπος {info.get('type', '')} · "
                                       f"ID {info.get('id', '')} · firmware {info.get('fv', '')}<br>Πάμε στο επόμενο βήμα…")
                QTimer.singleShot(1300, lambda: self.go(P_HOME) if self.stack.currentIndex() == P_AP else None)
            else:
                ssid = self.ap["ssid"] if self.ap else "humiditySensor…"
                self.ap_status.setText(f"❌ Δεν έγινε σύνδεση: {err}<br><b>Χειροκίνητα:</b> πάτα το εικονίδιο WiFi κάτω δεξιά "
                                       f"στα Windows → διάλεξε «{ssid}» → Σύνδεση → μετά πάτα «Συνδέθηκα μόνος μου — Έλεγχος».")

        # ── 3. WiFi σπιτιού/εργοταξίου ──
        def _p_home(self):
            w, v = self._page("🏠 Δώσε το WiFi σου",
                              "Ο αισθητήρας θα συνδεθεί σε αυτό το δίκτυο (σπίτι / γραφείο / εργοτάξιο).<br>"
                              "<b style='color:#ffc04d'>Μόνο 2.4 GHz</b> — όχι δίκτυα που τελειώνουν σε «-5G».")
            f = QFormLayout()
            self.home_ssid = QComboBox()
            self.home_ssid.setEditable(True)
            self.home_ssid.setMinimumHeight(38)
            self.home_ssid.currentTextChanged.connect(self._ssid_warn)
            self.home_pwd = QLineEdit()
            self.home_pwd.setMinimumHeight(38)
            self.home_pwd.setEchoMode(QLineEdit.EchoMode.Password)
            show = QCheckBox("👁 Εμφάνιση κωδικού")
            show.toggled.connect(lambda on: self.home_pwd.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
            f.addRow("Όνομα WiFi:", self.home_ssid)
            f.addRow("Κωδικός WiFi:", self.home_pwd)
            f.addRow("", show)
            v.addLayout(f)
            self.ssid_warn = QLabel("")
            self.ssid_warn.setStyleSheet("color:#ffc04d")
            v.addWidget(self.ssid_warn)
            r = QHBoxLayout()
            self.send_b = _btn("📤 Αποστολή στον αισθητήρα", self.send_home, True)
            r.addWidget(self.send_b)
            r.addStretch()
            v.addLayout(r)
            self.home_status = self._status()
            v.addWidget(self.home_status)
            v.addStretch()
            return w

        def _ssid_warn(self, t):
            five = bool(re.search(r"5g|5ghz|_5|-5", t.lower()))
            self.ssid_warn.setText("⚠ Αυτό μοιάζει με δίκτυο 5 GHz — ο αισθητήρας δεν θα συνδεθεί." if five else "")

        def enter_home(self):
            self.home_status.setText("Φόρτωση δικτύων που «βλέπει» ο αισθητήρας…")

            def job():
                names = []
                try:
                    js = http_json(AP_ADDR, "/api/wifi/scan", 15)
                    found = []
                    def walk(o):
                        if isinstance(o, dict):
                            if isinstance(o.get("ssid"), str) and o["ssid"]:
                                found.append(o["ssid"])
                            for x in o.values():
                                walk(x)
                        elif isinstance(o, list):
                            for x in o:
                                walk(x)
                    walk(js)
                    names += found
                except Exception:
                    pass
                return names
            Bg(self, job, self._home_names)

        def _home_names(self, sensor_names, err):
            sensor_names = sensor_names or []
            pc = [r["ssid"] for r in self.wifi_rows if not r["blebox"] and "5" not in r["band"][:1] and r["ssid"] != "(κρυφό)"]
            names = list(dict.fromkeys(sensor_names + pc))
            cur = self.home_ssid.currentText()
            self.home_ssid.clear()
            self.home_ssid.addItems(names)
            pick = cur or self.home.get("ssid", "")
            if pick:
                self.home_ssid.setCurrentText(pick)
            self.home_status.setText(f"Ο αισθητήρας βλέπει {len(sensor_names)} δίκτυα. Διάλεξε το δικό σου, γράψε τον κωδικό "
                                     "και πάτα «📤 Αποστολή»." if sensor_names else
                                     "Διάλεξε ή γράψε το όνομα του WiFi σου, τον κωδικό και πάτα «📤 Αποστολή».")

        def send_home(self):
            ssid = self.home_ssid.currentText().strip()
            if not ssid:
                return self.home_status.setText("Γράψε το όνομα του WiFi.")
            pwd = self.home_pwd.text()
            self.send_b.setEnabled(False)
            self.home_status.setText(f"📤 Αποστολή στοιχείων για «{ssid}»… μετά ο υπολογιστής επιστρέφει στο δικό σου WiFi "
                                     "(έως 1 λεπτό).")
            home = dict(self.home)
            ap_ssid = self.ap["ssid"] if self.ap else ""

            def job():
                warn = ""
                try:
                    http_json(AP_ADDR, "/api/wifi/connect", 15, "POST", {"ssid": ssid, "pwd": pwd})
                except urllib.error.HTTPError as e:
                    raise RuntimeError(f"Ο αισθητήρας απέρριψε το αίτημα (HTTP {e.code})")
                except Exception as e:
                    warn = f"(ο αισθητήρας έκλεισε τη σύνδεση: {e.__class__.__name__} — συνήθως σημαίνει ότι άλλαξε δίκτυο)"
                time.sleep(5)
                if os.name == "nt":
                    _run(["netsh", "wlan", "disconnect"])
                    time.sleep(1)
                    wifi_forget(ap_ssid)
                reconnected = wifi_reconnect(home.get("profile") or ssid)
                t_end = time.time() + 45
                while time.time() < t_end:
                    ips = [i for i in lan_ipv4s() if not i.startswith("192.168.4.")]
                    if ips:
                        return {"warn": warn, "ips": ips, "reconnected": reconnected}
                    time.sleep(2)
                return {"warn": warn, "ips": [], "reconnected": reconnected}
            Bg(self, job, self._home_done)

        def _home_done(self, res, err):
            self.send_b.setEnabled(True)
            if err:
                return self.home_status.setText(f"❌ {err}<br>Έλεγξε όνομα/κωδικό και ξαναδοκίμασε.")
            self.home_sent = True
            self.engine.log(f"Στάλθηκαν στοιχεία WiFi «{self.home_ssid.currentText()}» στον αισθητήρα")
            if res["ips"]:
                self.home_status.setText(f"✅ Στάλθηκαν! Ο υπολογιστής ξανά στο δίκτυο ({', '.join(res['ips'])}). "
                                         f"{res['warn']}<br>Πάμε να βρούμε τον αισθητήρα…")
                QTimer.singleShot(1500, lambda: self.go(P_FIND) if self.stack.currentIndex() == P_HOME else None)
            else:
                self.home_status.setText("✅ Στάλθηκαν στον αισθητήρα.<br>⚠ Ο υπολογιστής δεν επανασυνδέθηκε μόνος του: πάτα το "
                                         "εικονίδιο WiFi κάτω δεξιά, σύνδεσε τον υπολογιστή στο <b>δικό σου WiFi</b> και πάτα "
                                         "<b>Επόμενο</b>.")

        # ── 4. Εύρεση στο δίκτυο ──
        def _p_find(self):
            w, v = self._page("🔍 Εύρεση αισθητήρα στο δίκτυο")
            self.find_status = self._status()
            v.addWidget(self.find_status)
            self.find_bar = QProgressBar()
            v.addWidget(self.find_bar)
            self.find_list = QListWidget()
            v.addWidget(self.find_list, 1)
            r = QHBoxLayout()
            r.addWidget(_btn("🔄 Ξανά αναζήτηση", lambda: self.start_find(False)))
            r.addWidget(_btn("➕ Ξέρω την IP του", self.add_ip))
            r.addStretch()
            v.addLayout(r)
            tip = QLabel("<span style='color:#8b96ab'>Αν δεν βρεθεί: ο υπολογιστής πρέπει να είναι στο <b>ίδιο WiFi</b> με τον "
                         "αισθητήρα. Ο αισθητήρας μπορεί να θέλει έως 1 λεπτό για να συνδεθεί. Η IP του φαίνεται και στη "
                         "σελίδα του router (λίστα συσκευών).</span>")
            tip.setWordWrap(True)
            v.addWidget(tip)
            return w

        def start_find(self, auto_retry=False):
            if auto_retry:
                self.find_auto_retry = True
            self.find_tries += 1
            if not self.engine.scan["running"]:
                self.engine.start_scan()
            self.find_status.setText(f"🔍 Ψάχνω όλο το δίκτυο… (προσπάθεια {self.find_tries})")
            self.find_timer.start(400)

        def _find_tick(self):
            sc = self.engine.scan
            self.find_bar.setMaximum(max(1, sc["total"]))
            self.find_bar.setValue(sc["done"])
            if sc["running"]:
                return
            self.find_timer.stop()
            with self.engine.lock:
                bb = [dict(r) for r in sc["results"] if r["blebox"]]
            for r in bb:
                if r["type"].lower() in SENSOR_TYPES and not self.engine.device(r["id"]):
                    self.engine.add_scan_result(r)
            self.find_list.clear()
            ap_id = (self.ap or {}).get("dev_id", "")
            for r in bb:
                new = ap_id and r["id"].lower().endswith(ap_id[-6:])
                it = QListWidgetItem(f"{'⭐ ' if new else '✅ '}{r['name'] or r['type']}   [{r['type']}]\n"
                                     f"      IP {r['ip']}  ·  MAC {r.get('mac') or '—'}  ·  ID {r['id']}  ·  fw {r['fv']}")
                it.setForeground(tcol("#2ecc71"))
                self.find_list.addItem(it)
            devs = self.engine.devices()
            if devs:
                self.engine.poll_now()
                for d in devs:
                    if any(r["id"] == d["id"] for r in bb):
                        continue
                    st = self.engine.live.get(d["id"], {})
                    it = QListWidgetItem(f"✅ {d.get('name')}   [{d.get('type', '')}]\n      IP {d['ip']}  ·  MAC {d.get('mac') or '—'}"
                                         f"  ·  ID {d['id']}  ·  {_fmt(st.get('t'))} °C  {_fmt(st.get('h'))} %")
                    it.setForeground(tcol("#2ecc71"))
                    self.find_list.addItem(it)
                self.find_status.setText(f"🎉 <b>{'Βρέθηκε 1 αισθητήρας' if len(devs) == 1 else f'Βρέθηκαν {len(devs)} αισθητήρες'}!</b> Η καταγραφή ξεκίνησε. Πάτα <b>Επόμενο</b>.")
            elif self.find_auto_retry and self.find_tries < 4:
                self.find_status.setText("⏳ Ο αισθητήρας ίσως ακόμα συνδέεται στο WiFi… νέα προσπάθεια σε 15 δευτερόλεπτα.")
                QTimer.singleShot(15000, lambda: self.start_find() if self.stack.currentIndex() == P_FIND else None)
            else:
                nets = ", ".join(str(n) for n in build_networks(self.engine.cfg.get("subnets", ""))) or "—"
                self.find_status.setText(f"❌ Δεν βρέθηκε αισθητήρας στο δίκτυο ({nets}).<br>Δοκίμασε «🔄 Ξανά αναζήτηση» σε λίγο "
                                         "ή «➕ Ξέρω την IP του».")

        def add_ip(self):
            addr, ok = QInputDialog.getText(self, APP_NAME, "IP του αισθητήρα (π.χ. 192.168.1.50):")
            if ok and addr.strip():
                okk, msg = self.engine.add_manual(addr)
                self.find_status.setText(("✅ " if okk else "❌ ") + msg)

        # ── 5. Κινητό ──
        def _p_phone(self):
            w, v = self._page("📱 Δες τις μετρήσεις στο κινητό")
            row = QHBoxLayout()
            self.qr_lan = QLabel()
            self.qr_ts = QLabel()
            for q in (self.qr_lan, self.qr_ts):
                q.setAlignment(Qt.AlignmentFlag.AlignCenter)
                q.setTextFormat(Qt.TextFormat.RichText)
                q.setWordWrap(True)
                q.setOpenExternalLinks(True)
                row.addWidget(q, 1)
            v.addLayout(row, 1)
            self.phone_txt = QLabel()
            self.phone_txt.setWordWrap(True)
            self.phone_txt.setObjectName("big")
            v.addWidget(self.phone_txt)
            r = QHBoxLayout()
            r.addWidget(_btn("⟳ Έλεγχος Tailscale", lambda: self.refresh_phone(True)))
            r.addWidget(_btn("⬇ Λήψη Tailscale (Windows)", lambda: webbrowser.open("https://tailscale.com/download/windows")))
            r.addWidget(_btn("🛡 Άνοιγμα Firewall", self.win._firewall))
            r.addStretch()
            v.addLayout(r)
            return w

        def _qr_html(self, title, url):
            pm = qr_pixmap(url, 200)
            buf = io.BytesIO()
            from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
            ba = QByteArray()
            qb = QBuffer(ba)
            qb.open(QIODevice.OpenModeFlag.WriteOnly)
            pm.save(qb, "PNG")
            b64 = base64.b64encode(bytes(ba)).decode()
            return (f"<b style='font-size:13pt'>{title}</b><br><img src='data:image/png;base64,{b64}'><br>"
                    f"<a style='color:#3fa7ff;font-size:12pt' href='{url}'>{url}</a>")

        def refresh_phone(self, force=False):
            if not self.engine.httpd:
                self.engine.cfg["server"]["enabled"] = True
                self.engine.save_cfg()
                self.engine.start_server()
            port = self.engine.cfg["server"].get("port", 8765)
            lan = lan_ipv4s()
            self.qr_lan.setText(self._qr_html("🏠 Στο ίδιο WiFi", f"http://{lan[0]}:{port}") if lan else "Δεν βρέθηκε τοπικό δίκτυο")
            ts = self.engine.tailscale(force)
            if ts.get("ip"):
                self.qr_ts.setText(self._qr_html("🌍 Από παντού (Tailscale)", f"http://{ts['ip']}:{port}"))
            else:
                self.qr_ts.setText("<b style='font-size:13pt'>🌍 Από παντού (Tailscale)</b><br><br>"
                                   "<span style='color:#ffc04d'>Δεν είναι ακόμα εγκατεστημένο σε αυτόν τον υπολογιστή.</span>")
            self.phone_txt.setText(
                "<b>Στο ίδιο WiFi:</b> άνοιξε την κάμερα του κινητού και σκάναρε το αριστερό QR.<br>"
                "<b>Από παντού (4G/5G):</b> 1) Πάτα «Λήψη Tailscale», εγκατάστησε και συνδέσου (Google/Microsoft). "
                "2) Εγκατάστησε <b>Tailscale</b> στο κινητό με τον <b>ίδιο λογαριασμό</b> και άναψέ το. "
                "3) Πάτα «Έλεγχος Tailscale» και σκάναρε το δεξί QR.<br>"
                "<span style='color:#8b96ab'>Συμβουλή: στον browser του κινητού → μενού → «Προσθήκη στην αρχική οθόνη». "
                "Αν δεν ανοίγει η σελίδα, πάτα «Άνοιγμα Firewall».</span>")

        # ── 6. Τέλος ──
        def _p_done(self):
            w, v = self._page("🎉 Έτοιμο!",
                              "Ο αισθητήρας καταγράφεται συνεχώς. Τα δεδομένα αποθηκεύονται αυτόματα σε <b>CSV</b> και "
                              f"<b>XML</b> στον φάκελο<br><code>{DAILY_DIR}</code>.<br><br>"
                              "Άφησε τον υπολογιστή ανοιχτό· το «Χ» κρύβει την εφαρμογή κάτω δεξιά (δίπλα στο ρολόι).")
            self.done_auto = QCheckBox("Αυτόματη εκκίνηση μαζί με τα Windows (προτείνεται)")
            self.done_auto.setChecked(os.name == "nt")
            self.done_auto.setEnabled(os.name == "nt")
            self.done_min = QCheckBox("Εκκίνηση κρυμμένη κάτω δεξιά (tray)")
            v.addWidget(self.done_auto)
            v.addWidget(self.done_min)
            b = _btn("✉ Θέλω και αναφορές στο email — ρύθμιση τώρα", lambda: self.finish("email"))
            v.addWidget(b)
            v.addStretch()
            return w

        def finish(self, goto=None):
            if os.name == "nt" and self.done_auto.isChecked():
                self.win.cb_auto.setChecked(True)
            if self.done_min.isChecked():
                self.win.cb_min.setChecked(True)
            self.accept()
            if goto == "email":
                self.win.show_email()
            else:
                self.win.tabs.setCurrentWidget(self.win.T["home"])

        def done(self, r):
            self.find_timer.stop()
            if self.ap_connected and not self.home_sent and self.home.get("profile"):
                prof, ap = self.home["profile"], (self.ap or {}).get("ssid", "")
                threading.Thread(target=lambda: (wifi_reconnect(prof), wifi_forget(ap)), daemon=True).start()
                self.engine.log("Επιστροφή του υπολογιστή στο WiFi " + prof)
            super().done(r)


    RESET_URL = "https://blebox.eu/start/reset"


    MOVE_QSS = WIZ_QSS + """
    QFrame#mcard{background:#151a24;border:1px solid #262d3b;border-radius:16px}
    QFrame#mcard[sel="true"]{border:2px solid #2b6cff}
    QFrame#mcard QLabel{background:transparent}
    QFrame#mcard QLabel#badge{background:#2b6cff;color:white;border-radius:14px;font-weight:700;font-size:11pt;
                 min-width:28px;max-width:28px;min-height:28px;max-height:28px}
    QFrame#mcard QLabel#badge2{background:#2a3242;color:#dbe3f0;border-radius:14px;font-weight:700;font-size:11pt;
                 min-width:28px;max-width:28px;min-height:28px;max-height:28px}
    QFrame#mcard QLabel#chip{background:#1f3b26;color:#5be38a;border-radius:10px;padding:3px 10px;font-size:9.5pt;font-weight:600}
    QFrame#mcard QLabel#chip2{background:#3b2a1a;color:#ffb84d;border-radius:10px;padding:3px 10px;font-size:9.5pt;font-weight:600}
    QLabel#steplbl{font-size:10.5pt;color:#8b96ab;font-weight:600}
    QComboBox,QLineEdit{min-height:38px;font-size:11.5pt;border-radius:9px;padding:0 10px}
    QPushButton#big{font-size:13pt;font-weight:700;min-height:52px;border-radius:12px}
    QToolButton#ic{min-width:38px;min-height:38px;border-radius:9px;background:#222938;font-size:13pt}
    QToolButton#ic:hover{background:#2b6cff}
    QLabel#stat{font-size:11pt;padding:10px 14px;border-radius:10px}
    """

    class MoveWifiDialog(QDialog):
        """Εύκολη μεταφορά αισθητήρα σε άλλο WiFi (χωρίς reset) + οδηγίες reset."""

        @staticmethod
        def _badge(n, alt=False):
            b = QLabel(str(n))
            b.setObjectName("badge2" if alt else "badge")
            b.setAlignment(Qt.AlignmentFlag.AlignCenter)
            return b

        def _step(self, grid, row, n, title, widget, alt=False):
            grid.addWidget(self._badge(n, alt), row, 0, Qt.AlignmentFlag.AlignTop)
            col = QVBoxLayout()
            col.setSpacing(4)
            t = QLabel(title)
            t.setObjectName("steplbl")
            col.addWidget(t)
            if isinstance(widget, QLayout):
                col.addLayout(widget)
            else:
                col.addWidget(widget)
            grid.addLayout(col, row, 1)

        def __init__(self, win):
            super().__init__(win)
            self.win, self.engine = win, win.engine
            self.setWindowTitle(f"🔁 Αλλαγή WiFi αισθητήρα — {APP_NAME}")
            self.resize(1040, 700)
            self.setMinimumSize(900, 620)
            self.setStyleSheet(MOVE_QSS)
            v = QVBoxLayout(self)
            v.setContentsMargins(22, 18, 22, 16)
            v.setSpacing(12)
            t = QLabel("🔁 Αλλαγή WiFi αισθητήρα")
            t.setObjectName("h1")
            v.addWidget(t)
            sub = QLabel("Διάλεξε αυτό που ισχύει για σένα:")
            sub.setStyleSheet("color:#8b96ab;font-size:11pt")
            v.addWidget(sub)
            cards = QHBoxLayout()
            cards.setSpacing(14)

            # ── Κάρτα Α
            self.card_a = QFrame()
            self.card_a.setObjectName("mcard")
            self.card_a.setProperty("sel", True)
            ca = QVBoxLayout(self.card_a)
            ca.setContentsMargins(20, 16, 20, 18)
            ca.setSpacing(12)
            ha = QHBoxLayout()
            la = QLabel("<span style='font-size:14pt;font-weight:700'>Α · Ο αισθητήρας δουλεύει τώρα</span><br>"
                        "<span style='color:#8b96ab'>Του στέλνεις το νέο WiFi από εδώ — χωρίς reset.</span>")
            ha.addWidget(la, 1)
            ch = QLabel("ΣΥΝΙΣΤΑΤΑΙ")
            ch.setObjectName("chip")
            ha.addWidget(ch, 0, Qt.AlignmentFlag.AlignTop)
            ca.addLayout(ha)
            grid = QGridLayout()
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(12)
            grid.setColumnStretch(1, 1)
            self.dev = QComboBox()
            for d in self.engine.devices():
                st = self.engine.live.get(d["id"], {})
                self.dev.addItem(f"{'🟢' if st.get('online') else '🔴'}  {d.get('name')}   ·   {d['ip']}", d["id"])
            self.dev.currentIndexChanged.connect(self._dev_changed)
            self._step(grid, 0, 1, "ΑΙΣΘΗΤΗΡΑΣ", self.dev)
            self.ssid = QComboBox()
            self.ssid.setEditable(True)
            self.ssid.lineEdit().setPlaceholderText("Όνομα νέου WiFi (SSID)")
            scan = QToolButton()
            scan.setObjectName("ic")
            scan.setText("🔍")
            scan.setToolTip("Δίκτυα που βλέπει ο αισθητήρας")
            scan.clicked.connect(self.load_ssids)
            self.scan_b = scan
            r = QHBoxLayout()
            r.setSpacing(8)
            r.addWidget(self.ssid, 1)
            r.addWidget(scan)
            self._step(grid, 1, 2, "ΝΕΟ WiFi  ·  μόνο 2.4 GHz", r)
            self.pwd = QLineEdit()
            self.pwd.setPlaceholderText("Κωδικός WiFi")
            self.pwd.setEchoMode(QLineEdit.EchoMode.Password)
            self._eye_btn = QToolButton()
            self._eye_btn.setObjectName("ic")
            self._eye_btn.setText("👁")
            self._eye_btn.setCheckable(True)
            self._eye_btn.setToolTip("Εμφάνιση κωδικού")
            self._eye_btn.toggled.connect(lambda on: self.pwd.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
            rp = QHBoxLayout()
            rp.setSpacing(8)
            rp.addWidget(self.pwd, 1)
            rp.addWidget(self._eye_btn)
            self._step(grid, 2, 3, "ΚΩΔΙΚΟΣ", rp)
            ca.addLayout(grid)
            self.warn_a = QLabel()
            self.warn_a.setWordWrap(True)
            self.warn_a.setTextFormat(Qt.TextFormat.RichText)
            self.warn_a.setObjectName("stat")
            ca.addWidget(self.warn_a)
            ca.addStretch()
            self.send_b = _btn("📤  Αποστολή νέου WiFi", self.send, True)
            self.send_b.setObjectName("big")
            self.send_b.setStyleSheet("QPushButton#big{background:#2b6cff;color:white}"
                                      "QPushButton#big:hover{background:#4a82ff}"
                                      "QPushButton#big:disabled{background:#2a3242;color:#6b7588}")
            ca.addWidget(self.send_b)
            cards.addWidget(self.card_a, 3)

            # ── Κάρτα Β
            self.card_b = QFrame()
            self.card_b.setObjectName("mcard")
            cb = QVBoxLayout(self.card_b)
            cb.setContentsMargins(20, 16, 20, 18)
            cb.setSpacing(12)
            hb = QHBoxLayout()
            lb = QLabel("<span style='font-size:14pt;font-weight:700'>Β · Δεν εμφανίζεται πουθενά</span><br>"
                        "<span style='color:#8b96ab'>…ή θέλεις καθαρή αρχή.</span>")
            hb.addWidget(lb, 1)
            ch2 = QLabel("RESET")
            ch2.setObjectName("chip2")
            hb.addWidget(ch2, 0, Qt.AlignmentFlag.AlignTop)
            cb.addLayout(hb)
            g2 = QGridLayout()
            g2.setHorizontalSpacing(12)
            g2.setVerticalSpacing(14)
            g2.setColumnStretch(1, 1)
            for i, txt in enumerate((
                    "Κάνε <b>επαναφορά εργοστασιακών</b> (δες «📖 Οδηγίες Reset»).",
                    "Ο αισθητήρας ανοίγει δικό του WiFi:<br><span style='color:#3fa7ff'>humiditySensor_v2-…</span>",
                    "Πάτα <b>🧙 Οδηγός νέου αισθητήρα</b> — τον συνδέει στο νέο WiFi.")):
                g2.addWidget(self._badge(i + 1, True), i, 0, Qt.AlignmentFlag.AlignTop)
                lt = QLabel(txt)
                lt.setWordWrap(True)
                lt.setTextFormat(Qt.TextFormat.RichText)
                lt.setStyleSheet("font-size:11pt")
                g2.addWidget(lt, i, 1)
            cb.addLayout(g2)
            keep = QLabel("💾 Το ιστορικό μετρήσεων κρατιέται — ο αισθητήρας αναγνωρίζεται από το ID του.")
            keep.setWordWrap(True)
            keep.setStyleSheet("color:#8b96ab;font-size:10pt")
            cb.addWidget(keep)
            cb.addStretch()
            b1 = _btn("📖  Οδηγίες Reset (BleBox)", lambda: webbrowser.open(RESET_URL))
            b2 = _btn("🧙  Οδηγός νέου αισθητήρα", self.wizard, True)
            for bb_ in (b1, b2):
                bb_.setMinimumHeight(46)
                cb.addWidget(bb_)
            cards.addWidget(self.card_b, 2)
            v.addLayout(cards, 1)

            self.status = QLabel("")
            self.status.setWordWrap(True)
            self.status.setTextFormat(Qt.TextFormat.RichText)
            self.status.setObjectName("stat")
            self.status.hide()
            v.addWidget(self.status)
            bot = QHBoxLayout()
            bot.addStretch()
            close = _btn("Κλείσιμο", self.reject)
            close.setMinimumWidth(130)
            bot.addWidget(close)
            v.addLayout(bot)
            if not self.engine.devices():
                for wdg in (self.dev, self.ssid, self.pwd, self.send_b, self.scan_b, self._eye_btn):
                    wdg.setEnabled(False)
                self._warn("Δεν υπάρχει ακόμα αισθητήρας στη λίστα — χρησιμοποίησε το <b>Β</b>.", "warn")
                self._sel(self.card_b)
            else:
                self._dev_changed()

        _STYLES = {"info": "background:#18233a;color:#cfe0ff;border:1px solid #2b4a8a",
                   "ok": "background:#14281c;color:#bff5cf;border:1px solid #2c6b43",
                   "err": "background:#2e1719;color:#ffc9c9;border:1px solid #7a2c31",
                   "warn": "background:#2d2414;color:#ffe2a8;border:1px solid #6e5320"}

        def _say(self, html, kind="info"):
            if not html:
                self.status.hide()
                return
            self.status.setStyleSheet(self._STYLES.get(kind, self._STYLES["info"]))
            self.status.setText(html)
            self.status.show()

        def _warn(self, html, kind="warn"):
            if not html:
                self.warn_a.hide()
                return
            self.warn_a.setStyleSheet(self._STYLES.get(kind, self._STYLES["warn"]))
            self.warn_a.setText(html)
            self.warn_a.show()

        def _sel(self, card):
            for c in (self.card_a, self.card_b):
                c.setProperty("sel", c is card)
                c.style().unpolish(c)
                c.style().polish(c)

        def _dev_changed(self, *_):
            did = self.dev.currentData()
            online = bool(self.engine.live.get(did, {}).get("online")) if did else False
            if online:
                self._warn("")
                self._sel(self.card_a)
            else:
                self._warn("⚠ Αυτός ο αισθητήρας είναι <b>εκτός σύνδεσης</b> τώρα — δεν μπορεί να πάρει νέο WiFi από εδώ.<br>"
                           "Σύνδεσε τον υπολογιστή στο ίδιο WiFi με τον αισθητήρα, ή χρησιμοποίησε το <b>Β</b>.")
                self._sel(self.card_b)

        def _ip(self):
            d = self.engine.device(self.dev.currentData()) if self.dev.currentData() else None
            return d["ip"] if d else None

        def wizard(self):
            self.accept()
            self.win.open_wizard(P_POWER)

        def load_ssids(self):
            ip = self._ip()
            if not ip:
                return
            self._say("🔍 Ο αισθητήρας ψάχνει δίκτυα…")

            def job():
                js = http_json(ip, "/api/wifi/scan", 20)
                out = []

                def walk(o):
                    if isinstance(o, dict):
                        if isinstance(o.get("ssid"), str) and o["ssid"]:
                            out.append(o["ssid"])
                        for x in o.values():
                            walk(x)
                    elif isinstance(o, list):
                        for x in o:
                            walk(x)
                walk(js)
                return list(dict.fromkeys(out))

            def done(names, err):
                if err:
                    return self._say(f"❌ Ο αισθητήρας δεν απάντησε: {err}", "err")
                cur = self.ssid.currentText()
                self.ssid.clear()
                self.ssid.addItems(names)
                if cur:
                    self.ssid.setCurrentText(cur)
                self._say(f"✅ Ο αισθητήρας βλέπει {len(names)} δίκτυα — διάλεξε από τη λίστα στο βήμα 2.", "ok")
                self.ssid.showPopup()
            Bg(self, job, done)

        def send(self):
            ip, ssid = self._ip(), self.ssid.currentText().strip()
            if not ip or not ssid:
                return self._say("Διάλεξε αισθητήρα και γράψε το νέο WiFi.", "warn")
            if QMessageBox.question(self, APP_NAME, f"Ο αισθητήρας θα αποσυνδεθεί από το τωρινό δίκτυο και θα πάει στο «{ssid}».\n\n"
                                    "Αν ο κωδικός είναι λάθος, θα χρειαστεί Reset.\nΣυνέχεια;") != QMessageBox.StandardButton.Yes:
                return
            self.send_b.setEnabled(False)
            self._say("📤 Αποστολή…")
            pwd = self.pwd.text()

            def job():
                try:
                    http_json(ip, "/api/wifi/connect", 15, "POST", {"ssid": ssid, "pwd": pwd})
                    return ""
                except urllib.error.HTTPError as e:
                    raise RuntimeError(f"Ο αισθητήρας απέρριψε το αίτημα (HTTP {e.code})")
                except Exception as e:
                    return f"(η σύνδεση έκλεισε: {e.__class__.__name__} — συνήθως σημαίνει ότι άλλαξε δίκτυο)"

            def done(warn, err):
                self.send_b.setEnabled(True)
                if err:
                    return self._say(f"❌ {err}", "err")
                self.engine.log(f"Ο αισθητήρας {ip} μεταφέρεται στο WiFi «{ssid}»")
                self._say(
                    f"✅ <b>Στάλθηκε!</b> {warn}<br>Τώρα:<br>1. Πήγαινε τον αισθητήρα εκεί που υπάρχει το «{ssid}».<br>"
                    f"2. Σύνδεσε <b>τον υπολογιστή</b> στο ίδιο WiFi.<br>3. Πάτα <b>🔍 Βρες αισθητήρες</b> στην Αρχική — "
                    "θα τον αναγνωρίσει από το ID του και το ιστορικό συνεχίζει.", "ok")
            Bg(self, job, done)


    class AdminDialog(QDialog):
        """Κρυφές ρυθμίσεις διαχειριστή (Ctrl+Shift+A)."""

        def __init__(self, win):
            super().__init__(win)
            self.win, self.engine = win, win.engine
            self.setWindowTitle(f"🔐 Ρυθμίσεις διαχειριστή — {APP_NAME}")
            self.resize(1000, 640)
            v = QVBoxLayout(self)
            tabs = QTabWidget()
            tabs.addTab(self._tab_calib(), "🎚 Βαθμονόμηση μετρήσεων")
            tabs.addTab(self._tab_api(), "🧪 Κονσόλα API αισθητήρα")
            tabs.addTab(self._tab_data(), "🗂 Δεδομένα")
            tabs.addTab(self._tab_sec(), "🔑 Κωδικός")
            v.addWidget(tabs)
            bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            bb.rejected.connect(self.reject)
            v.addWidget(bb)
            self.tm = QTimer(self)
            self.tm.timeout.connect(self._preview)
            self.tm.start(1500)

        # ── βαθμονόμηση ──
        def _tab_calib(self):
            w = QWidget()
            v = QVBoxLayout(w)
            info = QLabel("Διόρθωση τιμών ανά αισθητήρα: <b>τελική = αισθητήρας × πολλαπλασιαστής + offset</b>. "
                          "Π.χ. αν δείχνει 0.6°C παραπάνω από ένα όργανο αναφοράς → Offset θερμ. = −0.6.<br>"
                          "<span style='color:#8b96ab'>Η αρχική τιμή του αισθητήρα κρατιέται πάντα στη βάση και φαίνεται "
                          "στο XML (sensorTemperature / sensorHumidity) — μπορείς να επιστρέψεις οποτεδήποτε.</span>")
            info.setWordWrap(True)
            info.setTextFormat(Qt.TextFormat.RichText)
            v.addWidget(info)
            self.cal_tbl = QTableWidget(0, 7)
            self.cal_tbl.setHorizontalHeaderLabels(["Αισθητήρας", "Offset θερμ. (°C)", "× θερμ.", "Offset υγρ. (%)", "× υγρ.",
                                                    "Αισθητήρας τώρα", "Μετά τη διόρθωση"])
            self.cal_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            self.cal_tbl.verticalHeader().setVisible(False)
            self.cal_tbl.verticalHeader().setDefaultSectionSize(40)
            devs = self.engine.devices()
            self.cal_tbl.setRowCount(len(devs))
            self.cal_w = []
            for i, d in enumerate(devs):
                c = self.engine.calib(d["id"])
                it = QTableWidgetItem(d.get("name") or d["id"])
                it.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.cal_tbl.setItem(i, 0, it)
                spins = []
                for j, (key, lo, hi, dec, step) in enumerate((("t_off", -20, 20, 2, 0.1), ("t_mul", 0.5, 1.5, 3, 0.005),
                                                              ("h_off", -40, 40, 2, 0.5), ("h_mul", 0.5, 1.5, 3, 0.005)), start=1):
                    sp = QDoubleSpinBox()
                    sp.setRange(lo, hi)
                    sp.setDecimals(dec)
                    sp.setSingleStep(step)
                    sp.setValue(c[key])
                    sp.valueChanged.connect(self._preview)
                    self.cal_tbl.setCellWidget(i, j, sp)
                    spins.append(sp)
                for j in (5, 6):
                    x = QTableWidgetItem("")
                    x.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    self.cal_tbl.setItem(i, j, x)
                self.cal_w.append((d["id"], spins))
            v.addWidget(self.cal_tbl, 1)
            r = QHBoxLayout()
            self.recalc = QCheckBox("Εφαρμογή και στο ιστορικό από:")
            self.recalc_from = QDateTimeEdit(QDateTime.currentDateTime().addDays(-1))
            self.recalc_from.setDisplayFormat("dd/MM/yyyy HH:mm")
            self.recalc_from.setCalendarPopup(True)
            r.addWidget(self.recalc)
            r.addWidget(self.recalc_from)
            r.addStretch()
            r.addWidget(_btn("↺ Μηδενισμός", self._reset_cal))
            r.addWidget(_btn("💾 Εφαρμογή", self._apply_cal, True))
            v.addLayout(r)
            self._preview()
            return w

        def _vals(self, spins):
            return {"t_off": spins[0].value(), "t_mul": spins[1].value(), "h_off": spins[2].value(), "h_mul": spins[3].value()}

        def _preview(self):
            for i, (did, spins) in enumerate(self.cal_w):
                st = self.engine.live.get(did, {})
                rt, rh = st.get("raw_t"), st.get("raw_h")
                t, h = calibrate_values(rt, rh, self._vals(spins))
                self.cal_tbl.item(i, 5).setText(f"{_fmt(rt, 2)} °C   {_fmt(rh, 2)} %")
                self.cal_tbl.item(i, 6).setText(f"{_fmt(t, 2)} °C   {_fmt(h, 2)} %")
                self.cal_tbl.item(i, 6).setForeground(tcol("#2ecc71"))

        def _reset_cal(self):
            for _, spins in self.cal_w:
                spins[0].setValue(0)
                spins[1].setValue(1)
                spins[2].setValue(0)
                spins[3].setValue(1)

        def _apply_cal(self):
            cal = self.engine.cfg.setdefault("calib", {})
            n = 0
            for did, spins in self.cal_w:
                vals = self._vals(spins)
                if cal.get(did) != vals:
                    name = (self.engine.device(did) or {}).get("name", did)
                    self.engine.log(f"Βαθμονόμηση {name}: θερμ. ×{vals['t_mul']:.3f} {vals['t_off']:+.2f}°C, "
                                    f"υγρ. ×{vals['h_mul']:.3f} {vals['h_off']:+.2f}%")
                cal[did] = vals
                if self.recalc.isChecked():
                    n += self.engine.store.recalibrate(did, self.recalc_from.dateTime().toSecsSinceEpoch(), vals)
            self.engine.save_cfg()
            if n:
                self.engine.log(f"Επανυπολογίστηκαν {n} παλιές μετρήσεις")
                self.engine.poll_counter += 1
            self.engine.poll_now()
            QMessageBox.information(self, APP_NAME, "Η βαθμονόμηση εφαρμόστηκε." + (f"\nΕπανυπολογίστηκαν {n} μετρήσεις." if n else ""))

        # ── κονσόλα API ──
        def _tab_api(self):
            w = QWidget()
            v = QVBoxLayout(w)
            r = QHBoxLayout()
            self.api_dev = QComboBox()
            for d in self.engine.devices():
                self.api_dev.addItem(f"{d.get('name')} ({d['ip']})", d["ip"])
            self.api_dev.addItem("Αισθητήρας σε λειτουργία AP (192.168.4.1)", AP_ADDR)
            self.api_path = QComboBox()
            self.api_path.setEditable(True)
            self.api_path.addItems(["/info", "/state/extended", "/state", "/api/settings/state", "/api/device/network",
                                    "/api/wifi/scan", "/api/device/uptime", "/api/device/state"])
            r.addWidget(QLabel("Συσκευή:"))
            r.addWidget(self.api_dev, 1)
            r.addWidget(QLabel("GET"))
            r.addWidget(self.api_path, 1)
            r.addWidget(_btn("▶ Αποστολή", self._api_go, True))
            v.addLayout(r)
            self.api_out = QPlainTextEdit()
            self.api_out.setReadOnly(True)
            self.api_out.setFont(QFont("Consolas", 10))
            v.addWidget(self.api_out, 1)
            n = QLabel("<span style='color:#8b96ab'>Μόνο ανάγνωση (GET) — ασφαλές, δεν αλλάζει τίποτα στον αισθητήρα. "
                       "Τεκμηρίωση: technical.blebox.eu</span>")
            v.addWidget(n)
            return w

        def _api_go(self):
            ip, path = self.api_dev.currentData(), self.api_path.currentText().strip() or "/info"
            self.api_out.setPlainText(f"GET http://{ip}{path} …")
            t0 = time.time()

            def done(js, err):
                ms = int((time.time() - t0) * 1000)
                self.api_out.setPlainText(f"GET http://{ip}{path}   ({ms} ms)\n\n" +
                                          (f"Σφάλμα: {err}" if err else json.dumps(js, ensure_ascii=False, indent=2)))
            Bg(self, lambda: http_json(ip, path, 10), done)

        # ── δεδομένα ──
        def _tab_data(self):
            w = QWidget()
            v = QVBoxLayout(w)
            g = QGroupBox("Διαγραφή μετρήσεων (π.χ. δοκιμαστικές μετρήσεις)")
            f = QGridLayout(g)
            self.del_dev = QComboBox()
            self.del_dev.addItem("Όλες οι συσκευές", "")
            for d in self.engine.devices():
                self.del_dev.addItem(d.get("name") or d["id"], d["id"])
            self.del_from = QDateTimeEdit(QDateTime.currentDateTime().addDays(-1))
            self.del_to = QDateTimeEdit(QDateTime.currentDateTime())
            for x in (self.del_from, self.del_to):
                x.setDisplayFormat("dd/MM/yyyy HH:mm")
                x.setCalendarPopup(True)
            f.addWidget(QLabel("Συσκευή:"), 0, 0)
            f.addWidget(self.del_dev, 0, 1, 1, 3)
            f.addWidget(QLabel("Από:"), 1, 0)
            f.addWidget(self.del_from, 1, 1)
            f.addWidget(QLabel("Έως:"), 1, 2)
            f.addWidget(self.del_to, 1, 3)
            f.addWidget(_btn("🗑 Διαγραφή", self._delete), 2, 3)
            v.addWidget(g)
            g2 = QGroupBox("Πληροφορίες")
            l2 = QVBoxLayout(g2)
            l2.addWidget(QLabel(f"Βάση: {DB_PATH}\nΡυθμίσεις: {CFG_PATH}\nLog: {LOG_FILE}\n"
                                f"Σύνολο μετρήσεων: {self.engine.store.count():,}".replace(",", ".")))
            r = QHBoxLayout()
            r.addWidget(_btn("📂 Φάκελος δεδομένων", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(DATA_DIR))))
            r.addWidget(_btn("📄 Άνοιγμα log", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(LOG_FILE))))
            r.addStretch()
            l2.addLayout(r)
            v.addWidget(g2)
            v.addStretch()
            return w

        def _delete(self):
            did = self.del_dev.currentData() or None
            t0, t1 = self.del_from.dateTime().toSecsSinceEpoch(), self.del_to.dateTime().toSecsSinceEpoch()
            n = self.engine.store.count_range(did, t0, t1)
            if not n:
                return QMessageBox.information(self, APP_NAME, "Δεν υπάρχουν μετρήσεις στο διάστημα.")
            if QMessageBox.question(self, APP_NAME, f"Οριστική διαγραφή {n} μετρήσεων;") == QMessageBox.StandardButton.Yes:
                k = self.engine.store.delete(did, t0, t1)
                self.engine.log(f"Διαγράφηκαν {k} μετρήσεις ({self.del_dev.currentText()}, "
                                f"{self.del_from.text()} – {self.del_to.text()})", "warn")
                self.engine.poll_counter += 1
                QMessageBox.information(self, APP_NAME, f"Διαγράφηκαν {k} μετρήσεις.")

        # ── κωδικός ──
        def _tab_sec(self):
            w = QWidget()
            f = QFormLayout(w)
            self.pw_old = QLineEdit()
            self.pw_new = QLineEdit()
            self.pw_new2 = QLineEdit()
            for x in (self.pw_old, self.pw_new, self.pw_new2):
                x.setEchoMode(QLineEdit.EchoMode.Password)
            f.addRow("Τρέχων κωδικός:", self.pw_old)
            f.addRow("Νέος κωδικός:", self.pw_new)
            f.addRow("Επανάληψη:", self.pw_new2)
            f.addRow(_btn("💾 Αλλαγή κωδικού", self._chg_pw, True))
            hint = QLabel("<span style='color:#8b96ab'>Άνοιγμα αυτού του παραθύρου: <b>Ctrl+Shift+A</b> ή 5 κλικ στον τίτλο "
                          "«Σχετικά» στις Ρυθμίσεις.<br>Ξέχασες τον κωδικό; Κλείσε την εφαρμογή και σβήσε την ενότητα "
                          f"\"admin\" από το {CFG_PATH}.</span>")
            hint.setWordWrap(True)
            f.addRow(hint)
            return w

        def _chg_pw(self):
            a = self.engine.cfg.get("admin", {})
            if not hmac.compare_digest(_pw_hash(self.pw_old.text(), a["salt"])[1], a["hash"]):
                return QMessageBox.warning(self, APP_NAME, "Λάθος τρέχων κωδικός.")
            if len(self.pw_new.text()) < 4 or self.pw_new.text() != self.pw_new2.text():
                return QMessageBox.warning(self, APP_NAME, "Ο νέος κωδικός πρέπει να έχει 4+ χαρακτήρες και να ταιριάζει.")
            salt, h = _pw_hash(self.pw_new.text())
            self.engine.cfg["admin"] = {"salt": salt, "hash": h}
            self.engine.save_cfg()
            self.engine.log("Αλλαγή κωδικού διαχειριστή")
            QMessageBox.information(self, APP_NAME, "Ο κωδικός άλλαξε.")


    class PiSdWifiDialog(QDialog):
        """Γράφει airsense-wifi.txt στην κάρτα SD του Raspberry Pi."""

        def __init__(self, parent):
            super().__init__(parent)
            self.setWindowTitle("🥧 WiFi στην κάρτα SD του Raspberry Pi")
            self.resize(780, 640)
            self.nets = []
            v = QVBoxLayout(self)
            t = QLabel("<b style='font-size:14pt'>🥧 WiFi για το Raspberry Pi (μέσω κάρτας SD)</b><br>"
                       "<span style='color:#8b96ab'>Πας το Pi αλλού (π.χ. γραφείο); Γράψε εδώ το WiFi εκεί, βάλε την "
                       "κάρτα στο Pi και άναψέ το — συνδέεται μόνο του. Μετά: <code>ssh pi@airsense.local</code> (ή το όνομα που έδωσες στο Pi)</span>")
            t.setWordWrap(True)
            v.addWidget(t)
            g1 = QGroupBox("1. Κάρτα SD του Pi (εμφανίζεται ως «bootfs»)")
            l1 = QVBoxLayout(g1)
            r = QHBoxLayout()
            self.drive = QComboBox()
            self.drive.setMinimumWidth(260)
            self.drive.currentIndexChanged.connect(self.check_card)
            r.addWidget(self.drive, 1)
            r.addWidget(_btn("⟳ Αναζήτηση", self.scan))
            r.addWidget(_btn("📁 Φάκελος…", self.pick))
            l1.addLayout(r)
            self.info = QLabel("")
            self.info.setWordWrap(True)
            self.info.setTextFormat(Qt.TextFormat.RichText)
            l1.addWidget(self.info)
            v.addWidget(g1)
            g2 = QGroupBox("2. WiFi που θα μάθει το Pi (μόνο 2.4 GHz)")
            f = QGridLayout(g2)
            self.ssid = QComboBox()
            self.ssid.setEditable(True)
            self.ssid.addItems(win_wifi_profiles())
            self.ssid.setCurrentText("")
            self.ssid.activated.connect(lambda _: self.fill_pw())
            self.pw = QLineEdit()
            self.pw.setEchoMode(QLineEdit.EchoMode.Password)
            show = QCheckBox("👁")
            show.toggled.connect(lambda on: self.pw.setEchoMode(QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
            self.prio = QSpinBox()
            self.prio.setRange(0, 999)
            self.prio.setValue(50)
            self.hidden = QCheckBox("Κρυφό δίκτυο")
            f.addWidget(QLabel("Όνομα WiFi:"), 0, 0)
            f.addWidget(self.ssid, 0, 1)
            f.addWidget(_btn("📶 WiFi αυτού του υπολογιστή", self.use_current), 0, 2)
            f.addWidget(QLabel("Κωδικός:"), 1, 0)
            f.addWidget(self.pw, 1, 1)
            f.addWidget(show, 1, 2)
            f.addWidget(QLabel("Προτεραιότητα:"), 2, 0)
            f.addWidget(self.prio, 2, 1)
            f.addWidget(self.hidden, 2, 2)
            f.addWidget(_btn("➕ Προσθήκη στη λίστα", self.add), 3, 1)
            self.note = QLabel("")
            self.note.setStyleSheet("color:#ffc04d")
            f.addWidget(self.note, 4, 0, 1, 3)
            self.tbl = QTableWidget(0, 4)
            self.tbl.setHorizontalHeaderLabels(["Όνομα WiFi", "Κωδικός", "Προτερ.", "Κρυφό"])
            self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self.tbl.verticalHeader().setVisible(False)
            f.addWidget(self.tbl, 5, 0, 1, 3)
            f.addWidget(_btn("🗑 Αφαίρεση επιλεγμένου", self.remove), 6, 0, 1, 2)
            v.addWidget(g2, 1)
            rb = QHBoxLayout()
            wb = _btn("💾  3. Γράψε στην κάρτα SD", self.write, True)
            wb.setMinimumHeight(44)
            rb.addWidget(wb)
            rb.addStretch()
            bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            bb.rejected.connect(self.reject)
            rb.addWidget(bb)
            v.addLayout(rb)
            self.scan()

        def scan(self):
            self.drive.blockSignals(True)
            self.drive.clear()
            for d in find_pi_boot_drives():
                self.drive.addItem(f"{d}   (κάρτα Raspberry Pi)", d)
            self.drive.blockSignals(False)
            if self.drive.count():
                self.drive.setCurrentIndex(0)
                self.check_card()
            else:
                self.info.setText("<span style='color:#ff5c5c'>⚠ Δεν βρέθηκε κάρτα Raspberry Pi. Βάλε την κάρτα στον "
                                  "υπολογιστή (εμφανίζεται ως «bootfs») και πάτα «Αναζήτηση».</span>")

        def pick(self):
            d = QFileDialog.getExistingDirectory(self, "Φάκελος bootfs της κάρτας")
            if d:
                self.drive.addItem(d, d)
                self.drive.setCurrentIndex(self.drive.count() - 1)

        def check_card(self):
            c = self.drive.currentData()
            if not c:
                return
            m = []
            BF, BL, BE = pi_boot_names(c)
            if not is_pi_boot_dir(c):
                m.append("⚠ Ο φάκελος δεν μοιάζει με κάρτα Raspberry Pi.")
            if os.path.exists(os.path.join(c, BE)):
                m.append("<span style='color:#2ecc71'>✅ Το Pi έχει την υπηρεσία «WiFi από κάρτα».</span>")
            else:
                m.append("<span style='color:#ffc04d'>⚠ Δεν βρέθηκε ένδειξη της υπηρεσίας στο Pi. Τρέξε πρώτα τον "
                         "installer v1.5.2+ όσο το Pi είναι στο σπίτι, αλλιώς το αρχείο δεν θα διαβαστεί.</span>")
            if os.path.exists(os.path.join(c, BF)):
                m.append(f"ℹ Υπάρχει ήδη {BF} που δεν έχει εφαρμοστεί (θα αντικατασταθεί).")
            lp = os.path.join(c, BL)
            if os.path.exists(lp):
                try:
                    with open(lp, encoding="utf-8", errors="replace") as fh:
                        last = [x.strip() for x in fh if x.strip()][-3:]
                    m.append("<span style='color:#8b96ab'>Τελευταία από το Pi:<br>" + "<br>".join(last) + "</span>")
                except Exception:
                    pass
            self.info.setText("<br>".join(m))

        def use_current(self):
            s = wifi_current().get("ssid", "")
            if not s:
                return QMessageBox.information(self, APP_NAME, "Ο υπολογιστής δεν είναι σε WiFi (ή χρειάζεται άδεια Τοποθεσίας).")
            self.ssid.setCurrentText(s)
            self.fill_pw()

        def fill_pw(self):
            pw = win_wifi_password(self.ssid.currentText().strip())
            self.pw.setText(pw)
            five = bool(re.search(r"5g|5ghz|[-_ ]5$", self.ssid.currentText().lower()))
            self.note.setText("⚠ Μοιάζει με 5 GHz — το Pi Zero 2 W βλέπει μόνο 2.4 GHz." if five else
                              ("✔ Ο κωδικός βρέθηκε από τα Windows." if pw else "ℹ Γράψε τον κωδικό."))

        def add(self):
            ssid, pw = self.ssid.currentText().strip(), self.pw.text()
            if not ssid:
                return QMessageBox.warning(self, APP_NAME, "Γράψε το όνομα του WiFi.")
            if pw and not 8 <= len(pw) <= 63:
                return QMessageBox.warning(self, APP_NAME, "Ο κωδικός WiFi πρέπει να έχει 8–63 χαρακτήρες.")
            if not pw and QMessageBox.question(self, APP_NAME, "Χωρίς κωδικό = ανοιχτό δίκτυο. Συνέχεια;") != QMessageBox.StandardButton.Yes:
                return
            self.nets = [n for n in self.nets if n["ssid"] != ssid]
            self.nets.append({"ssid": ssid, "password": pw, "priority": self.prio.value(), "hidden": self.hidden.isChecked()})
            self.refresh()
            self.ssid.setCurrentText("")
            self.pw.clear()
            self.hidden.setChecked(False)

        def remove(self):
            r = self.tbl.currentRow()
            if 0 <= r < len(self.nets):
                del self.nets[r]
                self.refresh()

        def refresh(self):
            self.tbl.setRowCount(len(self.nets))
            for i, n in enumerate(self.nets):
                for j, val in enumerate((n["ssid"], "●" * min(8, len(n["password"])) or "(ανοιχτό)",
                                         str(n["priority"]), "ναι" if n["hidden"] else "")):
                    self.tbl.setItem(i, j, QTableWidgetItem(val))

        def write(self):
            c = self.drive.currentData()
            BF, BL, _BE = pi_boot_names(c)
            if not c:
                return QMessageBox.warning(self, APP_NAME, "Βάλε την κάρτα SD και πάτα «Αναζήτηση».")
            if not self.nets and self.ssid.currentText().strip():
                self.add()
            if not self.nets:
                return QMessageBox.warning(self, APP_NAME, "Πρόσθεσε τουλάχιστον ένα WiFi.")
            try:
                with open(os.path.join(c, BF), "w", encoding="utf-8", newline="") as fh:
                    fh.write(build_pi_wifi_file(self.nets))
            except Exception as e:
                return QMessageBox.critical(self, APP_NAME, f"Δεν γράφτηκε στην κάρτα:\n{e}")
            self.check_card()
            QMessageBox.information(self, APP_NAME,
                                    "✅ Γράφτηκε στην κάρτα!\n\n"
                                    "1. Βγάλε την κάρτα με ασφάλεια (εικονίδιο USB κάτω δεξιά → Εξαγωγή).\n"
                                    "2. Βάλ' την στο Pi και δώσε ρεύμα.\n"
                                    "3. Σε 1–2 λεπτά:  ssh pi@airsense.local  (ή το όνομα του Pi)\n\n"
                                    "Ο κωδικός σβήνεται αυτόματα από την κάρτα μόλις εφαρμοστεί.\n"
                                    f"Στο {BL} της κάρτας γράφεται σε ποιο WiFi μπήκε και η IP.")

    class ClickLabel(QLabel):
        def __init__(self, text, on_multi, n=5):
            super().__init__(text)
            self._on, self._n, self._clicks, self._t = on_multi, n, 0, 0

        def mousePressEvent(self, e):
            now = time.time()
            self._clicks = self._clicks + 1 if now - self._t < 1.2 else 1
            self._t = now
            if self._clicks >= self._n:
                self._clicks = 0
                self._on()


    class QrCard(QFrame):
        """Κάρτα με μεγάλο QR (ή οδηγίες όταν δεν υπάρχει διεύθυνση)."""

        def __init__(self, title, subtitle):
            super().__init__()
            self.setObjectName("card")
            self.url = ""
            v = QVBoxLayout(self)
            v.setContentsMargins(20, 16, 20, 16)
            t = QLabel(f"<b style='font-size:14pt'>{title}</b><br><span style='color:#8b96ab'>{subtitle}</span>")
            t.setWordWrap(True)
            v.addWidget(t)
            self.qr = QLabel()
            self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.qr.setMinimumHeight(250)
            v.addWidget(self.qr)
            self.link = QLabel()
            self.link.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.link.setOpenExternalLinks(True)
            self.link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            v.addWidget(self.link)
            self.info = QLabel()
            self.info.setWordWrap(True)
            self.info.setTextFormat(Qt.TextFormat.RichText)
            self.info.setOpenExternalLinks(True)
            v.addWidget(self.info)
            self.btns = QHBoxLayout()
            v.addLayout(self.btns)
            v.addStretch(1)

        def _set_buttons(self, items):
            while self.btns.count():
                it = self.btns.takeAt(0)
                wd = it.widget()
                if wd:
                    wd.hide()
                    wd.setParent(None)
                    wd.deleteLater()
            self.btns.addStretch()
            for text, fn, primary in items:
                b = _btn(text, fn, primary)
                b.setMinimumHeight(38)
                self.btns.addWidget(b)
            self.btns.addStretch()

        def show_qr(self, url, extra=""):
            self.url = url
            pm = qr_pixmap(url, 240)
            self.qr.setPixmap(pm)
            self.qr.show()
            self.link.setText(f"<a style='color:#3fa7ff;font-size:13pt' href='{url}'>{url}</a>")
            self.link.show()
            self.info.setText(f"<span style='color:#8b96ab'>{extra}</span>")
            self._set_buttons([("🌐 Άνοιγμα", lambda: webbrowser.open(self.url), False),
                               ("📋 Αντιγραφή", lambda: QApplication.clipboard().setText(self.url), False)])

        def show_info(self, html, actions=()):
            self.url = ""
            self.qr.clear()
            self.qr.hide()
            self.link.hide()
            self.info.setText(f"<span style='font-size:11pt'>{html}</span>")
            self._set_buttons(list(actions))

    class SensorCard(QFrame):
        """Κάρτα αισθητήρα στην καρτέλα «Αισθητήρες»."""

        def __init__(self, win, did):
            super().__init__()
            self.win, self.did = win, did
            self.setObjectName("card")
            h = QHBoxLayout(self)
            h.setContentsMargins(18, 14, 18, 14)
            h.setSpacing(18)
            self.dot = QLabel("●")
            self.dot.setStyleSheet("font-size:24pt")
            h.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignTop)
            mid = QVBoxLayout()
            mid.setSpacing(3)
            self.name = QLabel()
            self.name.setStyleSheet("font-size:14pt;font-weight:700")
            self.sub = QLabel()
            self.sub.setStyleSheet("color:#8b96ab")
            self.state = QLabel()
            self.state.setWordWrap(True)
            self.state.setTextFormat(Qt.TextFormat.RichText)
            for x in (self.name, self.sub, self.state):
                mid.addWidget(x)
            mid.addStretch()
            h.addLayout(mid, 1)
            self.vals = QLabel()
            self.vals.setTextFormat(Qt.TextFormat.RichText)
            self.vals.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            h.addWidget(self.vals)
            col = QVBoxLayout()
            col.setSpacing(6)
            col.addWidget(_btn("✏ Επεξεργασία", lambda: win.edit_sensor(did)))
            col.addWidget(_btn("🔁 Αλλαγή WiFi", win.open_move))
            more = QPushButton("⋯ Περισσότερα")
            m = QMenu(more)
            m.addAction("🌐 Σελίδα της συσκευής", lambda: win.open_sensor_page(did))
            self.pause_act = m.addAction("⏸ Παύση καταγραφής", self.toggle)
            m.addSeparator()
            m.addAction("🗑 Αφαίρεση", lambda: win.remove_sensor(did))
            more.setMenu(m)
            col.addWidget(more)
            h.addLayout(col)

        def toggle(self):
            d = self.win.engine.device(self.did)
            if d:
                self.win.engine.set_device_field(self.did, "enabled", not d.get("enabled", True))
                self.win.engine.poll_now()

        def update_data(self, d, st, nets):
            on = st.get("online")
            enabled = d.get("enabled", True)
            col = "#5b6475" if not enabled else ("#2ecc71" if on else "#ff5c5c" if on is False else "#8b96ab")
            self.dot.setStyleSheet(f"font-size:24pt;color:{col}")
            self.name.setText(d.get("name") or d["id"])
            self.sub.setText(f"{d['ip']}  ·  {d.get('type', '')}  ·  MAC {d.get('mac') or '—'}")
            ts = st.get("ts")
            last = datetime.fromtimestamp(ts).strftime("%d/%m %H:%M:%S") if ts else "—"
            self.pause_act.setText("▶ Συνέχιση καταγραφής" if not enabled else "⏸ Παύση καταγραφής")
            if not enabled:
                txt = "<span style='color:#8b96ab'>⏸ Σε παύση — δεν καταγράφεται</span>"
            elif on:
                txt = f"<span style='color:#2ecc71'>● Online</span> <span style='color:#8b96ab'>· τελευταία μέτρηση {last}</span>"
            elif on is False:
                host = parse_host(d["ip"])[0]
                same = False
                try:
                    same = any(ipaddress.ip_address(host) in n for n in nets)
                except ValueError:
                    same = True
                if not same and nets:
                    here = ", ".join(str(n.network_address).rsplit(".", 1)[0] + ".x" for n in nets)
                    txt = (f"<span style='color:#ff5c5c'>● Offline</span> — <b>ο υπολογιστής είναι σε άλλο δίκτυο</b> "
                           f"({here}). Ο αισθητήρας θα φανεί όταν είστε στο ίδιο WiFi. "
                           f"<span style='color:#8b96ab'>Τελευταία μέτρηση {last}</span>")
                else:
                    txt = (f"<span style='color:#ff5c5c'>● Offline</span> — δεν απαντά. Είναι αναμμένος; Αν άλλαξε IP, "
                           f"πάτα «🔍 Βρες αισθητήρες». <span style='color:#8b96ab'>Τελευταία μέτρηση {last}</span>")
            else:
                txt = "<span style='color:#8b96ab'>Σύνδεση…</span>"
            self.state.setText(txt)
            dim = "" if (on and enabled) else ";opacity:0.5"
            self.vals.setText(f"<span style='font-size:26pt;font-weight:700;color:#ff9f43{dim}'>{_fmt(st.get('t'))}°</span>"
                              f"&nbsp;&nbsp;<span style='font-size:26pt;font-weight:700;color:#3fa7ff{dim}'>{_fmt(st.get('h'))}%</span>"
                              f"<br><span style='color:#8b96ab'>δρόσος {_fmt(st.get('dp'))}°C</span>")

    class MainWindow(QMainWindow):
        def __init__(self, engine: Engine):
            super().__init__()
            self.engine = engine
            self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} — BleBox humiditySensor")
            self.setWindowIcon(app_icon())
            self.resize(1180, 780)
            self._cards = {}
            self._card_ids = ()
            self._sel_dev = None
            self._last_poll_counter = -1
            self._dev_fill = False
            self._last_ev = 0
            self._scan_was_running = False
            self._quitting = False

            tabs = QTabWidget()
            self.tabs = tabs
            self.setCentralWidget(tabs)
            self.T = {}
            for key, fn, title in (("home", self._tab_home, "🏠 Αρχική · 🚀 Ρύθμιση"), ("dash", self._tab_dashboard, "📊 Γραφήματα"),
                                   ("weather", self._tab_weather, "🌦 Καιρός"),
                                   ("devices", self._tab_devices, "📡 Αισθητήρες"),
                                   ("server", self._tab_server, "📱 Κινητό"),
                                   ("export", self._tab_export, "💾 Δεδομένα"), ("settings", self._tab_settings, "⚙ Ρυθμίσεις"),
                                   ("help", self._tab_help, "❓ Βοήθεια")):
                self.T[key] = fn()
                tabs.addTab(self.T[key], title)
            self.T["log"] = self.T["export"]
            self.T["email"] = self.T["settings"]
            tabs.currentChanged.connect(self._tab_changed)
            self.statusBar().showMessage(f"{AUTHOR} · {TEAM}")

            self._make_tray()
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.refresh)
            self.timer.start(1500)
            self.refresh()
            self.refresh_server_info()
            self._admin_ok = False
            sc = QShortcut(QKeySequence("Ctrl+Shift+A"), self)
            sc.activated.connect(self.open_admin)
            if not engine.cfg["devices"]:
                QTimer.singleShot(900, self.open_wizard)

        def open_move(self):
            MoveWifiDialog(self).exec()

        def open_admin(self):
            a = self.engine.cfg.get("admin") or {}
            if not a.get("hash"):
                pw, ok = QInputDialog.getText(self, "🔐 Νέος κωδικός διαχειριστή",
                                              "Ορίστε κωδικό διαχειριστή (τουλάχιστον 4 χαρακτήρες):", QLineEdit.EchoMode.Password)
                if not ok:
                    return
                if len(pw) < 4:
                    return QMessageBox.warning(self, APP_NAME, "Τουλάχιστον 4 χαρακτήρες.")
                pw2, ok = QInputDialog.getText(self, "🔐 Επιβεβαίωση", "Ξαναγράψτε τον κωδικό:", QLineEdit.EchoMode.Password)
                if not ok or pw2 != pw:
                    return QMessageBox.warning(self, APP_NAME, "Οι κωδικοί δεν ταιριάζουν.")
                salt, h = _pw_hash(pw)
                self.engine.cfg["admin"] = {"salt": salt, "hash": h}
                self.engine.save_cfg()
                self.engine.log("Ορίστηκε κωδικός διαχειριστή")
            elif not self._admin_ok:
                pw, ok = QInputDialog.getText(self, "🔐 Διαχειριστής", "Κωδικός διαχειριστή:", QLineEdit.EchoMode.Password)
                if not ok:
                    return
                if not hmac.compare_digest(_pw_hash(pw, a["salt"])[1], a["hash"]):
                    self.engine.log("Λάθος κωδικός διαχειριστή", "warn")
                    return QMessageBox.warning(self, APP_NAME, "Λάθος κωδικός.")
            self._admin_ok = True
            AdminDialog(self).exec()

        def open_wizard(self, page=P_WELCOME, preselect=None):
            if not self.isVisible():
                self.show_normal()
            SetupWizard(self, page, preselect).exec()

        # ── Αρχική (απλή οθόνη) ──
        def _tab_home(self):
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setSpacing(10)
            t = QLabel(f"💧 {APP_NAME}")
            t.setStyleSheet("font-size:20pt;font-weight:700")
            lay.addWidget(t)
            self.home_vals = QLabel()
            self.home_vals.setTextFormat(Qt.TextFormat.RichText)
            self.home_vals.setWordWrap(True)
            self.home_vals.setStyleSheet("font-size:13pt;background:#171c26;border:1px solid #262d3b;border-radius:14px;padding:14px")
            lay.addWidget(self.home_vals)
            # ── 🚀 Easy setup: 4 steps, the next one in blue, then it folds away ──
            sg = QFrame()
            sg.setObjectName("card")
            sl = QVBoxLayout(sg)
            sl.setContentsMargins(16, 12, 16, 12)
            sl.setSpacing(8)
            top = QHBoxLayout()
            self.setup_title = QLabel("🚀 <b>Εύκολη ρύθμιση</b>")
            self.setup_title.setStyleSheet("font-size:14pt")
            top.addWidget(self.setup_title)
            top.addStretch()
            self.setup_toggle = _btn("▾ Βήματα", self._toggle_setup)
            top.addWidget(self.setup_toggle)
            sl.addLayout(top)
            self.setup_bar = QProgressBar()
            self.setup_bar.setRange(0, 4)
            self.setup_bar.setFormat("%v / 4")
            sl.addWidget(self.setup_bar)
            self.setup_next = _btn("", None, True)
            self.setup_next.setMinimumHeight(48)
            self.setup_next.setStyleSheet("font-size:13pt")
            self.setup_next.clicked.connect(lambda: self._setup_next_fn and self._setup_next_fn())
            self._setup_next_fn = None
            sl.addWidget(self.setup_next)
            self.setup_body = QWidget()
            grid = QGridLayout(self.setup_body)
            grid.setContentsMargins(0, 4, 0, 0)
            grid.setVerticalSpacing(6)
            self.chk_rows = {}
            self._steps = (
                ("sensor", "1", "Αισθητήρας στο WiFi",
                 "Ο αισθητήρας στο ρεύμα → ο οδηγός τον βάζει στο WiFi σου (2.4 GHz) και τον βρίσκει.",
                 "🧙 Οδηγός αισθητήρα", lambda: self.open_wizard()),
                ("log", "2", "Μετρήσεις",
                 "Ο αισθητήρας απαντά και γράφονται μετρήσεις (κάθε λεπτό).",
                 "🔍 Βρες αισθητήρες", lambda: self.open_wizard(P_FIND)),
                ("server", "3", "Κινητό (ίδιο WiFi)",
                 "Στο κινητό: εφαρμογή AirSense → «Βρες αυτόματα». Ή στείλε τον έτοιμο PDF οδηγό.",
                 "📄 PDF οδηγός κινητού", lambda: self._phone_guide_pdf()),
                ("ts", "4", "Από παντού (Tailscale)",
                 "Για 4G / άλλο WiFi: Tailscale σε υπολογιστή + κινητό, ίδιος λογαριασμός.",
                 "🌍 Ρύθμιση Tailscale", lambda: self.open_wizard(P_PHONE)),
            )
            for r, (k, num, title, desc, bt, fn) in enumerate(self._steps):
                badge = QLabel(num)
                badge.setFixedSize(30, 30)
                badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lb = QLabel(f"<b>{title}</b><br><span style='color:#8b96ab'>{desc}</span>")
                lb.setTextFormat(Qt.TextFormat.RichText)
                lb.setWordWrap(True)
                b = _btn(bt, fn)
                b.setMinimumWidth(190)
                grid.addWidget(badge, r, 0)
                grid.addWidget(lb, r, 1)
                grid.addWidget(b, r, 2)
                self.chk_rows[k] = (badge, b, True)
            grid.setColumnStretch(1, 1)
            # optional extras, in one line
            ex = QHBoxLayout()
            ex.addWidget(QLabel("<span style='color:#8b96ab'>Προαιρετικά:</span>"))
            self.opt_email = _btn("✉ Email αναφορές", self.show_email)
            self.opt_wx = _btn("🌦 Καιρός", lambda: self.tabs.setCurrentWidget(self.T["weather"]))
            self.opt_auto = _btn("🖥 Εκκίνηση με Windows", lambda: self.cb_auto.setChecked(True))
            for b in (self.opt_email, self.opt_wx, self.opt_auto):
                ex.addWidget(b)
            ex.addStretch()
            grid.addLayout(ex, len(self._steps), 0, 1, 3)
            self.setup_body.setStyleSheet("background:transparent")
            sl.addWidget(self.setup_body)
            self._setup_open = None          # None = automatic (open until everything is ready)
            lay.addWidget(sg)

            # ── everyday shortcuts ──
            tiles = QGridLayout()
            for i, (text, fn) in enumerate((
                    ("📊\nΓραφήματα", lambda: self.tabs.setCurrentWidget(self.T["dash"])),
                    ("🌦\nΚαιρός", lambda: self.tabs.setCurrentWidget(self.T["weather"])),
                    ("📱\nΚινητό (QR / PDF)", lambda: self.tabs.setCurrentWidget(self.T["server"])),
                    ("💾\nΛήψη CSV / PDF", lambda: self.tabs.setCurrentWidget(self.T["export"])),
                    ("🔁\nΑισθητήρας σε νέο WiFi", self.open_move),
                    ("❓\nΒοήθεια", lambda: self.tabs.setCurrentWidget(self.T["help"])))):
                b = _btn(text, fn)
                b.setObjectName("tile")
                tiles.addWidget(b, i // 6, i % 6)
            lay.addLayout(tiles)
            lay.addStretch()
            return w

        def _toggle_setup(self):
            self._setup_open = not self.setup_body.isVisible()
            self._update_home()

        def _update_home(self):
            e = self.engine
            devs = e.devices()
            now = time.time()
            poll = int(e.cfg.get("poll_seconds", 60))
            parts = []
            any_on = recent = False
            for d in devs:
                with e.lock:
                    st = dict(e.live.get(d["id"], {}))
                on = st.get("online")
                any_on |= bool(on)
                recent |= bool(st.get("ts") and now - st["ts"] < 3 * poll + 30)
                dot = "<span style='color:#2ecc71'>● online</span>" if on else (
                    "<span style='color:#ff5c5c'>● offline</span>" if on is False else "<span style='color:#8b96ab'>● …</span>")
                parts.append(f"<b>{d.get('name')}</b> &nbsp; <span style='color:#ff9f43;font-size:24pt;font-weight:700'>"
                             f"{_fmt(st.get('t'))}°C</span> &nbsp; <span style='color:#3fa7ff;font-size:24pt;font-weight:700'>"
                             f"{_fmt(st.get('h'))}%</span> &nbsp; {dot} &nbsp; <span style='color:#8b96ab;font-size:10pt'>"
                             f"δρόσος {_fmt(st.get('dp'))}°C</span>")
            cw = self.engine.wx_snapshot()
            diffs = []
            if cw:
                for d in devs:
                    with e.lock:
                        st = dict(e.live.get(d["id"], {}))
                    lb = labels(e.cfg)
                    df = inout_diff(st.get("t"), st.get("h"), cw.get("temp"), cw.get("hum"), lb)
                    if not df:
                        continue
                    sg = lambda x, dec=1: ("+" if x > 0 else "") + _fmt(x, dec)
                    col = {1: "#2ecc71", -1: "#ffc04d", 0: "#8b96ab"}[df["vent"]]
                    who = f"<b>{d.get('name')}</b> " if len(devs) > 1 else ""
                    diffs.append(
                        f"<span style='font-size:12pt'>↕ {who}{lb['inside']} − {lb['outside']}: "
                        f"<span style='color:#ff9f43;font-weight:700'>{sg(df['dt'])}°C</span> · "
                        f"<span style='color:#3fa7ff;font-weight:700'>{sg(df['dh'])}% RH</span> · "
                        f"απόλυτη {_fmt(df['ah_in'])} / {_fmt(df['ah_out'])} g/m³ "
                        f"<span style='color:#8b96ab'>({lb['inside']} / {lb['outside']})</span><br>"
                        f"<span style='color:{col}'>💨 {df['vent_txt']}</span></span>")
            if cw:
                parts.append(f"<span style='font-size:12pt'>{cw['icon']} <b>{self.engine.cfg['weather'].get('place', '')}</b>: "
                             f"{cw['text']} · <span style='color:#2ecc71'>{_fmt(cw['temp'])}°C</span> · "
                             f"{_fmt(cw['hum'], 0)}% · <i>{cw['status']}</i> <span style='color:#8b96ab'>({labels(e.cfg)['outside']}, Open-Meteo)"
                             f"</span></span>")
            parts += diffs
            self.home_vals.setText("<br>".join(parts) if parts else
                                   "👋 Δεν υπάρχει ακόμα αισθητήρας.<br>Πάτα το μπλε κουμπί <b>▶ Επόμενο</b> παρακάτω — σε πάει βήμα-βήμα.")
            state = {"sensor": any_on, "log": recent, "server": e.httpd is not None,
                     "ts": bool((e._ts_cache[1] or {}).get("ip")), "email": bool(e.cfg["email"].get("enabled")),
                     "auto": self.cb_auto.isChecked(), "wx": bool(self.engine.wx_snapshot())}
            done = 0
            nxt = None
            for k, num, title, _d, bt, fn in self._steps:
                badge, b, _req = self.chk_rows[k]
                ok = state[k]
                done += ok
                if ok:
                    badge.setText("✓")
                    badge.setStyleSheet("background:#2ecc71;color:#ffffff;border-radius:15px;font-weight:700;font-size:12pt")
                elif nxt is None:
                    nxt = (num, title, bt, fn)
                    badge.setText(num)
                    badge.setStyleSheet("background:#2b6cff;color:#ffffff;border-radius:15px;font-weight:700;font-size:12pt")
                else:
                    badge.setText(num)
                    badge.setStyleSheet("background:#262d3b;color:#8b96ab;border-radius:15px;font-weight:700;font-size:12pt")
                b.setText(bt if not ok else "✓ " + bt.split(" ", 1)[-1])
            self.setup_bar.setValue(done)
            self.opt_email.setVisible(not state["email"])
            self.opt_wx.setVisible(not state["wx"])
            self.opt_auto.setVisible(not state["auto"])
            if nxt:
                num, title, bt, fn = nxt
                self.setup_title.setText(f"🚀 <b>Εύκολη ρύθμιση</b> &nbsp;<span style='color:#8b96ab'>— βήμα {num} από 4</span>")
                self.setup_next.setText(f"▶  Επόμενο: {title}  —  {bt}")
                self._setup_next_fn = fn
                self.setup_next.setVisible(True)
            else:
                self.setup_title.setText("✅ <b>Όλα έτοιμα</b> &nbsp;<span style='color:#8b96ab'>— αισθητήρας, μετρήσεις, κινητό, από παντού</span>")
                self.setup_next.setVisible(False)
                self._setup_next_fn = None
            show = self._setup_open if self._setup_open is not None else bool(nxt)
            self.setup_body.setVisible(show)
            self.setup_bar.setVisible(bool(nxt))
            self.setup_toggle.setText("▴ Απόκρυψη" if show else "▾ Βήματα")

        # ── Πίνακας ──
        def _tab_dashboard(self):
            w = QWidget()
            lay = QVBoxLayout(w)
            self.cards_wrap = QWidget()
            self.cards_lay = QHBoxLayout(self.cards_wrap)
            self.cards_lay.setContentsMargins(0, 0, 0, 0)
            self.cards_lay.addStretch()
            sa = QScrollArea()
            sa.setWidget(self.cards_wrap)
            sa.setWidgetResizable(True)
            sa.setFixedHeight(175)
            sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            lay.addWidget(sa)
            ctl = QHBoxLayout()
            ctl.addWidget(QLabel("Συσκευή:"))
            self.dev_combo = QComboBox()
            self.dev_combo.setMinimumWidth(220)
            self.dev_combo.currentIndexChanged.connect(self._combo_changed)
            ctl.addWidget(self.dev_combo)
            ctl.addWidget(QLabel("Διάστημα:"))
            self.range_combo = QComboBox()
            for h, t in ((1, "1 ώρα"), (6, "6 ώρες"), (24, "24 ώρες"), (72, "3 ημέρες"), (168, "7 ημέρες"),
                         (720, "30 ημέρες"), (2160, "90 ημέρες"), (8784, "1 έτος")):
                self.range_combo.addItem(t, h)
            self.range_combo.setCurrentIndex(2)
            self.range_combo.currentIndexChanged.connect(self.refresh_chart)
            ctl.addWidget(self.range_combo)
            ctl.addStretch()
            self.stats_lbl = QLabel("")
            self.stats_lbl.setStyleSheet("color:#8b96ab")
            ctl.addWidget(self.stats_lbl)
            ctl.addWidget(_btn("⟳ Μέτρηση τώρα", self.engine.poll_now, True))
            lay.addLayout(ctl)

            pg.setConfigOptions(antialias=True, background=tc("#141821"), foreground=tc("#c8d0e0"))
            self.glw = pg.GraphicsLayoutWidget()
            self.plot_t = self.glw.addPlot(row=0, col=0, axisItems={"bottom": pg.DateAxisItem()})
            self.plot_h = self.glw.addPlot(row=1, col=0, axisItems={"bottom": pg.DateAxisItem()})
            self.plot_h.setXLink(self.plot_t)
            self.plot_t.setLabel("left", "Θερμοκρασία", units="°C")
            self.plot_h.setLabel("left", "Υγρασία", units="%RH")
            for p in (self.plot_t, self.plot_h):
                p.showGrid(x=True, y=True, alpha=0.2)
                p.addLegend(offset=(10, 5))
            lb = labels(self.engine.cfg)
            self.cur_t = self.plot_t.plot(pen=pg.mkPen("#ff9f43", width=2), name=f"Θερμοκρασία · {lb['inside']}", connect="finite")
            self.cur_dp = self.plot_t.plot(pen=pg.mkPen("#a78bfa", width=1, style=Qt.PenStyle.DashLine),
                                           name="Σημείο δρόσου", connect="finite")
            self.cur_h = self.plot_h.plot(pen=pg.mkPen("#3fa7ff", width=2), name=f"Υγρασία · {lb['inside']}", connect="finite",
                                          fillLevel=0, brush=QBrush(QColor(63, 167, 255, 40)))
            self.cur_out_t = self.plot_t.plot(pen=pg.mkPen("#2ecc71", width=1.6, style=Qt.PenStyle.DashLine),
                                              name=f"{lb['outside']} (Open-Meteo)", connect="finite")
            self.cur_out_h = self.plot_h.plot(pen=pg.mkPen("#1abc9c", width=1.6, style=Qt.PenStyle.DashLine),
                                              name=f"{lb['outside']} (Open-Meteo)", connect="finite")
            self.vline = pg.InfiniteLine(angle=90, pen=pg.mkPen("#00000040" if THEME["light"] else "#ffffff55"))
            self.hover_lbl = pg.TextItem(anchor=(0, 0), color="#e6ebf5", fill=QColor(23, 28, 38, 230))
            self.plot_t.addItem(self.vline, ignoreBounds=True)
            self.plot_t.addItem(self.hover_lbl, ignoreBounds=True)
            self.hover_lbl.hide()
            self._chart_data = None
            self.glw.scene().sigMouseMoved.connect(self._mouse_moved)
            lay.addWidget(self.glw, 1)
            return w

        def _mouse_moved(self, pos):
            if self._chart_data is None or not len(self._chart_data[0]):
                return
            vb = self.plot_t.vb
            if not self.plot_t.sceneBoundingRect().contains(pos) and not self.plot_h.sceneBoundingRect().contains(pos):
                self.hover_lbl.hide()
                return
            x = vb.mapSceneToView(pos).x()
            xs, ts, hs, dps = self._chart_data
            i = int(np.clip(np.searchsorted(xs, x), 0, len(xs) - 1))
            if i > 0 and abs(xs[i - 1] - x) < abs(xs[i] - x):
                i -= 1
            self.vline.setPos(xs[i])
            f = lambda v: "—" if np.isnan(v) else f"{v:.1f}"
            self.hover_lbl.setText(f"{datetime.fromtimestamp(xs[i]):%d/%m %H:%M}\n🌡 {f(ts[i])} °C\n💧 {f(hs[i])} %\n"
                                   f"Δρόσος {f(dps[i])} °C")
            yr = vb.viewRange()[1]
            self.hover_lbl.setPos(xs[i], yr[1])
            self.hover_lbl.show()

        def _combo_changed(self):
            did = self.dev_combo.currentData()
            if did and did != self._sel_dev:
                self._sel_dev = did
                self.refresh_chart()
                self.refresh_wx_charts()
                self._update_cards(force=True)

        def _select_dev(self, did):
            i = self.dev_combo.findData(did)
            if i >= 0:
                self.dev_combo.setCurrentIndex(i)

        def _update_cards(self, force=False):
            devs = self.engine.devices()
            ids = tuple(d["id"] for d in devs)
            if ids != self._card_ids:
                for c in self._cards.values():
                    c.setParent(None)
                self._cards = {}
                for d in devs:
                    c = DeviceCard(self._select_dev)
                    self._cards[d["id"]] = c
                    self.cards_lay.insertWidget(self.cards_lay.count() - 1, c)
                self._card_ids = ids
                self.dev_combo.blockSignals(True)
                self.dev_combo.clear()
                for d in devs:
                    self.dev_combo.addItem(d.get("name") or d["id"], d["id"])
                if self._sel_dev not in ids:
                    self._sel_dev = ids[0] if ids else None
                if self._sel_dev:
                    self.dev_combo.setCurrentIndex(self.dev_combo.findData(self._sel_dev))
                self.dev_combo.blockSignals(False)
                self.refresh_chart()
            for d in devs:
                if self.dev_combo.findData(d["id"]) >= 0:
                    self.dev_combo.setItemText(self.dev_combo.findData(d["id"]), d.get("name") or d["id"])
                with self.engine.lock:
                    st = dict(self.engine.live.get(d["id"], {}))
                self._cards[d["id"]].set_data(d, st, d["id"] == self._sel_dev)

        def refresh_chart(self):
            did = self._sel_dev
            hours = self.range_combo.currentData() or 24
            if not did:
                for c in (self.cur_t, self.cur_h, self.cur_dp):
                    c.setData([], [])
                self._chart_data = None
                self.stats_lbl.setText("")
                return
            pts = self.engine.history_points(did, hours)
            xs = np.array([p[0] for p in pts], dtype=float)
            nan = lambda v: np.nan if v is None else v
            ts = np.array([nan(p[1]) for p in pts], dtype=float)
            hs = np.array([nan(p[2]) for p in pts], dtype=float)
            dps = np.array([nan(p[3]) for p in pts], dtype=float)
            self._chart_data = (xs, ts, hs, dps)
            self.cur_t.setData(xs, ts, connect="finite")
            self.cur_dp.setData(xs, dps, connect="finite")
            self.cur_h.setData(xs, hs, connect="finite")
            few = len(xs) < 40
            for cur, col in ((self.cur_t, "#ff9f43"), (self.cur_h, "#3fa7ff")):
                cur.setSymbol("o" if few else None)
                cur.setSymbolSize(6)
                cur.setSymbolBrush(col)
                cur.setSymbolPen(col)
            wp = self.engine.weather_points(hours)
            wx_ = np.array([w[0] for w in wp], dtype=float)
            self.cur_out_t.setData(wx_, np.array([nan(w[1]) for w in wp], dtype=float), connect="finite")
            self.cur_out_h.setData(wx_, np.array([nan(w[2]) for w in wp], dtype=float), connect="finite")
            now = time.time()
            self.plot_t.setXRange(now - hours * 3600, now, padding=0.01)
            self.plot_t.enableAutoRange(axis="y")
            self.plot_h.enableAutoRange(axis="y")
            if len(xs) and np.isfinite(ts).any():
                self.stats_lbl.setText(f"Θερμ. {np.nanmin(ts):.1f}…{np.nanmax(ts):.1f} °C (μ.ο. {np.nanmean(ts):.1f})  ·  "
                                       f"Υγρ. {np.nanmin(hs):.1f}…{np.nanmax(hs):.1f} % (μ.ο. {np.nanmean(hs):.1f})")
            else:
                self.stats_lbl.setText("Δεν υπάρχουν μετρήσεις για το διάστημα")

        # ── Καιρός (Open-Meteo) ──
        def _tab_weather(self):
            w = QWidget()
            lay = QVBoxLayout(w)
            g = QGroupBox("📍 Τοποθεσία (πού βρίσκεται ο αισθητήρας)")
            gl = QHBoxLayout(g)
            self.wx_search = QLineEdit()
            self.wx_search.setPlaceholderText("Γράψε πόλη ή χωριό, π.χ. Αμύνταιο, Πτολεμαΐδα, Θεσσαλονίκη…")
            self.wx_search.returnPressed.connect(self._wx_find)
            self.wx_results = QComboBox()
            self.wx_results.setMinimumWidth(280)
            gl.addWidget(self.wx_search, 2)
            gl.addWidget(_btn("🔍 Αναζήτηση", self._wx_find))
            gl.addWidget(self.wx_results, 2)
            gl.addWidget(_btn("📍 Ορισμός", self._wx_set, True))
            gl.addWidget(_btn("🛰 Αυτόματα από τον υπολογιστή", self._wx_auto))
            wcfg = self.engine.cfg["weather"]
            self.wx_en = QCheckBox("Ενεργό")
            self.wx_en.setChecked(bool(wcfg.get("enabled")))
            self.wx_en.toggled.connect(self._wx_toggle)
            self.wx_int = QSpinBox()
            self.wx_int.setRange(5, 120)
            self.wx_int.setSuffix(" λεπτά")
            self.wx_int.setValue(int(wcfg.get("interval_min", 15)))
            self.wx_int.valueChanged.connect(lambda v: (self.engine.cfg["weather"].__setitem__("interval_min", v),
                                                        self.engine.save_cfg()))
            gl.addWidget(self.wx_en)
            gl.addWidget(QLabel("ανά"))
            gl.addWidget(self.wx_int)
            gl.addWidget(_btn("⟳", lambda: self.engine.wx_wake.set()))
            lay.addWidget(g)
            ar = QHBoxLayout()
            self.wx_auto_cb = QCheckBox("Αυτόματη τοποθεσία σε κάθε εκκίνηση (π.χ. laptop που αλλάζει εργοτάξιο)")
            self.wx_auto_cb.setChecked(bool(wcfg.get("auto")))
            self.wx_auto_cb.toggled.connect(lambda v: (self.engine.cfg["weather"].__setitem__("auto", v), self.engine.save_cfg()))
            ar.addWidget(self.wx_auto_cb)
            self.wx_loc_lbl = QLabel("<span style='color:#8b96ab'>Αυτόματα: πρώτα τοποθεσία Windows (WiFi/GPS — ενεργοποίησε "
                                     "Ρυθμίσεις → Απόρρητο → Τοποθεσία), αλλιώς από IP (κατά προσέγγιση· με Starlink "
                                     "μπορεί να βγει λάθος πόλη).</span>")
            self.wx_loc_lbl.setWordWrap(True)
            ar.addWidget(self.wx_loc_lbl, 1)
            lay.addLayout(ar)
            top = QHBoxLayout()
            self.wx_now = QLabel("")
            self.wx_now.setTextFormat(Qt.TextFormat.RichText)
            self.wx_now.setObjectName("card")
            self.wx_now.setStyleSheet("background:#171c26;border:1px solid #262d3b;border-radius:14px;padding:12px")
            self.wx_now.setMinimumWidth(330)
            top.addWidget(self.wx_now)
            fc = QScrollArea()
            fc.setWidgetResizable(True)
            fc.setFixedHeight(170)
            self.fc_wrap = QWidget()
            self.fc_lay = QHBoxLayout(self.fc_wrap)
            self.fc_lay.setContentsMargins(0, 0, 0, 0)
            fc.setWidget(self.fc_wrap)
            top.addWidget(fc, 1)
            lay.addLayout(top)
            ctl = QHBoxLayout()
            ctl.addWidget(QLabel("Γραφήματα:"))
            self.wx_range = QComboBox()
            for hh, tt in ((24, "24 ώρες"), (72, "3 ημέρες"), (168, "7 ημέρες"), (720, "30 ημέρες"), (2160, "90 ημέρες")):
                self.wx_range.addItem(tt, hh)
            self.wx_range.setCurrentIndex(1)
            self.wx_range.currentIndexChanged.connect(self.refresh_wx_charts)
            ctl.addWidget(self.wx_range)
            lb = labels(self.engine.cfg)
            ctl.addWidget(QLabel(f"<span style='color:#8b96ab'>{lb['inside']} = επιλεγμένος αισθητήρας · {lb['outside']} = Open-Meteo</span>"))
            ctl.addStretch()
            lay.addLayout(ctl)
            self.wx_glw = pg.GraphicsLayoutWidget()
            P = []
            for row, (lbl, unit) in enumerate((("Θερμοκρασία", "°C"), ("Υγρασία", "%"), ("Βροχή / Χιόνι", "mm·cm"),
                                               ("Ηλιοφάνεια", "λεπτά/ώρα"))):
                pl = self.wx_glw.addPlot(row=row, col=0, axisItems={"bottom": pg.DateAxisItem()})
                pl.setLabel("left", lbl, units=unit)
                pl.showGrid(x=True, y=True, alpha=0.2)
                if P:
                    pl.setXLink(P[0])
                P.append(pl)
            self.wx_plots = P
            P[0].addLegend(offset=(10, 5))
            P[1].addLegend(offset=(10, 5))
            self.wx_in_t = P[0].plot(pen=pg.mkPen("#ff9f43", width=2), name=lb["inside"], connect="finite")
            self.wx_out_t = P[0].plot(pen=pg.mkPen("#2ecc71", width=2), name=lb["outside"], connect="finite")
            self.wx_in_h = P[1].plot(pen=pg.mkPen("#3fa7ff", width=2), name=lb["inside"], connect="finite")
            self.wx_out_h = P[1].plot(pen=pg.mkPen("#1abc9c", width=2), name=lb["outside"], connect="finite")
            self.wx_rain = None
            self.wx_snow = None
            self.wx_sun = None
            lay.addWidget(self.wx_glw, 1)
            self.wx_note = QLabel("<span style='color:#8b96ab'>Δεδομένα καιρού: Open-Meteo.com (CC BY 4.0). Καταγράφονται "
                                  "μαζί με κάθε μέτρηση στα CSV/XML: εξωτ. θερμοκρασία/υγρασία, καιρός, κατάσταση "
                                  "(Βροχή / Χιόνι / Ηλιοφάνεια / Συννεφιά / Ομίχλη / Καταιγίδα / Νύχτα), βροχή, χιόνι, "
                                  "νέφωση, άνεμος, ηλιοφάνεια.</span>")
            self.wx_note.setWordWrap(True)
            lay.addWidget(self.wx_note)
            self._wx_seen = -1
            return w

        def _wx_find(self):
            q = self.wx_search.text().strip()
            if not q:
                return
            self.wx_results.clear()
            self.wx_results.addItem("Αναζήτηση…")

            def done(res, err):
                self.wx_results.clear()
                if err or not res:
                    self.wx_results.addItem("Δεν βρέθηκε" if not err else f"Σφάλμα: {err}")
                    return
                for r in res:
                    self.wx_results.addItem(f"{r['label']}  ({r['lat']:.3f}, {r['lon']:.3f})", r)
            Bg(self, lambda: geocode(q), done)

        def _wx_set(self):
            r = self.wx_results.currentData()
            if not r:
                return QMessageBox.information(self, APP_NAME, "Γράψε τοποθεσία, πάτα «Αναζήτηση» και διάλεξε από τη λίστα.")
            self.engine.set_weather_location(r["label"], r["lat"], r["lon"], True)
            self.wx_en.setChecked(True)
            self.wx_now.setText("⏳ Λήψη καιρού…")

        def _wx_auto(self):
            self.wx_now.setText("🛰 Εντοπισμός τοποθεσίας υπολογιστή… (έως 30″)")

            def done(loc, err):
                if err:
                    self.wx_now.setText(f"❌ {err}")
                    if os.name == "nt" and QMessageBox.question(
                            self, APP_NAME, f"{err}\n\nΆνοιγμα ρυθμίσεων Τοποθεσίας των Windows;") == QMessageBox.StandardButton.Yes:
                        try:
                            os.startfile("ms-settings:privacy-location")
                        except Exception:
                            pass
                    return
                self.wx_en.setChecked(True)
                self.wx_results.clear()
                self.wx_results.addItem(f"{loc['label']}  ({loc['lat']:.3f}, {loc['lon']:.3f})",
                                        {"label": loc["label"], "lat": loc["lat"], "lon": loc["lon"]})
                self.wx_now.setText(f"📍 <b>{loc['label']}</b><br><span style='color:#8b96ab'>{loc['source']}</span><br>⏳ Λήψη καιρού…")
            Bg(self, self.engine.auto_locate, done)

        def _wx_toggle(self, on):
            w = self.engine.cfg["weather"]
            if on and w.get("lat") is None:
                self.wx_en.setChecked(False)
                return QMessageBox.information(self, APP_NAME, "Όρισε πρώτα τοποθεσία (Αναζήτηση → Ορισμός).")
            w["enabled"] = on
            self.engine.save_cfg()
            self.engine.wx_wake.set()

        def refresh_weather(self):
            e = self.engine
            if e.wx_counter == self._wx_seen:
                return
            self._wx_seen = e.wx_counter
            wd = e.weather_dict()
            c = wd.get("current")
            if not wd["enabled"] or not c:
                self.wx_now.setText("<span style='font-size:12pt'>🌦 <b>Καιρός Open-Meteo</b></span><br><br>"
                                    "1. Γράψε την πόλη/χωριό του αισθητήρα<br>2. Πάτα <b>🔍 Αναζήτηση</b><br>"
                                    "3. Διάλεξε και πάτα <b>📍 Ορισμός</b>"
                                    + (f"<br><br><span style='color:#ff5c5c'>{wd['error']}</span>" if wd.get("error") else ""))
            else:
                sun = "—" if c.get("sunshine") is None else f"{c['sunshine'] / 60:.0f} λεπτά/ώρα"
                today = wd["daily"][0] if wd["daily"] else {}
                self.wx_now.setText(
                    f"<span style='font-size:34pt'>{c['icon']}</span> <span style='font-size:28pt;font-weight:700'>"
                    f"{_fmt(c['temp'])}°C</span><br><b style='font-size:13pt'>{c['text']}</b> &nbsp; "
                    f"<span style='background:#2b6cff55;border-radius:8px;padding:2px 8px'>{c['status']}</span><br>"
                    f"<span style='color:#8b96ab'>📍 {wd['place']}</span><br><br>"
                    f"Αίσθηση <b>{_fmt(c['feels'])}°C</b> · Υγρασία <b>{_fmt(c['hum'], 0)}%</b><br>"
                    f"🌬 {_fmt(c['wind'], 0)} km/h (ριπές {_fmt(c['gust'], 0)}) · ☁ {_fmt(c['cloud'], 0)}%<br>"
                    f"🌧 {_fmt(c['rain'])} mm · ❄ {_fmt(c['snow'])} cm · ☀ {sun}<br>"
                    f"🔽 {_fmt(c['pressure'], 0)} hPa · 🌅 {str(today.get('sunrise') or '')[-5:]} · 🌇 {str(today.get('sunset') or '')[-5:]}<br>"
                    f"<span style='color:#5b6475'>ενημέρωση {datetime.fromtimestamp(wd['updated']):%H:%M}</span>")
            while self.fc_lay.count():
                it = self.fc_lay.takeAt(0)
                if it.widget():
                    it.widget().deleteLater()
            for d in wd.get("daily") or []:
                prob = "" if d.get("prob") is None else f" · {d['prob']}%"
                snow = f"❄ {_fmt(d['snow'])} cm<br>" if (d.get("snow") or 0) > 0 else ""
                sunh = "—" if d.get("sunshine") is None else f"{d['sunshine'] / 3600:.1f}"
                card = QLabel(f"<div align='center'><b>{d['day']}</b><br><span style='font-size:24pt'>{d['icon']}</span><br>"
                              f"<span style='color:#8b96ab'>{d['text']}</span><br>{_fmt(d['tmin'], 0)}° / <b>{_fmt(d['tmax'], 0)}°</b><br>"
                              f"🌧 {_fmt(d['precip'])} mm{prob}<br>{snow}☀ {sunh} ώρ.</div>")
                card.setTextFormat(Qt.TextFormat.RichText)
                card.setStyleSheet("background:#1b2130;border-radius:12px;padding:8px")
                card.setMinimumWidth(118)
                self.fc_lay.addWidget(card)
            self.fc_lay.addStretch()
            self.refresh_wx_charts()

        def refresh_wx_charts(self):
            hours = self.wx_range.currentData() or 72
            nan = lambda v: np.nan if v is None else v
            wp = self.engine.weather_points(hours)
            xs = np.array([w[0] for w in wp], dtype=float)
            self.wx_out_t.setData(xs, np.array([nan(w[1]) for w in wp], dtype=float), connect="finite")
            self.wx_out_h.setData(xs, np.array([nan(w[2]) for w in wp], dtype=float), connect="finite")
            if self._sel_dev:
                pts = self.engine.history_points(self._sel_dev, hours)
                ix = np.array([p[0] for p in pts], dtype=float)
                self.wx_in_t.setData(ix, np.array([nan(p[1]) for p in pts], dtype=float), connect="finite")
                self.wx_in_h.setData(ix, np.array([nan(p[2]) for p in pts], dtype=float), connect="finite")
            width = max(600.0, float(np.median(np.diff(xs))) * 0.8) if len(xs) > 1 else 3000.0
            for attr, plot in (("wx_rain", 2), ("wx_snow", 2), ("wx_sun", 3)):
                old = getattr(self, attr)
                if old is not None:
                    self.wx_plots[plot].removeItem(old)
                setattr(self, attr, None)
            if len(xs):
                rain = np.array([w[3] or 0 for w in wp], dtype=float)
                snow = np.array([w[4] or 0 for w in wp], dtype=float)
                sun = np.array([(w[6] or 0) / 60.0 for w in wp], dtype=float)
                self.wx_rain = pg.BarGraphItem(x=xs, height=rain, width=width, brush=QColor(90, 169, 255, 190), pen=None)
                self.wx_snow = pg.BarGraphItem(x=xs, height=snow, width=width, brush=QColor(230, 240, 255, 200), pen=None)
                self.wx_sun = pg.BarGraphItem(x=xs, height=sun, width=width, brush=QColor(255, 200, 60, 200), pen=None)
                self.wx_plots[2].addItem(self.wx_rain)
                self.wx_plots[2].addItem(self.wx_snow)
                self.wx_plots[3].addItem(self.wx_sun)
            now = time.time()
            self.wx_plots[0].setXRange(now - hours * 3600, now + 600, padding=0.01)
            for pl in self.wx_plots:
                pl.enableAutoRange(axis="y")

        # ── Αισθητήρες ──
        def _tab_devices(self):
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setSpacing(10)
            bar = QHBoxLayout()
            self.find_btn = _btn("🔍  Βρες αισθητήρες στο δίκτυο", self._scan, True)
            add_btn = _btn("➕  Προσθήκη με IP", self._add_ip)
            wiz_btn = _btn("🧙  Νέος αισθητήρας (ρύθμιση WiFi)", lambda: self.open_wizard())
            for b_ in (self.find_btn, add_btn, wiz_btn):
                b_.setMinimumHeight(50)
                b_.setStyleSheet("font-size:11pt")
                bar.addWidget(b_, 1)
            lay.addLayout(bar)
            self.scan_bar = QProgressBar()
            self.scan_bar.setMaximumHeight(8)
            self.scan_bar.setTextVisible(False)
            self.scan_bar.hide()
            lay.addWidget(self.scan_bar)
            self.scan_msg = QLabel("")
            self.scan_msg.setWordWrap(True)
            self.scan_msg.setTextFormat(Qt.TextFormat.RichText)
            self.scan_msg.setStyleSheet("font-size:10.5pt")
            lay.addWidget(self.scan_msg)
            sa = QScrollArea()
            sa.setWidgetResizable(True)
            box = QWidget()
            self.cards_v = QVBoxLayout(box)
            self.cards_v.setContentsMargins(0, 0, 0, 0)
            self.cards_v.setSpacing(10)
            self.cards_v.addStretch()
            sa.setWidget(box)
            lay.addWidget(sa, 1)
            self.sensor_cards = {}
            self._sensor_ids = None
            self._nets_cache = (0, [])
            return w

        def _local_nets(self):
            if time.time() - self._nets_cache[0] > 30:
                self._nets_cache = (time.time(), build_networks(""))
            return self._nets_cache[1]

        def _fill_dev_table(self):
            devs = self.engine.devices()
            ids = tuple(d["id"] for d in devs)
            if ids != self._sensor_ids:
                self._sensor_ids = ids
                while self.cards_v.count() > 1:
                    it = self.cards_v.takeAt(0)
                    if it.widget():
                        it.widget().deleteLater()
                self.sensor_cards = {}
                if not devs:
                    e = QLabel("<div align='center' style='font-size:13pt'>📡<br><b>Δεν υπάρχει αισθητήρας ακόμα</b><br>"
                               "<span style='color:#8b96ab;font-size:11pt'>Είναι ήδη στο WiFi σου → «🔍 Βρες αισθητήρες»<br>"
                               "Είναι καινούριος → «🧙 Νέος αισθητήρας»</span></div>")
                    e.setTextFormat(Qt.TextFormat.RichText)
                    e.setMinimumHeight(220)
                    self.cards_v.insertWidget(0, e)
                for d in devs:
                    c = SensorCard(self, d["id"])
                    self.sensor_cards[d["id"]] = c
                    self.cards_v.insertWidget(self.cards_v.count() - 1, c)
            nets = self._local_nets()
            for d in devs:
                with self.engine.lock:
                    st = dict(self.engine.live.get(d["id"], {}))
                self.sensor_cards[d["id"]].update_data(d, st, nets)

        def _update_scan(self):
            sc = self.engine.scan
            running = sc["running"]
            self.find_btn.setEnabled(not running)
            self.find_btn.setText("⏳  Αναζήτηση… " + (f"{sc['done']}/{sc['total']}" if sc["total"] else "") if running
                                  else "🔍  Βρες αισθητήρες στο δίκτυο")
            self.scan_bar.setVisible(running)
            if running:
                self.scan_bar.setMaximum(max(1, sc["total"]))
                self.scan_bar.setValue(sc["done"])
                nets = ", ".join(str(n) for n in build_networks(self.engine.cfg.get("subnets", ""))) or "—"
                self.scan_msg.setText(f"<span style='color:#8b96ab'>Ψάχνω στο δίκτυο {nets}…</span>")
            elif self._scan_was_running:
                with self.engine.lock:
                    bb = [dict(r) for r in sc["results"] if r["blebox"]]
                nets = ", ".join(str(n) for n in build_networks(self.engine.cfg.get("subnets", ""))) or "—"
                mine = {d["id"] for d in self.engine.devices()}
                if bb:
                    rows = "<br>".join(f"&nbsp;&nbsp;• <b>{r['name'] or r['type']}</b> — {r['ip']}"
                                       + ("" if r["id"] in mine else " <span style='color:#ffc04d'>(δεν προστέθηκε — "
                                                                     "«➕ Προσθήκη με IP»)</span>") for r in bb)
                    self.scan_msg.setText(f"<span style='color:#2ecc71'>✅ Βρέθηκαν {len(bb)} συσκευές BleBox:</span><br>{rows}")
                else:
                    self.scan_msg.setText(
                        f"<span style='color:#ffc04d'>Δεν βρέθηκε αισθητήρας στο δίκτυο {nets}.</span> "
                        "<span style='color:#8b96ab'>Ο υπολογιστής και ο αισθητήρας πρέπει να είναι στο <b>ίδιο WiFi</b>. "
                        "Αν ο αισθητήρας είναι καινούριος → «🧙 Νέος αισθητήρας».</span>")
            self._scan_was_running = running

        def _scan(self):
            if not self.engine.start_scan():
                QMessageBox.information(self, APP_NAME, "Η αναζήτηση είναι ήδη σε εξέλιξη.")

        def _add_ip(self):
            addr, ok = QInputDialog.getText(self, "Προσθήκη αισθητήρα",
                                            "Διεύθυνση IP του αισθητήρα (π.χ. 192.168.1.50 ή IP:θύρα):")
            if ok and addr.strip():
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                try:
                    okk, msg = self.engine.add_manual(addr)
                finally:
                    QApplication.restoreOverrideCursor()
                (QMessageBox.information if okk else QMessageBox.warning)(self, APP_NAME, msg)

        def edit_sensor(self, did):
            d = self.engine.device(did)
            if not d:
                return
            dlg = QDialog(self)
            dlg.setWindowTitle(f"✏ {d.get('name')}")
            dlg.resize(460, 230)
            f = QFormLayout(dlg)
            name = QLineEdit(d.get("name", ""))
            ip = QLineEdit(d["ip"])
            en = QCheckBox("Καταγραφή ενεργή")
            en.setChecked(d.get("enabled", True))
            res = QLabel("")
            res.setWordWrap(True)

            def test():
                info = blebox_info(ip.text().strip(), 4)
                res.setText(f"✅ Απαντά: {info.get('deviceName')} [{info.get('type')}]" if info else
                            "❌ Δεν απαντά σε αυτή τη διεύθυνση.")
            f.addRow("Όνομα:", name)
            r = QHBoxLayout()
            r.addWidget(ip, 1)
            r.addWidget(_btn("Έλεγχος", test))
            f.addRow("IP:", r)
            f.addRow("", en)
            f.addRow(res)
            f.addRow(QLabel(f"<span style='color:#8b96ab'>ID {d['id']} · MAC {d.get('mac') or '—'} · "
                            f"{d.get('type', '')} · fw {d.get('fv', '')}</span>"))
            bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
            bb.accepted.connect(dlg.accept)
            bb.rejected.connect(dlg.reject)
            f.addRow(bb)
            if dlg.exec():
                if name.text().strip():
                    self.engine.set_device_field(did, "name", name.text().strip())
                if ip.text().strip() and ip.text().strip() != d["ip"]:
                    self.engine.set_device_field(did, "ip", ip.text().strip())
                self.engine.set_device_field(did, "enabled", en.isChecked())
                self._sensor_ids = None
                self._card_ids = ()
                self.engine.poll_now()

        def remove_sensor(self, did):
            d = self.engine.device(did)
            if d and QMessageBox.question(self, APP_NAME, f"Αφαίρεση «{d.get('name')}»;\n(Οι παλιές μετρήσεις μένουν.)") \
                    == QMessageBox.StandardButton.Yes:
                self.engine.remove_device(did)

        def open_sensor_page(self, did):
            d = self.engine.device(did)
            if d:
                h, p = parse_host(d["ip"])
                webbrowser.open(f"http://{h}:{p}/")

        # ── Server / κινητό ──
        def _tab_server(self):
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setSpacing(12)
            hint = QLabel("<b style='font-size:14pt'>📱 Δες τις μετρήσεις στο κινητό</b><br>"
                          "<span style='color:#8b96ab'>Άνοιξε την κάμερα του κινητού και σκάναρε το QR — ή βάλ' το στην "
                          "εφαρμογή AirSense για Android (Ρυθμίσεις → Σκανάρισμα QR).</span>")
            lay.addWidget(hint)
            row = QHBoxLayout()
            row.setSpacing(14)
            self.qr_lan = QrCard("🏠 Στο ίδιο WiFi", "Όταν το κινητό είναι στο ίδιο WiFi με τον υπολογιστή.")
            self.qr_ts = QrCard("🌍 Από παντού (Tailscale)", "Από 4G/5G ή άλλο WiFi — χωρίς ρυθμίσεις στο router.")
            row.addWidget(self.qr_lan, 1)
            row.addWidget(self.qr_ts, 1)
            lay.addLayout(row, 1)
            gr = QHBoxLayout()
            gl = QLabel("<b>📄 Οδηγός κινητού σε PDF</b> (ελληνικά + English) — με τα QR και τις διευθύνσεις αυτού του server. "
                        "<b>Φτιάχνεται μόνος του</b> κάθε φορά που αλλάζει το δίκτυο (νέο WiFi / μέρος) και είναι πάντα έτοιμος στον φάκελο "
                        "<i>exports</i>. Τον εκτυπώνεις ή τον στέλνεις σε όποιον θέλει να συνδεθεί.")
            gl.setWordWrap(True)
            gr.addWidget(gl, 1)
            gr.addWidget(_btn("📄 PDF οδηγός κινητού", self._phone_guide_pdf, True))
            gr.addWidget(_btn("📂", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(EXPORT_DIR))))
            lay.addLayout(gr)
            g = QGroupBox("⚙ Server")
            h = QHBoxLayout(g)
            s_ = self.engine.cfg["server"]
            self.srv_status = QLabel("")
            self.srv_status.setTextFormat(Qt.TextFormat.RichText)
            h.addWidget(self.srv_status)
            h.addStretch()
            self.srv_en = QCheckBox("Ενεργός")
            self.srv_en.setChecked(s_.get("enabled", True))
            h.addWidget(self.srv_en)
            h.addSpacing(10)
            h.addWidget(QLabel("Θύρα:"))
            self.srv_port = QSpinBox()
            self.srv_port.setRange(1024, 65535)
            self.srv_port.setValue(int(s_.get("port", 8765)))
            self.srv_port.setFixedWidth(95)
            h.addWidget(self.srv_port)
            h.addSpacing(10)
            h.addWidget(QLabel("PIN:"))
            self.srv_pin = QLineEdit(s_.get("pin", ""))
            self.srv_pin.setPlaceholderText("χωρίς PIN")
            self.srv_pin.setFixedWidth(140)
            h.addWidget(self.srv_pin)
            h.addWidget(_btn("💾 Εφαρμογή", self._apply_server, True))
            h.addWidget(_btn("🛡 Firewall", self._firewall))
            lay.addWidget(g)
            return w

        def _phone_guide_pdf(self):
            try:
                self.engine.server_urls(force=True)
                self.engine._guide_watch(force=True)          # fresh, with the addresses of right now
                fn = self.engine.guide_paths()[0]
                if not os.path.exists(fn):
                    raise RuntimeError("δεν βρέθηκε διεύθυνση δικτύου (είναι ο υπολογιστής σε WiFi/LAN;)")
                QDesktopServices.openUrl(QUrl.fromLocalFile(fn))
            except Exception as e:
                QMessageBox.warning(self, APP_NAME, f"Δεν έγινε το PDF:\n{e}")

        def _apply_server(self):
            s = self.engine.cfg["server"]
            s["enabled"] = self.srv_en.isChecked()
            s["port"] = self.srv_port.value()
            s["pin"] = self.srv_pin.text().strip()
            self.engine.save_cfg()
            self.engine.start_server()
            self.refresh_server_info()

        def _firewall(self):
            port = self.engine.cfg["server"].get("port", 8765)
            if os.name != "nt":
                return QMessageBox.information(self, APP_NAME, "Μόνο για Windows.")
            import ctypes
            args = (f'advfirewall firewall add rule name="{APP_NAME} {port}" dir=in action=allow '
                    f'protocol=TCP localport={port} profile=any')
            r = ctypes.windll.shell32.ShellExecuteW(None, "runas", "netsh", args, None, 0)
            QMessageBox.information(self, APP_NAME, "Ο κανόνας Firewall προστέθηκε." if r > 32 else
                                    "Ακυρώθηκε ή απέτυχε (χρειάζεται έγκριση διαχειριστή).")

        def refresh_server_info(self, force=False):
            e = self.engine
            port = e.cfg["server"].get("port", 8765)
            if e.httpd:
                self.srv_status.setText(f"<span style='color:#2ecc71'>● Ενεργός</span> · θύρα {port} · "
                                        + ("με PIN" if e.cfg["server"].get("pin") else "χωρίς PIN"))
            elif e.server_error:
                self.srv_status.setText(f"<span style='color:#ff5c5c'>● Σφάλμα: {e.server_error}</span>")
            else:
                self.srv_status.setText("<span style='color:#8b96ab'>● Ανενεργός</span>")
            if not e.httpd:
                msg = "Ο server είναι ανενεργός — τσέκαρε «Ενεργός» κάτω και πάτα «💾 Εφαρμογή»."
                self.qr_lan.show_info(msg)
                self.qr_ts.show_info(msg)
                return
            lan = sorted(lan_ipv4s(), key=lambda x: (not x.startswith("192.168."), not x.startswith("10."), x))
            if lan:
                others = ("<br>Άλλες διευθύνσεις: " + ", ".join(f"http://{x}:{port}" for x in lan[1:])) if len(lan) > 1 else ""
                self.qr_lan.show_qr(f"http://{lan[0]}:{port}",
                                    "Αν δεν ανοίγει στο κινητό: πάτα «🛡 Firewall» κάτω." + others)
            else:
                self.qr_lan.show_info("Ο υπολογιστής δεν είναι σε τοπικό δίκτυο.")
            ts = e.tailscale(force)
            chk = ("⟳ Έλεγχος", lambda: self.refresh_server_info(True), False)
            if ts.get("ip"):
                extra = f"MagicDNS: http://{ts['dns']}:{port}<br>" if ts.get("dns") else ""
                self.qr_ts.show_qr(f"http://{ts['ip']}:{port}",
                                   extra + "Στο κινητό: εφαρμογή <b>Tailscale</b> ενεργή, με τον <b>ίδιο λογαριασμό</b>.")
            elif ts.get("exe"):
                why = "δεν έχει γίνει σύνδεση (login)" if ts.get("state") in ("NeedsLogin", "NoState", "") else "είναι σταματημένο"
                self.qr_ts.show_info(
                    f"<span style='color:#ffc04d'>⚠ Το Tailscale είναι εγκατεστημένο, αλλά {why}.</span><br><br>"
                    "1. Πάτα <b>«▶ Σύνδεση Tailscale»</b> — ανοίγει η σελίδα σύνδεσης (Google/Microsoft/Apple).<br>"
                    "2. Στο κινητό: εφαρμογή Tailscale με τον <b>ίδιο λογαριασμό</b>.<br>"
                    "3. Εδώ θα εμφανιστεί το QR.",
                    [("▶ Σύνδεση Tailscale", self._ts_login, True), chk])
            else:
                self.qr_ts.show_info(
                    "Το Tailscale δεν είναι εγκατεστημένο σε αυτόν τον υπολογιστή.<br><br>"
                    "1. «⬇ Λήψη Tailscale» → εγκατάσταση → σύνδεση με λογαριασμό Google/Microsoft.<br>"
                    "2. Στο κινητό: εφαρμογή Tailscale με τον <b>ίδιο λογαριασμό</b>.<br>"
                    "3. Πάτα «⟳ Έλεγχος» — θα εμφανιστεί το QR.",
                    [("⬇ Λήψη Tailscale", lambda: webbrowser.open("https://tailscale.com/download/windows"), True), chk])

        def _ts_login(self):
            ts = self.engine.tailscale()
            self.qr_ts.show_info("⏳ Σύνδεση Tailscale…")

            def done(res, err):
                if err:
                    self.qr_ts.show_info(f"<span style='color:#ff5c5c'>✖ {err}</span><br>Δοκίμασε από το εικονίδιο Tailscale "
                                         "κάτω δεξιά → Log in.",
                                         [("⟳ Έλεγχος", lambda: self.refresh_server_info(True), True)])
                    return
                url, msg = res
                if url:
                    webbrowser.open(url)
                self.qr_ts.show_info(f"✅ {msg}.<br>Μόλις ολοκληρωθεί η σύνδεση, πάτα «⟳ Έλεγχος».",
                                     [("⟳ Έλεγχος", lambda: self.refresh_server_info(True), True)])
                for ms in (8000, 20000, 45000):
                    QTimer.singleShot(ms, lambda: self.refresh_server_info(True))
            Bg(self, lambda: tailscale_login(ts.get("exe")), done)

        # ── Email ──
        def _tab_email(self):
            w = QWidget()
            lay = QHBoxLayout(w)
            e = self.engine.cfg["email"]
            a = self.engine.cfg["alarms"]
            g = QGroupBox("Ρυθμίσεις SMTP")
            f = QFormLayout(g)
            self.em_en = QCheckBox("Ενεργοποίηση email")
            self.em_en.setChecked(e.get("enabled", False))
            self.em_host = QLineEdit(e.get("host", ""))
            self.em_port = QSpinBox()
            self.em_port.setRange(1, 65535)
            self.em_port.setValue(int(e.get("port", 587)))
            self.em_sec = QComboBox()
            self.em_sec.addItems(["STARTTLS", "SSL", "Κανένα"])
            self.em_sec.setCurrentText(e.get("security", "STARTTLS"))
            self.em_user = QLineEdit(e.get("user", ""))
            self.em_pwd = QLineEdit(dec_secret(e.get("password", "")))
            self.em_pwd.setEchoMode(QLineEdit.EchoMode.Password)
            self.em_from = QLineEdit(e.get("sender", ""))
            self.em_from.setPlaceholderText("κενό = ίδιο με χρήστη")
            self.em_to = QLineEdit(e.get("to", ""))
            self.em_to.setPlaceholderText("a@x.gr, b@y.gr")
            preset = QComboBox()
            preset.addItems(["— Γρήγορη ρύθμιση —", "Gmail", "Outlook / Hotmail", "Yahoo"])
            preset.currentTextChanged.connect(self._preset)
            quick = QHBoxLayout()
            bg = _btn("🔵  Σύνδεση Google", self._gmail_login, True)
            bm = _btn("🟦  Σύνδεση Outlook", self._ms_login, True)
            bo = _btn("⏏", self._mail_logout)
            bo.setToolTip("Αποσύνδεση email")
            bo.setFixedWidth(46)
            for b in (bg, bm):
                b.setMinimumHeight(44)
                quick.addWidget(b, 1)
            quick.addWidget(bo)
            f.addRow(quick)
            self.em_stat = QLabel()
            self.em_stat.setWordWrap(True)
            f.addRow(self.em_stat)
            f.addRow(QLabel("<span style='color:#8b96ab'>— ή χειροκίνητα —</span>"))
            f.addRow(self.em_en)
            f.addRow("Πάροχος:", preset)
            f.addRow("SMTP server:", self.em_host)
            f.addRow("Θύρα:", self.em_port)
            f.addRow("Ασφάλεια:", self.em_sec)
            f.addRow("Χρήστης (email):", self.em_user)
            f.addRow("Κωδικός:", self.em_pwd)
            f.addRow("Αποστολέας:", self.em_from)
            f.addRow("Παραλήπτες:", self.em_to)
            hint = QLabel("<span style='color:#8b96ab'>Outlook / Hotmail: μόνο με <b>🟦 Σύνδεση Outlook</b> (η Microsoft δεν δέχεται κωδικό). "
                          "Gmail: χρειάζεται <b>Κωδικός εφαρμογής</b> (App Password) από "
                          "<a style='color:#3fa7ff' href='https://myaccount.google.com/apppasswords'>myaccount.google.com/apppasswords</a> "
                          "(απαιτεί 2-Step Verification). Ο κωδικός αποθηκεύεται κρυπτογραφημένος.</span>")
            hint.setWordWrap(True)
            hint.setOpenExternalLinks(True)
            f.addRow(hint)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(g, 1, Qt.AlignmentFlag.AlignTop)
            self._mail_ui()

            right = QVBoxLayout()
            g2 = QGroupBox("Ημερήσια αναφορά (συνημμένα PDF + CSV + XML)")
            f2 = QFormLayout(g2)
            self.em_daily = QCheckBox("Αποστολή κάθε μέρα")
            self.em_daily.setChecked(e.get("daily_report", True))
            self.em_time = QTimeEdit(QTime.fromString(e.get("report_time", "08:00"), "HH:mm"))
            self.em_time.setDisplayFormat("HH:mm")
            self.em_pdf = QCheckBox("📄 Συνημμένη όμορφη αναφορά PDF")
            self.em_pdf.setChecked(e.get("attach_pdf", True))
            f2.addRow(self.em_daily)
            f2.addRow(self.em_pdf)
            f2.addRow("Ώρα αποστολής:", self.em_time)
            right.addWidget(g2)
            g3 = QGroupBox("Ειδοποιήσεις ορίων")
            f3 = QFormLayout(g3)
            self.al_en = QCheckBox("Ενεργές ειδοποιήσεις")
            self.al_en.setChecked(a.get("enabled", False))
            self.al_mail = QCheckBox("Αποστολή email σε ειδοποίηση")
            self.al_mail.setChecked(e.get("alarm_mails", True))

            def dsb(v, lo, hi, suf):
                s = QDoubleSpinBox()
                s.setRange(lo, hi)
                s.setDecimals(1)
                s.setSuffix(suf)
                s.setValue(float(v))
                return s
            self.al_tmin = dsb(a["temp_min"], -40, 125, " °C")
            self.al_tmax = dsb(a["temp_max"], -40, 125, " °C")
            self.al_hmin = dsb(a["hum_min"], 0, 100, " %")
            self.al_hmax = dsb(a["hum_max"], 0, 100, " %")
            self.al_off = QCheckBox("Ειδοποίηση όταν συσκευή βγει offline")
            self.al_off.setChecked(a.get("offline", True))
            self.al_cd = QSpinBox()
            self.al_cd.setRange(5, 1440)
            self.al_cd.setSuffix(" λεπτά")
            self.al_cd.setValue(int(a.get("cooldown_min", 60)))
            f3.addRow(self.al_en)
            f3.addRow(self.al_mail)
            f3.addRow("Θερμοκρασία κάτω από:", self.al_tmin)
            f3.addRow("Θερμοκρασία πάνω από:", self.al_tmax)
            f3.addRow("Υγρασία κάτω από:", self.al_hmin)
            f3.addRow("Υγρασία πάνω από:", self.al_hmax)
            f3.addRow(self.al_off)
            f3.addRow("Επανάληψη το πολύ κάθε:", self.al_cd)
            right.addWidget(g3)
            r = QHBoxLayout()
            r.addWidget(_btn("💾 Αποθήκευση", self._save_email, True))
            r.addWidget(_btn("✉ Δοκιμαστικό email", self._test_email))
            r.addWidget(_btn("📤 Αποστολή αναφοράς τώρα", self._report_now))
            right.addLayout(r)
            right.addStretch()
            lay.addLayout(right, 1)
            return w

        def _mail_ui(self):
            e = self.engine.cfg["email"]
            oauth = e.get("auth") == "oauth_ms"
            for w_ in (self.em_en, self.em_host, self.em_port, self.em_sec, self.em_user, self.em_pwd, self.em_from, self.em_to):
                w_.blockSignals(True)
            self.em_en.setChecked(bool(e.get("enabled")))
            self.em_host.setText(e.get("host", ""))
            self.em_port.setValue(int(e.get("port", 587)))
            self.em_sec.setCurrentText(e.get("security", "STARTTLS"))
            self.em_user.setText(e.get("user", ""))
            self.em_pwd.setText("" if oauth else dec_secret(e.get("password", "")))
            self.em_to.setText(e.get("to", ""))
            for w_ in (self.em_en, self.em_host, self.em_port, self.em_sec, self.em_user, self.em_pwd, self.em_from, self.em_to):
                w_.blockSignals(False)
            self.em_pwd.setEnabled(not oauth)
            self.em_user.setEnabled(not oauth)
            self.em_pwd.setPlaceholderText("— σύνδεση Microsoft, χωρίς κωδικό —" if oauth else "")
            if e.get("user"):
                kind = "Microsoft" if oauth else ("Google" if "gmail" in e.get("host", "") else e.get("host", ""))
                st = "✅ Ενεργό" if e.get("enabled") else "⏸ Ανενεργό"
                self.em_stat.setText(f"<b>{st}</b> · {e['user']} · {kind}")
            else:
                self.em_stat.setText("<span style='color:#8b96ab'>Πατήστε ένα κουμπί — 1 λεπτό, χωρίς ρυθμίσεις SMTP.</span>")

        def _gmail_login(self):
            d = QDialog(self)
            d.setWindowTitle("🔵 Σύνδεση Google (Gmail)")
            d.setMinimumWidth(520)
            v = QVBoxLayout(d)
            v.addWidget(QLabel("<b>3 βήματα:</b><br>1) Γράψτε το Gmail σας.<br>"
                               "2) Πατήστε <b>🔑 Φτιάξε κωδικό εφαρμογής</b> → όνομα «AirSense» → <b>Create</b>.<br>"
                               "3) Αντιγράψτε τον κωδικό των 16 γραμμάτων εδώ και πατήστε <b>✔ Σύνδεση</b>.<br>"
                               "<span style='color:#8b96ab'>Αν δεν βλέπετε τη σελίδα: ενεργοποιήστε πρώτα «Επαλήθευση σε 2 βήματα».</span>"))
            fl = QFormLayout()
            u = QLineEdit(self.em_user.text() if "gmail" in self.em_host.text() else "")
            u.setPlaceholderText("you@gmail.com")
            pw = QLineEdit()
            pw.setPlaceholderText("abcd efgh ijkl mnop")
            to = QLineEdit(self.em_to.text())
            to.setPlaceholderText("κενό = στο ίδιο email")
            fl.addRow("Gmail:", u)
            fl.addRow("", _btn("🔑  Φτιάξε κωδικό εφαρμογής", lambda: QDesktopServices.openUrl(QUrl(GMAIL_APP_PW))))
            fl.addRow("Κωδικός εφαρμογής:", pw)
            fl.addRow("Αποστολή σε:", to)
            v.addLayout(fl)
            msg = QLabel()
            msg.setWordWrap(True)
            v.addWidget(msg)
            go = _btn("✔  Σύνδεση και έλεγχος", None, True)
            go.setMinimumHeight(44)
            v.addWidget(go)

            def run():
                go.setEnabled(False)
                msg.setText("⏳ Έλεγχος σύνδεσης…")

                def done(res, err):
                    go.setEnabled(True)
                    ok, m = res if res else (False, str(err))
                    msg.setText(("<b style='color:#22c55e'>" if ok else "<b style='color:#ef4444'>") + m + "</b>")
                    if ok:
                        self._mail_ui()
                        QTimer.singleShot(1200, d.accept)
                Bg(d, lambda: self.engine.gmail_login(u.text(), pw.text(), to.text()), done)
            go.clicked.connect(run)
            d.exec()

        def _ms_login(self):
            d = QDialog(self)
            d.setWindowTitle("🟦 Σύνδεση Outlook / Hotmail / Microsoft 365")
            d.setMinimumWidth(520)
            v = QVBoxLayout(d)
            info = QLabel()
            info.setWordWrap(True)
            info.setOpenExternalLinks(True)
            info.setMinimumHeight(72)
            v.addWidget(info)
            code = QLabel("…")
            code.setAlignment(Qt.AlignmentFlag.AlignCenter)
            code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            code.setStyleSheet("font-size:26pt;font-weight:800;letter-spacing:4px;padding:6px")
            code.setMinimumHeight(78)
            v.addWidget(code)
            cid = QLineEdit()
            cid.setPlaceholderText("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
            cid.hide()
            v.addWidget(cid)
            row = QHBoxLayout()
            b_open = _btn("📋  Αντιγραφή κωδικού + άνοιγμα σελίδας", None, True)
            b_open.setMinimumHeight(44)
            row.addWidget(b_open, 1)
            v.addLayout(row)
            st = QLabel()
            st.setWordWrap(True)
            v.addWidget(st)
            state = {"flow": None}

            def open_page():
                f_ = state["flow"] or {}
                if f_.get("stage") == "need_id" or not f_:
                    start(cid.text())
                    return
                QApplication.clipboard().setText(f_.get("code", ""))
                QDesktopServices.openUrl(QUrl(f_.get("url", "https://microsoft.com/devicelogin")))
                st.setText("📋 Ο κωδικός αντιγράφηκε — επικολλήστε τον (Ctrl+V) στη σελίδα της Microsoft.")

            def show(f_):
                state["flow"] = f_
                stg = f_.get("stage")
                QTimer.singleShot(0, d.adjustSize)
                if stg == "need_id":
                    info.setText("<b>Μία φορά μόνο:</b> χρειάζεται το <b>Microsoft App (client) ID</b> του AirSense. "
                                 f"<a style='color:#3fa7ff' href='{MS_APP_GUIDE}'>Οδηγίες (3 λεπτά)</a>")
                    code.hide()
                    cid.show()
                    b_open.setText("✔  Συνέχεια")
                    return
                cid.hide()
                code.show()
                if stg == "wait":
                    info.setText("1) Πατήστε το κουμπί — ανοίγει η σελίδα της Microsoft (μπορείτε και από το κινητό: "
                                 f"<b>{f_.get('url', '').replace('https://', '')}</b>).<br>"
                                 "2) Επικολλήστε τον κωδικό → μπείτε στον λογαριασμό σας → <b>Αποδοχή</b>.<br>"
                                 "3) Αυτό ήταν — εδώ θα δείτε ✔ μόνο του.")
                    code.setText(f_.get("code", ""))
                    b_open.setText("📋  Αντιγραφή κωδικού + άνοιγμα σελίδας")
                elif stg == "ok":
                    code.setText("✔")
                    st.setText(f"<b style='color:#22c55e'>{f_.get('msg', '')}</b>")
                    self._mail_ui()
                    QTimer.singleShot(1500, d.accept)
                elif stg == "error":
                    code.setText("✖")
                    st.setText(f"<b style='color:#ef4444'>{f_.get('msg', '')}</b>")
                    b_open.setText("↻  Ξανά")
                    state["flow"] = None

            def start(c=""):
                st.setText("⏳ Σύνδεση με Microsoft…")

                def done(res, err):
                    st.setText("" if res else f"✖ {err}")
                    if res:
                        show(res)
                        if res.get("stage") == "wait":
                            open_page()
                Bg(d, lambda: dict(self.engine.ms_login_start(c)), done)

            def tick():
                f_ = state["flow"]
                if f_ and f_.get("stage") == "wait":
                    cur = self.engine.ms_flow or {}
                    if cur.get("stage") != "wait":
                        show(dict(cur))
            tm = QTimer(d)
            tm.timeout.connect(tick)
            tm.start(1000)
            b_open.clicked.connect(open_page)
            start()
            d.exec()
            tm.stop()
            if (self.engine.ms_flow or {}).get("stage") == "wait":
                self.engine.ms_flow = {}          # σταματά η αναμονή

        def _mail_logout(self):
            if QMessageBox.question(self, APP_NAME, "Αποσύνδεση email; (σβήνει κωδικό / σύνδεση)") == QMessageBox.StandardButton.Yes:
                self.engine.mail_logout()
                self._mail_ui()

        def _preset(self, t):
            if t.startswith("Outlook"):
                QTimer.singleShot(0, self._ms_login)
                return
            if t == "Gmail":
                QTimer.singleShot(0, self._gmail_login)
                return
            m = {"Gmail": ("smtp.gmail.com", 587, "STARTTLS"), "Outlook / Hotmail": ("smtp-mail.outlook.com", 587, "STARTTLS"),
                 "Yahoo": ("smtp.mail.yahoo.com", 465, "SSL")}
            if t in m:
                h, p, s = m[t]
                self.em_host.setText(h)
                self.em_port.setValue(p)
                self.em_sec.setCurrentText(s)

        def _save_email(self, quiet=False):
            e = self.engine.cfg["email"]
            a = self.engine.cfg["alarms"]
            if self.em_en.isChecked() and not e.get("enabled"):
                self.engine.cfg["last_report_date"] = datetime.now().strftime("%Y-%m-%d")  # πρώτη αναφορά αύριο
            e.update(enabled=self.em_en.isChecked(), host=self.em_host.text().strip(), port=self.em_port.value(),
                     security=self.em_sec.currentText(), user=self.em_user.text().strip(),
                     sender=self.em_from.text().strip(),
                     to=self.em_to.text().strip(), daily_report=self.em_daily.isChecked(),
                     attach_pdf=self.em_pdf.isChecked(),
                     report_time=self.em_time.time().toString("HH:mm"), alarm_mails=self.al_mail.isChecked())
            if e.get("auth") != "oauth_ms":
                e["password"] = enc_secret(self.em_pwd.text())
            if hasattr(self, "em_stat"):
                self._mail_ui()
            a.update(enabled=self.al_en.isChecked(), temp_min=self.al_tmin.value(), temp_max=self.al_tmax.value(),
                     hum_min=self.al_hmin.value(), hum_max=self.al_hmax.value(), offline=self.al_off.isChecked(),
                     cooldown_min=self.al_cd.value())
            self.engine.save_cfg()
            if not quiet:
                self.statusBar().showMessage("Οι ρυθμίσεις email αποθηκεύτηκαν", 4000)

        def _run_busy(self, fn):
            self._save_email(True)
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                ok, msg = fn()
            finally:
                QApplication.restoreOverrideCursor()
            (QMessageBox.information if ok else QMessageBox.warning)(self, APP_NAME, msg)

        def _test_email(self):
            self._run_busy(self.engine.send_test)

        def _report_now(self):
            self._run_busy(lambda: self.engine.send_report(24))

        # ── Εξαγωγή ──
        def _tab_export(self):
            w = QWidget()
            lay = QVBoxLayout(w)
            g = QGroupBox("Εξαγωγή μετρήσεων")
            f = QGridLayout(g)
            self.ex_dev = QComboBox()
            self.ex_from = QDateTimeEdit(QDateTime.currentDateTime().addDays(-1))
            self.ex_to = QDateTimeEdit(QDateTime.currentDateTime())
            for d in (self.ex_from, self.ex_to):
                d.setDisplayFormat("dd/MM/yyyy HH:mm")
                d.setCalendarPopup(True)
            f.addWidget(QLabel("Συσκευή:"), 0, 0)
            f.addWidget(self.ex_dev, 0, 1, 1, 3)
            f.addWidget(QLabel("Από:"), 1, 0)
            f.addWidget(self.ex_from, 1, 1)
            f.addWidget(QLabel("Έως:"), 1, 2)
            f.addWidget(self.ex_to, 1, 3)
            q = QHBoxLayout()
            for t, days in (("Σήμερα", 0), ("24 ώρες", 1), ("7 ημέρες", 7), ("30 ημέρες", 30), ("Όλα", 36500)):
                q.addWidget(_btn(t, lambda _=False, dd=days: self._quick_range(dd)))
            q.addStretch()
            f.addLayout(q, 2, 0, 1, 4)
            r = QHBoxLayout()
            bp = _btn("📄 PDF αναφορά…", lambda: self._export("pdf"), True)
            bp.setToolTip("Όμορφη αναφορά με σύνοψη, γραφήματα, καιρό, μέσα–έξω και πίνακα ανά ημέρα")
            r.addWidget(bp)
            r.addWidget(_btn("💾 Εξαγωγή CSV…", lambda: self._export("csv")))
            r.addWidget(_btn("💾 Εξαγωγή XML…", lambda: self._export("xml")))
            r.addWidget(_btn("📂 Άνοιγμα φακέλου δεδομένων", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(DATA_DIR))))
            r.addStretch()
            f.addLayout(r, 3, 0, 1, 4)
            lay.addWidget(g)
            g2 = QGroupBox("Αυτόματη αποθήκευση")
            l2 = QVBoxLayout(g2)
            self.ex_daily = QCheckBox("Ημερήσια αρχεία CSV (κάθε μέτρηση) + XML (ανανέωση κάθε 15′) στον φάκελο daily")
            self.ex_daily.setChecked(self.engine.cfg["export"].get("daily_files", True))
            self.ex_greek = QCheckBox("CSV για ελληνικό Excel (διαχωριστικό « ; » και υποδιαστολή « , »)")
            self.ex_greek.setChecked(self.engine.cfg["export"].get("greek_excel", True))
            for cb, k in ((self.ex_daily, "daily_files"), (self.ex_greek, "greek_excel")):
                cb.toggled.connect(lambda v, kk=k: (self.engine.cfg["export"].__setitem__(kk, v), self.engine.save_cfg()))
                l2.addWidget(cb)
            info = QLabel(f"<span style='color:#8b96ab'>Φάκελος: {DATA_DIR}<br>Βάση δεδομένων: {DB_PATH}</span>")
            info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            l2.addWidget(info)
            lay.addWidget(g2)
            g3 = QGroupBox("📝 Καταγραφή συμβάντων")
            l3 = QVBoxLayout(g3)
            self.log_view = QPlainTextEdit()
            self.log_view.setReadOnly(True)
            self.log_view.setFont(QFont("Consolas", 9))
            l3.addWidget(self.log_view)
            self.db_lbl = QLabel("")
            self.db_lbl.setStyleSheet("color:#8b96ab")
            l3.addWidget(self.db_lbl)
            lay.addWidget(g3, 1)
            return w

        def _tab_changed(self, i):
            if self.tabs.widget(i) is self.T.get("server"):
                self.refresh_server_info()
            if self.tabs.widget(i) is self.T.get("export"):
                now = QDateTime.currentDateTime()
                if self.ex_to.dateTime().secsTo(now) > 120:          # το «Έως» είχε μείνει στην ώρα εκκίνησης
                    span = self.ex_from.dateTime().secsTo(self.ex_to.dateTime())
                    self.ex_to.setDateTime(now)
                    self.ex_from.setDateTime(now.addSecs(-max(span, 3600)))
                self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

        def _quick_range(self, days):
            now = QDateTime.currentDateTime()
            if days == 0:
                self.ex_from.setDateTime(QDateTime(now.date(), QTime(0, 0)))
            else:
                self.ex_from.setDateTime(now.addDays(-days))
            self.ex_to.setDateTime(now)

        def _export(self, kind):
            did = self.ex_dev.currentData()
            t0, t1 = self.ex_from.dateTime().toSecsSinceEpoch(), self.ex_to.dateTime().toSecsSinceEpoch()
            rows = self.engine.store.rows(None if did == "all" else [did], t0, t1)
            if not rows:
                return QMessageBox.information(self, APP_NAME, "Δεν υπάρχουν μετρήσεις στο διάστημα.")
            fn = os.path.join(EXPORT_DIR, f"AirSense_{datetime.now():%Y%m%d_%H%M}.{kind}")
            path, _ = QFileDialog.getSaveFileName(self, "Αποθήκευση", fn, f"{kind.upper()} (*.{kind})")
            if not path:
                return
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                data = self.engine.export_bytes(kind, rows, t0, t1)
            except Exception as e:
                QApplication.restoreOverrideCursor()
                self.engine.log(f"Εξαγωγή {kind.upper()} απέτυχε: {e}", "err")
                return QMessageBox.warning(self, APP_NAME, f"Η εξαγωγή απέτυχε:\n{e}")
            QApplication.restoreOverrideCursor()
            with open(path, "wb") as f:
                f.write(data)
            self.engine.log(f"Εξαγωγή {len(rows)} μετρήσεων → {path}")
            if kind == "pdf":
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
                return
            if QMessageBox.question(self, APP_NAME, f"Αποθηκεύτηκαν {len(rows)} μετρήσεις.\n\nΆνοιγμα αρχείου;") \
                    == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))

        def _fill_export_devs(self):
            cur = self.ex_dev.currentData()
            ids = [d["id"] for d in self.engine.devices()]
            have = [self.ex_dev.itemData(i) for i in range(self.ex_dev.count())]
            if have != ["all"] + ids:
                self.ex_dev.clear()
                self.ex_dev.addItem("Όλες οι συσκευές", "all")
                for d in self.engine.devices():
                    self.ex_dev.addItem(f"{d.get('name')} ({d['ip']})", d["id"])
                i = self.ex_dev.findData(cur)
                self.ex_dev.setCurrentIndex(max(0, i))

        # ── Ρυθμίσεις ──
        def _tab_settings(self):
            sa = QScrollArea()
            sa.setWidgetResizable(True)
            sa.setFrameShape(QFrame.Shape.NoFrame)
            page = QWidget()
            v = QVBoxLayout(page)
            v.setContentsMargins(6, 4, 10, 10)
            v.setSpacing(6)

            def head(txt, sub=""):
                h = QLabel(f"<span style='font-size:13pt;font-weight:700'>{txt}</span>"
                           + (f"&nbsp;&nbsp;<span style='color:#8b96ab'>{sub}</span>" if sub else ""))
                h.setContentsMargins(4, 8, 0, 0)
                return h
            v.addWidget(head("⚙ Γενικά"))
            v.addWidget(self._tab_general())
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet("background:#262d3b")
            v.addSpacing(6)
            v.addWidget(line)
            self.set_email_head = head("✉ Email && Ειδοποιήσεις", "αναφορές με CSV/XML και ειδοποιήσεις ορίων")
            self.set_email_head.setText(self.set_email_head.text().replace("&&", "&amp;"))
            v.addWidget(self.set_email_head)
            self.set_email_page = self._tab_email()
            v.addWidget(self.set_email_page)
            v.addStretch()
            sa.setWidget(page)
            self.set_scroll = sa
            return sa


        def _theme_changed(self, *_):
            mode = self.theme_cb.currentData()
            self.engine.cfg["ui"]["theme"] = mode
            self.engine.save_cfg()
            app = QApplication.instance()
            if apply_theme(app, mode) and getattr(app, "rebuild_ui", None):
                QTimer.singleShot(0, app.rebuild_ui)

        def _labels_changed(self):
            new = {k: (ed.text().strip() or DEFAULT_LABELS[k]) for k, ed in self.lbl_edits.items()}
            if new == labels(self.engine.cfg):
                return
            self.engine.cfg["labels"] = new
            self.engine.save_cfg()
            self.engine.log(f"Λεκτικά: {new['inside']} / {new['outside']}")
            app = QApplication.instance()
            if getattr(app, "rebuild_ui", None):
                QTimer.singleShot(0, app.rebuild_ui)   # ξαναστήνει γραφήματα/υπομνήματα με τα νέα ονόματα
            else:
                self.refresh()

        def _labels_reset(self):
            for k, ed in self.lbl_edits.items():
                ed.setText(DEFAULT_LABELS[k])
            self._labels_changed()

        def show_email(self):
            self.tabs.setCurrentWidget(self.T["settings"])
            QTimer.singleShot(50, lambda: self.set_scroll.verticalScrollBar().setValue(
                self.set_email_head.y() - 4))

        def _tab_general(self):
            w = QWidget()
            outer = QHBoxLayout(w)
            outer.setSpacing(14)
            outer.setContentsMargins(0, 0, 0, 0)
            left = QVBoxLayout()
            mid = QVBoxLayout()
            right = QVBoxLayout()
            outer.addLayout(left, 1)
            outer.addLayout(mid, 1)
            outer.addLayout(right, 1)
            g = QGroupBox("⏱ Καταγραφή")
            f = QFormLayout(g)
            self.poll_spin = QSpinBox()
            self.poll_spin.setRange(2, 3600)
            self.poll_spin.setSuffix(" δευτερόλεπτα")
            self.poll_spin.setValue(int(self.engine.cfg.get("poll_seconds", 60)))
            self.poll_spin.setFixedWidth(170)
            self.poll_spin.valueChanged.connect(lambda v: (self.engine.cfg.__setitem__("poll_seconds", v), self.engine.save_cfg()))
            f.addRow("Μέτρηση κάθε:", self.poll_spin)
            left.addWidget(g)
            g2 = QGroupBox("🖥 Λειτουργία")
            l2 = QVBoxLayout(g2)
            ui = self.engine.cfg["ui"]
            self.cb_tray = QCheckBox("Το «Χ» κρύβει στο tray (συνεχίζει να δουλεύει)")
            self.cb_tray.setToolTip("Η καταγραφή και ο server συνεχίζουν· έξοδος από το εικονίδιο κάτω δεξιά")
            self.cb_tray.setChecked(ui.get("minimize_to_tray", True))
            self.cb_min = QCheckBox("Εκκίνηση κρυμμένη κάτω δεξιά (tray)")
            self.cb_min.setChecked(ui.get("start_minimized", False))
            for cb, k in ((self.cb_tray, "minimize_to_tray"), (self.cb_min, "start_minimized")):
                cb.toggled.connect(lambda v, kk=k: (self.engine.cfg["ui"].__setitem__(kk, v), self.engine.save_cfg()))
                l2.addWidget(cb)
            self.cb_auto = QCheckBox("Αυτόματη εκκίνηση με τα Windows")
            self.cb_auto.setChecked(self._autostart_get())
            self.cb_auto.toggled.connect(self._autostart_set)
            self.cb_auto.setEnabled(os.name == "nt")
            l2.addWidget(self.cb_auto)
            l2.addStretch()
            mid.addWidget(g2)
            mid.addStretch()
            gth = QGroupBox("🎨 Εμφάνιση")
            lth = QHBoxLayout(gth)
            lth.addWidget(QLabel("Θέμα:"))
            self.theme_cb = QComboBox()
            for k_, t_ in (("auto", "🖥 Αυτόματο (όπως τα Windows)"), ("dark", "🌙 Σκούρο"), ("light", "☀ Ανοιχτό")):
                self.theme_cb.addItem(t_, k_)
            self.theme_cb.setCurrentIndex(max(0, self.theme_cb.findData(self.engine.cfg["ui"].get("theme", "auto"))))
            self.theme_cb.setMinimumWidth(230)
            self.theme_cb.currentIndexChanged.connect(self._theme_changed)
            lth.addWidget(self.theme_cb)
            lth.addStretch()
            left.addWidget(gth)
            glb = QGroupBox("🏷 Λεκτικά")
            flb = QFormLayout(glb)
            lb = labels(self.engine.cfg)
            self.lbl_edits = {}
            for k_, cap in (("inside", "Αισθητήρας (μέσα):"), ("outside", "Καιρός (έξω):")):
                ed = QLineEdit(lb[k_])
                ed.setPlaceholderText(DEFAULT_LABELS[k_])
                ed.setMaxLength(30)
                ed.setMinimumWidth(180)
                ed.editingFinished.connect(self._labels_changed)
                self.lbl_edits[k_] = ed
                flb.addRow(cap, ed)
            hint_lb = QLabel("<span style='color:#8b96ab'>π.χ. «Σαλόνι» / «Αυλή», «Αποθήκη» / «Πτολεμαΐδα». "
                             "Αλλάζουν σε Αρχική, γραφήματα, καιρό και κινητό.</span>")
            hint_lb.setWordWrap(True)
            flb.addRow(hint_lb)
            rb = _btn("↺ Προεπιλογή", self._labels_reset)
            flb.addRow("", rb)
            left.addWidget(glb)
            left.addStretch()
            gsc = QGroupBox("📡 Σάρωση δικτύου (για προχωρημένους)")
            fsc = QVBoxLayout(gsc)
            self.subnets = QLineEdit(self.engine.cfg.get("subnets", ""))
            self.subnets.setPlaceholderText("π.χ. 192.168.2.0/24, 10.0.0.0/24")
            self.subnets.editingFinished.connect(lambda: (self.engine.cfg.__setitem__("subnets", self.subnets.text().strip()),
                                                          self.engine.save_cfg()))
            self.auto_add = QCheckBox("Αυτόματη προσθήκη αισθητήρων που βρίσκονται στη σάρωση")
            self.auto_add.setChecked(self.engine.cfg.get("auto_add_sensors", True))
            self.auto_add.toggled.connect(lambda v: (self.engine.cfg.__setitem__("auto_add_sensors", v), self.engine.save_cfg()))
            fsc.addWidget(QLabel("Επιπλέον δίκτυα για σάρωση (προαιρετικά):"))
            fsc.addWidget(self.subnets)
            fsc.addWidget(self.auto_add)
            right.addWidget(gsc)
            gpi = QGroupBox("🥧 Raspberry Pi")
            lpi = QVBoxLayout(gpi)
            lp = QLabel("Άλλο WiFi για το Pi; Γράψ' το στην κάρτα SD — το παίρνει μόνο του στην εκκίνηση.")
            lp.setWordWrap(True)
            lpi.addWidget(lp)
            bpi = _btn("📶 WiFi στην κάρτα SD του Pi…", lambda: PiSdWifiDialog(self).exec(), True)
            bpi.setMinimumHeight(42)
            lpi.addWidget(bpi)
            right.addWidget(gpi)
            right.addStretch()
            return w

        def _autostart_cmd(self):
            exe = sys.executable
            if exe.lower().endswith("python.exe"):
                cand = exe[:-10] + "pythonw.exe"
                if os.path.exists(cand):
                    exe = cand
            return f'"{exe}" "{os.path.abspath(sys.argv[0])}" --minimized'

        def _autostart_get(self):
            if os.name != "nt":
                return False
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
                    winreg.QueryValueEx(k, APP_NAME)
                    return True
            except Exception:
                return False

        def _autostart_set(self, on):
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                                    winreg.KEY_SET_VALUE) as k:
                    if on:
                        winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, self._autostart_cmd())
                    else:
                        try:
                            winreg.DeleteValue(k, APP_NAME)
                        except FileNotFoundError:
                            pass
            except Exception as e:
                QMessageBox.warning(self, APP_NAME, f"Αποτυχία: {e}")

        # ── Καταγραφή ──
        def _update_log(self):
            with self.engine.lock:
                evs = [e for e in self.engine.events if e[0] > self._last_ev]
            for ts, lvl, msg in evs:
                icon = {"warn": "⚠", "err": "✖"}.get(lvl, "•")
                self.log_view.appendPlainText(f"{datetime.fromtimestamp(ts):%d/%m %H:%M:%S}  {icon} {msg}")
                self._last_ev = ts
                if lvl == "warn" and self.tray and not self.isVisible():
                    self.tray.showMessage(APP_NAME, msg, QSystemTrayIcon.MessageIcon.Warning, 6000)
                elif msg.startswith("📄 Νέο δίκτυο") and self.tray:
                    self.tray.showMessage(APP_NAME, "📄 Νέο δίκτυο — ο οδηγός κινητού PDF ενημερώθηκε (καρτέλα 📱 Κινητό)",
                                          QSystemTrayIcon.MessageIcon.Information, 6000)

        # ── Οδηγός ──
        def _tab_help(self):
            w = QWidget()
            hl = QHBoxLayout(w)
            hl.setSpacing(14)
            tb = QTextBrowser()
            tb.setOpenExternalLinks(True)
            tb.setHtml(f"""
    <h2>❓ Βοήθεια — βήμα-βήμα</h2>
    <p style='font-size:12pt'>👉 Ο πιο εύκολος τρόπος: καρτέλα <b>🏠 Αρχική</b> → <b>🧙 Οδηγός εγκατάστασης</b>. Σε πάει βήμα-βήμα σε όλα.</p>
    <h3>1. Σύνδεση του αισθητήρα στο WiFi σας (μία φορά)</h3>
    <ul><li>Με την εφαρμογή <b>wBox</b> της BleBox <i>ή</i></li>
    <li>Καρτέλα <b>📡 Αισθητήρες</b> → «🧙 Νέος αισθητήρας»: βρίσκει τον αισθητήρα στο WiFi και τον συνδέει στο δίκτυό σου.</li>
    <li>Μόνο WiFi <b>2.4 GHz</b>.</li></ul>
    <h3>2. Εύρεση αισθητήρα</h3>
    <ul><li>Καρτέλα <b>📡 Αισθητήρες</b> → «🔍 Βρες αισθητήρες». Οι αισθητήρες προστίθενται αυτόματα.</li>
    <li>Αν αλλάξει IP (DHCP), η εφαρμογή τον ξαναβρίσκει μόνη της.</li></ul>
    <h3>3. Καταγραφή & γραφήματα</h3>
    <ul><li>Μετρά κάθε {self.engine.cfg.get('poll_seconds', 60)}″ (αλλάζει στις Ρυθμίσεις). Καρτέλα <b>📊 Γραφήματα</b> και <b>🌦 Καιρός</b>.</li>
    <li>Υπολογίζει επίσης <b>σημείο δρόσου</b> και <b>απόλυτη υγρασία</b>.</li></ul>
    <h3>4. Από το κινητό — ίδιο WiFi</h3>
    <ul><li>Καρτέλα <b>📱 Κινητό</b> → σκανάρετε το QR «🏠 Στο ίδιο WiFi».</li>
    <li>Αν δεν ανοίγει: «🛡 Firewall» (καρτέλα 📱 Κινητό).</li></ul>
    <h3>5. Από το κινητό — από παντού (Tailscale)</h3>
    <ul><li>Εγκαταστήστε <a style="color:#3fa7ff" href="https://tailscale.com/download">Tailscale</a> στον υπολογιστή <b>και</b> στο κινητό, με τον <b>ίδιο λογαριασμό</b>.</li>
    <li>Καρτέλα <b>📱 Κινητό</b> → «▶ Σύνδεση Tailscale» → σκανάρετε το QR «🌍 Από παντού». Δουλεύει από 4G/5G χωρίς άνοιγμα θυρών στο router.</li>
    <li>Στον browser: «Προσθήκη στην αρχική οθόνη» → γίνεται εικονίδιο σαν εφαρμογή.</li></ul>
    <h3>6. Email</h3>
    <ul><li><b>⚙ Ρυθμίσεις → ✉ Email &amp; Ειδοποιήσεις</b> → Πάροχος Gmail → χρήστης + <b>App Password</b> → παραλήπτες → «Δοκιμαστικό email».</li>
    <li>Ημερήσια αναφορά με συνημμένα CSV/XML και ειδοποιήσεις όταν ξεπεραστούν τα όρια.</li></ul>
    <h3>7. CSV / XML</h3>
    <ul><li>Αυτόματα ημερήσια αρχεία στον φάκελο <code>{DAILY_DIR}</code>.</li>
    <li>Εξαγωγή οποιουδήποτε διαστήματος από την καρτέλα <b>💾 Δεδομένα</b> ή από το κινητό.</li></ul>
    <h3>8. Μεταφορά σε άλλο WiFi / Reset</h3>
    <ul><li>Αρχική → <b>🔁 Αλλαγή WiFi / Reset</b>: όσο ο αισθητήρας δουλεύει, του στέλνεις το νέο WiFi με ένα κλικ.</li>
    <li>Αν δεν εμφανίζεται πουθενά: Reset κατά τις οδηγίες BleBox → Οδηγός νέου αισθητήρα. Το ιστορικό κρατιέται.</li></ul>
    <h3>9. Να τρέχει συνέχεια</h3>
    <ul><li>Ο υπολογιστής πρέπει να είναι ανοιχτός. Το «Χ» κρύβει την εφαρμογή στο tray (κάτω δεξιά).</li>
    <li>Ρυθμίσεις → «Αυτόματη εκκίνηση με τα Windows».</li></ul>
    <h3>10. Raspberry Pi</h3>
    <ul><li>Ο server μπορεί να τρέχει σε Raspberry Pi 24/7 (πακέτο AirSense-Pi).</li>
    <li>Αλλαγή WiFi του Pi: <b>⚙ Ρυθμίσεις → 🥧 Raspberry Pi → WiFi στην κάρτα SD</b>.</li></ul>""")
            hl.addWidget(tb, 1)
            about = QFrame()
            about.setObjectName("card")
            av = QVBoxLayout(about)
            av.setContentsMargins(24, 20, 24, 20)
            av.addWidget(ClickLabel("<b style='color:#8b96ab;letter-spacing:2px'>ΣΧΕΤΙΚΑ · ABOUT</b>", self.open_admin))
            top = QHBoxLayout()
            ic = QLabel()
            ic.setPixmap(app_icon().pixmap(84, 84))
            top.addWidget(ic)
            tl = QLabel(f"<span style='font-size:22pt;font-weight:700'>{APP_NAME}</span><br>"
                        f"<span style='font-size:12pt;color:#3fa7ff'>έκδοση {APP_VERSION}</span>")
            top.addWidget(tl, 1)
            av.addLayout(top)
            try:
                from PyQt6.QtCore import PYQT_VERSION_STR as _pyqt
            except Exception:
                _pyqt = "?"
            body = QLabel(
                "<p style='font-size:11pt'>Παρακολούθηση, καταγραφή και ειδοποιήσεις για αισθητήρες "
                "<b>BleBox humiditySensor</b> — με γραφήματα, καιρό Open-Meteo, CSV/XML, email και πρόσβαση από το κινητό.</p>"
                "<p style='font-size:11pt'>Developer: <b>Nikolaos K. Paridis (aka nikkpap)</b><br>ALU DEV TEAM</p>"
                "<table style='color:#8b96ab' cellspacing='4'>"
                f"<tr><td>Python</td><td>{sys.version.split()[0]}</td></tr>"
                f"<tr><td>PyQt</td><td>{_pyqt}</td></tr>"
                f"<tr><td>Δεδομένα</td><td>{DATA_DIR}</td></tr>"
                f"<tr><td>Log</td><td>{LOG_FILE}</td></tr></table>"
                "<p style='color:#8b96ab'>BleBox API: <a style='color:#3fa7ff' href='https://technical.blebox.eu'>technical.blebox.eu</a><br>"
                "Καιρός: <a style='color:#3fa7ff' href='https://open-meteo.com'>Open-Meteo.com</a> (CC BY 4.0)<br>"
                "Απομακρυσμένη πρόσβαση: <a style='color:#3fa7ff' href='https://tailscale.com'>Tailscale</a></p>")
            body.setWordWrap(True)
            body.setTextFormat(Qt.TextFormat.RichText)
            body.setOpenExternalLinks(True)
            body.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            av.addWidget(body)
            br = QGridLayout()
            br.addWidget(_btn("🧙 Οδηγός εγκατάστασης", lambda: self.open_wizard(), True), 0, 0)
            br.addWidget(_btn("📂 Φάκελος δεδομένων", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(DATA_DIR))), 0, 1)
            br.addWidget(_btn("📄 Αρχείο log", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(LOG_FILE))), 1, 0)
            br.addWidget(_btn("🌐 Web σελίδα", lambda: webbrowser.open(f"http://127.0.0.1:{self.engine.cfg['server'].get('port', 8765)}")), 1, 1)
            av.addLayout(br)
            av.addStretch()
            foot = QLabel(f"<span style='color:#5b6475'>© {datetime.now().year} Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM</span>")
            av.addWidget(foot)
            hl.addWidget(about, 1)
            return w

        # ── Tray ──
        def _make_tray(self):
            self.tray = None
            if not QSystemTrayIcon.isSystemTrayAvailable():
                return
            self.tray = QSystemTrayIcon(app_icon(), self)
            m = QMenu()
            for text, fn in (("Άνοιγμα", self.show_normal), ("Άνοιγμα web εφαρμογής",
                             lambda: webbrowser.open(f"http://127.0.0.1:{self.engine.cfg['server']['port']}")),
                             ("Μέτρηση τώρα", self.engine.poll_now)):
                a = QAction(text, self)
                a.triggered.connect(fn)
                m.addAction(a)
            m.addSeparator()
            q = QAction("Έξοδος", self)
            q.triggered.connect(self.quit_app)
            m.addAction(q)
            self.tray.setContextMenu(m)
            self.tray.activated.connect(lambda r: self.show_normal() if r in (
                QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick) else None)
            self.tray.setToolTip(APP_NAME)
            self.tray.show()

        def show_normal(self):
            self.show()
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
            self.raise_()
            self.activateWindow()

        def quit_app(self):
            self._quitting = True
            self.engine.shutdown()
            if self.tray:
                self.tray.hide()
            QApplication.quit()

        def closeEvent(self, ev):
            if not self._quitting and self.tray and self.engine.cfg["ui"].get("minimize_to_tray", True):
                ev.ignore()
                self.hide()
                if not self.engine.cfg["ui"].get("tray_hint_shown"):
                    self.tray.showMessage(APP_NAME, "Η εφαρμογή συνεχίζει στο παρασκήνιο (καταγραφή + server). "
                                                    "Δεξί κλικ στο εικονίδιο → Έξοδος.", QSystemTrayIcon.MessageIcon.Information, 6000)
                    self.engine.cfg["ui"]["tray_hint_shown"] = True
                    self.engine.save_cfg()
                return
            self.quit_app()
            ev.accept()

        # ── περιοδική ανανέωση ──
        def refresh(self):
            try:
                self._update_cards()
                self.refresh_weather()
                self._update_home()
                self._fill_dev_table()
                self._update_scan()
                self._fill_export_devs()
                self._update_log()
                if self.engine.poll_counter != self._last_poll_counter:
                    self._last_poll_counter = self.engine.poll_counter
                    self.refresh_chart()
                    self.refresh_wx_charts()
                    self.db_lbl.setText(f"Σύνολο μετρήσεων στη βάση: {self.engine.store.count():,}".replace(",", "."))
                if self.tray:
                    parts = []
                    for d in self.engine.devices()[:3]:
                        st = self.engine.live.get(d["id"], {})
                        parts.append(f"{d.get('name')}: {_fmt(st.get('t'))}°C {_fmt(st.get('h'))}%")
                    self.tray.setToolTip(APP_NAME + ("\n" + "\n".join(parts) if parts else ""))
            except Exception as e:
                self.statusBar().showMessage(f"Σφάλμα UI: {e}", 5000)


# ═══════════════════════════════════════════════════════════════════════════
# 12) main
# ═══════════════════════════════════════════════════════════════════════════
def _ver(v):
    try:
        return tuple(int(x) for x in re.findall(r"\d+", v)[:3])
    except Exception:
        return (0,)


def _kill_old_instances():
    """Κλείνει παλιές εκδόσεις AirSense / ALU_HygroLink που τρέχουν (εκτός από αυτήν και τους «γονείς» της)."""
    if os.name != "nt":
        return
    try:
        ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?(3[0-9.]*)?\\.exe$' -and "
              "($_.CommandLine -like '*ALU_HygroLink*' -or $_.CommandLine -like '*AirSense*.pyw*') } | "
              "Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                           timeout=25, creationflags=0x08000000)
        data = json.loads(r.stdout or "[]")
        if isinstance(data, dict):
            data = [data]
        allp = subprocess.run(["powershell", "-NoProfile", "-Command",
                               "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId | ConvertTo-Json -Compress"],
                              capture_output=True, text=True, timeout=25, creationflags=0x08000000)
        parent = {d["ProcessId"]: d["ParentProcessId"] for d in json.loads(allp.stdout or "[]")}
        keep, pid = set(), os.getpid()
        while pid and pid not in keep:
            keep.add(pid)
            pid = parent.get(pid)
        for d in data:
            if d["ProcessId"] not in keep:
                subprocess.run(["taskkill", "/PID", str(d["ProcessId"]), "/T", "/F"], capture_output=True,
                               creationflags=0x08000000)
                _log(f"Έκλεισε παλιό αντίγραφο PID {d['ProcessId']}: {d.get('CommandLine', '')[:150]}")
    except Exception as e:
        _log(f"Κλείσιμο παλιών αντιγράφων απέτυχε: {e}")


def _excepthook(et, ev, tb):
    import traceback
    txt = "".join(traceback.format_exception(et, ev, tb))
    _log("ΣΦΑΛΜΑ:\n" + txt)
    try:
        QMessageBox.critical(None, APP_NAME, f"Απρόσμενο σφάλμα:\n\n{ev}\n\nΛεπτομέρειες: {LOG_FILE}")
    except Exception:
        pass


def main():
    sys.excepthook = _excepthook
    _log(f"{APP_NAME} v{APP_VERSION} — Python {sys.version.split()[0]} ({sys.executable})")
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AirSense")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    app.setWindowIcon(app_icon())

    old = QLocalSocket()                      # τρέχει ακόμα το παλιό «ALU HygroLink»; → κλείσ' το
    old.connectToServer("ALU_HygroLink_single_instance")
    if old.waitForConnected(300):
        _log("Κλείνει το παλιό ALU HygroLink — το νέο όνομα είναι AirSense")
        old.write(b"hello")
        old.flush()
        if old.waitForReadyRead(800):
            old.readAll()
        old.write(b"quit")
        old.flush()
        old.waitForBytesWritten(300)
        old.abort()
        time.sleep(1.5)
        _kill_old_instances()
        time.sleep(0.8)
    key = "AirSense_single_instance"
    sock = QLocalSocket()
    sock.connectToServer(key)
    if sock.waitForConnected(400):
        sock.write(b"hello")
        sock.flush()
        reply = bytes(sock.readAll()).decode(errors="ignore").strip() if sock.waitForReadyRead(4000) else ""
        if reply and _ver(reply) >= _ver(APP_VERSION):
            sock.write(b"show")          # ίδια ή νεότερη έκδοση τρέχει ήδη → εμφάνισέ την
            sock.flush()
            sock.waitForBytesWritten(300)
            return 0
        _log(f"Τρέχει παλιότερη έκδοση ({reply or '≤1.1.2'}) — κλείνει για να ανοίξει η v{APP_VERSION}")
        if reply:
            sock.write(b"quit")
            sock.flush()
            sock.waitForBytesWritten(300)
        sock.abort()
        t_end = time.time() + 6
        while time.time() < t_end:
            probe = QLocalSocket()
            probe.connectToServer(key)
            if not probe.waitForConnected(200):
                break
            probe.abort()
            if not reply or time.time() > t_end - 4:
                _kill_old_instances()
            time.sleep(0.4)
        time.sleep(0.8)  # να ελευθερωθεί η θύρα του web server
    QLocalServer.removeServer(key)
    srv = QLocalServer()
    srv.listen(key)

    engine = Engine()
    engine.log(f"{APP_NAME} v{APP_VERSION} ξεκίνησε · δεδομένα: {DATA_DIR}")
    if os.name == "nt":       # αυτόματη εκκίνηση: παλιό όνομα → νέο
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                                winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as k:
                found = False
                for _old in OLD_APP_NAMES:
                    try:
                        winreg.QueryValueEx(k, _old)
                        winreg.DeleteValue(k, _old)
                        found = True
                    except OSError:
                        pass
                if not found:
                    raise FileNotFoundError
                pyw = sys.executable.replace("python.exe", "pythonw.exe")
                winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, f'"{pyw}" "{os.path.abspath(sys.argv[0])}" --minimized')
                engine.log("Αυτόματη εκκίνηση: μεταφέρθηκε στο νέο όνομα AirSense")
        except Exception:
            pass
    apply_theme(app, engine.cfg["ui"].get("theme", "auto"))
    engine.start()
    W = {"win": MainWindow(engine)}

    def rebuild_ui():
        """Ξαναφτιάχνει το παράθυρο με το νέο θέμα (η καταγραφή και ο server συνεχίζουν κανονικά)."""
        old = W["win"]
        was_visible = old.isVisible()
        geo, tab = old.saveGeometry(), old.tabs.currentIndex()
        sub = old.set_scroll.verticalScrollBar().value()
        old.timer.stop()
        if old.tray:
            old.tray.hide()
        old._quitting = True
        old.hide()
        old.deleteLater()
        new = MainWindow(engine)
        new.restoreGeometry(geo)
        new.tabs.setCurrentIndex(tab)
        QTimer.singleShot(80, lambda: new.set_scroll.verticalScrollBar().setValue(sub))
        W["win"] = new
        if was_visible:
            new.show()
    app.rebuild_ui = rebuild_ui

    def on_scheme(*_):
        if engine.cfg["ui"].get("theme", "auto") == "auto" and apply_theme(app, "auto"):
            rebuild_ui()
    try:
        app.styleHints().colorSchemeChanged.connect(on_scheme)
    except Exception:
        pass

    def on_conn():
        c = srv.nextPendingConnection()
        if not c:
            return

        def on_read():
            data = bytes(c.readAll())
            if b"hello" in data:
                c.write(APP_VERSION.encode())
                c.flush()
            if b"quit" in data:
                engine.log("Κλείσιμο: ανοίγει νεότερη έκδοση")
                W["win"].quit_app()
            elif b"show" in data:
                W["win"].show_normal()
        c.readyRead.connect(on_read)
    srv.newConnection.connect(on_conn)

    start_hidden = ("--minimized" in sys.argv or engine.cfg["ui"].get("start_minimized")) and W["win"].tray is not None
    if not start_hidden:
        W["win"].show()
    rc = app.exec()
    engine.shutdown()
    return rc


def headless_main():
    """Server χωρίς παράθυρο (Raspberry Pi / Linux / υπηρεσία)."""
    import signal
    engine = Engine()
    engine.log(f"{APP_NAME} v{APP_VERSION} (headless) — Python {sys.version.split()[0]} — δεδομένα: {DATA_DIR}")
    engine.start()
    for label, url in engine.server_urls(True):
        engine.log(f"{label}: {url}")
    if not (engine.cfg.get("admin") or {}).get("hash"):
        engine.log("Δεν έχει οριστεί κωδικός διαχειριστή — ορίστε τον: airsense set-admin (ή από τη web σελίδα)", "warn")
    stop = threading.Event()

    def on_sig(*_):
        stop.set()
    signal.signal(signal.SIGTERM, on_sig)
    signal.signal(signal.SIGINT, on_sig)
    while not stop.wait(1):
        pass
    engine.log("Τερματισμός…")
    engine.shutdown()
    return 0


def cli_main():
    """Εντολές γραμμής: --set-admin, --set-pin [PIN], --status, --add IP, --scan [ΔΙΚΤΥΑ], --locate ΠΟΛΗ"""
    import getpass
    a = sys.argv[1:]
    if "--help-cli" in a:
        print(f"""{APP_NAME} v{APP_VERSION}
  --headless            server χωρίς παράθυρο
  --set-admin           ορισμός κωδικού διαχειριστή
  --set-pin [PIN]       PIN για web/κινητό (κενό = χωρίς PIN)
  --status              κατάσταση & διευθύνσεις
  --add IP              προσθήκη αισθητήρα με IP
  --scan [ΔΙΚΤΥΑ]       σάρωση δικτύου: βρίσκει και προσθέτει μόνο αισθητήρες BleBox (π.χ. --scan 10.0.0.0/24)
  --locate "Πόλη"       τοποθεσία καιρού (Open-Meteo)
  --data ΦΑΚΕΛΟΣ        φάκελος δεδομένων""")
        return 0
    ensure_dirs()
    cfg = load_cfg()

    def save(c):
        tmp = CFG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(c, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CFG_PATH)
        if os.name != "nt":
            os.chmod(CFG_PATH, 0o600)
    if "--set-admin" in a:
        p1 = os.environ.get("AIRSENSE_ADMIN_PW")          # χωρίς ερώτηση (π.χ. από airsense-settings.txt)
        p2 = p1
        if not p1:
            p1 = getpass.getpass("Νέος κωδικός διαχειριστή (4+ χαρακτήρες): ")
            p2 = getpass.getpass("Επανάληψη: ")
        if len(p1) < 4 or p1 != p2:
            print("✖ Οι κωδικοί δεν ταιριάζουν ή είναι μικρός.")
            return 1
        salt, h = _pw_hash(p1)
        cfg["admin"] = {"salt": salt, "hash": h}
        save(cfg)
        print("✔ Ο κωδικός διαχειριστή ορίστηκε.")
        return 0
    if "--set-pin" in a:
        pin = _arg_value("--set-pin")
        if pin is None or pin.startswith("--"):
            pin = input("PIN για web/κινητό (Enter = χωρίς PIN): ").strip()
        cfg["server"]["pin"] = pin
        save(cfg)
        print("✔ PIN " + ("ορίστηκε." if pin else "αφαιρέθηκε."))
        return 0
    if "--add" in a:
        ip = _arg_value("--add")
        info = blebox_info(ip or "", 5)
        if not info:
            print(f"✖ Δεν βρέθηκε BleBox στο {ip}")
            return 1
        did = str(info.get("id") or ip)
        if not any(d["id"] == did for d in cfg["devices"]):
            cfg["devices"].append({"id": did, "name": info.get("deviceName") or ip, "ip": ip, "type": info.get("type", ""),
                                   "product": info.get("product", ""), "fv": info.get("fv", ""),
                                   "apiLevel": str(info.get("apiLevel", "")), "mac": "", "enabled": True})
        save(cfg)
        print(f"✔ Προστέθηκε: {info.get('deviceName')} [{info.get('type')}]")
        return 0
    if "--scan" in a:
        extra = _arg_value("--scan")
        if extra and extra.startswith("--"):
            extra = None
        nets = build_networks(extra or cfg.get("subnets", ""))
        hosts = list(dict.fromkeys(str(h) for n in nets for h in n.hosts()))
        print(f"🔍 Σάρωση: {', '.join(str(n) for n in nets) or '—'} ({len(hosts)} διευθύνσεις)…", flush=True)
        found, done = [], 0
        with ThreadPoolExecutor(max_workers=48) as ex:
            for r in ex.map(probe_host, hosts):
                done += 1
                if done % 32 == 0 or done == len(hosts):
                    print(f"\r   {done}/{len(hosts)} · BleBox: {len(found)}", end="", flush=True)
                if r and r.get("blebox"):
                    found.append(r)
        print()
        added = moved = 0
        for r in found:
            sensor = (r.get("type") or "").lower() in SENSOR_TYPES
            did = str(r.get("id") or r["ip"])
            ex_d = next((d for d in cfg["devices"] if d["id"] == did), None)
            mark = "αισθητήρας" if sensor else "άλλη συσκευή BleBox — παραλείπεται"
            if ex_d:
                if ex_d["ip"] != r["ip"]:
                    print(f"  ↻ {r.get('name') or did}  {ex_d['ip']} → {r['ip']}  (νέα IP)")
                    ex_d["ip"] = r["ip"]
                    moved += 1
                else:
                    print(f"  ✔ {r.get('name') or did}  {r['ip']}  (υπάρχει ήδη)")
                continue
            if not sensor:
                print(f"  · {r.get('name') or did}  {r['ip']}  [{r.get('type')}] — {mark}")
                continue
            info = blebox_info(r["ip"], 5) or {}
            cfg["devices"].append({"id": did, "name": info.get("deviceName") or r.get("name") or r["ip"], "ip": r["ip"],
                                   "type": info.get("type", r.get("type", "")), "product": info.get("product", ""),
                                   "fv": info.get("fv", ""), "apiLevel": str(info.get("apiLevel", "")),
                                   "mac": "", "enabled": True})
            print(f"  ＋ {info.get('deviceName') or r.get('name') or did}  {r['ip']}  [{r.get('type')}] — προστέθηκε")
            added += 1
        if added or moved:
            save(cfg)
        sensors = sum(1 for r in found if (r.get("type") or "").lower() in SENSOR_TYPES)
        print(f"✔ Βρέθηκαν {sensors} αισθητήρες BleBox · νέοι: {added} · νέα IP: {moved}" if found
              else "✖ Δεν βρέθηκε αισθητήρας BleBox. Είναι στο ίδιο δίκτυο; (άλλο δίκτυο: --scan 10.0.0.0/24)")
        return 0 if found else 1
    if "--locate" in a:
        name = _arg_value("--locate") or input("Πόλη / χωριό: ")
        res = geocode(name)
        if not res:
            print("✖ Δεν βρέθηκε.")
            return 1
        for i, r in enumerate(res[:8], 1):
            print(f"  {i}. {r['label']}  ({r['lat']:.3f}, {r['lon']:.3f})")
        k = input("Αριθμός [1]: ").strip() or "1"
        r = res[max(0, min(len(res), int(k)) - 1)]
        cfg["weather"].update(place=r["label"], lat=r["lat"], lon=r["lon"], enabled=True)
        save(cfg)
        print(f"✔ Τοποθεσία: {r['label']}")
        return 0
    if "--status" in a:
        port = cfg["server"].get("port", 8765)
        print(f"{APP_NAME} v{APP_VERSION}\nΔεδομένα: {DATA_DIR}")
        print(f"Αισθητήρες: {len(cfg['devices'])}")
        for d in cfg["devices"]:
            print(f"  • {d.get('name')}  {d['ip']}  [{d.get('type')}]  {'ενεργός' if d.get('enabled', True) else 'ανενεργός'}")
        w = cfg.get("weather") or {}
        print(f"Καιρός: {w.get('place') or '—'} ({'ενεργός' if w.get('enabled') else 'ανενεργός'})")
        print(f"Email: {'ενεργό' if cfg['email'].get('enabled') else 'ανενεργό'} · PIN: {'ναι' if cfg['server'].get('pin') else 'όχι'}"
              f" · Διαχειριστής: {'ναι' if (cfg.get('admin') or {}).get('hash') else 'ΟΧΙ'}")
        for ip in lan_ipv4s():
            print(f"Web (τοπικά):   http://{ip}:{port}")
        ts = tailscale_info()
        if ts.get("ip"):
            print(f"Web (Tailscale): http://{ts['ip']}:{port}")
        return 0
    return None


def _cli_safe():
    try:
        return cli_main()
    except (EOFError, KeyboardInterrupt):
        print("\n✖ Ακυρώθηκε.")
        return 1


if __name__ == "__main__":
    rc = _cli_safe() if any(x in sys.argv for x in CLI_FLAGS[1:]) else None
    if rc is not None:
        sys.exit(rc)
    sys.exit(headless_main() if HEADLESS else main())
