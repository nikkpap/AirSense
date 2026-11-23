# 🌬 AirSense σε Luckfox Pico Pro / Max — οδηγίες βήμα-βήμα

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
2. Βάλε την κάρτα στον υπολογιστή, φορμάρισέ τη με το **SD Card Formatter**.
3. Άνοιξε το **SocToolKit** → διάλεξε **RV1106** → **SD Card Tool** → διάλεξε την κάρτα →
   φάκελος της εικόνας Ubuntu → **Start create SD card**.
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
wget -qO get.sh https://raw.githubusercontent.com/nikkpap/AirSense/main/luckfox/get.sh && sudo bash get.sh
```
Οι ερωτήσεις είναι **Y/N** — πάτα **Enter** για την προεπιλογή (Y). Όλα τα υπόλοιπα γίνονται μόνα τους:
swap, πακέτα, `/run` 32MB (λίγη RAM), όνομα **airsense**, υπηρεσία εκκίνησης, Tailscale, και στο τέλος επανεκκίνηση για έλεγχο.
Την ίδια εντολή τρέχεις και για **ενημέρωση** σε νέα έκδοση.

### Από Windows (χωρίς internet στην πλακέτα για το κατέβασμα)
1. Αποσυμπίεσε το **AirSense-Luckfox_vX.zip** σε έναν φάκελο.
2. (Προαιρετικά) άνοιξε το **airsense-settings.txt** και γράψε κωδικό διαχειριστή, IP αισθητήρα, πόλη.
3. Διπλό κλικ στο **install_from_windows.bat** → γράψε την **IP** → κωδικός **luckfox** (2 φορές).
4. Στις ερωτήσεις **Y/N**: **Enter** = ναι. Στο «Θέλεις Tailscale;» → **Y** (από παντού) ή **N** (μόνο τοπικά).

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
3. Ελέγχει/εγκαθιστά ό,τι λείπει (python3, reportlab για PDF, γραμματοσειρές).
4. Περιμένει να πάρει σωστή ώρα από το internet.
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
| `airsense update` | ψάχνει νέο `.pyw` τώρα |
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
- Ώρα Κίνας (UTC+8): το setup βάζει ζώνη **Europe/Athens**.

## Σημειώσεις για την πλακέτα
- **Μνήμη:** η Pro έχει 128MB (λιγότερα στην πράξη) → η εγκατάσταση φτιάχνει **swap 512MB** στην κάρτα.
  Τα PDF βγαίνουν σε λίγα δευτερόλεπτα παραπάνω από τον υπολογιστή — φυσιολογικό.
- **Ώρα:** χωρίς μπαταρία RTC η ώρα έρχεται από το internet στην εκκίνηση (γίνεται αυτόματα, ζώνη Europe/Athens).
- **Ρεύμα:** σταθερός φορτιστής 5V/1A+. Απότομο κόψιμο ρεύματος = κίνδυνος για την κάρτα· `sudo poweroff` πριν το βγάλεις.
- **Reset από την αρχή:** ξαναγράφεις το Ubuntu (Βήμα 1) και ξανατρέχεις το install (Βήμα 3).
