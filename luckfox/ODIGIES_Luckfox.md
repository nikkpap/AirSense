# 🌬 AirSense on Luckfox Pico Pro / Max — step-by-step guide

**[English](#-english) · [Ελληνικά](#-ελληνικά)**

**Developer:** Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM

---

# 🇬🇧 English

The small Luckfox Pico Pro (128MB) / Max (256MB) board becomes a 24/7 AirSense server:
readings, charts, weather, PDF, email — and your phone connects to it.

> The board has **no WiFi** → it needs an **Ethernet cable** to the router.
> The sensor can be on the WiFi of the same router.

## What you need
- Luckfox Pico Pro or Max
- microSD card, **8GB or bigger**
- Ethernet cable to the router
- USB-C cable for power (5V phone charger)
- A Windows PC (to write the card and run the install)

## Step 1 — Write Ubuntu to the card (once, or whenever you want a "reset")
1. From the Luckfox wiki — RV1106 pages (the Pico Pro/Max belong there):
   [Image Overview and Download](https://wiki.luckfox.com/Luckfox-Pico-RV1106/Getting-Started/overview) ·
   [Image Flashing](https://wiki.luckfox.com/Luckfox-Pico-RV1106/Getting-Started/Image-flashing) — download the image
   **Ubuntu_Luckfox_Pico_Pro_MicroSD** (for the Max: **Ubuntu_Luckfox_Pico_Max_MicroSD**) and **SocToolKit**.
2. Format the card as **FAT32** (not exFAT; a card >32GB: use **Rufus** → File system FAT32).
3. Open **SocToolKit** → **RV1106** → **SDBoot** (not SD upgrade) → choose the card →
   load the **individual `.img` files** of the Ubuntu folder (**not** `update.img`) → **Start create SD card**.
4. Put the card in the board, connect **Ethernet** and then **power**. Wait **1–2 minutes**.

> If after 2 minutes it is not on the network, or the old system answers (Buildroot, user root):
> the board booted from its own flash instead of the card — see the Luckfox wiki section on booting from the SD card.

## Step 2 — Find the IP
- The router's page → "connected devices" (name usually *luckfox*), **or**
- the **Fing** app on the phone (network scan), or Angry IP Scanner on the PC.

## Step 3 — Install (ONCE)
### ⭐ Easiest: one command (always downloads the latest version)
Log in with ssh (`ssh pico@IP`, password `luckfox` — or PuTTY / MobaXterm) and type:
```bash
wget -qO get.sh https://raw.githubusercontent.com/nikkpap/AirSense/main/get.sh && sudo bash get.sh
```
(The old address `…/main/luckfox/get.sh` works too — same file.)

**All questions come together in Step 1/6** — then it runs by itself:
- **Time zone** from a list with the UTC offset (`1) Europe/Athens UTC+02:00 ← suggested`) → **Enter**
- name **airsense** (Y) · fixed MAC (Y) · **Tailscale** (Y = from anywhere, N = local only)

Then by itself: **clock** (time zone + NTP `europe.pool.ntp.org`, synced **before** apt — the board has no clock battery),
swap, packages, `/run` 32MB (little RAM), services, server, Tailscale + Tailscale SSH, and at the end a reboot to check everything.

**After the reboot:** `ssh pico@airsense.local` → because the password is still the factory **luckfox**, it asks
"Change it now? (Y/n)" → **Enter** → type the current one (`luckfox`), then the **new** one twice.
If **root** also has a factory password, it asks for that one too. Any time: `airsense password`.
Run the same command to **update** to a new version.

### From Windows (no internet download on the board)
1. Unzip **AirSense-Luckfox_vX.zip** into a folder.
2. (Optional) open **airsense-settings.txt** and write the admin password, sensor IP, city.
3. Double-click **install_from_windows.bat** → type the **IP** → password **luckfox** (twice).
4. Questions (all at the start): **Enter** = default. Tailscale → **Y** (from anywhere) or **N** (local only).

### Or by hand with scp
```bash
scp -r AirSense-Luckfox pico@IP:~/airsense-setup
ssh pico@IP                 # password: luckfox
sudo bash ~/airsense-setup/airsense-setup.sh
```

At the end it shows the address and a **QR code** → scan it with the phone. Done!

## After that: everything automatic on every boot
On every power-on the board (service `airsense-boot`):
1. **Looks for** `AirSense*.py` / `AirSense_vX.pyw` in the card root, `/home/pico` and on a **USB stick**.
   If it finds a **newer version**, it installs it by itself.
2. Applies **airsense-settings.txt** (if it changed).
3. Waits for the correct time from the internet (European NTP pool).
4. Checks/installs what is missing (python3, reportlab for PDF, fonts) · checks whether the password is still the factory one.
5. **Tailscale:** if **`tailscale.sh`** exists → runs it (ON) · if it does **not** → local only (OFF).
6. Starts the server — if it ever stops, it starts again by itself.

### 🔄 Automatic update from GitHub
The board checks for a new version **10 minutes after every boot and every 6 hours**.
If GitHub has a newer one, it downloads it, checks it and installs it — data and settings are kept.

| I want | Command |
|---|---|
| Check + update **now** | `airsense update` |
| State / last checks | `airsense autoupdate` |
| Turn off / on | `airsense autoupdate off` / `on` (or `AUTO_UPDATE=off` in airsense-settings.txt) |
| History | `/var/lib/airsense/update.log` |

### 🔄 Manual update
The same command as Step 3 (`wget -qO get.sh … && sudo bash get.sh`) — **or** put the new `AirSense_vX.pyw`
in `/home/pico` (or on a USB stick in the board) → `sudo reboot`.
The data (history, settings) stays in `/var/lib/airsense`.

### 🌍 Tailscale ON / OFF
| I want | I do |
|---|---|
| ON | file **`tailscale.sh`** in `/home/pico` (or card root / USB) → reboot · or `airsense tailscale on` |
| OFF (local only) | delete / rename `tailscale.sh` → reboot · or `airsense tailscale off` |
| Log in the account | `airsense tailscale` → shows a link + QR to log in (Google/Microsoft/Apple) |
| Without a browser | write `AUTHKEY="tskey-auth-…"` inside `tailscale.sh` |

On the phone: the **Tailscale** app with the **same account** → `http://100.x.x.x:8765` (`airsense` shows it).
Tailscale SSH: `ssh pico@airsense` from any of your Tailscale devices. In the admin console: **Disable key expiry**.

## Useful commands (over ssh)
| Command | What it does |
|---|---|
| `airsense` or `airsense status` | **full diagnosis** (server, sensors, network, clock, Tailscale, updates, password, system) with ✔/⚠/✖ |
| `airsense qr` | QR codes for the phone |
| `airsense logs` / `airsense live` | messages / live |
| `airsense restart` | restart the server |
| `airsense update` | check GitHub + update now |
| `airsense password` | change the password (and root's) |
| `airsense clock [Europe/Athens]` | clock, time zone, NTP |
| `airsense mac` | MAC for an IP reservation in the router |
| `airsense set-admin` | admin password |
| `airsense set-pin 1234` | PIN for the web page |
| `airsense add 192.168.1.241` | add a sensor |
| `airsense city Ptolemaida` | weather location |
| `airsense tailscale on/off` | Tailscale |

## Known issues of the Ubuntu image (fixed automatically)
- Random MAC → new IP on every boot: fixed MAC (the IP changes once, then stays). `airsense mac` → IP reservation in the router.
- Tailscale: installed from the official static package (no apt), in its own service; log: `/var/lib/airsense/tailscale.log`.
  The kernel has no TUN device → Tailscale runs in userspace mode (port 8765 is still reachable).
- "Refusing to reload, not enough space available on /run/systemd": `/run` is small because of the RAM → the setup makes it
  32MB and keeps it (service `airsense-run-size`). By hand: `sudo mount -o remount,size=32M /run`.
- "Could not set static hostname": `hostnamectl` does not work here → the name is written directly to `/etc/hostname`.
- China time (UTC+8) / 1970: the setup asks for the time zone (default **Europe/Athens**) and sets NTP `europe.pool.ntp.org` — change: `airsense clock Europe/Athens`.
- SocToolKit "No found env or parameter partition item" / "update is not exist in the partition table": you selected `update.img` → select the individual `.img` files.

## Notes about the board
- **Memory:** the Pro has 128MB (less in practice) → the install makes a **512MB swap** on the card.
  PDFs take a few seconds longer than on the PC — normal.
- **Time:** without an RTC battery the time comes from the internet at boot (European NTP pool, automatic).
- **Password:** everyone knows the factory `luckfox` → change it when asked (or `airsense password`).
- **Power:** a stable 5V/1A+ charger. Pulling the power suddenly = risk for the card; `sudo poweroff` before you unplug it.
- **Reset from scratch:** write Ubuntu again (Step 1) and run the install again (Step 3).

---
---

# 🇬🇷 Ελληνικά

**Developer:** Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM

Η μικρή πλακέτα Luckfox Pico Pro (128MB) / Max (256MB) γίνεται server του AirSense 24/7:
μετρήσεις, γραφήματα, καιρός, PDF, email — και το κινητό συνδέεται σε αυτήν.

> Η πλακέτα **δεν έχει WiFi** → θέλει **καλώδιο Ethernet** στο router.
> Ο αισθητήρας μπορεί να είναι στο WiFi του ίδιου router.

---

## Τι χρειάζεσαι
- Luckfox Pico Pro ή Max
- Κάρτα microSD **8GB ή μεγαλύτερη**
- Καλώδιο Ethernet προς το router
- Καλώδιο USB-C για ρεύμα (φορτιστής κινητού 5V)
- Υπολογιστή με Windows (για το γράψιμο της κάρτας και την εγκατάσταση)

---

## Βήμα 1 — Γράψιμο Ubuntu στην κάρτα (μία φορά, ή όποτε θέλεις «reset»)
1. Κατέβασε από το wiki της Luckfox — σελίδες RV1106 (εκεί ανήκει η Pico Pro/Max):
   [Image Overview and Download](https://wiki.luckfox.com/Luckfox-Pico-RV1106/Getting-Started/overview) ·
   [Image Flashing](https://wiki.luckfox.com/Luckfox-Pico-RV1106/Getting-Started/Image-flashing) — την εικόνα
   **Ubuntu_Luckfox_Pico_Pro_MicroSD** (για Max: **Ubuntu_Luckfox_Pico_Max_MicroSD**) και το **SocToolKit**.
2. Φόρμαρε την κάρτα σε **FAT32** (όχι exFAT· κάρτα >32GB: με το **Rufus** → File system FAT32).
3. Άνοιξε το **SocToolKit** → **RV1106** → **SDBoot** (όχι SD upgrade) → διάλεξε την κάρτα →
   φόρτωσε τα **ξεχωριστά `.img`** του φακέλου Ubuntu (**όχι** το `update.img`) → **Start create SD card**.
4. Βάλε την κάρτα στην πλακέτα, σύνδεσε **Ethernet** και μετά **ρεύμα**. Περίμενε **1–2 λεπτά**.

> Αν μετά από 2 λεπτά δεν φαίνεται στο δίκτυο ή απαντά το παλιό σύστημα (Buildroot, χρήστης root):
> η πλακέτα ξεκίνησε από τη δική της μνήμη flash αντί για την κάρτα — δες στο wiki της Luckfox
> την ενότητα για εκκίνηση από κάρτα SD.

## Βήμα 2 — Βρες την IP
- Στη σελίδα του router → «συνδεδεμένες συσκευές» (όνομα συνήθως *luckfox*), **ή**
- εφαρμογή **Fing** στο κινητό (σάρωση δικτύου).

## Βήμα 3 — Εγκατάσταση (ΜΙΑ φορά)
### ⭐ Πιο εύκολα: μία εντολή (κατεβάζει πάντα την τελευταία έκδοση)
Μπες με ssh (`ssh pico@IP`, κωδικός `luckfox` — ή με PuTTY/MobaXterm) και γράψε:
```bash
wget -qO get.sh https://raw.githubusercontent.com/nikkpap/AirSense/main/get.sh && sudo bash get.sh
```
(Η παλιά διεύθυνση `…/main/luckfox/get.sh` δουλεύει κι αυτή — ίδιο αρχείο.)

**Όλες οι ερωτήσεις έρχονται μαζί στο Step 1/6** — μετά τρέχει μόνο του:
- **Ζώνη ώρας** από λίστα με τη διαφορά UTC (`1) Europe/Athens UTC+02:00 ← suggested`) → **Enter**
- όνομα **airsense** (Y) · σταθερή MAC (Y) · **Tailscale** (Y = από παντού, N = μόνο τοπικά)

Μετά μόνα τους: **ρολόι** (ζώνη + NTP `europe.pool.ntp.org`, συγχρονίζει **πριν** το apt — η πλακέτα δεν έχει μπαταρία ρολογιού),
swap, πακέτα, `/run` 32MB (λίγη RAM), υπηρεσίες, server, Tailscale + Tailscale SSH, και στο τέλος επανεκκίνηση για έλεγχο.

**Μετά το reboot:** `ssh pico@airsense.local` → επειδή ο κωδικός είναι ακόμα ο εργοστασιακός **luckfox**, σε ρωτά
«Change it now? (Y/n)» → **Enter** → γράφεις τον τωρινό (`luckfox`) και μετά τον **νέο** δύο φορές.
Αν και ο **root** έχει εργοστασιακό κωδικό, ρωτά και γι' αυτόν. Οποτεδήποτε: `airsense password`.
Την ίδια εντολή τρέχεις και για **ενημέρωση** σε νέα έκδοση.

### Από Windows (χωρίς internet στην πλακέτα για το κατέβασμα)
1. Αποσυμπίεσε το **AirSense-Luckfox_vX.zip** σε έναν φάκελο.
2. (Προαιρετικά) άνοιξε το **airsense-settings.txt** και γράψε κωδικό διαχειριστή, IP αισθητήρα, πόλη.
3. Διπλό κλικ στο **install_from_windows.bat** → γράψε την **IP** → κωδικός **luckfox** (2 φορές).
4. Στις ερωτήσεις (όλες στην αρχή): **Enter** = προεπιλογή. Στο Tailscale → **Y** (από παντού) ή **N** (μόνο τοπικά).

### Ή χειροκίνητα με scp
```bash
scp -r AirSense-Luckfox pico@IP:~/airsense-setup
ssh pico@IP                 # κωδικός: luckfox
sudo bash ~/airsense-setup/airsense-setup.sh
```

Στο τέλος δείχνει τη διεύθυνση και ένα **QR** → το σκανάρεις με το κινητό. Τέλος!

---

## Μετά: όλα αυτόματα σε κάθε εκκίνηση
Σε κάθε άναμμα η πλακέτα (υπηρεσία `airsense-boot`):
1. **Ψάχνει** το `AirSense*.py` / `AirSense_vX.pyw` στη ρίζα της κάρτας, στο `/home/pico` και σε **USB στικάκι**.
   Αν βρει **νεότερη έκδοση**, την εγκαθιστά μόνη της.
2. Εφαρμόζει το **airsense-settings.txt** (αν άλλαξε).
3. Περιμένει να πάρει σωστή ώρα από το internet (NTP pool της Ευρώπης).
4. Ελέγχει/εγκαθιστά ό,τι λείπει (python3, reportlab για PDF, γραμματοσειρές) · ελέγχει αν ο κωδικός είναι ακόμα εργοστασιακός.
5. **Tailscale:** αν υπάρχει το **`tailscale.sh`** → το τρέχει (ON) · αν **δεν υπάρχει** → μόνο τοπικά (OFF).
6. Ξεκινά τον server — αν κάποτε κλείσει, ξανανοίγει μόνος του.

### 🔄 Αυτόματη ενημέρωση από το GitHub (από v1.6.4)
Η πλακέτα ελέγχει μόνη της για νέα έκδοση **10 λεπτά μετά από κάθε εκκίνηση και κάθε 6 ώρες**.
Αν βρει νεότερη στο GitHub, την κατεβάζει, την ελέγχει και την εγκαθιστά — τα δεδομένα και οι ρυθμίσεις μένουν.

| Θέλω | Εντολή |
|---|---|
| Έλεγχος + ενημέρωση **τώρα** | `airsense update` |
| Κατάσταση / τελευταίοι έλεγχοι | `airsense autoupdate` |
| Απενεργοποίηση / ενεργοποίηση | `airsense autoupdate off` / `on` (ή `AUTO_UPDATE=off` στο airsense-settings.txt) |
| Ιστορικό | `/var/lib/airsense/update.log` |

### 🔄 Ενημέρωση με το χέρι
Η ίδια εντολή του Βήματος 3 (`wget -qO get.sh … && sudo bash get.sh`) — **ή** βάλε το νέο `AirSense_vX.pyw`
στο `/home/pico` (ή σε στικάκι USB στην πλακέτα) → `sudo reboot`.
Τα δεδομένα (ιστορικό, ρυθμίσεις) μένουν στο `/var/lib/airsense`.

### 🌍 Tailscale ON / OFF
| Θέλω | Κάνω |
|---|---|
| ON | αρχείο **`tailscale.sh`** στο `/home/pico` (ή ρίζα κάρτας / USB) → reboot · ή `airsense tailscale on` |
| OFF (μόνο τοπικά) | σβήνω / μετονομάζω το `tailscale.sh` → reboot · ή `airsense tailscale off` |
| Σύνδεση λογαριασμού | `airsense tailscale` → δείχνει link + QR για login (Google/Microsoft/Apple) |
| Χωρίς browser | γράψε `AUTHKEY="tskey-auth-…"` μέσα στο `tailscale.sh` |

Στο κινητό: εφαρμογή **Tailscale** με τον **ίδιο λογαριασμό** → `http://100.x.x.x:8765` (`airsense` το δείχνει).

---

## Χρήσιμες εντολές (μέσω ssh)
| Εντολή | Τι κάνει |
|---|---|
| `airsense` ή `airsense status` | **πλήρης διάγνωση** (server, αισθητήρες, δίκτυο, Tailscale, ενημερώσεις, σύστημα) με ✔/⚠/✖ |
| `airsense qr` | QR για το κινητό |
| `airsense logs` / `airsense live` | μηνύματα / ζωντανά |
| `airsense restart` | επανεκκίνηση server |
| `airsense update` | έλεγχος GitHub + ενημέρωση τώρα |
| `airsense password` | αλλαγή κωδικού (και root) |
| `airsense clock [Europe/Athens]` | ρολόι, ζώνη ώρας, NTP |
| `airsense mac` | MAC για κράτηση IP στο router |
| `airsense set-admin` | κωδικός διαχειριστή |
| `airsense set-pin 1234` | PIN για τη web σελίδα |
| `airsense add 192.168.1.241` | προσθήκη αισθητήρα |
| `airsense city Πτολεμαΐδα` | τοποθεσία καιρού |
| `airsense tailscale on/off` | Tailscale |

---

## Γνωστά θέματα της εικόνας Ubuntu (λύνονται αυτόματα)
- Τυχαία MAC → νέα IP σε κάθε εκκίνηση: από v1.6.11 σταθερή MAC (η IP αλλάζει μία φορά, μετά μένει). `airsense mac` → κράτηση IP στο router.
- Tailscale: από v1.6.11 μπαίνει από το επίσημο στατικό πακέτο (χωρίς apt), σε δική του υπηρεσία· log: `/var/lib/airsense/tailscale.log`.
- «Refusing to reload, not enough space available on /run/systemd»: το `/run` είναι μικρό λόγω RAM → το setup το κάνει
  32MB και το κρατά μόνιμα (υπηρεσία `airsense-run-size`). Χειροκίνητα: `sudo mount -o remount,size=32M /run`.
- «Could not set static hostname»: το `hostnamectl` δεν δουλεύει εδώ → το όνομα γράφεται απευθείας στο `/etc/hostname`.
- Ώρα Κίνας (UTC+8) / 1970: το setup ρωτά ζώνη ώρας (προεπιλογή **Europe/Athens**) και βάζει NTP `europe.pool.ntp.org` — αλλαγή: `airsense clock Europe/Athens`.

## Σημειώσεις για την πλακέτα
- **Μνήμη:** η Pro έχει 128MB (λιγότερα στην πράξη) → η εγκατάσταση φτιάχνει **swap 512MB** στην κάρτα.
  Τα PDF βγαίνουν σε λίγα δευτερόλεπτα παραπάνω από τον υπολογιστή — φυσιολογικό.
- **Ώρα:** χωρίς μπαταρία RTC η ώρα έρχεται από το internet στην εκκίνηση (NTP pool Ευρώπης, αυτόματα).
- **Κωδικός:** ο εργοστασιακός `luckfox` τον ξέρουν όλοι → άλλαξέ τον όταν σε ρωτήσει (ή `airsense password`).
- **Ρεύμα:** σταθερός φορτιστής 5V/1A+. Απότομο κόψιμο ρεύματος = κίνδυνος για την κάρτα· `sudo poweroff` πριν το βγάλεις.
- **Reset από την αρχή:** ξαναγράφεις το Ubuntu (Βήμα 1) και ξανατρέχεις το install (Βήμα 3).
