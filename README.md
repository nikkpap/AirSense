# 🌬 AirSense

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
| `AirSense-Android_vX(-debug).apk` | Android 8+ | Εγκατάσταση APK → σκανάρεις το QR του server. |

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
