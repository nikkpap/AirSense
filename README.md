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

---

## 🧰 Commands on the board (ssh)
| Command | What it does |
|---|---|
| `airsense` / `airsense status` | **full diagnosis** with ✔/⚠/✖: server, sensors, network, WiFi, clock/NTP, Tailscale, updates, password, RAM/SD card |
| `airsense qr` | QR codes for the phone (local + Tailscale) |
| `airsense logs` / `airsense live` | messages / live log |
| `airsense restart` / `stop` | restart / stop the server |
| `airsense update` | check GitHub + update **now** |
| `airsense autoupdate on\|off` | automatic updates (every 6 hours) |
| `airsense password` | change the user password (and root's, if it is the factory default) |
| `airsense clock [Europe/Athens]` | clock, time zone, NTP sync |
| `airsense wifi` | (Raspberry Pi) WiFi: scan, add a network, saved networks |
| `airsense mac` | MAC address — for an IP reservation in the router |
| `airsense set-admin` / `set-pin 1234` | admin password / PIN of the web page |
| `airsense add 192.168.1.241` | add a sensor |
| `airsense city Ptolemaida` | weather location |
| `airsense tailscale [on\|off]` | Tailscale login / ON / OFF |
| `airsense uninstall` | remove (the data stays in `/var/lib/airsense`) |

## 🌍 Tailscale — access from anywhere
- **ON** = the file `~/tailscale.sh` exists · **OFF** (local only) = it does not. (`airsense tailscale on/off`)
- Login: open the link / QR code it shows → Google / Microsoft / Apple account. Or `AUTHKEY="tskey-auth-…"` inside `tailscale.sh`.
- On the phone: the **Tailscale** app with the **same account** → `http://100.x.x.x:8765`.
- **Tailscale SSH** is turned on automatically: `ssh USER@airsense` from any of your Tailscale devices.
- In the [admin console](https://login.tailscale.com/admin/machines): machine **airsense** → ⋯ → **Disable key expiry** (so it never asks to log in again).

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

---

## 🧰 Εντολές στην πλακέτα (ssh)
| Εντολή | Τι κάνει |
|---|---|
| `airsense` / `airsense status` | **πλήρης διάγνωση** με ✔/⚠/✖: server, αισθητήρες, δίκτυο, WiFi, ρολόι/NTP, Tailscale, ενημερώσεις, κωδικός, RAM/κάρτα |
| `airsense qr` | QR για το κινητό (τοπικό + Tailscale) |
| `airsense logs` / `airsense live` | μηνύματα / ζωντανά |
| `airsense restart` / `stop` | επανεκκίνηση / στάση server |
| `airsense update` | έλεγχος GitHub + ενημέρωση **τώρα** |
| `airsense autoupdate on\|off` | αυτόματες ενημερώσεις (κάθε 6 ώρες) |
| `airsense password` | αλλαγή κωδικού χρήστη (και root, αν είναι εργοστασιακός) |
| `airsense clock [Europe/Athens]` | ρολόι, ζώνη ώρας, συγχρονισμός NTP |
| `airsense wifi` | (Raspberry Pi) WiFi: σάρωση, νέο δίκτυο, αποθηκευμένα |
| `airsense mac` | MAC — για κράτηση IP στο router |
| `airsense set-admin` / `set-pin 1234` | κωδικός διαχειριστή / PIN web σελίδας |
| `airsense add 192.168.1.241` | προσθήκη αισθητήρα |
| `airsense city Ptolemaida` | τοποθεσία καιρού |
| `airsense tailscale [on\|off]` | Tailscale login / ON / OFF |
| `airsense uninstall` | αφαίρεση (τα δεδομένα μένουν στο `/var/lib/airsense`) |

## 🌍 Tailscale — πρόσβαση από παντού
- **ON** = υπάρχει το αρχείο `~/tailscale.sh` · **OFF** (μόνο τοπικά) = δεν υπάρχει. (`airsense tailscale on/off`)
- Login: ανοίγεις το link/QR που δείχνει → λογαριασμός Google/Microsoft/Apple. Ή `AUTHKEY="tskey-auth-…"` μέσα στο `tailscale.sh`.
- Στο κινητό: εφαρμογή **Tailscale** με τον **ίδιο λογαριασμό** → `http://100.x.x.x:8765`.
- **Tailscale SSH** ανοίγει αυτόματα: `ssh ΧΡΗΣΤΗΣ@airsense` από κάθε συσκευή σου στο Tailscale.
- Στο [admin](https://login.tailscale.com/admin/machines): μηχάνημα **airsense** → ⋯ → **Disable key expiry** (να μη ζητά ξανά login κάθε 6 μήνες).

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
