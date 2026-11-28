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
APP_VERSION = "1.7.0"

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
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QUrl, QSize, QRect, QPoint  # noqa: E402
from PyQt6.QtWidgets import QLayout, QScrollArea  # noqa: E402
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
    "lan": "", "mdns": "airsense.local", "tailscale": "", "magicdns": "",
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
ANSI_COLORS = {30: "#5b6475", 31: "#ff5c5c", 32: "#2ecc71", 33: "#ffc04d", 34: "#5b8cff", 35: "#c678dd",
               36: "#4dd0e1", 37: "#e6ebf5", 90: "#8b96ab", 91: "#ff7b7b", 92: "#57e389", 93: "#ffc04d",
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
            st.append("color:#8b96ab")
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


def find_boards(progress=None):
    """Boards on this PC's networks: AirSense web :8765 (installed) or SSH :22 named airsense / luckfox / raspberry."""
    hosts = [str(h) for n in pc_networks() for h in n.hosts()]
    out = []

    def probe(ip):
        web = tcp_ok(ip, 8765, 0.6)
        ssh = tcp_ok(ip, 22, 0.6)
        if not (web or ssh):
            return None
        name = ""
        try:
            name = socket.gethostbyaddr(ip)[0]
        except Exception:
            pass
        is_as = False
        if web:
            try:
                urllib.request.urlopen(f"http://{ip}:8765/api/status", timeout=2)
                is_as = True
            except urllib.error.HTTPError as e:
                is_as = e.code in (401, 403)
            except Exception:
                pass
        hint = re.search(r"airsense|luckfox|raspberry|pico|rpi", name, re.I)
        if is_as or (ssh and hint):
            return {"ip": ip, "name": name, "airsense": is_as, "ssh": ssh}
        return None
    with ThreadPoolExecutor(max_workers=64) as ex:
        for r in ex.map(probe, hosts):
            if r:
                out.append(r)
    return sorted(out, key=lambda r: (not r["airsense"], r["ip"]))


GET_SH = "wget -qO get.sh https://raw.githubusercontent.com/nikkpap/AirSense/main/get.sh && sudo bash get.sh"


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
    learned = pyqtSignal(str, str, str)  # board LAN IP, Tailscale IP, Tailscale MagicDNS name
    open_file = pyqtSignal(str)


# ═════════════════════════ UI pieces ═════════════════════════
QSS = """
QWidget { background: transparent; }
* { font-family: 'Segoe UI', 'Noto Sans', sans-serif; font-size: 10.5pt; color: #e6ebf5; }
QStatusBar { background: #11151c; color: #8b96ab; }
QCheckBox::indicator { background: #11151c; border: 1px solid #2b4a8a; border-radius: 4px; }
QCheckBox::indicator:checked { background: #2b6cff; border-color: #2b6cff; image: none; }
QScrollBar:vertical { background: #11151c; width: 10px; margin: 0; border: none; }
QScrollBar::handle:vertical { background: #2f3747; border-radius: 5px; min-height: 30px; }
QScrollBar:horizontal { background: #11151c; height: 10px; margin: 0; border: none; }
QScrollBar::handle:horizontal { background: #2f3747; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QToolTip { background: #171c26; color: #e6ebf5; border: 1px solid #2f3747; }
QSplitter::handle { background: transparent; }
QMainWindow, QWidget#root { background: #11151c; }
QDialog, QMessageBox, QInputDialog { background: #11151c; }
QGroupBox { border: 1px solid #262d3b; border-radius: 12px; margin-top: 14px; padding: 10px 8px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; color: #c8d0e0; font-weight: 700; }
QCheckBox::indicator { width: 18px; height: 18px; }
QFrame#card { background: #171c26; border: 1px solid #262d3b; border-radius: 14px; }
QLabel#h1 { font-size: 17pt; font-weight: 700; }
QLabel#h2 { font-size: 11pt; font-weight: 700; color: #c8d0e0; }
QLabel#muted { color: #8b96ab; }
QPushButton { background: #1e2533; border: 1px solid #2f3747; border-radius: 9px; padding: 7px 12px; }
QPushButton:hover { background: #273042; border-color: #2b4a8a; }
QPushButton:pressed { background: #2b6cff; }
QPushButton:disabled { color: #6b7588; background: #1b2130; }
QPushButton#pri { background: #2b6cff; border-color: #2b6cff; font-weight: 700; color: #ffffff; }
QPushButton#pri:hover { background: #3f7bff; }
QPushButton#danger { border-color: #7a2c31; }
QPushButton#burger { font-size: 17pt; padding: 0; border-radius: 10px; }
QPushButton#burger[todo="true"] { border: 2px solid #2b6cff; color: #5aa9ff; }
QPushButton#burger:checked { background: #2b6cff; border-color: #2b6cff; color: #fff; }
QPushButton#danger:hover { background: #3a1d22; }
QLineEdit, QComboBox, QSpinBox { background: #11151c; border: 1px solid #2f3747; border-radius: 8px; padding: 6px 8px; }
QLineEdit:focus, QComboBox:focus { border-color: #2b6cff; }
QComboBox QAbstractItemView { background: #171c26; selection-background-color: #2b6cff; }
QTextEdit#term { background: #0a0e14; color: #d7dde8; border: 1px solid #262d3b; border-radius: 10px; padding: 6px;
                 font-family: 'Cascadia Mono', 'Consolas', 'DejaVu Sans Mono', monospace; font-size: 10pt; }
QTreeWidget { background: #11151c; border: 1px solid #262d3b; border-radius: 10px; }
QTreeWidget::item { padding: 3px; }
QHeaderView::section { background: #171c26; border: none; padding: 5px; color: #c8d0e0; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: #171c26; padding: 7px 14px; border-top-left-radius: 9px; border-top-right-radius: 9px; margin-right: 3px; }
QTabBar::tab:selected { background: #2b6cff; }
QGroupBox { border: 1px solid #262d3b; border-radius: 10px; margin-top: 12px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #c8d0e0; font-weight: 700; }
QScrollArea { border: none; background: transparent; }
QCheckBox::indicator { width: 18px; height: 18px; }
"""


class Led(QWidget):
    """● colored dot + label + tooltip."""
    COL = {"ok": "#2ecc71", "bad": "#ff5c5c", "warn": "#ffc04d", "off": "#2f3747"}

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
        glow = f"border: 2px solid {c}55;" if state != "off" else "border: 2px solid #262d3b;"
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


class FlowLayout(QLayout):
    """Buttons that wrap to the next line when the window is narrow (responsive)."""

    def __init__(self, parent=None, spacing=6, stretch=False):
        super().__init__(parent)
        self._items = []
        self._sp = spacing
        self._stretch = stretch
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._do(QRect(0, 0, w, 0), True)

    def setGeometry(self, r):
        super().setGeometry(r)
        self._do(r, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        sz = QSize()
        for it in self._items:
            sz = sz.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return sz + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do(self, r, test):
        m = self.contentsMargins()
        x0, y, right = r.x() + m.left(), r.y() + m.top(), r.right() - m.right()
        rows, row, x, rh = [], [], x0, 0
        for it in self._items:
            if it.widget() is not None and not it.widget().isVisible() and not test:
                continue
            hs = it.sizeHint()
            if row and x + hs.width() > right + 1:
                rows.append((row, rh))
                row, x, rh = [], x0, 0
            row.append((it, hs))
            x += hs.width() + self._sp
            rh = max(rh, hs.height())
        if row:
            rows.append((row, rh))
        for items, h in rows:
            if not test:
                # stretch the buttons of the row to fill the width (tidy grid)
                used = sum(hs.width() for _, hs in items) + self._sp * (len(items) - 1)
                extra = max(0, (right - x0 + 1) - used) // max(1, len(items)) if self._stretch and len(rows) > 1 else 0
                x = x0
                for it, hs in items:
                    w = hs.width() + extra
                    it.setGeometry(QRect(QPoint(x, y), QSize(w, h)))
                    x += w + self._sp
            y += h + self._sp
        return y - self._sp - r.y() + m.bottom() if rows else 0


class GridBox(QWidget):
    """Buttons in a grid whose number of columns follows the width (responsive, no overlap)."""

    def __init__(self, min_w=150, spacing=6):
        super().__init__()
        self.min_w, self.items, self.cols = min_w, [], 0
        self.g = QGridLayout(self)
        self.g.setContentsMargins(0, 0, 0, 0)
        self.g.setSpacing(spacing)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def addWidget(self, w):
        w.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        w.setMinimumWidth(0)
        self.items.append(w)
        self._lay(max(1, self.cols or 6), force=True)

    def _lay(self, cols, force=False):
        if cols == self.cols and not force:
            return
        self.cols = cols
        for w in self.items:
            self.g.removeWidget(w)
        for i, w in enumerate(self.items):
            self.g.addWidget(w, i // cols, i % cols)
        for c in range(12):
            self.g.setColumnStretch(c, 1 if c < cols else 0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cols = max(1, min(len(self.items) or 1, (e.size().width() + 6) // (self.min_w + 6)))
        if cols != self.cols:
            QTimer.singleShot(0, lambda c=cols: (self._lay(c), self.updateGeometry()))


class Drawer(QWidget):
    """☰ side menu that slides over the window (Easy setup)."""

    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.scrim = QWidget(host)
        self.scrim.setStyleSheet("background: rgba(0,0,0,110)")
        self.scrim.mousePressEvent = lambda e: self.close_drawer()
        self.scrim.hide()
        self.setObjectName("drawer")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("QWidget#drawer{background:#141821;border-right:1px solid #2f3747}")
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 8, 10)
        hd = QHBoxLayout()
        t = QLabel("🚀  Easy setup")
        t.setObjectName("h2")
        hd.addWidget(t)
        hd.addStretch()
        hint = QLabel("☰ / Esc = hide")
        hint.setObjectName("muted")
        hd.addWidget(hint)
        v.addLayout(hd)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea{background:transparent}")
        self.body = QWidget()
        self.body.setObjectName("dbody")
        self.body.setStyleSheet("QWidget#dbody{background:transparent}")
        self.bl = QVBoxLayout(self.body)
        self.bl.setContentsMargins(0, 0, 6, 0)
        self.scroll.setWidget(self.body)
        v.addWidget(self.scroll, 1)
        self.hide()

    def place(self):
        h = self.host
        y = 0
        if getattr(self, "below", None) is not None:          # start under the top bar → the ☰ button stays visible
            y = self.below.geometry().bottom() + 6
        w = min(470, max(320, int(h.width() * 0.92)))
        self.setGeometry(0, y, min(w, h.width()), h.height() - y)
        self.scrim.setGeometry(0, y, h.width(), h.height() - y)

    def open_drawer(self):
        if getattr(self, "button", None) is not None:
            self.button.setChecked(True)
        self.place()
        QTimer.singleShot(30, lambda: hasattr(self.host.window(), "_update_ez") and self.host.window()._update_ez())
        self.scrim.show()
        self.scrim.raise_()
        self.show()
        self.raise_()

    def close_drawer(self):
        self.hide()
        self.scrim.hide()
        if getattr(self, "button", None) is not None:
            self.button.setChecked(False)

    def toggle(self):
        self.close_drawer() if self.isVisible() else self.open_drawer()


def tcol(hexcol):
    """Colour for tree items — replaced by AirSense's theme-aware version when it runs inside AirSense."""
    return QColor(hexcol)


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
        self.magic = QLineEdit(cfg.get("magicdns", ""))
        self.magic.setPlaceholderText("airsense.tailXXXX.ts.net (learned by itself)")
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
        lan_row = QHBoxLayout()
        lan_row.addWidget(self.lan, 1)
        self.btn_findb = QPushButton("🔍 Find board")
        self.btn_findb.setToolTip("Look for the board on this PC's network")
        self.btn_findb.clicked.connect(self.find_board)
        lan_row.addWidget(self.btn_findb)
        f.addRow("🏠 Local IP (LAN)", lan_row)
        f.addRow("🔤 Name (mDNS)", self.mdns)
        f.addRow("🌍 Tailscale IP", self.ts)
        f.addRow("🌍 MagicDNS", self.magic)
        f.addRow("👤 User", self.user)
        f.addRow("🔑 Password", self.pw)
        f.addRow("SSH port", self.port)
        f.addRow("Web port", self.web)
        f.addRow("📟 PIN", self.pin)
        lay.addLayout(f)
        lay.addWidget(self.save_pw)
        lay.addWidget(self.auto)
        # 📱 QR for the phone — follows the fields above as you type
        qg = QGroupBox("📱 QR for the phone (AirSense app → Add server → scan)")
        qv = QVBoxLayout(qg)
        qr_row = QHBoxLayout()
        self.qr_lan = QrView("🏠 Local")
        self.qr_ts = QrView("🌍 Tailscale")
        qr_row.addWidget(self.qr_lan)
        qr_row.addWidget(self.qr_ts)
        qv.addLayout(qr_row)
        n = QLabel("🏠 = same WiFi as the board · 🌍 = from anywhere (4G, other WiFi) with Tailscale ON on the phone.")
        n.setObjectName("muted")
        n.setWordWrap(True)
        qv.addWidget(n)
        lay.addWidget(qg)
        for w_ in (self.lan, self.ts):
            w_.textChanged.connect(self._qr)
        self.web.valueChanged.connect(self._qr)
        self._qr()
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.ok)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _qr(self, *_):
        wp = self.web.value()
        lan, ts = self.lan.text().strip(), self.ts.text().strip()
        self.qr_lan.show_url(f"http://{lan}:{wp}" if lan else "")
        self.qr_ts.show_url(f"http://{ts}:{wp}" if ts else "")

    def find_board(self):
        self.btn_findb.setEnabled(False)
        self.btn_findb.setText("searching…")
        QApplication.processEvents()
        res = {}
        t = threading.Thread(target=lambda: res.update(r=find_boards()), daemon=True)
        t.start()
        while t.is_alive():
            QApplication.processEvents()
            time.sleep(0.05)
        boards = res.get("r") or []
        self.btn_findb.setEnabled(True)
        self.btn_findb.setText("🔍 Find board")
        if not boards:
            QMessageBox.information(self, APP_NAME, "No board found on this network.\n\n• Is the board on power and on the router (cable)?\n"
                                    "• Wait 1–2 minutes after power-on and try again.\n• Or type its IP (router page / Fing app).")
            return
        items = [f"{b['ip']}  ·  {b['name'] or '?'}  ·  {'AirSense ✔' if b['airsense'] else 'SSH only (AirSense not installed yet)'}" for b in boards]
        it, ok = QInputDialog.getItem(self, "🔍 Boards found", "Choose your board:", items, 0, False)
        if ok:
            self.lan.setText(boards[items.index(it)]["ip"])

    def ok(self):
        c = self.cfg
        c.update(lan=self.lan.text().strip(), mdns=self.mdns.text().strip(), tailscale=self.ts.text().strip(),
                 magicdns=self.magic.text().strip().rstrip(".").replace("http://", "").split(":")[0].split("/")[0],
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
    ("Info", "📄 Phone guide", "", "guide", "Phone setup guide PDF (Greek + English, with QR codes) — print it or send it"),
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
    ("System", "⬇ Install on board", GET_SH, "install", "Install / repair AirSense on the board (new board: first time) — answer the questions below"),
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
        scr = QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
        self.resize(min(1360, int(scr.width() * 0.92)) if scr else 1360, min(860, int(scr.height() * 0.9)) if scr else 860)
        self.setMinimumSize(760, 520)
        self._build()
        self.bus.term.connect(self._term_lines)
        self.bus.live.connect(self._live_line)
        self.bus.cmd_done.connect(self._cmd_done)
        self.bus.connected.connect(self._on_connected)
        self.bus.leds.connect(self._on_leds)
        self.bus.status.connect(self._on_status)
        self.bus.sensors.connect(self._on_sensors)
        self.bus.find_done.connect(self._find_done)
        self.bus.learned.connect(self._on_learned)
        self.bus.open_file.connect(lambda fn: QDesktopServices.openUrl(QUrl.fromLocalFile(fn)))
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
        if not os.path.exists(CFG_PATH):
            QTimer.singleShot(500, self.first_run)          # first time: guided setup
        elif self.cfg.get("auto_connect"):
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
        top, tl0 = card()
        self.top_h = QHBoxLayout()
        self.top_h.setSpacing(14)
        tl = QVBoxLayout()
        tl.setSpacing(8)
        self.top_h.addLayout(tl, 1)
        tl0.addLayout(self.top_h)
        row = FlowLayout(spacing=8)
        self.btn_menu = QPushButton("☰")
        self.btn_menu.setObjectName("burger")
        self.btn_menu.setCheckable(True)
        self.btn_menu.setFixedSize(44, 40)
        self.btn_menu.setToolTip("Show / hide 🚀 Easy setup (Ctrl+M)")
        self.btn_menu.clicked.connect(lambda: self.drawer.toggle())
        row.addWidget(self.btn_menu)
        t = QLabel("🌬 AirSense Remote")
        t.setObjectName("h1")
        row.addWidget(t)
        self.route = QComboBox()
        self.route.addItems(["Auto", "🏠 LAN", "🔤 airsense.local", "🌍 Tailscale", "🌍 MagicDNS"])
        self.route.setCurrentIndex({"auto": 0, "lan": 1, "mdns": 2, "tailscale": 3, "magicdns": 4}.get(self.cfg.get("route"), 0))
        self.route.currentIndexChanged.connect(self._route_changed)
        self.route.setToolTip("Route: how to reach the board")
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
        tl.addLayout(row)
        self.conn_lbl = QLabel("not connected")
        self.conn_lbl.setObjectName("muted")
        leds = FlowLayout(spacing=14)
        self.led = {k: Led(n) for k, n in (("host", "Board"), ("ssh", "SSH"), ("web", "Web :8765"),
                                            ("sensor", "Sensors"), ("ts", "Tailscale"), ("health", "Health"))}
        for k in ("host", "ssh", "web", "sensor", "ts", "health"):
            leds.addWidget(self.led[k])
        self.led_time = QLabel("")
        self.led_time.setObjectName("muted")
        leds.addWidget(self.conn_lbl)
        leds.addWidget(self.led_time)
        tl.addLayout(leds)
        v.addWidget(top)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        self.split = split
        v.addWidget(split, 1)

        # left: sensors + status + QR
        left = QTabWidget()
        left.setMinimumWidth(330)
        self.left_tabs = left
        self.drawer = Drawer(root)
        self.drawer.below = top
        self.drawer.button = self.btn_menu
        ec, ecl = card()
        self.ez_title = QLabel("🚀 <b>Easy setup</b>")
        self.ez_title.setStyleSheet("font-size:13pt")
        ecl.addWidget(self.ez_title)
        self.ez_bar = QFrame()
        self.ez_bar.setFixedHeight(8)
        self.ez_bar_fill = QFrame(self.ez_bar)
        self.ez_bar.setStyleSheet("background:#262d3b;border-radius:4px")
        self.ez_bar_fill.setStyleSheet("background:#2b6cff;border-radius:4px")
        ecl.addWidget(self.ez_bar)
        self.ez_next = QPushButton("")
        self.ez_next.setObjectName("pri")
        self.ez_next.setMinimumHeight(46)
        self.ez_next.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)   # long text never widens the menu
        self.ez_next.setStyleSheet("font-size:11.5pt;text-align:left;padding-left:14px")
        self.ez_next.clicked.connect(lambda: self._ez_next_fn and (self.drawer.close_drawer(), self._ez_next_fn()))
        self._ez_next_fn = None
        ecl.addWidget(self.ez_next)
        self.ez_rows = {}
        self.EZ = (
            ("board", "1", "Board on the network", "Board on power (+ cable for Luckfox). The program finds it and connects.",
             "🔍 Find board / 🔌 Connect", self._ez_board),
            ("install", "2", "AirSense on the board", "New board? One click installs everything (5–20 min). Answer with Enter.",
             "⬇ Install on board", lambda: self.preset(GET_SH, "install", "⬇ Install on board")),
            ("sensor", "3", "Sensor found", "Sensor on the WiFi (2.4 GHz) → the board finds it by itself.",
             "🔎 Find sensor", lambda: self.find_sensor(quiet=False)),
            ("phone", "4", "Phone", "AirSense app → «Find automatically». Or send the ready PDF guide with the QR codes.",
             "📄 Phone guide (PDF)", self.phone_guide),
            ("ts", "5", "From anywhere (Tailscale)", "4G / other WiFi: Tailscale on the board + phone, same account.",
             "🌍 Tailscale login", lambda: self.preset("airsense tailscale", "run", "Tailscale")),
        )
        for k, num, title, desc, bt, fn in self.EZ:
            sf = QFrame()
            sf.setObjectName("step")
            sf.setStyleSheet("QFrame#step{background:#11151c;border:1px solid #262d3b;border-radius:11px}")
            row = QHBoxLayout(sf)
            row.setContentsMargins(10, 8, 10, 8)
            row.setSpacing(10)
            badge = QLabel(num)
            badge.setFixedSize(30, 30)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col = QVBoxLayout()
            col.setSpacing(6)
            lb = QLabel(f"<b>{title}</b><br><span style='color:#8b96ab'>{desc}</span>")
            lb.setWordWrap(True)
            b = QPushButton(bt)
            b.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            b.clicked.connect(lambda _=False, f=fn: (self.drawer.close_drawer(), f()))
            col.addWidget(lb)
            col.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
            row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
            row.addLayout(col, 1)
            ecl.addWidget(sf)
            self.ez_rows[k] = (badge, b)
        tip = QLabel("<span style='color:#8b96ab'>Moved / new WiFi? Only step 3 again — the rest finds the new addresses by itself.</span>")
        tip.setWordWrap(True)
        ecl.addWidget(tip)
        self.drawer.bl.addWidget(ec)
        self.drawer.bl.addStretch()
        # — Overview tab
        ov = QWidget()
        ol = QVBoxLayout(ov)
        ol.setContentsMargins(0, 6, 0, 0)
        sc = QFrame()                                   # 🌡 live sensors → top-right corner of the window
        sc.setObjectName("sensp")
        sc.setStyleSheet("QFrame#sensp{background:#11151c;border:1px solid #262d3b;border-radius:12px}")
        sc.setMinimumWidth(340)
        sc.setMaximumWidth(520)
        sc.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        sl = QVBoxLayout(sc)
        sl.setContentsMargins(12, 8, 12, 8)
        sl.setSpacing(4)
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
        self.btn_find = QPushButton("🔎 Find")
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
        self.top_h.addWidget(sc, 0, Qt.AlignmentFlag.AlignTop)
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
        left.tabBar().hide()                            # one page: Overview (QR → ⚙ Settings)
        split.addWidget(left)

        # right: commands + terminal
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        cc, ccl = card()
        chd = QHBoxLayout()
        h = QLabel("⚡ Commands")
        h.setObjectName("h2")
        chd.addWidget(h)
        chd.addStretch()
        self.btn_more = QPushButton("▸ All commands")
        self.btn_more.setToolTip("Show / hide every command (advanced)")
        self.btn_more.clicked.connect(self._toggle_more)
        chd.addWidget(self.btn_more)
        ccl.addLayout(chd)
        quick = GridBox(132)
        QUICK = (("🩺 Status", "airsense status", "status"), ("⬇ Update", "airsense update", "run"),
                 ("🔎 Find sensor", "", "find"), ("📄 Phone guide", "", "guide"),
                 ("↻ Restart", "airsense restart", "run"), ("📜 Logs", "airsense logs", "run"))
        self.cmd_buttons = []
        for label, cmd, kind in QUICK:
            b = QPushButton(label)
            b.setMinimumHeight(38)
            b.clicked.connect(lambda _=False, c=cmd, k=kind, lb=label: self.preset(c, k, lb))
            quick.addWidget(b)
            self.cmd_buttons.append(b)
        ccl.addWidget(quick)
        self.more_box = QWidget()
        grid = QVBoxLayout(self.more_box)
        grid.setContentsMargins(0, 6, 0, 0)
        grid.setSpacing(4)
        groups = []
        for g, *_ in COMMANDS:
            if g not in groups:
                groups.append(g)
        for gi, g in enumerate(groups):
            gl = QLabel(g)
            gl.setObjectName("muted")
            grid.addWidget(gl)
            gf = GridBox(132)
            grid.addWidget(gf)
            for ci, (gg, label, cmd, kind, tip) in enumerate([c for c in COMMANDS if c[0] == g]):
                b = QPushButton(label)
                b.setToolTip(f"{tip}\n$ {cmd}")
                if kind == "confirm":
                    b.setObjectName("danger")
                b.clicked.connect(lambda _=False, c=cmd, k=kind, lb=label: self.preset(c, k, lb))
                gf.addWidget(b)
                self.cmd_buttons.append(b)
        ccl.addWidget(self.more_box)
        self.more_box.setVisible(bool(self.cfg.get("show_all_commands", False)))
        self.btn_more.setText("▾ Fewer commands" if self.more_box.isVisible() else "▸ All commands")
        self.cmd_card = cc
        self.cmd_scroll = QScrollArea()
        self.cmd_scroll.setWidgetResizable(True)
        self.cmd_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cmd_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cmd_scroll.setStyleSheet("QScrollArea{background:transparent}")
        self.cmd_scroll.setWidget(cc)
        self.rsplit = QSplitter(Qt.Orientation.Vertical)
        self.rsplit.setChildrenCollapsible(False)
        self.rsplit.addWidget(self.cmd_scroll)
        rl.addWidget(self.rsplit, 1)

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
        self.live_lbl.setStyleSheet("color:#ffc04d")
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
        tc.setMinimumHeight(220)
        self.rsplit.addWidget(tc)
        self.rsplit.setStretchFactor(1, 1)
        QTimer.singleShot(0, self._fit_cmds)
        split.addWidget(right)
        split.setSizes([520, 840])

        foot = QLabel(f"{APP_NAME} v{APP_VERSION} · Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM")
        foot.setObjectName("muted")
        v.addWidget(foot)
        for key, fn in (("Ctrl+L", lambda: self.term.clear()), ("Ctrl+M", lambda: self.drawer.toggle()),
                        ("Esc", lambda: self.drawer.close_drawer()),
                        ("F5", lambda: (self.refresh_leds(), self.refresh_status(False)))):
            sc = QShortcut(QKeySequence(key), self, activated=fn)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)   # also right when it lives in a tab of AirSense
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
        self.cfg["route"] = ("auto", "lan", "mdns", "tailscale", "magicdns")[i]
        save_cfg(self.cfg)
        self.refresh_leds()

    def _candidates(self):
        r = self.cfg.get("route", "auto")
        if r == "auto":
            hs = [self.cfg.get("lan"), self.cfg.get("mdns"), self.cfg.get("tailscale"), self.cfg.get("magicdns")]
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
        pass                                            # the QR codes live in ⚙ Settings (built when it opens)

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
            via = ("Tailscale" if host == self.cfg.get("tailscale") else "MagicDNS" if host == self.cfg.get("magicdns")
                   else "LAN" if host == self.cfg.get("lan") else host)
            self.conn_lbl.setText(f"✔ {self.cfg['user']}@{host} ({via})")
            self.led["ssh"].set("ok", f"connected to {host}")
            self._term_sys(f"✔ Connected to {self.cfg['user']}@{host} via {via}")
            self._learn_addresses()
            self.refresh_status(quiet=True)
            self.refresh_leds()
        else:
            self._set_connected_ui(False)
            self.conn_lbl.setText("✖ not connected")
            self.led["ssh"].set("bad", msg)
            self._term_sys("✖ Could not connect — " + msg, err=True)
            if "password" in msg.lower() or "authentication" in msg.lower():
                QMessageBox.warning(self, APP_NAME, "Wrong user or password.\n\n⚙ Settings → User / Password.")

    def _learn_addresses(self):
        """Ask the board for its current LAN IP and Tailscale IP → keep ⚙ Settings and the QR codes up to date by themselves."""
        conn = self.conn

        def job():
            try:
                _, out = conn.run("hostname -I 2>/dev/null; echo '##'; tailscale ip -4 2>/dev/null; echo '##'; "
                                  "tailscale status --self=true --peers=false --json 2>/dev/null | grep -m1 DNSName", timeout=20)
            except Exception:
                return
            lan_part, _, rest = strip_ansi(out).partition("##")
            ts_part, _, dns_part = rest.partition("##")
            m = re.search(r'"DNSName"\s*:\s*"([^"]+?)\.?"', dns_part)
            magic = m.group(1) if m and ".ts.net" in m.group(1) else ""
            ips = re.findall(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", lan_part)
            lan = next((i for i in ips if not i.startswith(("100.", "127.", "172.32."))), "")
            ts = next(iter(re.findall(r"\b(100\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", ts_part)), "")
            self.bus.learned.emit(lan, ts, magic)
        threading.Thread(target=job, daemon=True).start()

    def _on_learned(self, lan, ts, magic=""):
        changed = []
        if magic and magic != self.cfg.get("magicdns"):
            changed.append(f"MagicDNS → {magic}")
            self.cfg["magicdns"] = magic
        if lan and lan != self.cfg.get("lan"):
            changed.append(f"local IP {self.cfg.get('lan') or '—'} → {lan}")
            self.cfg["lan"] = lan
        if ts and ts != self.cfg.get("tailscale"):
            changed.append(f"Tailscale {self.cfg.get('tailscale') or '—'} → {ts}")
            self.cfg["tailscale"] = ts
        if changed:
            save_cfg(self.cfg)
            self._update_qr()
            self._term_sys("ℹ Settings updated by themselves: " + " · ".join(changed))
            # new network → fresh phone guide PDF in Downloads, ready to send
            QTimer.singleShot(2000, lambda: self.phone_guide(open_it=False))

    def _set_connected_ui(self, on):
        self.btn_conn.setText("⏏ Disconnect" if on else "🔌 Connect")
        if hasattr(self, "ez_rows"):
            QTimer.singleShot(0, self._update_ez)
        QTimer.singleShot(60, self._fit_cmds)
        for b in self.cmd_buttons:
            b.setEnabled(on)
        if hasattr(self, "btn_find"):
            self.btn_find.setEnabled(on and not getattr(self, "_finding", False))

    def first_run(self):
        QMessageBox.information(self, f"👋 {APP_NAME}",
            "<b>Welcome!</b> Three steps:<br><br>"
            "<b>1.</b> The next window looks for your board by itself (🔍 Find board) — pick it from the list.<br>"
            "<b>2.</b> Type the board's <b>user</b> and <b>password</b><br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;Luckfox: <code>pico</code> / <code>luckfox</code> · Raspberry Pi: the ones you set in Raspberry Pi Imager.<br>"
            "<b>3.</b> Save → it connects. New board? Press <b>⬇ Install on board</b> (System row).<br><br>"
            "Everything else (Tailscale address, new IPs) it learns from the board by itself.")
        d = SettingsDialog(self, self.cfg)
        QTimer.singleShot(300, d.find_board)
        if d.exec():
            self._update_qr()
            self.connect_ssh()
        else:
            save_cfg(self.cfg)

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
            tsh = cfg.get("tailscale") or cfg.get("magicdns")
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
        self._update_ez()
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
            nm = QLabel(f"<b>{d.get('name') or d.get('id')}</b><br><span style='color:#8b96ab'>{d.get('ip')} · {d.get('type') or ''}</span>")
            nm.setMinimumWidth(60)
            nm.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            h.addWidget(nm, 1)
            t, hu = d.get("t"), d.get("h")
            val = QLabel(f"<span style='color:#ff9f43;font-size:17pt;font-weight:700'>{'—' if t is None else f'{t:.1f}°C'}</span>"
                         f"&nbsp;&nbsp;<span style='color:#3fa7ff;font-size:17pt;font-weight:700'>{'—' if hu is None else f'{hu:.1f}%'}</span>")
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
        icon_col = {"✔": "#2ecc71", "⚠": "#ffc04d", "✖": "#ff5c5c"}
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
                sec_item.setForeground(1, tcol("#c8d0e0"))
                self.tree.addTopLevelItem(sec_item)
                sec_item.setExpanded(True)
                continue
            if re.match(r"^\s*[✔✖]\s+(All good|\d+ problem)", line):
                continue
            m = re.match(r"^\s*([✔⚠✖])\s+(\S.{0,14}?)\s{2,}(.*)$", line) or re.match(r"^\s*([✔⚠✖])\s+(\S+)\s+(.*)$", line)
            if m:
                ic, key, val = m.groups()
                it = QTreeWidgetItem([ic, key.strip(), val.strip()])
                it.setForeground(0, tcol(icon_col[ic]))
                it.setToolTip(2, val.strip())
                bad += ic == "✖"
                warn += ic == "⚠"
            else:
                txt = line.strip()
                if txt.startswith("🌬"):
                    self.setWindowTitle(f"🌬 {APP_NAME} v{APP_VERSION} — {txt[1:].strip()}")
                it = QTreeWidgetItem(["", "", txt])
                it.setForeground(2, tcol("#c8d0e0"))
            if sec_item:
                sec_item.addChild(it)
            else:
                self.tree.addTopLevelItem(it)
        if bad:
            self.st_sum.setText(f"<span style='color:#ff5c5c'>✖ {bad} problem(s)</span>")
            self.led["health"].set("bad", f"{bad} problem(s) in the status")
        elif warn:
            self.st_sum.setText(f"<span style='color:#ffc04d'>⚠ {warn} warning(s)</span>")
            self.led["health"].set("warn", f"{warn} warning(s)")
        elif out.strip():
            self.st_sum.setText("<span style='color:#2ecc71'>✔ All good</span>")
            self.led["health"].set("ok", "airsense status: all good")

    # ── 🚀 easy setup ──
    def _toggle_more(self):
        on = not self.more_box.isVisible()
        self.more_box.setVisible(on)
        self.btn_more.setText("▾ Fewer commands" if on else "▸ All commands")
        self.cfg["show_all_commands"] = on
        save_cfg(self.cfg)
        QTimer.singleShot(0, self._fit_cmds)

    def _fit_cmds(self):
        """Commands card: as tall as its buttons (scrolls when the window is small); the terminal gets the rest."""
        if not hasattr(self, "rsplit"):
            return
        total = sum(self.rsplit.sizes()) or self.rsplit.height()
        w = self.cmd_scroll.viewport().width() or self.cmd_card.width()
        lay = self.cmd_card.layout()
        need = lay.heightForWidth(w) if lay.hasHeightForWidth() else self.cmd_card.sizeHint().height()
        need = max(need, self.cmd_card.minimumSizeHint().height()) + 30
        top = max(90, min(need, total - 220))
        self.rsplit.setSizes([top, max(220, total - top)])

    def _ez_board(self):
        if self.conn and self.conn.alive:
            return
        if not (self.cfg.get("lan") or self.cfg.get("tailscale")) or not self.cfg.get("_pw"):
            d = SettingsDialog(self, self.cfg)
            QTimer.singleShot(300, d.find_board)
            if not d.exec():
                return
            self._update_qr()
        self.connect_ssh()

    def _update_ez(self):
        L = {k: v.state for k, v in self.led.items()}
        conn = bool(self.conn and self.conn.alive)
        state = {"board": conn, "install": L["web"] == "ok", "sensor": L["sensor"] == "ok",
                 "phone": L["web"] == "ok", "ts": L["ts"] == "ok"}
        done, nxt = 0, None
        for k, num, title, _d, bt, fn in self.EZ:
            badge, b = self.ez_rows[k]
            ok = state[k]
            done += ok
            if ok:
                badge.setText("✓")
                badge.setStyleSheet("background:#2ecc71;color:#fff;border-radius:15px;font-weight:700")
            elif nxt is None:
                nxt = (num, title, bt, fn)
                badge.setText(num)
                badge.setStyleSheet("background:#2b6cff;color:#fff;border-radius:15px;font-weight:700")
            else:
                badge.setText(num)
                badge.setStyleSheet("background:#262d3b;color:#8b96ab;border-radius:15px;font-weight:700")
            b.setText(("✓ " + bt.split(" ", 1)[-1]) if ok else bt)
        w = self.ez_bar.width()
        self.ez_bar_fill.setGeometry(0, 0, int(w * done / len(self.EZ)), 8)
        if nxt:
            num, title, bt, fn = nxt
            self.ez_title.setText(f"🚀 <b>Easy setup</b> <span style='color:#8b96ab'>— step {num} of {len(self.EZ)}</span>")
            self.ez_next.setText(f"▶  Next: {title}")
            self._ez_next_fn = fn
            self.ez_next.setVisible(True)
        else:
            self.ez_title.setText("✅ <b>All ready</b> <span style='color:#8b96ab'>— board, AirSense, sensor, phone, from anywhere</span>")
            self.ez_next.setVisible(False)
            self._ez_next_fn = None
        self.btn_menu.setProperty("todo", bool(nxt))         # blue dot while a step is missing
        self.btn_menu.setToolTip(f"Show / hide 🚀 Easy setup — {done}/{len(self.EZ)} done (Ctrl+M)")
        self.btn_menu.style().unpolish(self.btn_menu)
        self.btn_menu.style().polish(self.btn_menu)
        if not getattr(self, "_ez_tab_chosen", False) and self.led_time.text():
            self._ez_tab_chosen = True                  # first check: open the ☰ Easy setup only while something is missing
            if nxt:
                self.drawer.open_drawer()

    # ── 📄 phone guide PDF (made by the board's server) ──
    def phone_guide(self, open_it=True):
        h = self.web_host()
        url = f"http://{h}:{self.cfg.get('web_port', 8765)}/setup.pdf"
        self._term_sys(f"📄 Phone guide ← {url}")

        def job():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": APP_NAME})
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = r.read()
                if not data.startswith(b"%PDF"):
                    raise RuntimeError("not a PDF (old AirSense on the board? → ⬇ Update)")
                d = os.path.join(os.path.expanduser("~"), "Downloads")
                os.makedirs(d, exist_ok=True)
                fn = os.path.join(d, "AirSense_Phone_Setup_GR_EN.pdf")
                with open(fn, "wb") as f:
                    f.write(data)
                self.bus.term.emit(f"\x1b[32m✔ Saved: {fn}\x1b[0m")
                if open_it:
                    self.bus.open_file.emit(fn)
            except urllib.error.HTTPError as e:
                self.bus.term.emit(f"\x1b[31m✖ HTTP {e.code} — old AirSense on the board? Press ⬇ Update first\x1b[0m")
            except Exception as e:
                self.bus.term.emit(f"\x1b[31m✖ {e}\x1b[0m")
        threading.Thread(target=job, daemon=True).start()

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
                    "<span style='color:#8b96ab'>Still nothing? The WiFi may keep its devices apart (client isolation / guest WiFi) "
                    "or put them on another network than the board's cable.</span>")
        self._append_html(f"<span style='color:#ffc04d'>{help_txt}</span>")
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
        if kind == "guide":
            self.phone_guide()
            return
        if kind == "install":
            if QMessageBox.question(self, "⬇ Install on board",
                    "Installs (or repairs / updates) AirSense on the board — 5–20 minutes.\n\n"
                    "• The board needs internet (cable to the router).\n"
                    "• Questions appear in yellow under the terminal: type the answer in the box and press Send\n"
                    "  (Enter alone = the suggested answer).\n"
                    "• At the end it asks to reboot → the connection drops; press Connect again in 1–2 minutes.\n\nStart?"
                    ) != QMessageBox.StandardButton.Yes:
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
        col = "#2ecc71" if rc == 0 else ("#8b96ab" if rc == -1 else "#ff5c5c")
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
        col = "#ff5c5c" if err else ("#7aa2ff" if cmd else "#c8d0e0")
        self._append_html(f"<span style='color:{col};font-weight:{700 if cmd else 400}'>{t}</span>")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "drawer") and self.drawer.isVisible():
            self.drawer.place()
        if hasattr(self, "ez_rows"):
            QTimer.singleShot(0, self._update_ez)

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
