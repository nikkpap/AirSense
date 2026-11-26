#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AirSense Remote — manage your AirSense board (Raspberry Pi / Luckfox Pico) over SSH, with a GUI.

  • LEDs: board reachable · SSH · web server :8765 · sensors · Tailscale
  • «airsense status» as a clean GUI (sections with ✔ / ⚠ / ✖)
  • live sensor values · QR codes for the phone
  • one-click commands (status, logs, update, scan, restart, clock, Tailscale, reboot …)
  • your own command + a terminal window (colors, sudo password answered by itself, Ctrl+C)
  • LAN / airsense.local / Tailscale — finds the route that works by itself

Double-click: installs what it needs (PyQt6, paramiko, qrcode) by itself.
Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM
"""
APP_NAME = "AirSense Remote"
APP_VERSION = "1.1.0"

import os
import sys
import json
import time
import re
import socket
import base64
import threading
import subprocess
import importlib.util
import urllib.request
import urllib.error
import ipaddress
from concurrent.futures import ThreadPoolExecutor

REQUIRED = [("PyQt6", "PyQt6"), ("paramiko", "paramiko"), ("qrcode", "qrcode")]


# ═════════════════════════ dependencies (auto-install) ═════════════════════════
def _ensure_deps():
    missing = [pip for mod, pip in REQUIRED if importlib.util.find_spec(mod) is None]
    if not missing:
        return
    win = None
    try:
        import tkinter as tk
        win = tk.Tk()
        win.title(APP_NAME)
        win.geometry("460x120")
        tk.Label(win, text=f"{APP_NAME}: installing {', '.join(missing)} …\n(first run only — 1–3 minutes)",
                 font=("Segoe UI", 11), pady=25).pack()
        win.update()
    except Exception:
        win = None
    py = sys.executable
    if py.lower().endswith("pythonw.exe"):
        py = py[:-len("pythonw.exe")] + "python.exe"
    flags = 0x08000000 if os.name == "nt" else 0
    r = subprocess.run([py, "-m", "pip", "install", "--user", "--disable-pip-version-check", "-q"] + missing,
                       capture_output=True, text=True, creationflags=flags)
    if r.returncode != 0:
        r = subprocess.run([py, "-m", "pip", "install", "--disable-pip-version-check", "-q"] + missing,
                           capture_output=True, text=True, creationflags=flags)
    if win:
        win.destroy()
    if r.returncode != 0:
        try:
            import tkinter.messagebox as mb
            mb.showerror(APP_NAME, "Could not install:\n" + ", ".join(missing) + "\n\n" + (r.stderr or r.stdout)[-800:])
        except Exception:
            print(r.stderr)
        sys.exit(1)
    import site
    importlib.invalidate_caches()
    try:
        sys.path.append(site.getusersitepackages())
    except Exception:
        pass


if __name__ == "__main__" and "--no-deps" not in sys.argv:
    _ensure_deps()

import paramiko                                                    # noqa: E402
import qrcode                                                      # noqa: E402
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QUrl, QSize  # noqa: E402
from PyQt6.QtGui import (QColor, QFont, QPainter, QPixmap, QIcon, QTextCursor, QDesktopServices,  # noqa: E402
                         QKeySequence, QShortcut, QFontDatabase)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton, QLineEdit,  # noqa: E402
                             QComboBox, QHBoxLayout, QVBoxLayout, QGridLayout, QFrame, QTextEdit,
                             QTreeWidget, QTreeWidgetItem, QSplitter, QDialog, QFormLayout, QCheckBox,
                             QMessageBox, QInputDialog, QSpinBox, QDialogButtonBox, QGroupBox, QScrollArea,
                             QSizePolicy, QHeaderView, QTabWidget)

# ═════════════════════════ settings ═════════════════════════
CFG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~/.config"), APP_NAME)
CFG_PATH = os.path.join(CFG_DIR, "config.json")
DEFAULT_CFG = {
    "lan": "192.168.1.29", "mdns": "airsense.local", "tailscale": "100.104.13.118",
    "route": "auto", "user": "pico", "password": "", "port": 22, "web_port": 8765, "pin": "",
    "auto_connect": True, "save_password": True, "geometry": "", "auto_find": True,
}


def _dpapi(data: bytes, protect: bool) -> bytes:
    """Windows DPAPI: the password can only be read by YOUR Windows user on THIS PC."""
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(data, len(data))
    bi = BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    bo = BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    if not fn(ctypes.byref(bi), None, None, None, None, 0, ctypes.byref(bo)):
        raise OSError("DPAPI failed")
    out = ctypes.string_at(bo.pbData, bo.cbData)
    ctypes.windll.kernel32.LocalFree(bo.pbData)
    return out


def enc_pw(pw: str) -> str:
    if not pw:
        return ""
    try:
        return "dpapi:" + base64.b64encode(_dpapi(pw.encode(), True)).decode() if os.name == "nt" \
            else "b64:" + base64.b64encode(pw.encode()).decode()
    except Exception:
        return "b64:" + base64.b64encode(pw.encode()).decode()


def dec_pw(s: str) -> str:
    try:
        if s.startswith("dpapi:"):
            return _dpapi(base64.b64decode(s[6:]), False).decode()
        if s.startswith("b64:"):
            return base64.b64decode(s[4:]).decode()
    except Exception:
        pass
    return ""


def load_cfg():
    c = dict(DEFAULT_CFG)
    try:
        with open(CFG_PATH, encoding="utf-8") as f:
            c.update(json.load(f))
    except Exception:
        pass
    c["_pw"] = dec_pw(c.get("password", ""))
    return c


def save_cfg(c):
    os.makedirs(CFG_DIR, exist_ok=True)
    d = {k: v for k, v in c.items() if not k.startswith("_")}
    d["password"] = enc_pw(c.get("_pw", "")) if c.get("save_password", True) else ""
    tmp = CFG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CFG_PATH)


# ═════════════════════════ helpers ═════════════════════════
def tcp_ok(host, port, timeout=2.0):
    if not host:
        return False
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def http_json(url, pin="", timeout=5):
    req = urllib.request.Request(url, headers={"X-PIN": pin or "", "User-Agent": f"{APP_NAME}/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[()][A-Z0-9]|\x1b[=>]")
ANSI_COLORS = {30: "#5b6678", 31: "#ff5c5c", 32: "#2ecc71", 33: "#f5b942", 34: "#5b8cff", 35: "#c678dd",
               36: "#4dd0e1", 37: "#e6e9ef", 90: "#7d8799", 91: "#ff7b7b", 92: "#57e389", 93: "#ffd866",
               94: "#7aa2ff", 95: "#d7a1ff", 96: "#7ee8f2", 97: "#ffffff"}


def strip_ansi(s):
    return ANSI_RE.sub("", s)


def ansi_to_html(line):
    """One line with ANSI colors → HTML (bold, dim, 16 colors)."""
    out, fg, bold, dim = [], None, False, False
    pos = 0
    for m in re.finditer(r"\x1b\[([0-9;]*)m", line):
        out.append((line[pos:m.start()], fg, bold, dim))
        for code in (m.group(1) or "0").split(";"):
            try:
                c = int(code or 0)
            except ValueError:
                continue
            if c == 0:
                fg, bold, dim = None, False, False
            elif c == 1:
                bold = True
            elif c == 2:
                dim = True
            elif c in (22,):
                bold = dim = False
            elif c in ANSI_COLORS:
                fg = ANSI_COLORS[c]
            elif c == 39:
                fg = None
        pos = m.end()
    out.append((line[pos:], fg, bold, dim))
    html = []
    for txt, fg, b, d in out:
        txt = strip_ansi(txt)
        if not txt:
            continue
        txt = txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(" ", "&nbsp;")
        st = []
        if fg:
            st.append(f"color:{fg}")
        elif d:
            st.append("color:#7d8799")
        if b:
            st.append("font-weight:700")
        html.append(f"<span style='{';'.join(st)}'>{txt}</span>" if st else txt)
    return "".join(html)


def last_cr(s):
    """progress bars redraw a line with \\r → keep what is visible."""
    return s.split("\r")[-1] if "\r" in s else s


# ═════════════════════════ BleBox search from this PC ═════════════════════════
SENSOR_TYPES = {"humiditysensor", "multisensor", "tempsensor"}


def pc_networks():
    """The /24 networks of this PC (WiFi / Ethernet), without loopback / link-local / Tailscale."""
    ips = set()
    try:
        for fam, *_rest, addr in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(addr[0])
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    nets = []
    for ip in ips:
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if a.is_loopback or a.is_link_local or a in ipaddress.ip_network("100.64.0.0/10"):
            continue
        n = ipaddress.ip_network(f"{ip}/24", strict=False)
        if n not in nets:
            nets.append(n)
    return nets


def blebox_sensor(ip, timeout=2.0):
    """BleBox sensor at this IP? → dict(device) or None"""
    try:
        with socket.create_connection((ip, 80), timeout=0.5):
            pass
    except Exception:
        return None
    for path in ("/info", "/api/device/state"):
        try:
            req = urllib.request.Request(f"http://{ip}{path}", headers={"User-Agent": APP_NAME})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                js = json.loads(r.read().decode("utf-8", "replace"))
            dev = js.get("device") if isinstance(js, dict) else None
            if isinstance(dev, dict) and str(dev.get("type", "")).lower() in SENSOR_TYPES:
                return dev
        except Exception:
            continue
    return None


# ═════════════════════════ SSH ═════════════════════════
class SSHConn:
    """paramiko Transport with auth: none (Tailscale SSH) → password → keyboard-interactive → keys."""

    def __init__(self, host, port, user, pw):
        self.host, self.port, self.user, self.pw = host, int(port), user, pw
        self.t = None

    def connect(self, timeout=8):
        sock = socket.create_connection((self.host, self.port), timeout=timeout)
        t = paramiko.Transport(sock)
        t.banner_timeout = timeout
        t.start_client(timeout=timeout)
        allowed = []
        try:
            t.auth_none(self.user)
        except paramiko.BadAuthenticationType as e:
            allowed = list(e.allowed_types)
        except paramiko.SSHException:
            allowed = ["password", "keyboard-interactive", "publickey"]
        if not t.is_authenticated() and self.pw and "password" in allowed:
            try:
                t.auth_password(self.user, self.pw)
            except paramiko.AuthenticationException:
                pass
        if not t.is_authenticated() and self.pw and "keyboard-interactive" in allowed:
            try:
                t.auth_interactive(self.user, lambda title, instr, prompts: [self.pw for _ in prompts])
            except paramiko.AuthenticationException:
                pass
        if not t.is_authenticated() and "publickey" in allowed:
            for k in self._keys():
                try:
                    t.auth_publickey(self.user, k)
                    break
                except Exception:
                    continue
        if not t.is_authenticated():
            t.close()
            raise paramiko.AuthenticationException("wrong user or password")
        t.set_keepalive(20)
        self.t = t
        return self

    def _keys(self):
        keys = []
        try:
            keys += list(paramiko.Agent().get_keys())
        except Exception:
            pass
        d = os.path.join(os.path.expanduser("~"), ".ssh")
        for n in ("id_ed25519", "id_ecdsa", "id_rsa"):
            p = os.path.join(d, n)
            if os.path.isfile(p):
                for cls in (paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.RSAKey):
                    try:
                        keys.append(cls.from_private_key_file(p))
                        break
                    except Exception:
                        continue
        return keys

    @property
    def alive(self):
        return bool(self.t and self.t.is_active())

    def run(self, cmd, timeout=60):
        """Short command without terminal → (exit code, text)."""
        ch = self.t.open_session(timeout=10)
        ch.settimeout(timeout)
        ch.get_pty(term="dumb", width=200, height=50)
        ch.exec_command(cmd)
        buf, t0, sudo_sent = b"", time.time(), False
        while True:
            if ch.recv_ready():
                d = ch.recv(65536)
                buf += d
                if not sudo_sent and b"[sudo] password for" in buf[-200:] and self.pw:
                    ch.send(self.pw + "\n")
                    sudo_sent = True
            elif ch.exit_status_ready():
                while ch.recv_ready():
                    buf += ch.recv(65536)
                break
            elif time.time() - t0 > timeout:
                ch.close()
                break
            else:
                time.sleep(0.05)
        rc = ch.recv_exit_status() if ch.exit_status_ready() else -1
        ch.close()
        return rc, buf.decode("utf-8", "replace")

    def close(self):
        try:
            if self.t:
                self.t.close()
        except Exception:
            pass
        self.t = None


class Bus(QObject):
    """signals from worker threads → GUI thread"""
    term = pyqtSignal(str)              # completed lines (raw, with ANSI)
    live = pyqtSignal(str)              # current (unfinished) line / prompt
    cmd_done = pyqtSignal(str, int)
    connected = pyqtSignal(bool, str, str)   # ok, host, message
    leds = pyqtSignal(dict)
    status = pyqtSignal(str)
    sensors = pyqtSignal(object)
    find_done = pyqtSignal(str, str)     # result: found / added / none / error, message


# ═════════════════════════ UI pieces ═════════════════════════
QSS = """
* { font-family: 'Segoe UI', 'Noto Sans', sans-serif; font-size: 10.5pt; color: #e6e9ef; }
QMainWindow, QWidget#root { background: #0f141c; }
QFrame#card { background: #161d29; border: 1px solid #222c3b; border-radius: 14px; }
QLabel#h1 { font-size: 17pt; font-weight: 700; }
QLabel#h2 { font-size: 11pt; font-weight: 700; color: #9fb1d0; }
QLabel#muted { color: #7d8799; }
QPushButton { background: #1f2836; border: 1px solid #2c3850; border-radius: 9px; padding: 7px 12px; }
QPushButton:hover { background: #26324a; border-color: #3d5280; }
QPushButton:pressed { background: #2b6cff; }
QPushButton:disabled { color: #59627a; background: #171d27; }
QPushButton#pri { background: #2b6cff; border-color: #2b6cff; font-weight: 700; }
QPushButton#pri:hover { background: #3f7bff; }
QPushButton#danger { border-color: #6b2b33; }
QPushButton#danger:hover { background: #4a1f26; }
QLineEdit, QComboBox, QSpinBox { background: #0f141c; border: 1px solid #2c3850; border-radius: 8px; padding: 6px 8px; }
QLineEdit:focus, QComboBox:focus { border-color: #2b6cff; }
QComboBox QAbstractItemView { background: #161d29; selection-background-color: #2b6cff; }
QTextEdit#term { background: #0a0e14; border: 1px solid #222c3b; border-radius: 10px; padding: 6px;
                 font-family: 'Cascadia Mono', 'Consolas', 'DejaVu Sans Mono', monospace; font-size: 10pt; }
QTreeWidget { background: #0f141c; border: 1px solid #222c3b; border-radius: 10px; }
QTreeWidget::item { padding: 3px; }
QHeaderView::section { background: #161d29; border: none; padding: 5px; color: #9fb1d0; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: #161d29; padding: 7px 14px; border-top-left-radius: 9px; border-top-right-radius: 9px; margin-right: 3px; }
QTabBar::tab:selected { background: #2b6cff; }
QGroupBox { border: 1px solid #222c3b; border-radius: 10px; margin-top: 12px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #9fb1d0; font-weight: 700; }
QScrollArea { border: none; background: transparent; }
QCheckBox::indicator { width: 18px; height: 18px; }
"""


class Led(QWidget):
    """● colored dot + label + tooltip."""
    COL = {"ok": "#2ecc71", "bad": "#ff5c5c", "warn": "#f5b942", "off": "#3b4558"}

    def __init__(self, text):
        super().__init__()
        self.state = "off"
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 2, 6, 2)
        lay.setSpacing(6)
        self.dot = QLabel()
        self.dot.setFixedSize(16, 16)
        self.lbl = QLabel(text)
        lay.addWidget(self.dot)
        lay.addWidget(self.lbl)
        self.set("off", "")

    def set(self, state, tip=""):
        self.state = state
        c = self.COL.get(state, self.COL["off"])
        glow = f"border: 2px solid {c}55;" if state != "off" else "border: 2px solid #222c3b;"
        self.dot.setStyleSheet(f"background:{c}; border-radius:8px; {glow}")
        self.setToolTip(tip)


class QrView(QLabel):
    def __init__(self, title):
        super().__init__()
        self.title = title
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(190, 220)

    def show_url(self, url):
        if not url:
            self.setText(f"{self.title}\n—")
            return
        q = qrcode.QRCode(border=2, box_size=1, error_correction=qrcode.constants.ERROR_CORRECT_M)
        q.add_data(url)
        q.make(fit=True)
        m = q.get_matrix()
        n, s = len(m), 6
        pm = QPixmap(n * s, n * s + 34)
        pm.fill(QColor("#ffffff"))
        p = QPainter(pm)
        for y, row in enumerate(m):
            for x, v in enumerate(row):
                if v:
                    p.fillRect(x * s, y * s, s, s, QColor("#000000"))
        p.setPen(QColor("#1b2433"))
        f = QFont()
        f.setPointSize(8)
        f.setBold(True)
        p.setFont(f)
        p.drawText(0, n * s + 4, n * s, 28, Qt.AlignmentFlag.AlignCenter, f"{self.title}\n{url}")
        p.end()
        self.setPixmap(pm)


def card(title=None):
    fr = QFrame()
    fr.setObjectName("card")
    lay = QVBoxLayout(fr)
    lay.setContentsMargins(14, 12, 14, 12)
    lay.setSpacing(8)
    if title:
        t = QLabel(title)
        t.setObjectName("h2")
        lay.addWidget(t)
    return fr, lay


# ═════════════════════════ settings dialog ═════════════════════════
class SettingsDialog(QDialog):
    def __init__(self, parent, cfg):
        super().__init__(parent)
        self.setWindowTitle(f"⚙ Connection — {APP_NAME}")
        self.cfg = cfg
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        intro = QLabel("The board can be reached in 3 ways — <b>Auto</b> tries them in order and keeps the one that works.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        f = QFormLayout()
        self.lan = QLineEdit(cfg["lan"])
        self.lan.setPlaceholderText("192.168.1.29")
        self.mdns = QLineEdit(cfg["mdns"])
        self.ts = QLineEdit(cfg["tailscale"])
        self.ts.setPlaceholderText("100.x.x.x (Tailscale)")
        self.user = QLineEdit(cfg["user"])
        self.pw = QLineEdit(cfg.get("_pw", ""))
        self.pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw.setPlaceholderText("the board user's password (pico / pi)")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(int(cfg["port"]))
        self.web = QSpinBox()
        self.web.setRange(1, 65535)
        self.web.setValue(int(cfg["web_port"]))
        self.pin = QLineEdit(cfg.get("pin", ""))
        self.pin.setPlaceholderText("PIN of the web page (if you set one)")
        self.save_pw = QCheckBox("Remember the password (encrypted with your Windows account)")
        self.save_pw.setChecked(cfg.get("save_password", True))
        self.auto = QCheckBox("Connect automatically when the program opens")
        self.auto.setChecked(cfg.get("auto_connect", True))
        f.addRow("🏠 Local IP (LAN)", self.lan)
        f.addRow("🔤 Name (mDNS)", self.mdns)
        f.addRow("🌍 Tailscale IP", self.ts)
        f.addRow("👤 User", self.user)
        f.addRow("🔑 Password", self.pw)
        f.addRow("SSH port", self.port)
        f.addRow("Web port", self.web)
        f.addRow("📟 PIN", self.pin)
        lay.addLayout(f)
        lay.addWidget(self.save_pw)
        lay.addWidget(self.auto)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.ok)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def ok(self):
        c = self.cfg
        c.update(lan=self.lan.text().strip(), mdns=self.mdns.text().strip(), tailscale=self.ts.text().strip(),
                 user=self.user.text().strip() or "pico", port=self.port.value(), web_port=self.web.value(),
                 pin=self.pin.text().strip(), save_password=self.save_pw.isChecked(), auto_connect=self.auto.isChecked())
        c["_pw"] = self.pw.text()
        save_cfg(c)
        self.accept()


# ═════════════════════════ main window ═════════════════════════
COMMANDS = [
    # (group, label, command, kind, tooltip)   kind: run = terminal · stream = until Stop · confirm · ask:<question>
    ("Info", "🩺 Status", "airsense status", "status", "Full diagnosis (also shown on the left)"),
    ("Info", "📜 Logs", "airsense logs", "run", "Last messages: server, boot, Tailscale"),
    ("Info", "📡 Live log", "airsense live", "stream", "Live log — Stop to end"),
    ("Info", "🕒 Clock", "airsense clock", "run", "Time, time zone, NTP"),
    ("Info", "🔗 MAC", "airsense mac", "run", "MAC address (for an IP reservation in the router)"),
    ("Info", "📋 Help", "airsense help", "run", "All airsense commands"),
    ("Server", "↻ Restart", "airsense restart", "run", "Restart the AirSense server"),
    ("Server", "■ Stop", "airsense stop", "confirm", "Stop the server (starts again on reboot)"),
    ("Server", "⬇ Update", "airsense update", "run", "Check GitHub + update now"),
    ("Server", "🔄 Auto-update", "airsense autoupdate", "run", "Automatic update state"),
    ("Server", "🌍 Tailscale", "airsense tailscale", "run", "Tailscale connect / login link"),
    ("Server", "🔐 Admin password", "airsense set-admin", "run", "Admin password (interactive — answer below)"),
    ("Sensors", "🔎 Find sensor", "", "find", "Automatic check: board scan → PC scan → add → tell me what is wrong"),
    ("Sensors", "🔍 Scan", "airsense scan", "run", "Find + add BleBox sensors on the network (board only)"),
    ("Sensors", "＋ Add by IP", "airsense add {ip}", "ask:Sensor IP (e.g. 192.168.1.253)", "Add a sensor by IP"),
    ("Sensors", "📟 Set PIN", "airsense set-pin {pin}", "ask:New PIN for the web page (empty = no PIN)", "PIN of the web page"),
    ("Sensors", "🌤 City", "airsense city {city}", "ask:City / village for the weather", "Weather location"),
    ("Sensors", "🕒 Time zone", "airsense clock {tz}", "ask:Time zone (e.g. Europe/Athens)", "Change the time zone"),
    ("System", "💽 Disk / RAM", "df -h / && free -m", "run", "Free space and memory"),
    ("System", "🌡 CPU temp", "cat /sys/class/thermal/thermal_zone0/temp | awk '{printf \"%.1f °C\\n\", $1/1000}'", "run", "CPU temperature"),
    ("System", "🔑 Password", "airsense password", "run", "Change the login password (interactive — answer below)"),
    ("System", "⟳ Reboot", "sudo reboot", "confirm", "Restart the board (1–2 minutes)"),
    ("System", "⏻ Power off", "sudo poweroff", "confirm", "Shut down — then unplug safely"),
]


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_cfg()
        self.bus = Bus()
        self.conn = None
        self.host = ""
        self.chan = None
        self.chan_lock = threading.Lock()
        self.history, self.hidx = [], 0
        self._sudo_sent = False
        self.setWindowTitle(f"🌬 {APP_NAME} v{APP_VERSION}")
        self.resize(1360, 860)
        self._build()
        self.bus.term.connect(self._term_lines)
        self.bus.live.connect(self._live_line)
        self.bus.cmd_done.connect(self._cmd_done)
        self.bus.connected.connect(self._on_connected)
        self.bus.leds.connect(self._on_leds)
        self.bus.status.connect(self._on_status)
        self.bus.sensors.connect(self._on_sensors)
        self.bus.find_done.connect(self._find_done)
        self._finding = False
        self._sensor_bad = 0
        self._last_autofind = 0.0
        self.led_timer = QTimer(self)
        self.led_timer.timeout.connect(self.refresh_leds)
        self.led_timer.start(15000)
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(lambda: self.refresh_status(quiet=True))
        self.status_timer.start(180000)
        QTimer.singleShot(300, self.refresh_leds)
        if self.cfg.get("auto_connect") and (self.cfg.get("_pw") or True):
            QTimer.singleShot(600, self.connect_ssh)

    # ── layout ──
    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(14, 12, 14, 10)
        v.setSpacing(10)

        # top bar
        top, tl = card()
        row = QHBoxLayout()
        t = QLabel("🌬 AirSense Remote")
        t.setObjectName("h1")
        row.addWidget(t)
        row.addSpacing(14)
        self.route = QComboBox()
        self.route.addItems(["Auto", "🏠 LAN", "🔤 airsense.local", "🌍 Tailscale"])
        self.route.setCurrentIndex({"auto": 0, "lan": 1, "mdns": 2, "tailscale": 3}.get(self.cfg.get("route"), 0))
        self.route.currentIndexChanged.connect(self._route_changed)
        row.addWidget(QLabel("Route"))
        row.addWidget(self.route)
        self.btn_conn = QPushButton("🔌 Connect")
        self.btn_conn.setObjectName("pri")
        self.btn_conn.clicked.connect(self.toggle_conn)
        row.addWidget(self.btn_conn)
        b = QPushButton("⚙ Settings")
        b.clicked.connect(self.open_settings)
        row.addWidget(b)
        b = QPushButton("🌐 Web page")
        b.clicked.connect(self.open_web)
        row.addWidget(b)
        row.addStretch()
        self.conn_lbl = QLabel("not connected")
        self.conn_lbl.setObjectName("muted")
        row.addWidget(self.conn_lbl)
        tl.addLayout(row)
        leds = QHBoxLayout()
        self.led = {k: Led(n) for k, n in (("host", "Board"), ("ssh", "SSH"), ("web", "Web :8765"),
                                            ("sensor", "Sensors"), ("ts", "Tailscale"), ("health", "Health"))}
        for k in ("host", "ssh", "web", "sensor", "ts", "health"):
            leds.addWidget(self.led[k])
        leds.addStretch()
        self.led_time = QLabel("")
        self.led_time.setObjectName("muted")
        leds.addWidget(self.led_time)
        tl.addLayout(leds)
        v.addWidget(top)

        split = QSplitter(Qt.Orientation.Horizontal)
        v.addWidget(split, 1)

        # left: sensors + status + QR
        left = QTabWidget()
        # — Overview tab
        ov = QWidget()
        ol = QVBoxLayout(ov)
        ol.setContentsMargins(0, 6, 0, 0)
        sc, sl = card()
        sh = QHBoxLayout()
        h = QLabel("🌡 Sensors (live)")
        h.setObjectName("h2")
        sh.addWidget(h)
        sh.addStretch()
        self.chk_autofind = QCheckBox("auto")
        self.chk_autofind.setToolTip("When the sensor stays offline, look for it by itself (at most every 10 minutes)")
        self.chk_autofind.setChecked(bool(self.cfg.get("auto_find", True)))
        self.chk_autofind.toggled.connect(self._autofind_toggled)
        sh.addWidget(self.chk_autofind)
        self.btn_find = QPushButton("🔎 Find sensor")
        self.btn_find.setObjectName("pri")
        self.btn_find.setToolTip("Automatic check: board scan → PC scan → add → tell me what is wrong")
        self.btn_find.clicked.connect(lambda: self.find_sensor(quiet=False))
        sh.addWidget(self.btn_find)
        sl.addLayout(sh)
        self.sens_box = QVBoxLayout()
        self.sens_empty = QLabel("—")
        self.sens_empty.setObjectName("muted")
        self.sens_box.addWidget(self.sens_empty)
        sl.addLayout(self.sens_box)
        ol.addWidget(sc)
        stc, stl = card()
        hr = QHBoxLayout()
        h = QLabel("🩺 Board status")
        h.setObjectName("h2")
        hr.addWidget(h)
        hr.addStretch()
        self.st_sum = QLabel("")
        hr.addWidget(self.st_sum)
        b = QPushButton("↻")
        b.setToolTip("Refresh the status (airsense status)")
        b.setFixedWidth(40)
        b.clicked.connect(lambda: self.refresh_status(quiet=False))
        hr.addWidget(b)
        stl.addLayout(hr)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["", "Item", "Value"])
        self.tree.setRootIsDecorated(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setStretchLastSection(True)
        self.tree.setWordWrap(True)
        stl.addWidget(self.tree, 1)
        ol.addWidget(stc, 1)
        left.addTab(ov, "📊 Overview")
        # — QR tab
        qw = QWidget()
        ql = QVBoxLayout(qw)
        qc, qcl = card("📱 Scan with the phone (AirSense app → Add server)")
        qr_row = QHBoxLayout()
        self.qr_lan = QrView("🏠 Local")
        self.qr_ts = QrView("🌍 Tailscale")
        qr_row.addWidget(self.qr_lan)
        qr_row.addWidget(self.qr_ts)
        qcl.addLayout(qr_row)
        n = QLabel("Tailscale works from anywhere (4G, other WiFi) while Tailscale is ON on the phone.")
        n.setObjectName("muted")
        n.setWordWrap(True)
        qcl.addWidget(n)
        ql.addWidget(qc)
        ql.addStretch()
        left.addTab(qw, "📱 QR")
        split.addWidget(left)

        # right: commands + terminal
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        cc, ccl = card("⚡ Commands")
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        groups = []
        for g, *_ in COMMANDS:
            if g not in groups:
                groups.append(g)
        self.cmd_buttons = []
        for gi, g in enumerate(groups):
            gl = QLabel(g)
            gl.setObjectName("muted")
            grid.addWidget(gl, gi, 0)
            for ci, (gg, label, cmd, kind, tip) in enumerate([c for c in COMMANDS if c[0] == g]):
                b = QPushButton(label)
                b.setToolTip(f"{tip}\n$ {cmd}")
                if kind == "confirm":
                    b.setObjectName("danger")
                b.clicked.connect(lambda _=False, c=cmd, k=kind, lb=label: self.preset(c, k, lb))
                grid.addWidget(b, gi, ci + 1)
                self.cmd_buttons.append(b)
        ccl.addLayout(grid)
        rl.addWidget(cc)

        tc, tcl = card()
        th = QHBoxLayout()
        h = QLabel("🖥 Terminal")
        h.setObjectName("h2")
        th.addWidget(h)
        th.addStretch()
        self.busy_lbl = QLabel("")
        self.busy_lbl.setObjectName("muted")
        th.addWidget(self.busy_lbl)
        self.btn_stop = QPushButton("■ Stop (Ctrl+C)")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_cmd)
        th.addWidget(self.btn_stop)
        b = QPushButton("🧹 Clear")
        b.clicked.connect(lambda: self.term.clear())
        th.addWidget(b)
        tcl.addLayout(th)
        self.term = QTextEdit()
        self.term.setObjectName("term")
        self.term.setReadOnly(True)
        self.term.document().setMaximumBlockCount(5000)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        for fam in ("Cascadia Mono", "Consolas", "DejaVu Sans Mono"):
            if fam in QFontDatabase.families():
                mono = QFont(fam)
                break
        mono.setPointSize(10)
        self.term.setFont(mono)
        tcl.addWidget(self.term, 1)
        self.live_lbl = QLabel("")
        self.live_lbl.setFont(mono)
        self.live_lbl.setStyleSheet("color:#ffd866")
        self.live_lbl.setWordWrap(True)
        tcl.addWidget(self.live_lbl)
        ir = QHBoxLayout()
        pr = QLabel("$")
        pr.setFont(mono)
        ir.addWidget(pr)
        self.inp = QLineEdit()
        self.inp.setFont(mono)
        self.inp.setPlaceholderText("your command (e.g. airsense status) — or the answer to a question (Y / n / password) while a command runs")
        self.inp.returnPressed.connect(self.send_input)
        ir.addWidget(self.inp, 1)
        self.chk_hide = QCheckBox("hidden")
        self.chk_hide.setToolTip("Hide what you type (for passwords)")
        self.chk_hide.toggled.connect(lambda on: self.inp.setEchoMode(QLineEdit.EchoMode.Password if on else QLineEdit.EchoMode.Normal))
        ir.addWidget(self.chk_hide)
        b = QPushButton("➤ Send")
        b.setObjectName("pri")
        b.clicked.connect(self.send_input)
        ir.addWidget(b)
        tcl.addLayout(ir)
        rl.addWidget(tc, 1)
        split.addWidget(right)
        split.setSizes([520, 840])

        foot = QLabel(f"{APP_NAME} v{APP_VERSION} · Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM")
        foot.setObjectName("muted")
        v.addWidget(foot)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=lambda: self.term.clear())
        QShortcut(QKeySequence("F5"), self, activated=lambda: (self.refresh_leds(), self.refresh_status(False)))
        self.inp.installEventFilter(self)
        self._set_connected_ui(False)
        self._update_qr()

    # ── history ↑ ↓ ──
    def eventFilter(self, obj, ev):
        if obj is self.inp and ev.type() == ev.Type.KeyPress and not self.chan and self.history:
            if ev.key() == Qt.Key.Key_Up:
                self.hidx = max(0, self.hidx - 1)
                self.inp.setText(self.history[self.hidx])
                return True
            if ev.key() == Qt.Key.Key_Down:
                self.hidx = min(len(self.history), self.hidx + 1)
                self.inp.setText(self.history[self.hidx] if self.hidx < len(self.history) else "")
                return True
        return super().eventFilter(obj, ev)

    # ── routes ──
    def _route_changed(self, i):
        self.cfg["route"] = ("auto", "lan", "mdns", "tailscale")[i]
        save_cfg(self.cfg)
        self.refresh_leds()

    def _candidates(self):
        r = self.cfg.get("route", "auto")
        if r == "auto":
            hs = [self.cfg.get("lan"), self.cfg.get("mdns"), self.cfg.get("tailscale")]
        else:
            hs = [self.cfg.get(r)]
        return [h for h in hs if h]

    def web_host(self):
        if self.host:
            return self.host
        for h in self._candidates():
            return h
        return ""

    def _update_qr(self):
        wp = self.cfg.get("web_port", 8765)
        self.qr_lan.show_url(f"http://{self.cfg['lan']}:{wp}" if self.cfg.get("lan") else "")
        self.qr_ts.show_url(f"http://{self.cfg['tailscale']}:{wp}" if self.cfg.get("tailscale") else "")

    # ── connection ──
    def toggle_conn(self):
        if self.conn and self.conn.alive:
            self.disconnect_ssh()
        else:
            self.connect_ssh()

    def connect_ssh(self):
        if not self.cfg.get("_pw") and not self.cfg.get("tailscale"):
            if not self.open_settings():
                return
        self.btn_conn.setEnabled(False)
        self.conn_lbl.setText("connecting…")
        self.led["ssh"].set("warn", "connecting…")
        cfg = dict(self.cfg)

        def job():
            errs = []
            for h in self._candidates():
                if not tcp_ok(h, cfg["port"], 3):
                    errs.append(f"{h}: no answer")
                    continue
                try:
                    c = SSHConn(h, cfg["port"], cfg["user"], cfg.get("_pw", "")).connect()
                    self.conn = c
                    self.host = h
                    self.bus.connected.emit(True, h, "")
                    return
                except Exception as e:
                    errs.append(f"{h}: {e}")
            self.bus.connected.emit(False, "", " · ".join(errs) or "no address set")
        threading.Thread(target=job, daemon=True).start()

    def disconnect_ssh(self):
        self.stop_cmd()
        if self.conn:
            self.conn.close()
        self.conn, self.host = None, ""
        self._set_connected_ui(False)
        self.conn_lbl.setText("disconnected")
        self.led["ssh"].set("off", "not connected")

    def _on_connected(self, ok, host, msg):
        self.btn_conn.setEnabled(True)
        if ok:
            self._set_connected_ui(True)
            via = "Tailscale" if host == self.cfg.get("tailscale") else ("LAN" if host == self.cfg.get("lan") else host)
            self.conn_lbl.setText(f"✔ {self.cfg['user']}@{host} ({via})")
            self.led["ssh"].set("ok", f"connected to {host}")
            self._term_sys(f"✔ Connected to {self.cfg['user']}@{host} via {via}")
            self.refresh_status(quiet=True)
            self.refresh_leds()
        else:
            self._set_connected_ui(False)
            self.conn_lbl.setText("✖ not connected")
            self.led["ssh"].set("bad", msg)
            self._term_sys("✖ Could not connect — " + msg, err=True)
            if "password" in msg.lower() or "authentication" in msg.lower():
                QMessageBox.warning(self, APP_NAME, "Wrong user or password.\n\n⚙ Settings → User / Password.")

    def _set_connected_ui(self, on):
        self.btn_conn.setText("⏏ Disconnect" if on else "🔌 Connect")
        for b in self.cmd_buttons:
            b.setEnabled(on)
        if hasattr(self, "btn_find"):
            self.btn_find.setEnabled(on and not getattr(self, "_finding", False))

    def open_settings(self):
        d = SettingsDialog(self, self.cfg)
        if d.exec():
            self._update_qr()
            self.refresh_leds()
            return True
        return False

    def open_web(self):
        h = self.web_host()
        if h:
            QDesktopServices.openUrl(QUrl(f"http://{h}:{self.cfg.get('web_port', 8765)}"))

    # ── LEDs (cheap checks, every 15 s) ──
    def refresh_leds(self):
        cfg = dict(self.cfg)
        conn, host = self.conn, self.host

        def job():
            wp, res = cfg.get("web_port", 8765), {}
            hosts = [h for h in ([host] if host else []) + self._candidates() if h]
            hosts = list(dict.fromkeys(hosts))
            reach = next((h for h in hosts if tcp_ok(h, cfg["port"], 2) or tcp_ok(h, wp, 2)), "")
            res["host"] = ("ok", f"{reach} answers") if reach else ("bad", "no answer from: " + ", ".join(hosts))
            res["ssh"] = ("ok", f"connected to {host}") if conn and conn.alive else (
                ("bad", "connection lost") if conn else ("off", "not connected"))
            st = None
            wh = reach or (hosts[0] if hosts else "")
            if wh and tcp_ok(wh, wp, 2):
                try:
                    st = http_json(f"http://{wh}:{wp}/api/status", cfg.get("pin", ""), 5)
                    res["web"] = ("ok", f"http://{wh}:{wp} · AirSense v{st.get('version', '?')}")
                except urllib.error.HTTPError as e:
                    res["web"] = ("warn", f"answers but HTTP {e.code} — wrong PIN? (⚙ Settings → PIN)")
                except Exception as e:
                    res["web"] = ("warn", f"answers, no data: {e}")
            else:
                res["web"] = ("bad", f"http://{wh}:{wp} does not answer")
            if st:
                devs = st.get("devices") or []
                on = [d for d in devs if d.get("online")]
                if not devs:
                    res["sensor"] = ("warn", "no sensor added → Scan")
                elif len(on) == len(devs):
                    res["sensor"] = ("ok", " · ".join(f"{d.get('name')}: {d.get('t')}°C {d.get('h')}%" for d in on))
                else:
                    res["sensor"] = ("bad", f"{len(devs) - len(on)} of {len(devs)} offline")
                self.bus.sensors.emit(devs)
            else:
                res["sensor"] = ("off", "unknown (no web data)")
            tsh = cfg.get("tailscale")
            if tsh:
                res["ts"] = ("ok", f"{tsh} answers") if tcp_ok(tsh, wp, 3) or tcp_ok(tsh, cfg["port"], 3) else (
                    "bad", f"{tsh} does not answer — Tailscale ON on this PC?")
            else:
                res["ts"] = ("off", "no Tailscale IP in ⚙ Settings")
            self.bus.leds.emit(res)
        threading.Thread(target=job, daemon=True).start()

    def _on_leds(self, res):
        for k, (s, tip) in res.items():
            if k == "ssh" and s == "off" and self.led["ssh"].state == "warn":
                continue
            self.led[k].set(s, tip)
        self.led_time.setText("checked " + time.strftime("%H:%M:%S"))
        st = res.get("sensor", ("off", ""))[0]
        self._sensor_bad = self._sensor_bad + 1 if st in ("bad", "warn") else 0
        if (self.chk_autofind.isChecked() and self._sensor_bad >= 2 and not self._finding and self.chan is None
                and self.conn and self.conn.alive and time.time() - self._last_autofind > 600):
            self._last_autofind = time.time()
            self._term_sys("🔎 The sensor is offline — looking for it by itself (auto)…")
            self.find_sensor(quiet=True)

    # ── sensors ──
    def _on_sensors(self, devs):
        while self.sens_box.count():
            w = self.sens_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not devs:
            lb = QLabel("No sensor on the board yet → ⚡ Sensors → 🔍 Scan")
            lb.setObjectName("muted")
            self.sens_box.addWidget(lb)
            return
        for d in devs:
            fr = QFrame()
            h = QHBoxLayout(fr)
            h.setContentsMargins(0, 2, 0, 2)
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{'#2ecc71' if d.get('online') else '#ff5c5c'}; font-size:16pt")
            h.addWidget(dot)
            nm = QLabel(f"<b>{d.get('name') or d.get('id')}</b><br><span style='color:#7d8799'>{d.get('ip')} · {d.get('type') or ''}</span>")
            h.addWidget(nm, 1)
            t, hu = d.get("t"), d.get("h")
            val = QLabel(f"<span style='color:#ff9f43;font-size:20pt;font-weight:700'>{'—' if t is None else f'{t:.1f}°C'}</span>"
                         f"&nbsp;&nbsp;<span style='color:#4da3ff;font-size:20pt;font-weight:700'>{'—' if hu is None else f'{hu:.1f}%'}</span>")
            h.addWidget(val)
            fr.setToolTip(f"dew point {d.get('dp')} °C · absolute {d.get('ah')} g/m³\n{d.get('error') or ''}")
            self.sens_box.addWidget(fr)

    # ── status → tree ──
    def refresh_status(self, quiet=True):
        if not (self.conn and self.conn.alive):
            if not quiet:
                self._term_sys("Not connected — 🔌 Connect first", err=True)
            return
        self.st_sum.setText("⏳")
        conn = self.conn

        def job():
            try:
                rc, out = conn.run("airsense status", timeout=90)
                self.bus.status.emit(out)
            except Exception as e:
                self.bus.status.emit(f"✖ {e}")
        threading.Thread(target=job, daemon=True).start()

    def _on_status(self, out):
        self.tree.clear()
        sec_item, bad, warn = None, 0, 0
        icon_col = {"✔": "#2ecc71", "⚠": "#f5b942", "✖": "#ff5c5c"}
        for raw in out.splitlines():
            line = strip_ansi(last_cr(raw)).rstrip()
            if not line.strip() or "password for" in line:
                continue
            m = re.match(r"^\s*──\s*(.+?)\s*──\s*$", line)
            if m:
                sec_item = QTreeWidgetItem(["", m.group(1), ""])
                f = sec_item.font(1)
                f.setBold(True)
                sec_item.setFont(1, f)
                sec_item.setForeground(1, QColor("#9fb1d0"))
                self.tree.addTopLevelItem(sec_item)
                sec_item.setExpanded(True)
                continue
            if re.match(r"^\s*[✔✖]\s+(All good|\d+ problem)", line):
                continue
            m = re.match(r"^\s*([✔⚠✖])\s+(\S.{0,14}?)\s{2,}(.*)$", line) or re.match(r"^\s*([✔⚠✖])\s+(\S+)\s+(.*)$", line)
            if m:
                ic, key, val = m.groups()
                it = QTreeWidgetItem([ic, key.strip(), val.strip()])
                it.setForeground(0, QColor(icon_col[ic]))
                it.setToolTip(2, val.strip())
                bad += ic == "✖"
                warn += ic == "⚠"
            else:
                txt = line.strip()
                if txt.startswith("🌬"):
                    self.setWindowTitle(f"🌬 {APP_NAME} v{APP_VERSION} — {txt[1:].strip()}")
                it = QTreeWidgetItem(["", "", txt])
                it.setForeground(2, QColor("#aab4c6"))
            if sec_item:
                sec_item.addChild(it)
            else:
                self.tree.addTopLevelItem(it)
        if bad:
            self.st_sum.setText(f"<span style='color:#ff5c5c'>✖ {bad} problem(s)</span>")
            self.led["health"].set("bad", f"{bad} problem(s) in the status")
        elif warn:
            self.st_sum.setText(f"<span style='color:#f5b942'>⚠ {warn} warning(s)</span>")
            self.led["health"].set("warn", f"{warn} warning(s)")
        elif out.strip():
            self.st_sum.setText("<span style='color:#2ecc71'>✔ All good</span>")
            self.led["health"].set("ok", "airsense status: all good")

    # ── 🔎 find the sensor automatically ──
    def _autofind_toggled(self, on):
        self.cfg["auto_find"] = bool(on)
        save_cfg(self.cfg)

    def find_sensor(self, quiet=False):
        if not (self.conn and self.conn.alive):
            self._term_sys("Not connected — 🔌 Connect first", err=True)
            return
        if self._finding:
            return
        if self.chan is not None:
            self._term_sys("A command is still running — ■ Stop first", err=True)
            return
        self._finding = True
        self._find_quiet = quiet
        self.btn_find.setEnabled(False)
        self.btn_find.setText("🔎 Searching…")
        self.busy_lbl.setText("⏳ looking for the sensor…")
        conn = self.conn

        def say(t, err=False):
            self.bus.term.emit(("\x1b[31m" if err else "\x1b[36m") + t + "\x1b[0m")

        def job():
            try:
                say("── 🔎 Find sensor ── step 1/3: the board scans its network …")
                rc, out = conn.run("airsense scan", timeout=240)
                lines = [strip_ansi(last_cr(l)).rstrip() for l in out.splitlines()]
                for l in lines:
                    if l.strip() and "password for" not in l and not re.match(r"^\s*\d+/\d+ ·", l.strip()):
                        self.bus.term.emit("   " + l)
                m = re.search(r"Βρέθηκαν (\d+) αισθητήρες", out)
                if m and int(m.group(1)) > 0:
                    self.bus.find_done.emit("found", f"✔ The board found {m.group(1)} sensor(s) — they are on the board now")
                    return
                say("step 2/3: the board sees none → this PC scans its own networks …")
                nets = pc_networks()
                hosts = [str(h) for n in nets for h in n.hosts()]
                say("   " + (", ".join(str(n) for n in nets) or "no network on this PC") + f" ({len(hosts)} addresses)")
                found = []
                with ThreadPoolExecutor(max_workers=64) as ex:
                    for ip, dev in zip(hosts, ex.map(blebox_sensor, hosts)):
                        if dev:
                            found.append((ip, dev))
                            say(f"   ＋ {dev.get('deviceName') or dev.get('type')}  {ip}  [{dev.get('type')}]")
                if not found:
                    self.bus.find_done.emit("none", "")
                    return
                say(f"step 3/3: adding {len(found)} sensor(s) to the board …")
                ok = 0
                for ip, dev in found:
                    rc, out = conn.run(f"airsense add {ip}", timeout=90)
                    txt = strip_ansi(out).strip().splitlines()
                    self.bus.term.emit("   " + (txt[-1] if txt else f"exit {rc}"))
                    ok += rc == 0
                self.bus.find_done.emit("added", f"✔ Added from this PC: {', '.join(ip for ip, _ in found)}"
                                        + ("" if ok == len(found) else " (some failed — see above)"))
            except Exception as e:
                self.bus.find_done.emit("error", str(e))
        threading.Thread(target=job, daemon=True).start()

    def _find_done(self, result, msg):
        self._finding = False
        self.btn_find.setText("🔎 Find sensor")
        self.btn_find.setEnabled(bool(self.conn and self.conn.alive))
        self.busy_lbl.setText("")
        if result in ("found", "added"):
            self._append_html(f"<span style='color:#2ecc71;font-weight:700'>{msg}</span>")
            self._sensor_bad = 0
            QTimer.singleShot(3000, self.refresh_leds)
            QTimer.singleShot(4000, lambda: self.refresh_status(quiet=True))
            return
        if result == "error":
            self._term_sys("✖ Find sensor: " + msg, err=True)
            return
        self._term_sys("✖ No BleBox sensor answers — neither from the board nor from this PC.", err=True)
        help_txt = ("<b>The sensor is most likely not on this WiFi</b> (new place, new WiFi or new password).<br><br>"
                    "<b>1.</b> Sensor on power, wait 1 minute.<br>"
                    "<b>2.</b> On this PC open <b>AirSense</b> → 📡 Sensors → <b>🧙 New sensor (WiFi setup)</b> "
                    "→ the green <i>humiditySensor-…</i> network → give it the WiFi here (<b>2.4 GHz</b>).<br>"
                    "&nbsp;&nbsp;&nbsp;&nbsp;Or on the phone: WiFi <i>humiditySensor-…</i> → <b>wBox</b> app → WiFi settings.<br>"
                    "<b>3.</b> Back here → <b>🔎 Find sensor</b> again (or leave <b>auto</b> ticked — it looks every 10 minutes).<br><br>"
                    "<span style='color:#7d8799'>Still nothing? The WiFi may keep its devices apart (client isolation / guest WiFi) "
                    "or put them on another network than the board's cable.</span>")
        self._append_html(f"<span style='color:#f5b942'>{help_txt}</span>")
        if not getattr(self, "_find_quiet", False):
            box = QMessageBox(self)
            box.setWindowTitle("🔎 Find sensor")
            box.setTextFormat(Qt.TextFormat.RichText)
            box.setText(help_txt)
            box.exec()

    # ── commands ──
    def preset(self, cmd, kind, label):
        if not (self.conn and self.conn.alive):
            self._term_sys("Not connected — 🔌 Connect first", err=True)
            return
        if kind == "find":
            self.find_sensor(quiet=False)
            return
        if kind == "confirm":
            if QMessageBox.question(self, APP_NAME, f"{label}\n\n$ {cmd}\n\nAre you sure?") != QMessageBox.StandardButton.Yes:
                return
        if kind.startswith("ask:"):
            q = kind[4:]
            val, ok = QInputDialog.getText(self, label, q)
            if not ok:
                return
            val = val.strip()
            if "{ip}" in cmd and not re.fullmatch(r"[0-9.]{7,15}", val):
                QMessageBox.warning(self, APP_NAME, "Write an IP like 192.168.1.253")
                return
            safe = "'" + val.replace("'", "'\\''") + "'" if val else ""
            cmd = re.sub(r"\{\w+\}", safe, cmd).rstrip()
        if kind == "status":
            self.refresh_status(quiet=False)
        self.run_cmd(cmd)

    def send_input(self):
        txt = self.inp.text()
        if self.chan is not None:                     # a command is running → answer it
            try:
                self.chan.send(txt + "\n")
                self._term_sys(("•" * len(txt)) if self.chk_hide.isChecked() else txt, prefix="» ")
            except Exception:
                pass
            self.inp.clear()
            return
        cmd = txt.strip()
        if not cmd:
            return
        if not (self.conn and self.conn.alive):
            self._term_sys("Not connected — 🔌 Connect first", err=True)
            return
        if not self.history or self.history[-1] != cmd:
            self.history.append(cmd)
        self.hidx = len(self.history)
        self.inp.clear()
        self.run_cmd(cmd)

    def run_cmd(self, cmd):
        if not (self.conn and self.conn.alive):
            self._term_sys("Not connected — 🔌 Connect first", err=True)
            return
        if self.chan is not None:
            self._term_sys("A command is still running — ■ Stop first", err=True)
            return
        self._term_sys(cmd, prefix=f"{self.cfg['user']}@{self.host}:~$ ", cmd=True)
        self.btn_stop.setEnabled(True)
        self.busy_lbl.setText("⏳ running…")
        self.chk_hide.setChecked(False)
        conn = self.conn

        def job():
            rc = -1
            try:
                ch = conn.t.open_session(timeout=10)
                ch.get_pty(term="xterm", width=140, height=45)
                ch.exec_command(cmd)
                with self.chan_lock:
                    self.chan = ch
                pending, sudo_sent = "", False
                while True:
                    if ch.recv_ready():
                        pending += ch.recv(32768).decode("utf-8", "replace")
                        if "\n" in pending:
                            *lines, pending = pending.split("\n")
                            self.bus.term.emit("\n".join(l.rstrip("\r") for l in lines))
                        tail = last_cr(pending)
                        low = strip_ansi(tail).lower()
                        if "[sudo] password for" in low and not sudo_sent and conn.pw:
                            ch.send(conn.pw + "\n")
                            sudo_sent = True
                            self.bus.term.emit("\x1b[2m[sudo] password sent automatically\x1b[0m")
                            pending = ""
                            continue
                        self.bus.live.emit(tail)
                    elif ch.exit_status_ready() or ch.closed:
                        while ch.recv_ready():
                            pending += ch.recv(32768).decode("utf-8", "replace")
                        if pending.strip():
                            self.bus.term.emit("\n".join(last_cr(l) for l in pending.split("\n")))
                        break
                    else:
                        time.sleep(0.03)
                rc = ch.recv_exit_status() if ch.exit_status_ready() else -1
            except Exception as e:
                self.bus.term.emit(f"\x1b[31m✖ {e}\x1b[0m")
            finally:
                with self.chan_lock:
                    try:
                        if self.chan:
                            self.chan.close()
                    except Exception:
                        pass
                    self.chan = None
                self.bus.cmd_done.emit(cmd, rc)
        threading.Thread(target=job, daemon=True).start()

    def stop_cmd(self):
        with self.chan_lock:
            ch = self.chan
        if ch is not None:
            try:
                ch.send("\x03")
                time.sleep(0.3)
                ch.close()
            except Exception:
                pass

    def _cmd_done(self, cmd, rc):
        self.btn_stop.setEnabled(False)
        self.busy_lbl.setText("")
        self.live_lbl.setText("")
        col = "#2ecc71" if rc == 0 else ("#7d8799" if rc == -1 else "#ff5c5c")
        self._append_html(f"<span style='color:{col}'>── done (exit {rc}) ──</span>")
        if any(k in cmd for k in ("scan", "add ", "restart", "update", "set-pin", "city", "clock")):
            QTimer.singleShot(4000, self.refresh_leds)
            QTimer.singleShot(5000, lambda: self.refresh_status(quiet=True))
        if "set-pin" in cmd:
            m = re.search(r"set-pin\s+'?([^']*)'?", cmd)
            self.cfg["pin"] = (m.group(1) if m else "").strip()
            save_cfg(self.cfg)
        if cmd.strip() in ("sudo reboot", "sudo poweroff"):
            self.disconnect_ssh()
            self._term_sys("The board is " + ("restarting — reconnect in 1–2 minutes" if "reboot" in cmd else "shutting down — unplug it in ~20 s"))

    # ── terminal output ──
    def _append_html(self, html):
        sb = self.term.verticalScrollBar()
        at_end = sb.value() >= sb.maximum() - 4
        self.term.append(f"<span>{html}</span>")   # always rich text (else &nbsp; shows literally)
        if at_end:
            self.term.moveCursor(QTextCursor.MoveOperation.End)

    def _term_lines(self, text):
        for line in text.split("\n"):
            line = last_cr(line)
            if line.startswith("\x1b[2J") or line.startswith("\x1b[H"):
                continue
            self._append_html(ansi_to_html(line) or "&nbsp;")
        self.live_lbl.setText("")

    def _live_line(self, text):
        self.live_lbl.setText(strip_ansi(text)[-300:])

    def _term_sys(self, text, err=False, prefix="", cmd=False):
        t = (prefix + text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        col = "#ff5c5c" if err else ("#7aa2ff" if cmd else "#9fb1d0")
        self._append_html(f"<span style='color:{col};font-weight:{700 if cmd else 400}'>{t}</span>")

    def closeEvent(self, e):
        try:
            self.stop_cmd()
            if self.conn:
                self.conn.close()
        except Exception:
            pass
        super().closeEvent(e)


def main():
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AirSense.Remote")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    pm = QPixmap(64, 64)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#2b6cff"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(4, 4, 56, 56)
    p.setPen(QColor("white"))
    f = QFont()
    f.setPointSize(26)
    f.setBold(True)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "R")
    p.end()
    app.setWindowIcon(QIcon(pm))
    w = Main()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
