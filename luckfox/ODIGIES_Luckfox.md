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
1. Κατέβασε από το wiki της Luckfox (Luckfox Pico Pro/Max → Flash image) την εικόνα
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
### Εύκολα από Windows
1. Αποσυμπίεσε το **AirSense-Luckfox_vX.zip** σε έναν φάκελο.
2. (Προαιρετικά) άνοιξε το **airsense-settings.txt** και γράψε κωδικό διαχειριστή, IP αισθητήρα, πόλη.
3. Διπλό κλικ στο **install_from_windows.bat** → γράψε την **IP** → κωδικός **luckfox** (2 φορές).
4. Στην ερώτηση «Θέλεις Tailscale;» → **ν** (από παντού) ή **ο** (μόνο τοπικά).

### Ή με ssh (για όποιον προτιμά)
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

### 🔄 Ενημέρωση έκδοσης
Βάλε το νέο `AirSense_vX.pyw` στο `/home/pico` (ή σε στικάκι USB στην πλακέτα) → `sudo reboot`.
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
| `airsense` | κατάσταση, διευθύνσεις, μνήμη |
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

## Σημειώσεις για την πλακέτα
- **Μνήμη:** η Pro έχει 128MB (λιγότερα στην πράξη) → η εγκατάσταση φτιάχνει **swap 512MB** στην κάρτα.
  Τα PDF βγαίνουν σε λίγα δευτερόλεπτα παραπάνω από τον υπολογιστή — φυσιολογικό.
- **Ώρα:** χωρίς μπαταρία RTC η ώρα έρχεται από το internet στην εκκίνηση (γίνεται αυτόματα, ζώνη Europe/Athens).
- **Ρεύμα:** σταθερός φορτιστής 5V/1A+. Απότομο κόψιμο ρεύματος = κίνδυνος για την κάρτα· `sudo poweroff` πριν το βγάλεις.
- **Reset από την αρχή:** ξαναγράφεις το Ubuntu (Βήμα 1) και ξανατρέχεις το install (Βήμα 3).
