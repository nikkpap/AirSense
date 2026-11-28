@file:OptIn(ExperimentalLayoutApi::class)

package gr.nikkpap.airsense.ui

import android.os.Build
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import gr.nikkpap.airsense.BuildConfig

@Composable
fun SettingsScreen(vm: MainViewModel, ui: UiState) {
    val ctx = LocalContext.current
    LaunchedEffect(Unit) { vm.updateTs() }
    ResponsiveGrid {
        full("s1") { SectionTitle(tr("Σύνδεση", "Connection")) }
        item(key = "conn") { HCard { ConnectionForm(vm) { vm.refreshNow() } } }
        item(key = "ts") { TailscaleCard(vm, ui) }
        item(key = "pdf") { HCard {
            Text(tr("📄 Οδηγός κινητού (PDF)", "📄 Phone guide (PDF)"), fontWeight = FontWeight.Bold)
            Text(
                tr("Ελληνικά + English, με τα QR του server σου — στείλ' τον σε όποιον θέλει να συνδεθεί.",
                    "Greek + English, with your server's QR codes — send it to anyone who wants to connect."),
                fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.height(6.dp))
            OutlinedButton(onClick = {
                val base = vm.api.currentBase()
                if (base.isNotBlank()) runCatching {
                    ctx.startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse("$base/setup.pdf")))
                }
            }) { Text(tr("Άνοιγμα / κοινοποίηση", "Open / share")) }
        } }

        full("s2") { SectionTitle(tr("Εμφάνιση · Ενημερώσεις", "Appearance · Updates")) }
        item(key = "look") { HCard {
            Text(tr("Γλώσσα", "Language"), fontWeight = FontWeight.Bold)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(selected = !ui.en, onClick = { vm.setLang(false) }, label = { Text("🇬🇷 Ελληνικά") })
                FilterChip(selected = ui.en, onClick = { vm.setLang(true) }, label = { Text("🇬🇧 English") })
            }
            Spacer(Modifier.height(8.dp))
            Text(tr("Θέμα", "Theme"), fontWeight = FontWeight.Bold)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for ((k, l) in listOf("system" to tr("🌓 Αυτόματο", "🌓 Auto"), "time" to tr("🕗 Με την ώρα", "🕗 By time"),
                        "dark" to tr("🌙 Σκούρο", "🌙 Dark"), "light" to tr("☀ Φωτεινό", "☀ Light"))) {
                    FilterChip(selected = ui.theme == k, onClick = { vm.setTheme(k) }, label = { Text(l) })
                }
            }
            Text(when (ui.theme) {
                "time" -> tr("Σκούρο 20:00–07:00, φωτεινό την ημέρα — αλλάζει μόνο του", "Dark 20:00–07:00, light by day — switches by itself")
                "dark" -> tr("Πάντα σκούρο", "Always dark")
                "light" -> tr("Πάντα φωτεινό", "Always light")
                else -> tr("Ακολουθεί το κινητό (σκούρο/φωτεινό θέμα του Android)", "Follows the phone (Android dark/light theme)")
            }, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (Build.VERSION.SDK_INT >= 31) {
                SwitchRow(tr("Δυναμικά χρώματα (Material You)", "Dynamic colors (Material You)"),
                    tr("Χρώματα από την ταπετσαρία σου", "Colors from your wallpaper"), ui.dynamic) { vm.setDynamic(it) }
            }
        } }

        item(key = "upd") { HCard {
            Text(tr("Έκδοση: ", "Version: ") + BuildConfig.VERSION_NAME, fontWeight = FontWeight.Bold)
            val up = ui.update
            when {
                ui.updateProgress != null -> {
                    val p = ui.updateProgress ?: 0f
                    Text(tr("Λήψη v${up?.version}…", "Downloading v${up?.version}…"))
                    Spacer(Modifier.height(6.dp))
                    if (p >= 0f) LinearProgressIndicator(progress = { p }, modifier = Modifier.fillMaxWidth())
                    else LinearProgressIndicator(Modifier.fillMaxWidth())
                }
                up != null -> {
                    Text(tr("🆕 Νέα έκδοση: v${up.version}", "🆕 New version: v${up.version}"), color = OkC, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(6.dp))
                    Button(onClick = { vm.downloadAndInstall() }) { Text(tr("⬇ Λήψη & εγκατάσταση", "⬇ Download & install")) }
                }
                ui.updateMsg != null -> Text(ui.updateMsg, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.height(6.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedButton(onClick = { vm.checkUpdate() }, enabled = !ui.updateChecking && ui.updateProgress == null) {
                    Text(if (ui.updateChecking) tr("Έλεγχος…", "Checking…") else tr("🔄 Έλεγχος για ενημέρωση", "🔄 Check for updates"))
                }
            }
            SwitchRow(tr("Αυτόματος έλεγχος", "Automatic check"),
                tr("Στο άνοιγμα της εφαρμογής, το πολύ κάθε 12 ώρες (GitHub Releases)", "When the app opens, at most every 12 hours (GitHub Releases)"),
                ui.autoUpdate) { vm.setAutoUpdateCheck(it) }
        } }

        full("s3") { SectionTitle(tr("Σχετικά", "About")) }
        item(key = "about") { HCard {
            Text("💧 AirSense ${BuildConfig.VERSION_NAME}", fontWeight = FontWeight.Bold, fontSize = 18.sp)
            Text(tr("Εφαρμογή για το AirSense (BleBox humiditySensor)", "Companion app for AirSense (BleBox humiditySensor)"))
            Spacer(Modifier.height(8.dp))
            Text("Developer: Nikolaos K. Paridis (aka nikkpap)")
            Text("ALU DEV TEAM", color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            Text(tr("Καιρός: Open-Meteo.com (CC BY 4.0)", "Weather data: Open-Meteo.com (CC BY 4.0)"), fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(tr("Server: AirSense v1.4.1+ στον υπολογιστή (λεκτικά μέσα/έξω: v1.5.8+)", "Server: AirSense v1.4.1+ on the PC (in/out labels: v1.5.8+)"),
                fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = { vm.resetSetup() }) { Text(tr("Οδηγός σύνδεσης από την αρχή", "Run connection setup again")) }
        } }
        full("end") { Spacer(Modifier.height(20.dp)) }
    }
}

/** 🌍 Tailscale: status, automatic on / off, one-tap buttons. */
@Composable
fun TailscaleCard(vm: MainViewModel, ui: UiState) {
    val ctx = LocalContext.current
    HCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("🌍 Tailscale", fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
            when {
                !ui.tsInstalled -> StatusPill(tr("δεν υπάρχει", "not installed"), MaterialTheme.colorScheme.outline)
                ui.tsVpn -> StatusPill(tr("ενεργό", "on"), OkC)
                else -> StatusPill(tr("κλειστό", "off"), MaterialTheme.colorScheme.outline)
            }
        }
        Text(
            tr("Για σύνδεση από παντού (4G, άλλο WiFi). Το AirSense το ανοίγει μόνο του όταν χρειάζεται και το κλείνει όταν φεύγεις.",
                "To connect from anywhere (4G, other WiFi). AirSense turns it on by itself when needed and off when you leave."),
            fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        if (ui.tsInstalled) {
            Spacer(Modifier.height(8.dp))
            Text(tr("Αυτόματο άνοιγμα", "Turn on automatically"), fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for ((k, l) in listOf("smart" to tr("🧠 Έξυπνα", "🧠 Smart"), "always" to tr("Πάντα", "Always"), "off" to tr("Ποτέ", "Never"))) {
                    FilterChip(selected = ui.tsAuto == k, onClick = { vm.setTsAuto(k) }, label = { Text(l) })
                }
            }
            Text(when (ui.tsAuto) {
                "smart" -> tr("Μόνο όταν η πλακέτα δεν απαντά στο WiFi σου (εκτός σπιτιού).", "Only when the board does not answer on your WiFi (away from home).")
                "always" -> tr("Κάθε φορά που ανοίγεις την εφαρμογή.", "Every time you open the app.")
                else -> tr("Ποτέ — το ανοίγεις μόνος σου (κουμπί 🔑 πάνω).", "Never — you turn it on yourself (🔑 button at the top).")
            }, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            SwitchRow(tr("Κλείσιμο όταν φεύγω από την εφαρμογή", "Turn off when I leave the app"),
                tr("Μόνο αν το άνοιξε το AirSense · όχι όταν τρέχει η «Ζωντανή παρακολούθηση»",
                    "Only if AirSense turned it on · not while “Live monitoring” runs"), ui.tsAutoOff) { vm.setTsAutoOff(it) }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { vm.toggleTailscale() }) { Text(if (ui.tsVpn) tr("Απενεργοποίηση", "Turn off") else tr("Ενεργοποίηση", "Turn on")) }
                OutlinedButton(onClick = { gr.nikkpap.airsense.data.TailscaleCtl.openApp(ctx) }) { Text(tr("Άνοιγμα εφαρμογής", "Open app")) }
            }
            Text(tr("Πρώτη φορά: άνοιξε το Tailscale, κάνε login και δώσε την άδεια VPN.",
                "First time: open Tailscale, log in and allow the VPN."), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 6.dp))
        } else {
            Spacer(Modifier.height(8.dp))
            Button(onClick = { openUrl(ctx, gr.nikkpap.airsense.data.TailscaleCtl.PLAY) }) { Text(tr("Εγκατάσταση Tailscale", "Install Tailscale")) }
        }
    }
}
