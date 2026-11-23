# 🌬 AirSense on Raspberry Pi (Zero 2 W / 3 / 4 / 5) — step-by-step guide

**[English](#-english) · [Ελληνικά](#-ελληνικά)**

**Developer:** Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM

---

# 🇬🇧 English

The Raspberry Pi becomes a 24/7 AirSense server: readings, charts, weather, PDF, email — and your phone connects to it.
Same scripts as the Luckfox: same `Step X/6` progress bars, same `airsense` command, automatic updates from GitHub, Tailscale on/off.
Extra on the Pi: **WiFi** (many networks, also from the SD card).

## What you need
- Raspberry Pi **Zero 2 W** (or 3 / 4 / 5)
- microSD card **8GB+** (a good brand, A1)
- 5V power supply (Zero 2 W: 2.5A micro-USB)
- A Windows/Mac PC to write the card

> The Zero 2 W sees **2.4 GHz WiFi only**.

## Step 1 — Write the card (Raspberry Pi Imager)
1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/) and open it.
2. **Device:** Raspberry Pi Zero 2 W · **OS:** *Raspberry Pi OS (other)* → **Raspberry Pi OS Lite (64-bit)** · **Storage:** the card.
3. **Next → Edit settings** (very important):
   - **Hostname:** `airsense`
   - **Username / password:** e.g. `pi` and **your own** password (not `raspberry`)
   - **Wireless LAN:** name + password of your WiFi · **country: GR**
   - **Locale:** Europe/Athens
   - tab **Services → Enable SSH** (with password)
4. **Save → Yes** → wait for it to write and verify.
5. Card in the Pi → power → wait **2–3 minutes** (the first boot is slow).

## Step 2 — Log in with ssh
From Windows (PowerShell / CMD):
```
ssh pi@airsense.local
```
(If it is not found: the IP from the router or the **Fing** app → `ssh pi@192.168.1.xx`.) Type **yes** and your password.

## Step 3 — Install with ONE command
```bash
wget -qO get.sh https://raw.githubusercontent.com/nikkpap/AirSense/main/get.sh && sudo bash get.sh
```
1. **Step 1/6** — all questions **together at the start** (then you can leave, it runs by itself):
   - **Time zone**: a numbered list with the UTC offset (e.g. `1) Europe/Athens UTC+02:00 ← suggested`) → **Enter**
   - Name **airsense** → Enter (Y)
   - **Tailscale** (from anywhere) → **Y** or **N** (local only)
   - "Save another WiFi at the end?" → **Y** if you also want the site's WiFi / your phone hotspot
2. **Step 2/6** clock (NTP `europe.pool.ntp.org`) · **3/6** packages (5–10 min) · **4/6** services · **5/6** start the server · **6/6** Tailscale.
3. Tailscale: open the **link / QR code** it shows (phone or PC) → log in. It waits up to 10 min. Then **Tailscale SSH** turns on by itself.
4. At the end: address + **QR code** for the phone → "Reboot now?" → **Enter**.
5. After the reboot: `ssh pi@airsense.local` → if the password is still the factory one (`raspberry`) it asks you to change it → **Y**.

> **Old install** (ALU HygroLink or AirSense ≤ v1.6.13 with `install_pi.sh`): just run the same command.
> The old service is replaced and the data is copied from `~/airsense-data` to `/var/lib/airsense`
> (the old folder is kept as a copy). A Tailscale that already works stays ON.

### From Windows without internet on the Pi
Unzip **AirSense-Pi_vX.zip** → double-click **install_from_windows.bat** → name/IP, user, password.

## 📶 WiFi
| I want | I do |
|---|---|
| Menu (scan, new network, saved, priority) | `airsense wifi` |
| Quick | `sudo airsense-wifi add "WiFi name" "password"` |
| **Without ssh** (e.g. at a new site) | Card in the PC → on **bootfs** copy `airsense-wifi.example.txt` as **`airsense-wifi.txt`** → write `ssid` / `password` → card in the Pi → power |

The Pi keeps **all** networks and joins whichever it finds (priority: higher number first).
`airsense-wifi.txt` is applied on every boot; then the password is removed from the card and the result + IP are written to `airsense-wifi-log.txt`.
If "Connect NOW" to a new WiFi fails, the Pi **goes back by itself** to the previous one in ~1 minute.

## 🔄 Automatic on every boot
1. WiFi from the card (if `airsense-wifi.txt` exists).
2. Finds the newest `AirSense_vX.pyw` (home, card, USB) → installs it.
3. Applies `airsense-settings.txt` (if it changed).
4. Waits for the correct time (NTP) → then checks/installs what is missing.
5. Checks whether the password is the factory one (→ question at the next ssh login).
6. Tailscale: `~/tailscale.sh` exists → ON · missing → local only.
7. Starts the server (if it stops, it starts again by itself).
8. 10 min later and every 6 hours: **automatic update** from GitHub (`airsense autoupdate off` to stop it).

## Commands
All commands are in the [README](https://github.com/nikkpap/AirSense#-commands-on-the-board-ssh--all-of-them) — the most useful:
`airsense` (diagnosis) · `airsense qr` · `airsense wifi` · `airsense update` · `airsense password` · `airsense clock` · `airsense tailscale`.

## Notes
- **Data:** `/var/lib/airsense` (history, settings, logs). Backup: `sudo tar czf ~/airsense-backup.tar.gz /var/lib/airsense`.
- **Power:** `sudo poweroff` before you unplug it — it protects the card.
- **Reset from scratch:** write the card again (Step 1) and run the command again (Step 3).

---
---

# 🇬🇷 Ελληνικά

**Developer:** Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM

Το Raspberry Pi γίνεται server του AirSense 24/7: μετρήσεις, γραφήματα, καιρός, PDF, email — και το κινητό συνδέεται σε αυτό.
Ίδια scripts με το Luckfox: ίδια μπάρα `Step X/6`, ίδια εντολή `airsense`, αυτόματη ενημέρωση από GitHub, Tailscale on/off.
Επιπλέον στο Pi: **WiFi** (πολλά δίκτυα, και από την κάρτα SD).

---

## Τι χρειάζεσαι
- Raspberry Pi **Zero 2 W** (ή 3 / 4 / 5)
- Κάρτα microSD **8GB+** (καλή μάρκα, A1)
- Τροφοδοτικό 5V (Zero 2 W: 2.5A micro-USB)
- Υπολογιστή με Windows/Mac για το γράψιμο της κάρτας

> Το Zero 2 W βλέπει **μόνο WiFi 2.4 GHz**.

## Βήμα 1 — Γράψιμο της κάρτας (Raspberry Pi Imager)
1. Κατέβασε το [Raspberry Pi Imager](https://www.raspberrypi.com/software/) και άνοιξέ το.
2. **Device:** Raspberry Pi Zero 2 W · **OS:** *Raspberry Pi OS (other)* → **Raspberry Pi OS Lite (64-bit)** · **Storage:** η κάρτα.
3. **Next → Edit settings** (πολύ σημαντικό):
   - **Hostname:** `airsense`
   - **Username / password:** π.χ. `pi` και **δικός σου** κωδικός (όχι `raspberry`)
   - **Wireless LAN:** όνομα + κωδικός του WiFi σου · **country: GR**
   - **Locale:** Europe/Athens
   - καρτέλα **Services → Enable SSH** (με password)
4. **Save → Yes** → περίμενε να γραφτεί και να ελεγχθεί.
5. Κάρτα στο Pi → ρεύμα → περίμενε **2–3 λεπτά** (το πρώτο boot αργεί).

## Βήμα 2 — Μπες με ssh
Από Windows (PowerShell / CMD):
```
ssh pi@airsense.local
```
(Αν δεν το βρει: την IP από το router ή την εφαρμογή **Fing** → `ssh pi@192.168.1.xx`.) Γράψε **yes** και τον κωδικό σου.

## Βήμα 3 — Εγκατάσταση με ΜΙΑ εντολή
```bash
wget -qO get.sh https://raw.githubusercontent.com/nikkpap/AirSense/main/get.sh && sudo bash get.sh
```
1. **Step 1/6** — όλες οι ερωτήσεις **μαζί στην αρχή** (μετά φεύγεις, τρέχει μόνο του):
   - **Ζώνη ώρας**: λίστα με αριθμούς και τη διαφορά UTC (π.χ. `1) Europe/Athens UTC+02:00 ← suggested`) → **Enter**
   - Όνομα **airsense** → Enter (Y)
   - **Tailscale** (από παντού) → **Y** ή **N** (μόνο τοπικά)
   - «Save another WiFi at the end?» → **Y** αν θες να βάλεις και το WiFi του εργοταξίου / hotspot του κινητού
2. **Step 2/6** ρολόι (NTP `europe.pool.ntp.org`) · **3/6** πακέτα (5–10') · **4/6** υπηρεσίες · **5/6** εκκίνηση server · **6/6** Tailscale.
3. Tailscale: άνοιξε το **link / QR** που δείχνει (κινητό ή PC) → login. Περιμένει έως 10'. Μετά ανοίγει μόνο του και το **Tailscale SSH**.
4. Στο τέλος: διεύθυνση + **QR** για το κινητό → «Reboot now?» → **Enter**.
5. Μετά το reboot: `ssh pi@airsense.local` → αν ο κωδικός είναι ακόμα εργοστασιακός (`raspberry`) σε ρωτά να τον αλλάξεις → **Y**.

> **Παλιά εγκατάσταση** (ALU HygroLink ή AirSense ≤ v1.6.13 με `install_pi.sh`): τρέξε απλά την ίδια εντολή.
> Η παλιά υπηρεσία αντικαθίσταται και τα δεδομένα αντιγράφονται από `~/airsense-data` στο `/var/lib/airsense`
> (ο παλιός φάκελος μένει ως αντίγραφο). Ένα Tailscale που ήδη δουλεύει μένει ON.

### Από Windows χωρίς internet στο Pi
Αποσυμπίεσε το **AirSense-Pi_vX.zip** → διπλό κλικ **install_from_windows.bat** → όνομα/IP, χρήστης, κωδικός.

---

## 📶 WiFi
| Θέλω | Κάνω |
|---|---|
| Μενού (σάρωση, νέο δίκτυο, αποθηκευμένα, προτεραιότητα) | `airsense wifi` |
| Γρήγορα | `sudo airsense-wifi add "Όνομα WiFi" "κωδικός"` |
| **Χωρίς ssh** (π.χ. σε νέο εργοτάξιο) | Βάλε την κάρτα στον υπολογιστή → στο **bootfs** αντέγραψε το `airsense-wifi.example.txt` ως **`airsense-wifi.txt`** → γράψε `ssid` / `password` → κάρτα στο Pi → ρεύμα |

Το Pi κρατά **όλα** τα δίκτυα και συνδέεται μόνο του σε όποιο βρει (προτεραιότητα: μεγαλύτερο νούμερο).
Το `airsense-wifi.txt` εφαρμόζεται σε κάθε boot· μετά ο κωδικός σβήνεται από την κάρτα και το αποτέλεσμα + IP γράφονται στο `airsense-wifi-log.txt`.
Αν το «Σύνδεση ΤΩΡΑ» σε νέο WiFi δεν πετύχει, το Pi **γυρίζει μόνο του** στο προηγούμενο σε ~1 λεπτό.

## 🔄 Αυτόματα σε κάθε εκκίνηση
1. WiFi από την κάρτα (αν υπάρχει `airsense-wifi.txt`).
2. Βρίσκει το νεότερο `AirSense_vX.pyw` (home, κάρτα, USB) → το εγκαθιστά.
3. Εφαρμόζει το `airsense-settings.txt` (αν άλλαξε).
4. Περιμένει σωστή ώρα (NTP) → μετά ελέγχει/εγκαθιστά ό,τι λείπει.
5. Ελέγχει αν ο κωδικός είναι εργοστασιακός (→ ερώτηση στο επόμενο ssh).
6. Tailscale: `~/tailscale.sh` υπάρχει → ON · λείπει → μόνο τοπικά.
7. Ξεκινά τον server (αν κλείσει, ξανανοίγει μόνος του).
8. 10' μετά και κάθε 6 ώρες: **αυτόματη ενημέρωση** από το GitHub (`airsense autoupdate off` για να σταματήσει).

## Εντολές
Όλες οι εντολές στο [README](https://github.com/nikkpap/AirSense#-εντολές-στην-πλακέτα-ssh) — οι πιο χρήσιμες:
`airsense` (διάγνωση) · `airsense qr` · `airsense wifi` · `airsense update` · `airsense password` · `airsense clock` · `airsense tailscale`.

## Σημειώσεις
- **Δεδομένα:** `/var/lib/airsense` (ιστορικό, ρυθμίσεις, logs). Αντίγραφο: `sudo tar czf ~/airsense-backup.tar.gz /var/lib/airsense`.
- **Ρεύμα:** `sudo poweroff` πριν το βγάλεις από την πρίζα — προστατεύει την κάρτα.
- **Reset από την αρχή:** ξαναγράφεις την κάρτα (Βήμα 1) και ξανατρέχεις την εντολή (Βήμα 3).
