# 🌬 AirSense

Παρακολούθηση, καταγραφή και ειδοποιήσεις για αισθητήρες **BleBox humiditySensor**: γραφήματα, καιρός Open-Meteo,
διαφορά μέσα–έξω με συμβουλή αερισμού, CSV/XML, email, και πρόσβαση από το κινητό (τοπικά ή από παντού με Tailscale).
*(πρώην ALU HygroLink)*

**Developer:** Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM

## ⬇ Λήψη
Από τα **[Releases](https://github.com/nikkpap/AirSense/releases/latest)**:

| Αρχείο | Για | Πώς |
|---|---|---|
| `AirSense_vX.pyw` | Windows | Διπλό κλικ — εγκαθιστά μόνο του ό,τι χρειάζεται (Python 3.9–3.14, 64-bit) και ανοίγει τον Οδηγό. |
| `AirSense-Pi_vX.zip` | Raspberry Pi (24/7 server) | Δες `ODIGIES_Raspberry_Pi.md` μέσα στο zip. |
| `AirSense-Android_vX(-debug).apk` | Android 8+ | Εγκατάσταση APK → Ρυθμίσεις → σκανάρισμα QR από τον υπολογιστή. |

## 📁 Φάκελοι
- `desktop/` — η εφαρμογή υπολογιστή (PyQt6) που είναι και server για web/κινητό.
- `pi/` — installer, εργαλείο WiFi και οδηγίες για Raspberry Pi.
- `android/` — η εφαρμογή Android (Kotlin, Jetpack Compose) — ανοίγει στο Android Studio.

## 🛠 Build & Release (GitHub Actions)
- Κάθε push στο `main` → έλεγχος + build (τα αρχεία στα *Artifacts* του run).
- Νέο Release: ανέβασε την έκδοση (`APP_VERSION` στο `desktop/AirSense.pyw`, `versionName/versionCode` στο
  `android/app/build.gradle.kts`), γράψε στο `CHANGELOG.md`, και μετά **tag** `vX.Y.Z` (ή Actions → Build & Release →
  *Run workflow* → ✔ release).

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
BleBox API · Καιρός: [Open-Meteo.com](https://open-meteo.com) (CC BY 4.0) · Απομακρυσμένη πρόσβαση: [Tailscale](https://tailscale.com)
