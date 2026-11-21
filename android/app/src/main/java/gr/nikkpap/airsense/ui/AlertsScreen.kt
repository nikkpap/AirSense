@file:OptIn(ExperimentalLayoutApi::class)

package gr.nikkpap.airsense.ui

import android.Manifest
import android.content.Intent
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import gr.nikkpap.airsense.work.CheckWorker
import gr.nikkpap.airsense.work.Checker
import gr.nikkpap.airsense.work.MonitorService
import gr.nikkpap.airsense.work.Notifier
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun SwitchRow(title: String, sub: String = "", checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title)
            if (sub.isNotBlank()) Text(sub, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked = checked, onCheckedChange = onChange)
    }
}

@Composable
fun NumField(label: String, value: String, modifier: Modifier = Modifier, onChange: (String) -> Unit) {
    OutlinedTextField(
        value, onChange, modifier, singleLine = true, label = { Text(label) },
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal)
    )
}

fun String.toFloatSafe(): Float? = replace(',', '.').toFloatOrNull()

@Composable
fun AlertsScreen(vm: MainViewModel, ui: UiState) {
    val ctx = LocalContext.current
    val p = vm.prefs
    val scope = rememberCoroutineScope()
    var canPost by remember { mutableStateOf(Notifier.canPost(ctx)) }
    val permLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { canPost = it }

    var enabled by remember { mutableStateOf(p.notifEnabled) }
    var tMin by remember { mutableStateOf(p.tMin.toString()) }
    var tMax by remember { mutableStateOf(p.tMax.toString()) }
    var hMin by remember { mutableStateOf(p.hMin.toString()) }
    var hMax by remember { mutableStateOf(p.hMax.toString()) }
    var offline by remember { mutableStateOf(p.offlineAlert) }
    var server by remember { mutableStateOf(p.serverAlert) }
    var weather by remember { mutableStateOf(p.weatherAlert) }
    var frost by remember { mutableStateOf(p.frostAlert) }
    var forward by remember { mutableStateOf(p.forwardPc) }
    var every by remember { mutableIntStateOf(p.checkMinutes) }
    var cooldown by remember { mutableIntStateOf(p.cooldownMin) }
    var live by remember { mutableStateOf(p.liveEnabled) }
    var liveSec by remember { mutableIntStateOf(p.liveSeconds) }

    fun saveThresholds() {
        tMin.toFloatSafe()?.let { p.tMin = it }
        tMax.toFloatSafe()?.let { p.tMax = it }
        hMin.toFloatSafe()?.let { p.hMin = it }
        hMax.toFloatSafe()?.let { p.hMax = it }
        vm.say(vm.t("Τα όρια αποθηκεύτηκαν", "Limits saved"))
    }

    LazyColumn(contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        if (!canPost) {
            item {
                HCard {
                    Text(tr("🔕 Οι ειδοποιήσεις είναι κλειστές", "🔕 Notifications are off"), fontWeight = FontWeight.Bold, color = WarnC)
                    Spacer(Modifier.height(6.dp))
                    Button(onClick = {
                        if (Build.VERSION.SDK_INT >= 33) permLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                        else ctx.startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, ctx.packageName))
                    }) { Text(tr("Ενεργοποίηση ειδοποιήσεων", "Enable notifications")) }
                }
            }
        }
        item {
            HCard {
                SwitchRow(tr("Ειδοποιήσεις", "Notifications"), tr("Έλεγχος στο παρασκήνιο", "Background checks"), enabled) {
                    enabled = it; p.notifEnabled = it; CheckWorker.schedule(ctx)
                }
                Text(tr("Έλεγχος κάθε", "Check every"), fontSize = 13.sp)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    for (m in listOf(15, 30, 60, 120)) {
                        FilterChip(selected = every == m, onClick = { every = m; p.checkMinutes = m; CheckWorker.schedule(ctx) },
                            label = { Text("$m′") })
                    }
                }
                Text(
                    tr("Το Android επιτρέπει έλεγχο στο παρασκήνιο το πολύ κάθε 15′. Για συνεχή έλεγχο ενεργοποίησε τη «Ζωντανή παρακολούθηση».",
                        "Android allows background checks at most every 15′. For continuous checks enable “Live monitoring”."),
                    fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
        item {
            HCard {
                Text(tr("📏 Όρια αισθητήρων", "📏 Sensor limits"), fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(6.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    NumField(tr("Θερμ. min °C", "Temp min °C"), tMin, Modifier.weight(1f)) { tMin = it }
                    NumField(tr("Θερμ. max °C", "Temp max °C"), tMax, Modifier.weight(1f)) { tMax = it }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    NumField(tr("Υγρ. min %", "Hum min %"), hMin, Modifier.weight(1f)) { hMin = it }
                    NumField(tr("Υγρ. max %", "Hum max %"), hMax, Modifier.weight(1f)) { hMax = it }
                }
                Spacer(Modifier.height(8.dp))
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { saveThresholds() }) { Text(tr("💾 Αποθήκευση", "💾 Save")) }
                    OutlinedButton(onClick = {
                        ui.status?.alarms?.let { a ->
                            tMin = a.tempMin.toString(); tMax = a.tempMax.toString()
                            hMin = a.humMin.toString(); hMax = a.humMax.toString()
                            saveThresholds()
                        }
                    }) { Text(tr("Όπως στον υπολογιστή", "Copy from PC")) }
                }
                Text(tr("Επανάληψη ειδοποίησης το πολύ κάθε", "Repeat alert at most every"), fontSize = 13.sp)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    for (m in listOf(15, 30, 60, 180)) {
                        FilterChip(selected = cooldown == m, onClick = { cooldown = m; p.cooldownMin = m }, label = { Text("$m′") })
                    }
                }
            }
        }
        item {
            HCard {
                Text(tr("🔔 Τι να με ειδοποιεί", "🔔 Notify me about"), fontWeight = FontWeight.Bold)
                SwitchRow(tr("Αισθητήρας offline", "Sensor offline"), checked = offline) { offline = it; p.offlineAlert = it }
                SwitchRow(tr("Ο υπολογιστής δεν απαντά", "PC not reachable"), checked = server) { server = it; p.serverAlert = it }
                SwitchRow(tr("Αρχίζει βροχή / χιόνι / καταιγίδα", "Rain / snow / storm starts"), "Open-Meteo", weather) { weather = it; p.weatherAlert = it }
                SwitchRow(tr("Παγετός έξω (≤ 0°C)", "Frost outside (≤ 0°C)"), "Open-Meteo", frost) { frost = it; p.frostAlert = it }
                SwitchRow(tr("Ειδοποιήσεις του υπολογιστή", "PC warnings"), tr("Προώθηση ⚠ συμβάντων", "Forward ⚠ events"), forward) { forward = it; p.forwardPc = it }
                Spacer(Modifier.height(6.dp))
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { Notifier.alert(ctx, "test", "💧 AirSense", vm.t("Δοκιμαστική ειδοποίηση ✔", "Test notification ✔")) }) {
                        Text(tr("Δοκιμαστική ειδοποίηση", "Test notification"))
                    }
                    OutlinedButton(onClick = { scope.launch { Checker.run(ctx); vm.say(vm.t("Έλεγχος ολοκληρώθηκε", "Check done")) } }) {
                        Text(tr("Έλεγχος τώρα", "Check now"))
                    }
                }
            }
        }
        item {
            HCard {
                SwitchRow(
                    tr("📌 Ζωντανή παρακολούθηση", "📌 Live monitoring"),
                    tr("Μόνιμη ειδοποίηση με τις τιμές + γρήγορος έλεγχος ορίων", "Persistent notification with values + fast limit checks"),
                    live
                ) {
                    live = it
                    p.liveEnabled = it
                    if (it) MonitorService.start(ctx) else MonitorService.stop(ctx)
                }
                Text(tr("Ανανέωση κάθε", "Refresh every"), fontSize = 13.sp)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    for ((s, l) in listOf(30 to "30″", 60 to "1′", 300 to "5′", 900 to "15′")) {
                        FilterChip(selected = liveSec == s, onClick = { liveSec = s; p.liveSeconds = s }, label = { Text(l) })
                    }
                }
                OutlinedButton(onClick = {
                    runCatching { ctx.startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) }
                }) { Text(tr("🔋 Εξαίρεση από εξοικονόμηση μπαταρίας", "🔋 Exclude from battery saver")) }
                Text(
                    tr("Προτείνεται, ώστε το Android να μη σταματά τους ελέγχους.", "Recommended so Android won't stop the checks."),
                    fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
        item { SectionTitle(tr("Συμβάντα υπολογιστή", "PC events")) }
        val evs = ui.status?.log?.reversed() ?: emptyList()
        items(evs) { e ->
            val col = when (e.level) {
                "warn" -> WarnC; "err" -> BadC; else -> MaterialTheme.colorScheme.onSurface
            }
            Text(
                SimpleDateFormat("dd/MM HH:mm", Locale.getDefault()).format(Date((e.ts * 1000).toLong())) + "  " + e.msg,
                fontSize = 12.sp, color = col, modifier = Modifier.padding(horizontal = 4.dp)
            )
        }
        item { Spacer(Modifier.height(12.dp)) }
    }
}
