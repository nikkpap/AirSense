# 🌬 AirSense

**[English](#-english) · [Ελληνικά](#-ελληνικά)**

**Developer:** Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM

---

# 🇬🇧 English

Monitoring, logging and alerts for **BleBox humiditySensor** sensors: charts, Open-Meteo weather,
inside–outside difference with ventilation advice, **PDF reports**, CSV/XML, email, and access from your phone
(on the local network or from anywhere with Tailscale). *(formerly ALU HygroLink)*

## 📌 How it works
```
 BleBox sensors ──WiFi──►  AirSense server  ──►  web page :8765  ──►  phone (Android app / browser)
                           (Windows PC, or                            local  or  from anywhere (Tailscale)
                            Raspberry Pi / Luckfox 24/7)
```
The **server** reads the sensors, keeps the history, makes PDF/CSV reports and sends emails.
It can be your PC (`AirSense_vX.pyw`) **or** a small board that stays on 24/7.

## ⬇ Download — [Releases](https://github.com/nikkpap/AirSense/releases/latest)
| File | For | How |
|---|---|---|
| `AirSense_vX.pyw` | Windows | Double-click — installs everything it needs by itself (Python 3.9–3.14, 64-bit) and opens the Wizard. |
| `AirSense-Pi_vX.zip` | **Raspberry Pi** Zero 2 W / 3 / 4 / 5 | One command (below) · [pi/ODIGIES_Raspberry_Pi.md](pi/ODIGIES_Raspberry_Pi.md) |
| `AirSense-Luckfox_vX.zip` | **Luckfox Pico** Pro / Max (Ubuntu) | One command (below) · [luckfox/ODIGIES_Luckfox.md](luckfox/ODIGIES_Luckfox.md) |
| `AirSense-Android_vX.apk` | Android 8+ | Signed APK — install it, then scan the server's QR code. |
| `AirSense_Remote_vX.pyw` | Windows | **Manage the board** (Pi / Luckfox) over SSH with a GUI — see below. |

## ✨ Features
- **Live dashboard** for every sensor: temperature, humidity, dew point, absolute humidity — inside / outside with the **difference** and **ventilation advice**.
- **Configurable labels** (Inside / Outside / Basement … whatever you like) — from the Settings.
- **History & charts** (SQLite): 6 hours / 24 hours / 7 days / 30 days.
- **Weather** from Open-Meteo (city or automatic from the IP).
- **Export:** PDF report with a clean design · CSV · XML.
- **Email** reports and alarms (thresholds), with the PDF attached.
- **Themes:** Auto / Dark / Light.
- **Web page + Android app** — PIN for the web page, admin password for the settings, QR to connect the phone.
- **Remote access** with Tailscale (no open router ports).

---

## 🚀 Quick start

### Windows
1. Download `AirSense_vX.pyw` → **double-click**.
2. The Wizard finds the sensors on your network by itself → **Finish**.
3. For the phone: Settings → QR → scan it with the Android app.

### Raspberry Pi or Luckfox (24/7 server) — ONE command
Log in to the board with **ssh** and type:
```bash
wget -qO get.sh https://raw.githubusercontent.com/nikkpap/AirSense/main/get.sh && sudo bash get.sh
```
It detects the board **by itself** (Raspberry Pi / Luckfox), downloads the right package and:

| Step | What happens |
|---|---|
| **1/6** | System check + **all questions at the start** (time zone from a list, name `airsense`, fixed MAC, Tailscale, WiFi) — then it runs by itself |
| **2/6** | **Clock**: time zone + NTP from [ntppool.org](https://www.ntppool.org/zone/europe) (Europe: `europe.pool.ntp.org`) — synced **before** apt · swap |
| **3/6** | Packages (python3, reportlab for PDF, fonts, avahi for `airsense.local`, qrencode) |
| **4/6** | AirSense + autostart on boot + automatic updates from GitHub (+ WiFi tool on the Pi) |
| **5/6** | Network name, fixed address, start the server |
| **6/6** | Tailscale (access from anywhere) + Tailscale SSH |
| End | Address + **QR code** for the phone → "Reboot now?" → **Y** |

Every task shows a moving progress bar with a timer: moving = working, not stuck.
After the reboot, on the **first ssh login**, it asks you to **change the factory password** (e.g. `luckfox`, `raspberry`) if it was not changed yet.
Run the same command any time to **reinstall / update** — your data is kept.

#### Raspberry Pi — prepare the SD card
Raspberry Pi Imager → **Raspberry Pi OS Lite (64-bit)** → *Edit settings*: hostname `airsense`, user + your own password,
your WiFi (country GR), *Services → Enable SSH* → write → card in the Pi → `ssh pi@airsense.local`.

#### Luckfox Pico — prepare the SD card
Ubuntu image from the [Luckfox wiki](https://wiki.luckfox.com/Luckfox-Pico-RV1106/Getting-Started/overview) → SocToolKit (SD card, FAT32) →
Ethernet cable to the router → `ssh pico@IP` (password `luckfox`). Details: [luckfox/ODIGIES_Luckfox.md](luckfox/ODIGIES_Luckfox.md).

### Android
Install the APK → "Add server" → scan the QR code (`airsense qr` on the board, or Settings on the PC).
**Updates (OTA):** the app checks GitHub Releases by itself (when it opens, at most every 12 hours) → «🆕 New version» → **Update**.
By hand: Settings → **Updates** → «🔄 Check for updates». The first time Android asks to allow *Install unknown apps* for AirSense.

---

## 🖥 AirSense Remote — manage the board from Windows (GUI)
`AirSense_Remote_vX.pyw` → double-click (installs PyQt6, paramiko, qrcode by itself) → **⚙ Settings**: local IP, Tailscale IP, user, password, PIN.
- **LEDs:** Board · SSH · Web :8765 · Sensors · Tailscale · Health — green / orange / red, checked every 15 s (hover = details).
- **Route:** Auto tries LAN → airsense.local → Tailscale and keeps the one that works (home or office, same program).
- **Board status** = `airsense status` as a tree with ✔ / ⚠ / ✖ · **live sensor values** · **QR** codes for the phone.
- **One-click commands:** Status, Logs, Live log, Clock, MAC, Restart, Stop, Update, Auto-update, Tailscale, Admin password,
  Scan, Add by IP, Set PIN, City, Time zone, Disk/RAM, CPU temp, Password, Reboot, Power off (dangerous ones ask first).
- **Terminal + your own command** (↑ ↓ history): colors, progress bars, the `[sudo]` password is answered by itself,
  questions (Y/n, passwords — tick *hidden*) are answered in the same box, **■ Stop** = Ctrl+C.
- Works with Tailscale SSH too (no password). The password is stored encrypted with your Windows account (DPAPI).

## 🧰 Commands on the board (ssh) — all of them
| Command | What it does |
|---|---|
| `airsense` / `airsense status` / `airsense doctor` / `airsense diag` | **full diagnosis** with ✔/⚠/✖: server, sensors, network, WiFi, clock/NTP, Tailscale, updates, password, RAM/swap/SD card, last messages |
| `airsense help` | the list of all commands |
| `airsense qr` | QR codes for the phone (local + Tailscale) |
| `airsense logs` | last messages (server + boot + Tailscale) |
| `airsense live` | live log (Ctrl+C to exit) |
| `airsense restart` | restart the server |
| `airsense stop` | stop the server (it starts again on the next reboot) |
| `airsense update` | check GitHub + update **now** |
| `airsense autoupdate` | automatic update state + last checks |
| `airsense autoupdate on` / `off` | automatic updates on/off (every 6 hours) |
| `airsense password` (or `passwd`) | change the user password (and root's, if it is the factory default) |
| `airsense clock` (or `time`) | time, time zone, NTP sync |
| `airsense clock Europe/Athens` | change the time zone |
| `airsense mac` | MAC address — for an IP reservation in the router |
| `airsense wifi` | (Raspberry Pi only) WiFi menu: scan, add, saved networks, priority |
| `airsense set-admin` | admin password (settings from the web page / phone) |
| `airsense set-pin 1234` | PIN for the web page (`airsense set-pin` with no number = no PIN) |
| `airsense scan` | find + add **BleBox sensors** on the network (only sensors; other network: `airsense scan 10.0.0.0/24`) |
| `airsense add 192.168.1.241` | add a sensor by IP |
| `airsense city Ptolemaida` | weather location |
| `airsense tailscale` | Tailscale connect / login (link + QR) |
| `airsense tailscale on` / `off` | Tailscale ON / OFF (OFF = local only) |
| `airsense uninstall` | remove (the data stays in `/var/lib/airsense`) |

System: `sudo reboot` · `sudo poweroff` (before unplugging) · `sudo airsense-update --force` (= `airsense update`) ·
`sudo airsense-wifi add "Name" "password"` (Pi) · logs: `/var/lib/airsense/boot.log`, `update.log`, `tailscale.log`.

### ✏ I changed `AirSense.pyw` — how does it get to the board?
`airsense update` installs only the **latest GitHub release**, and only if its version is **higher** than the board's.
1. Change `desktop/AirSense.pyw` **and** raise `APP_VERSION` (e.g. `"1.6.15"`) → push to `main`.
2. GitHub → **Actions** → **Build & Release** → **Run workflow** → ✔ release.
3. On the board: `airsense update` (or it updates by itself within 6 hours).

Quick test without a release: `scp AirSense.pyw pico@airsense.local:~/AirSense_v1.6.15.pyw` then `ssh pico@airsense.local "airsense restart"`
(it installs the highest `APP_VERSION` it finds in the home folder). While testing, `airsense autoupdate off` stops GitHub from replacing it.

## 🔀 Another network / subnet (e.g. from 192.168.1.x to 10.0.0.x)
**No new SD card, no reinstall.** Nothing is tied to 192.168.1.x:
- **Board IP:** taken automatically from the router (DHCP) on any network. With the fixed MAC the new router always gives it the same IP.
- **Address:** `http://airsense.local:8765` works on every network — no need to know the IP.
- **Tailscale:** connects by itself; the `100.x.x.x` address **stays the same** everywhere — nothing to change on the phone.
- **Sensors:** if their IP changes, AirSense finds them again by their ID. A **new** sensor: `airsense add NEW_IP`.
- **Only rule:** the board and the sensors must be on the **same** network (same router).
- `SENSORS=` in `airsense-settings.txt` was applied once at the start — it does not lock anything.
- Find the board on the new network: `airsense.local`, the Tailscale app, or `ssh USER@airsense` over Tailscale from anywhere.
- Raspberry Pi on a new WiFi: `airsense wifi` (before you move it), or `airsense-wifi.txt` on the SD card.

### ❓ `http://airsense.local:8765` does not open (new place, e.g. the office)
Plug in Ethernet + power and wait **1–2 minutes** (IP from DHCP, clock sync, server start). Check:
- Your PC / phone is on the **same network** as the board.
- **Windows 10/11:** `.local` normally works. **Android:** not always (depends on the version / browser) → use the IP or Tailscale on the phone.
- **Company networks** often block `.local` (WiFi client isolation, WiFi and cables on separate VLANs) — the board works, only the name does not answer.
- The **BleBox sensors must be on the same network** too — if they stayed at home, the page opens but the sensors show Offline.

Other ways in, from the surest:
1. **Tailscale:** `http://100.x.x.x:8765` — same as at home; connects by itself as soon as it has internet, even behind a company firewall. No need to know the office IP.
2. **Find the IP:** the router's page, or Fing / Angry IP Scanner → `http://IP:8765`.
3. **ssh over Tailscale:** `ssh pico@airsense` → `airsense status` shows the local IP.
4. **USB-C cable to the PC (Luckfox):** `ssh pico@172.32.0.70` — see *SSH over USB* below.

## 📡 Move the BleBox sensor to another WiFi (e.g. the office)
The sensor remembers only the WiFi it was set up on. It does **not** reset by itself: it keeps trying the saved WiFi, and its own
access point **`humiditySensor-xxxxxxxxxx`** (xxxxxxxxxx = serial number) normally stays on — that is the "door" for the settings.
Changing the WiFi keeps the same sensor **ID** → the server finds it again and the history continues on the same sensor.

**A) At the new place — PC app: 📡 Sensors → «🧙 New sensor (WiFi setup)»** (Windows PC with WiFi)
1. Sensor on power; open `AirSense_vX.pyw`.
2. The wizard scans the WiFi around and shows the sensors' networks in **green** (`humiditySensor-…`).
3. Connect → the PC joins the sensor's WiFi by itself (`192.168.4.1`) — the PC internet drops for a moment, that is normal.
4. Give it the **office WiFi** + password → the sensor connects, the PC goes back to its own WiFi, and the wizard finds the sensor on the network.
   No WiFi list on Windows? The wizard asks you to turn on **Location** (it has a button that opens it).

**B) Before you leave — PC app: «🔁 Move sensor to another WiFi» → «A · The sensor works now»**
While the sensor still works at home, **type** the office WiFi name (exactly, case-sensitive) and password. It disappears at home and
joins the office WiFi as soon as it gets power there — nothing to do on site. A typo → use way A at the office.

**C) Phone:** connect the phone to `humiditySensor-xxxx` → **wBox** app (BleBox) → WiFi settings → office WiFi.

**Then the server (Luckfox / Raspberry Pi):** the known sensor stops answering at the old IP → after 3 failed readings the server **scans the
network**, finds the same sensor by its **ID** and keeps the new IP (the first time almost at once, then at most every 30 min).
Faster: find the sensor's IP (router / Fing) → `airsense add NEW_IP`. Check: `airsense status` → *Sensors* online, green ● on the page.

> ⚠ If the sensor's **Access point** was switched **OFF** (BleBox setting) and it cannot reach its WiFi, the access point cannot be turned on
> again — only a **factory reset** (button, see the BleBox manual). Before moving it, check in wBox that *Access point* is **ON**.
> The Luckfox has no WiFi, so the sensor's WiFi is always set from the PC app or wBox — never from the board.

## 🔌 SSH over USB (Luckfox Pico)
With the Ubuntu image the board shows up on the PC as a network card over USB (RNDIS) with a fixed IP **172.32.0.70**
([Luckfox wiki](https://wiki.luckfox.com/Luckfox-Pico/SSH-Telnet-Login)) — handy with no network or an unknown IP.
1. Connect a USB-C **data** cable (not a charge-only one) from the board to the PC — it also powers the board.
2. The first time Windows may need the driver: **RK DriverAssistant** (see the Luckfox RNDIS guide).
3. Windows → Network settings → on the new **RNDIS** adapter set IP **172.32.0.1**, mask **255.255.0.0**.
4. `ssh pico@172.32.0.70` (with your **new** password).

Raspberry Pi Zero 2 W: SSH over USB needs extra setup (USB gadget) — use `airsense-wifi.txt` on the SD card for a new network instead.

## 🌍 Tailscale — access from anywhere
- **ON** = the file `~/tailscale.sh` exists · **OFF** (local only) = it does not. (`airsense tailscale on/off`)
- Login: open the link / QR code it shows → Google / Microsoft / Apple account. Or `AUTHKEY="tskey-auth-…"` inside `tailscale.sh`.
- On the phone: the **Tailscale** app with the **same account** → `http://100.x.x.x:8765`.
- **Tailscale SSH** is turned on automatically: `ssh USER@airsense` from any of your Tailscale devices.
- In the [admin console](https://login.tailscale.com/admin/machines): machine **airsense** → ⋯ → **Disable key expiry** (so it never asks to log in again).

## 👥 Access for another person (e.g. a colleague in Athens with an Android phone) — Luckfox & Raspberry Pi
📄 Ready PDF guide for the other person: [English](docs/AirSense_Phone_Guide_EN_v1.0.0.pdf) · [Ελληνικά](docs/AirSense_Odigos_Kinitou_GR_v1.0.0.pdf) (send it together with your invitation link, address / QR and PIN).

You share **only the airsense machine** through Tailscale — no router ports, and they see nothing else of your network.
They log in with **their own** Tailscale account (free); they never learn your passwords.

**You (once):**
1. https://login.tailscale.com/admin/machines → **airsense** → **⋯** → **Share…**
2. **Copy share link** (or **Share via email**). *Reusable link:* **OFF** = works once, for one person ·
   **ON** = works for anyone who has it (handy for a group — send it only to people you trust).
3. Set a **PIN** for the web page: `airsense set-pin 1234` — and give it to them.
4. Send them the address: `airsense qr` → screenshot of the **🌍 Tailscale** QR, or `http://100.x.x.x:8765`
   (the same 100.x address you see — a shared machine keeps it).

**They (on the phone):**
1. Install **Tailscale** (Play Store) → log in with **their own** account (Google, etc.).
2. Open the invitation **in Chrome** → **Accept** → **airsense** appears in their Tailscale list → switch Tailscale **ON**.
3. Install the **AirSense APK** from [Releases](https://github.com/nikkpap/AirSense/releases/latest) (allow "unknown sources" once).
4. AirSense → **Add server** → scan the QR or type `http://100.x.x.x:8765` (with `http://` and `:8765`) → PIN.

Works from anywhere (4G, any WiFi) while their Tailscale is ON. Remove someone any time: admin → airsense → Share → remove.
The **admin password** (`airsense set-admin`) stays yours — only the admin changes settings.

**How many people at the same time?** No limit — the server answers everyone in parallel and nobody "takes a seat".
Rough estimate (not measured) on a Luckfox Pico Pro (128MB): viewing values / charts — easily **10–20 people** at once
(the sensors are read once by the board and everyone gets the same values); **PDF reports** are the heavy part —
2–3 at the same moment just take a few seconds longer. Tailscale on the Luckfox runs in userspace mode (a bit slower, not noticeable for pages).
Sharing has no practical limit on the free plan. If it feels slow, `airsense status` shows RAM/swap; a swap that is always full means
the board is too small → a **Luckfox Pico Max** (256MB) or **Raspberry Pi Zero 2 W** (512MB) runs the same setup with the same command.

**Raspberry Pi Zero 2 W** (512MB, 4 cores): the sharing steps are exactly the same (machine **airsense** → Share).
Rough estimate (not measured): viewing — easily **30–50 people** at once; PDF reports about 2–3× faster than on the Luckfox and several at once without trouble;
Tailscale runs in normal (kernel/TUN) mode — faster than the Luckfox userspace mode. On WiFi the signal matters more than the board:
`airsense status` shows the WiFi signal % — keep it above ~50%.

**"Failed to accept invitation"** — usually one of these:
1. Opened inside **Viber / Messenger / WhatsApp** (their small built-in browser breaks the login) → long-press the link → **Copy** → paste in **Chrome**.
2. **Not logged in** to Tailscale yet → first open the Tailscale app (or login.tailscale.com) and create the account, **then** open the link in Chrome.
3. Logged in with **your** account (or you are testing it on your own phone) → you cannot share with yourself; it must be **another** account.
4. The link **expired / was cancelled** → Share → **Copy share link** again and resend it.
5. **Company account** → its admin may block accepting shared machines → try a personal Gmail.
Surest way: **Share via email** to their Gmail → they open it from the Gmail app into Chrome.

## 📶 WiFi (Raspberry Pi)
- `airsense wifi` — menu: scan, add, saved networks, priority, hidden network.
- **Without ssh:** put the SD card in a PC → on the boot partition copy `airsense-wifi.example.txt` as **`airsense-wifi.txt`** →
  write `ssid` / `password` → card back in the Pi → power on. The Pi keeps all networks and joins whichever it finds.

## ⚙ airsense-settings.txt (optional)
In the user's home folder (or on the SD card boot partition / a USB stick). Applied on the next boot, only when it changes:
`ADMIN_PASSWORD` · `PIN` · `SENSORS` · `CITY` · `TIMEZONE` · `HOSTNAME` · `AUTO_UPDATE=on/off` · `TAILSCALE_SSH=on/off`.

## 🔄 Automatic updates
10 minutes after every boot and every 6 hours the board checks GitHub; a newer release is downloaded, checked and installed
(data and settings are kept). Turn off: `airsense autoupdate off` or `AUTO_UPDATE=off`. Log: `/var/lib/airsense/update.log`.

## 🩺 Troubleshooting
| I see | I do |
|---|---|
| Anything | `airsense` → it shows what is wrong and the command that fixes it |
| The page does not open | `airsense logs` · `airsense restart` |
| The IP changed | `http://airsense.local:8765` or an IP reservation in the router (`airsense mac`) |
| Wrong time | `airsense clock` (or `airsense clock Europe/Athens`) |
| Tailscale "needs login" | `airsense tailscale` → link + QR |
| The install looks stuck | A moving bar = working. Ctrl+C and run the same command again — it continues. Log: `/tmp/airsense-setup.log` |
| Android update does not install | Uninstall the old **-debug** app once; signed APKs then update over each other |

---

## 📁 Folders
- `desktop/` — the PC app (PyQt6), which is also the server for the web page / phone.
- `linux/` — **shared** scripts for Raspberry Pi + Luckfox (setup, boot, update, tailscale, `airsense` command, password, clock).
- `pi/` — WiFi tool, `.bat` and Raspberry Pi guide.
- `luckfox/` — `.bat` and Luckfox Pico guide.
- `remote/` — AirSense Remote (Windows GUI to manage the board over SSH).
- `android/` — the Android app (Kotlin, Jetpack Compose) — opens in Android Studio. `android/signing/` — one-click signing key setup.
- `get.sh` — the one-command installer (same as `linux/get.sh`, `pi/get.sh`, `luckfox/get.sh`).

## 🛠 Build & Release (GitHub Actions)
- Every push to `main` → checks + build (files in the run's *Artifacts*).
- New release: bump the version (`APP_VERSION` in `desktop/AirSense.pyw`, `versionName/versionCode` in
  `android/app/build.gradle.kts`), add a `CHANGELOG.md` entry, then Actions → Build & Release → *Run workflow* → ✔ release.
- **APK signing:** the 4 secrets `AIRSENSE_KEYSTORE_B64`, `AIRSENSE_KEYSTORE_PASSWORD`, `AIRSENSE_KEY_ALIAS`, `AIRSENSE_KEY_PASSWORD`
  (*Settings → Secrets and variables → Actions*). With them the APK is signed and the `-debug` APK is removed from the release.
  Keep `airsense.jks` and its password safe — without them you cannot publish updates of the same app.

## License / sources
BleBox API · Weather: [Open-Meteo.com](https://open-meteo.com) (CC BY 4.0) · Time: [NTP Pool](https://www.ntppool.org) ·
Remote access: [Tailscale](https://tailscale.com)

---
---

# 🇬🇷 Ελληνικά

Παρακολούθηση, καταγραφή και ειδοποιήσεις για αισθητήρες **BleBox humiditySensor**: γραφήματα, καιρός Open-Meteo,
διαφορά μέσα–έξω με συμβουλή αερισμού, **αναφορές PDF**, CSV/XML, email, και πρόσβαση από το κινητό
(τοπικά ή από παντού με Tailscale). *(πρώην ALU HygroLink)*

**Developer:** Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM

---

## 📌 Πώς δουλεύει
```
 BleBox αισθητήρες ──WiFi──►  AirSense server  ──►  web σελίδα :8765  ──►  κινητό (Android app / browser)
                              (Windows PC, ή                                  τοπικά  ή  από παντού (Tailscale)
                               Raspberry Pi / Luckfox 24/7)
```
Ο **server** διαβάζει τους αισθητήρες, κρατά ιστορικό, φτιάχνει PDF/CSV, στέλνει email.
Μπορεί να είναι ο υπολογιστής σου (`AirSense_vX.pyw`) **ή** μια μικρή πλακέτα που μένει αναμμένη 24/7.

## ⬇ Λήψη — [Releases](https://github.com/nikkpap/AirSense/releases/latest)
| Αρχείο | Για | Πώς |
|---|---|---|
| `AirSense_vX.pyw` | Windows | Διπλό κλικ — εγκαθιστά μόνο του ό,τι χρειάζεται (Python 3.9–3.14, 64-bit) και ανοίγει τον Οδηγό. |
| `AirSense-Pi_vX.zip` | **Raspberry Pi** Zero 2 W / 3 / 4 / 5 | Μία εντολή (παρακάτω) · [pi/ODIGIES_Raspberry_Pi.md](pi/ODIGIES_Raspberry_Pi.md) |
| `AirSense-Luckfox_vX.zip` | **Luckfox Pico** Pro / Max (Ubuntu) | Μία εντολή (παρακάτω) · [luckfox/ODIGIES_Luckfox.md](luckfox/ODIGIES_Luckfox.md) |
| `AirSense-Android_vX.apk` | Android 8+ | Υπογεγραμμένο APK → εγκατάσταση → σκανάρεις το QR του server. |
| `AirSense_Remote_vX.pyw` | Windows | **Διαχείριση της πλακέτας** (Pi / Luckfox) μέσω SSH με γραφικό — δες παρακάτω. |

---

## 🚀 Γρήγορη εκκίνηση

### Windows
1. Κατέβασε το `AirSense_vX.pyw` → **διπλό κλικ**.
2. Ο Οδηγός βρίσκει μόνος του τους αισθητήρες στο δίκτυο → **Τέλος**.
3. Για το κινητό: Ρυθμίσεις → QR → το σκανάρεις με την εφαρμογή Android.

### Raspberry Pi ή Luckfox (server 24/7) — ΜΙΑ εντολή
Μπες στην πλακέτα με **ssh** και γράψε:
```bash
wget -qO get.sh https://raw.githubusercontent.com/nikkpap/AirSense/main/get.sh && sudo bash get.sh
```
Βρίσκει **μόνη της** ποια πλακέτα είναι (Raspberry Pi / Luckfox), κατεβάζει το σωστό πακέτο και:

| Step | Τι γίνεται |
|---|---|
| **1/6** | Έλεγχος + **όλες οι ερωτήσεις μαζί στην αρχή** (ζώνη ώρας από λίστα, όνομα `airsense`, σταθερή MAC, Tailscale, WiFi) — μετά τρέχει μόνο του |
| **2/6** | **Ρολόι**: ζώνη ώρας + NTP από [ntppool.org](https://www.ntppool.org/zone/europe) (Ευρώπη: `europe.pool.ntp.org`) — συγχρονίζει **πριν** το apt · swap |
| **3/6** | Πακέτα (python3, reportlab για PDF, γραμματοσειρές, avahi για `airsense.local`, qrencode) |
| **4/6** | AirSense + αυτόματη εκκίνηση + αυτόματη ενημέρωση από GitHub (+ WiFi εργαλείο στο Pi) |
| **5/6** | Όνομα δικτύου, σταθερή διεύθυνση, εκκίνηση του server |
| **6/6** | Tailscale (πρόσβαση από παντού) + Tailscale SSH |
| Τέλος | Διεύθυνση + **QR** για το κινητό → «Reboot now?» → **Y** |

Μετά την επανεκκίνηση, στο **πρώτο ssh** σε ρωτά να **αλλάξεις τον εργοστασιακό κωδικό** (π.χ. `luckfox`), αν δεν τον έχεις αλλάξει.
Την ίδια εντολή τρέχεις όποτε θέλεις για **επανεγκατάσταση/ενημέρωση** — τα δεδομένα μένουν.

### Android
Εγκατάσταση του APK → «Προσθήκη server» → σκανάρισμα QR (`airsense qr` στην πλακέτα, ή Ρυθμίσεις στο PC).
**Ενημερώσεις (OTA):** η εφαρμογή ελέγχει μόνη της τα GitHub Releases (στο άνοιγμα, το πολύ κάθε 12 ώρες) → «🆕 Νέα έκδοση» → **Ενημέρωση**.
Με το χέρι: Ρυθμίσεις → **Ενημερώσεις** → «🔄 Έλεγχος για ενημέρωση». Την πρώτη φορά το Android ζητά άδεια *Εγκατάσταση άγνωστων εφαρμογών* για το AirSense.

---

## 🖥 AirSense Remote — διαχείριση της πλακέτας από Windows (γραφικό)
`AirSense_Remote_vX.pyw` → διπλό κλικ (εγκαθιστά μόνο του PyQt6, paramiko, qrcode) → **⚙ Settings**: τοπική IP, Tailscale IP, χρήστης, κωδικός, PIN.
- **LED:** Πλακέτα · SSH · Web :8765 · Αισθητήρες · Tailscale · Υγεία — πράσινο / πορτοκαλί / κόκκινο, έλεγχος κάθε 15″ (ποντίκι από πάνω = λεπτομέρειες).
- **Route:** το Auto δοκιμάζει LAN → airsense.local → Tailscale και κρατά όποιο δουλεύει (σπίτι ή γραφείο, ίδιο πρόγραμμα).
- **Κατάσταση πλακέτας** = `airsense status` σε δέντρο με ✔ / ⚠ / ✖ · **ζωντανές τιμές αισθητήρων** · **QR** για το κινητό.
- **Εντολές με ένα κλικ:** Status, Logs, Live log, Clock, MAC, Restart, Stop, Update, Auto-update, Tailscale, Admin password,
  Scan, Add by IP, Set PIN, City, Time zone, Disk/RAM, CPU temp, Password, Reboot, Power off (τα επικίνδυνα ρωτούν πρώτα).
- **Τερματικό + δική σου εντολή** (↑ ↓ ιστορικό): χρώματα, μπάρες προόδου, ο κωδικός του `[sudo]` μπαίνει μόνος του,
  οι ερωτήσεις (Y/n, κωδικοί — τσέκαρε *hidden*) απαντιούνται στο ίδιο κουτί, **■ Stop** = Ctrl+C.
- Δουλεύει και με Tailscale SSH (χωρίς κωδικό). Ο κωδικός αποθηκεύεται κρυπτογραφημένος με τον λογαριασμό σου στα Windows (DPAPI).

## 🧰 Εντολές στην πλακέτα (ssh) — όλες
| Εντολή | Τι κάνει |
|---|---|
| `airsense` / `airsense status` / `airsense doctor` / `airsense diag` | **πλήρης διάγνωση** με ✔/⚠/✖: server, αισθητήρες, δίκτυο, WiFi, ρολόι/NTP, Tailscale, ενημερώσεις, κωδικός, RAM/swap/κάρτα, τελευταία μηνύματα |
| `airsense help` | η λίστα με όλες τις εντολές |
| `airsense qr` | QR για το κινητό (τοπικό + Tailscale) |
| `airsense logs` | τελευταία μηνύματα (server + boot + Tailscale) |
| `airsense live` | ζωντανό log (Ctrl+C για έξοδο) |
| `airsense restart` | επανεκκίνηση του server |
| `airsense stop` | σταματά τον server (ξεκινά ξανά στο επόμενο reboot) |
| `airsense update` | έλεγχος GitHub + ενημέρωση **τώρα** |
| `airsense autoupdate` | κατάσταση αυτόματης ενημέρωσης + τελευταίοι έλεγχοι |
| `airsense autoupdate on` / `off` | αυτόματη ενημέρωση ναι/όχι (κάθε 6 ώρες) |
| `airsense password` (ή `passwd`) | αλλαγή κωδικού χρήστη (και του root, αν είναι εργοστασιακός) |
| `airsense clock` (ή `time`) | ώρα, ζώνη, συγχρονισμός NTP |
| `airsense clock Europe/Athens` | αλλαγή ζώνης ώρας |
| `airsense mac` | η MAC — για κράτηση IP στο router |
| `airsense wifi` | (μόνο Raspberry Pi) μενού WiFi: σάρωση, νέο, αποθηκευμένα, προτεραιότητα |
| `airsense set-admin` | κωδικός διαχειριστή (ρυθμίσεις από web/κινητό) |
| `airsense set-pin 1234` | PIN για τη web σελίδα (`airsense set-pin` χωρίς αριθμό = χωρίς PIN) |
| `airsense scan` | εύρεση + προσθήκη **αισθητήρων BleBox** στο δίκτυο (μόνο αισθητήρες· άλλο δίκτυο: `airsense scan 10.0.0.0/24`) |
| `airsense add 192.168.1.241` | προσθήκη αισθητήρα με IP |
| `airsense city Ptolemaida` | τοποθεσία καιρού |
| `airsense tailscale` | σύνδεση / login Tailscale (link + QR) |
| `airsense tailscale on` / `off` | Tailscale ON / OFF (OFF = μόνο τοπικά) |
| `airsense uninstall` | αφαίρεση (τα δεδομένα μένουν στο `/var/lib/airsense`) |

Σύστημα: `sudo reboot` · `sudo poweroff` (πριν βγάλεις το ρεύμα) · `sudo airsense-update --force` (= `airsense update`) ·
`sudo airsense-wifi add "Όνομα" "κωδικός"` (Pi) · logs: `/var/lib/airsense/boot.log`, `update.log`, `tailscale.log`.

### ✏ Άλλαξα το `AirSense.pyw` — πώς πάει στην πλακέτα;
Το `airsense update` εγκαθιστά μόνο το **τελευταίο release του GitHub**, και μόνο αν η έκδοσή του είναι **μεγαλύτερη** από της πλακέτας.
1. Αλλαγή στο `desktop/AirSense.pyw` **και** ανέβασμα του `APP_VERSION` (π.χ. `"1.6.15"`) → push στο `main`.
2. GitHub → **Actions** → **Build & Release** → **Run workflow** → ✔ release.
3. Στην πλακέτα: `airsense update` (ή μόνη της μέσα σε 6 ώρες).

Γρήγορη δοκιμή χωρίς release: `scp AirSense.pyw pico@airsense.local:~/AirSense_v1.6.15.pyw` και `ssh pico@airsense.local "airsense restart"`
(εγκαθιστά το μεγαλύτερο `APP_VERSION` που βρίσκει στο home). Όσο δοκιμάζεις, `airsense autoupdate off` ώστε να μην το αντικαταστήσει το GitHub.

## 🔀 Άλλο δίκτυο / subnet (π.χ. από 192.168.1.x σε 10.0.0.x)
**Ούτε νέα κάρτα, ούτε ξανά εγκατάσταση.** Τίποτα δεν είναι «κλειδωμένο» στο 192.168.1.x:
- **IP πλακέτας:** την παίρνει αυτόματα από το router (DHCP) σε κάθε δίκτυο. Με τη σταθερή MAC το νέο router της δίνει πάντα την ίδια IP.
- **Διεύθυνση:** το `http://airsense.local:8765` δουλεύει σε κάθε δίκτυο — δεν χρειάζεται να ξέρεις την IP.
- **Tailscale:** συνδέεται μόνο του· η `100.x.x.x` **μένει ίδια** παντού — στο κινητό δεν αλλάζεις τίποτα.
- **Αισθητήρες:** αν αλλάξει η IP τους, το AirSense τους ξαναβρίσκει από το ID τους. **Νέος** αισθητήρας: `airsense add ΝΕΑ_IP`.
- **Μόνος κανόνας:** πλακέτα και αισθητήρες στο **ίδιο** δίκτυο (ίδιο router).
- Το `SENSORS=` στο `airsense-settings.txt` εφαρμόστηκε μία φορά στην αρχή — δεν δεσμεύει τίποτα.
- Βρες την πλακέτα στο νέο δίκτυο: `airsense.local`, η εφαρμογή Tailscale, ή `ssh ΧΡΗΣΤΗΣ@airsense` μέσω Tailscale από οπουδήποτε.
- Raspberry Pi σε νέο WiFi: `airsense wifi` (πριν το μεταφέρεις) ή `airsense-wifi.txt` στην κάρτα SD.

### ❓ Δεν ανοίγει το `http://airsense.local:8765` (νέο μέρος, π.χ. γραφείο)
Ethernet + ρεύμα και περίμενε **1–2 λεπτά** (IP από DHCP, ώρα, εκκίνηση server). Έλεγξε:
- Το PC / κινητό σου είναι στο **ίδιο δίκτυο** με την πλακέτα.
- **Windows 10/11:** το `.local` κανονικά δουλεύει. **Android:** όχι πάντα (ανάλογα με έκδοση / browser) → στο κινητό IP ή Tailscale.
- **Εταιρικά δίκτυα** συχνά κόβουν το `.local` (απομόνωση συσκευών στο WiFi, WiFi και καλώδια σε χωριστά VLAN) — η πλακέτα δουλεύει, απλά το όνομα δεν απαντά.
- Οι **αισθητήρες BleBox πρέπει να είναι κι αυτοί στο ίδιο δίκτυο** — αν έμειναν στο σπίτι, η σελίδα ανοίγει αλλά δείχνει τους αισθητήρες Offline.

Άλλοι τρόποι, από τον πιο σίγουρο:
1. **Tailscale:** `http://100.x.x.x:8765` — όπως στο σπίτι· συνδέεται μόνο του μόλις βρει internet, ακόμα και πίσω από εταιρικό firewall. Δεν χρειάζεται να ξέρεις την IP του γραφείου.
2. **Βρες την IP:** σελίδα του router ή Fing / Angry IP Scanner → `http://IP:8765`.
3. **ssh μέσω Tailscale:** `ssh pico@airsense` → `airsense status` δείχνει την τοπική IP.
4. **Καλώδιο USB-C στο PC (Luckfox):** `ssh pico@172.32.0.70` — δες *SSH μέσω USB* παρακάτω.

## 📡 Μεταφορά του αισθητήρα BleBox σε άλλο WiFi (π.χ. γραφείο)
Ο αισθητήρας θυμάται μόνο το WiFi στο οποίο ρυθμίστηκε. **Δεν** κάνει reset μόνος του: συνεχίζει να ψάχνει το αποθηκευμένο WiFi, και το δικό του
access point **`humiditySensor-xxxxxxxxxx`** (xxxxxxxxxx = σειριακός αριθμός) κανονικά μένει ανοιχτό — αυτή είναι η «πόρτα» για τις ρυθμίσεις.
Η αλλαγή WiFi κρατά το ίδιο **ID** → ο server τον ξαναβρίσκει και το ιστορικό συνεχίζει στον ίδιο αισθητήρα.

**Α) Στο νέο μέρος — εφαρμογή PC: 📡 Αισθητήρες → «🧙 Νέος αισθητήρας (ρύθμιση WiFi)»** (PC Windows με WiFi)
1. Ο αισθητήρας στο ρεύμα· άνοιξε το `AirSense_vX.pyw`.
2. Ο οδηγός ψάχνει τα WiFi γύρω και δείχνει με **πράσινο** τα δίκτυα των αισθητήρων (`humiditySensor-…`).
3. Σύνδεση → το PC μπαίνει μόνο του στο WiFi του αισθητήρα (`192.168.4.1`) — το internet του PC κόβεται για λίγο, φυσιολογικό.
4. Του δίνεις το **WiFi του γραφείου** + κωδικό → ο αισθητήρας συνδέεται, το PC γυρίζει στο δικό του WiFi και ο οδηγός τον βρίσκει στο δίκτυο.
   Δεν βλέπεις WiFi στα Windows; Ο οδηγός ζητά **Τοποθεσία** (έχει κουμπί που την ανοίγει).

**Β) Πριν φύγεις — εφαρμογή PC: «🔁 Μεταφορά αισθητήρα σε άλλο WiFi» → «Α · Ο αισθητήρας δουλεύει τώρα»**
Όσο δουλεύει ακόμα στο σπίτι, **γράφεις** το όνομα του WiFi του γραφείου (ακριβώς, με κεφαλαία/μικρά) και τον κωδικό. Στο σπίτι «χάνεται» και
στο γραφείο συνδέεται μόλις πάρει ρεύμα — εκεί δεν κάνεις τίποτα. Λάθος γράμμα → τρόπος Α στο γραφείο.

**Γ) Κινητό:** σύνδεση του κινητού στο `humiditySensor-xxxx` → εφαρμογή **wBox** (BleBox) → ρυθμίσεις WiFi → WiFi του γραφείου.

**Μετά ο server (Luckfox / Raspberry Pi):** ο γνωστός αισθητήρας δεν απαντά στην παλιά IP → μετά από 3 αποτυχημένες αναγνώσεις ο server **σαρώνει
το δίκτυο**, βρίσκει τον ίδιο αισθητήρα από το **ID** του και κρατά τη νέα IP (την πρώτη φορά σχεδόν αμέσως, μετά το πολύ κάθε 30').
Πιο γρήγορα: βρες την IP του αισθητήρα (router / Fing) → `airsense add ΝΕΑ_IP`. Έλεγχος: `airsense status` → *Sensors* online, πράσινο ● στη σελίδα.

> ⚠ Αν το **Access point** του αισθητήρα έχει κλείσει (**OFF**, ρύθμιση BleBox) και δεν βρίσκει το WiFi του, το access point δεν ξανανοίγει —
> μόνο **factory reset** (κουμπί, δες το εγχειρίδιο BleBox). Πριν τον μεταφέρεις, έλεγξε στο wBox ότι το *Access point* είναι **ON**.
> Το Luckfox δεν έχει WiFi, άρα το WiFi του αισθητήρα ρυθμίζεται πάντα από την εφαρμογή PC ή το wBox — όχι από την πλακέτα.

## 🔌 SSH μέσω USB (Luckfox Pico)
Με την εικόνα Ubuntu η πλακέτα εμφανίζεται στο PC ως κάρτα δικτύου μέσω USB (RNDIS) με σταθερή IP **172.32.0.70**
([wiki Luckfox](https://wiki.luckfox.com/Luckfox-Pico/SSH-Telnet-Login)) — χρήσιμο χωρίς δίκτυο ή όταν δεν ξέρεις την IP.
1. Καλώδιο USB-C **δεδομένων** (όχι μόνο φόρτισης) από την πλακέτα στο PC — δίνει και ρεύμα.
2. Την πρώτη φορά μπορεί να χρειαστεί driver: **RK DriverAssistant** (δες τον οδηγό RNDIS της Luckfox).
3. Windows → Ρυθμίσεις δικτύου → στη νέα κάρτα **RNDIS** βάλε IP **172.32.0.1**, μάσκα **255.255.0.0**.
4. `ssh pico@172.32.0.70` (με τον **νέο** σου κωδικό).

Raspberry Pi Zero 2 W: το SSH μέσω USB θέλει ειδική ρύθμιση (USB gadget) — για νέο δίκτυο χρησιμοποίησε το `airsense-wifi.txt` στην κάρτα SD.

## 🌍 Tailscale — πρόσβαση από παντού
- **ON** = υπάρχει το αρχείο `~/tailscale.sh` · **OFF** (μόνο τοπικά) = δεν υπάρχει. (`airsense tailscale on/off`)
- Login: ανοίγεις το link/QR που δείχνει → λογαριασμός Google/Microsoft/Apple. Ή `AUTHKEY="tskey-auth-…"` μέσα στο `tailscale.sh`.
- Στο κινητό: εφαρμογή **Tailscale** με τον **ίδιο λογαριασμό** → `http://100.x.x.x:8765`.
- **Tailscale SSH** ανοίγει αυτόματα: `ssh ΧΡΗΣΤΗΣ@airsense` από κάθε συσκευή σου στο Tailscale.
- Στο [admin](https://login.tailscale.com/admin/machines): μηχάνημα **airsense** → ⋯ → **Disable key expiry** (να μη ζητά ξανά login κάθε 6 μήνες).

## 👥 Πρόσβαση για άλλον (π.χ. συνάδελφος στην Αθήνα με Android) — Luckfox & Raspberry Pi
📄 Έτοιμος οδηγός PDF για τον άλλον: [Ελληνικά](docs/AirSense_Odigos_Kinitou_GR_v1.0.0.pdf) · [English](docs/AirSense_Phone_Guide_EN_v1.0.0.pdf) (τον στέλνεις μαζί με το link πρόσκλησης, τη διεύθυνση / QR και το PIN).

Μοιράζεσαι **μόνο το μηχάνημα airsense** μέσω Tailscale — χωρίς πόρτες στο router, και δεν βλέπει τίποτε άλλο από το δίκτυό σου.
Μπαίνει με τον **δικό του** λογαριασμό Tailscale (δωρεάν)· τους δικούς σου κωδικούς δεν τους μαθαίνει ποτέ.

**Εσύ (μία φορά):**
1. https://login.tailscale.com/admin/machines → **airsense** → **⋯** → **Share…**
2. **Copy share link** (ή **Share via email**). *Reusable link:* **OFF** = δουλεύει μία φορά, για ένα άτομο ·
   **ON** = δουλεύει για όποιον τον έχει (βολικό για ομάδα — στείλ' τον μόνο σε άτομα που εμπιστεύεσαι).
3. **PIN** στη σελίδα: `airsense set-pin 1234` — και του το δίνεις.
4. Στείλε τη διεύθυνση: `airsense qr` → screenshot του **🌍 Tailscale** QR, ή `http://100.x.x.x:8765`
   (η ίδια 100.x που βλέπεις κι εσύ — το κοινόχρηστο μηχάνημα την κρατά).

**Αυτός (στο κινητό):**
1. Εγκαθιστά το **Tailscale** (Play Store) → login με τον **δικό του** λογαριασμό (Google κ.λπ.).
2. Ανοίγει την πρόσκληση **στο Chrome** → **Accept** → εμφανίζεται το **airsense** στη λίστα του → Tailscale **ON**.
3. Εγκαθιστά το **AirSense APK** από τα [Releases](https://github.com/nikkpap/AirSense/releases/latest) (μία φορά «άγνωστες πηγές»).
4. AirSense → **Προσθήκη server** → σκανάρει το QR ή γράφει `http://100.x.x.x:8765` (με `http://` και `:8765`) → PIN.

Δουλεύει από παντού (4G, κάθε WiFi) όσο το Tailscale του είναι ON. Αφαίρεση όποτε θες: admin → airsense → Share → αφαίρεση.
Ο **κωδικός διαχειριστή** (`airsense set-admin`) μένει δικός σου — μόνο ο διαχειριστής αλλάζει ρυθμίσεις.

**Πόσα άτομα ταυτόχρονα;** Δεν υπάρχει όριο — ο server εξυπηρετεί όλους παράλληλα (κάθε άτομο σε δικό του νήμα), κανείς δεν «πιάνει θέση».
Εκτίμηση (δεν έχει μετρηθεί) σε Luckfox Pico Pro (128MB): προβολή τιμών / γραφημάτων — άνετα **10–20 άτομα** μαζί
(οι αισθητήρες διαβάζονται μία φορά από την πλακέτα και όλοι παίρνουν τις ίδιες έτοιμες τιμές)· η **αναφορά PDF** είναι το πιο «βαρύ» —
2–3 μαζί απλά αργούν λίγα δευτερόλεπτα παραπάνω. Το Tailscale στο Luckfox τρέχει σε userspace mode (λίγο πιο αργό, δεν φαίνεται στις σελίδες).
Η κοινοποίηση δεν έχει πρακτικό όριο στο δωρεάν πλάνο. Αν το νιώσεις αργό, το `airsense status` δείχνει RAM/swap· αν η swap γεμίζει
συνέχεια, η πλακέτα δεν φτάνει → ένα **Luckfox Pico Max** (256MB) ή **Raspberry Pi Zero 2 W** (512MB) τρέχει το ίδιο setup με την ίδια εντολή.

**Raspberry Pi Zero 2 W** (512MB, 4 πυρήνες): τα βήματα κοινοποίησης είναι ακριβώς ίδια (μηχάνημα **airsense** → Share).
Εκτίμηση (δεν έχει μετρηθεί): προβολή — άνετα **30–50 άτομα** μαζί· τα PDF βγαίνουν περίπου 2–3× πιο γρήγορα από το Luckfox, και πολλά μαζί χωρίς πρόβλημα·
το Tailscale τρέχει κανονικά (kernel/TUN) — πιο γρήγορο από το userspace του Luckfox. Στο WiFi μετράει περισσότερο το σήμα παρά η πλακέτα:
το `airsense status` δείχνει το σήμα WiFi % — κράτα το πάνω από ~50%.

**«Failed to accept invitation»** — συνήθως ένα από αυτά:
1. Τον άνοιξε μέσα από **Viber / Messenger / WhatsApp** (ο μικρός browser τους χαλάει το login) → πατημένο στον σύνδεσμο → **Αντιγραφή** → επικόλληση στο **Chrome**.
2. **Δεν έχει κάνει login** στο Tailscale → πρώτα η εφαρμογή Tailscale (ή login.tailscale.com) και λογαριασμός, **μετά** ο σύνδεσμος στο Chrome.
3. Είναι μπασμένος με τον **δικό σου** λογαριασμό (ή τον δοκιμάζεις εσύ στο κινητό σου) → δεν μοιράζεσαι με τον εαυτό σου· πρέπει **άλλος** λογαριασμός.
4. Ο σύνδεσμος **έληξε / ακυρώθηκε** → Share → **Copy share link** ξανά και νέα αποστολή.
5. **Εταιρικός λογαριασμός** → ο διαχειριστής εκεί μπορεί να έχει κλείσει την αποδοχή κοινόχρηστων μηχανημάτων → δοκιμή με προσωπικό Gmail.
Πιο σίγουρα: **Share via email** στο Gmail του → το ανοίγει από την εφαρμογή Gmail στο Chrome.

## ⚙ airsense-settings.txt (προαιρετικό)
Στον φάκελο του χρήστη (ή στο boot partition της κάρτας / USB). Εφαρμόζεται στο επόμενο boot, μόνο όταν αλλάξει:
`ADMIN_PASSWORD` · `PIN` · `SENSORS` · `CITY` · `TIMEZONE` · `HOSTNAME` · `AUTO_UPDATE=on/off` · `TAILSCALE_SSH=on/off`.

## 🩺 Προβλήματα
| Βλέπω | Κάνω |
|---|---|
| Οτιδήποτε | `airsense` → δείχνει τι φταίει και την εντολή που το φτιάχνει |
| Δεν ανοίγει η σελίδα | `airsense logs` · `airsense restart` |
| Άλλαξε η IP | `http://airsense.local:8765` ή κράτηση IP στο router (`airsense mac`) |
| Λάθος ώρα | `airsense clock` (ή `airsense clock Europe/Athens`) |
| Tailscale «needs login» | `airsense tailscale` → link + QR |
| Κόλλησε η εγκατάσταση | Η μπάρα κινείται = δουλεύει. Ctrl+C και ξανά η ίδια εντολή — συνεχίζει. Log: `/tmp/airsense-setup.log` |

---

## 📁 Φάκελοι
- `desktop/` — η εφαρμογή υπολογιστή (PyQt6) που είναι και ο server για web/κινητό.
- `linux/` — **κοινά** scripts για Raspberry Pi + Luckfox (setup, boot, update, tailscale, εντολή `airsense`, κωδικός, ρολόι).
- `pi/` — WiFi εργαλείο, `.bat` και οδηγίες Raspberry Pi.
- `luckfox/` — `.bat` και οδηγίες Luckfox Pico.
- `remote/` — AirSense Remote (γραφικό Windows για διαχείριση της πλακέτας μέσω SSH).
- `android/` — η εφαρμογή Android (Kotlin, Jetpack Compose) — ανοίγει στο Android Studio.
- `get.sh` — ο installer μιας εντολής (ίδιος με `linux/get.sh`, `pi/get.sh`, `luckfox/get.sh`).

## 🛠 Build & Release (GitHub Actions)
- Κάθε push στο `main` → έλεγχος + build (τα αρχεία στα *Artifacts* του run).
- Νέο Release: ανέβασε την έκδοση (`APP_VERSION` στο `desktop/AirSense.pyw`, `versionName/versionCode` στο
  `android/app/build.gradle.kts`), γράψε στο `CHANGELOG.md`, και μετά Actions → Build & Release → *Run workflow* → ✔ release.

### Σταθερή υπογραφή APK (προτείνεται)
Χωρίς κλειδί, το APK υπογράφεται με debug κλειδί που αλλάζει σε κάθε build — τότε μια νέα έκδοση δεν εγκαθίσταται
πάνω στην παλιά (θέλει απεγκατάσταση). Για κανονικές ενημερώσεις φτιάξε **μία φορά** ένα κλειδί και βάλ' το στα
*Settings → Secrets and variables → Actions*:

```
keytool -genkeypair -v -keystore airsense.jks -alias airsense -keyalg RSA -keysize 4096 -validity 36500
```
| Secret | Τιμή |
|---|---|
| `AIRSENSE_KEYSTORE_B64` | το `airsense.jks` σε base64 (PowerShell: `[Convert]::ToBase64String([IO.File]::ReadAllBytes("airsense.jks"))`) |
| `AIRSENSE_KEYSTORE_PASSWORD` | ο κωδικός του keystore |
| `AIRSENSE_KEY_ALIAS` | `airsense` |
| `AIRSENSE_KEY_PASSWORD` | ο κωδικός του κλειδιού (αν είναι ίδιος, μπορεί να λείπει) |

> Κράτα το `airsense.jks` και τον κωδικό σε ασφαλές μέρος — χωρίς αυτά δεν μπορείς να βγάλεις ενημέρωση της ίδιας εφαρμογής.

## Άδειες / πηγές
BleBox API · Καιρός: [Open-Meteo.com](https://open-meteo.com) (CC BY 4.0) · Ώρα: [NTP Pool](https://www.ntppool.org) ·
Απομακρυσμένη πρόσβαση: [Tailscale](https://tailscale.com)
