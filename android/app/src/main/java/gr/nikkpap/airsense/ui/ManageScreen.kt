@file:OptIn(ExperimentalLayoutApi::class)

package gr.nikkpap.airsense.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import gr.nikkpap.airsense.data.Calib
import gr.nikkpap.airsense.data.Device
import gr.nikkpap.airsense.data.Place
import gr.nikkpap.airsense.data.f
import kotlinx.coroutines.launch
import org.json.JSONObject

@Composable
fun ManageScreen(vm: MainViewModel, ui: UiState) {
    val ctx = LocalContext.current
    val st = ui.status
    var rename by remember { mutableStateOf<Device?>(null) }
    var wifi by remember { mutableStateOf<Device?>(null) }
    var remove by remember { mutableStateOf<Device?>(null) }
    var adminOpen by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { vm.loadConfig() }

    LazyColumn(contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        // ── υπολογιστής ──
        item {
            HCard {
                Text("💻 AirSense ${st?.version ?: ""}", fontWeight = FontWeight.Bold)
                Text(vm.api.currentBase(), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (st != null) Text(tr("Μέτρηση κάθε ${st.pollSeconds}″", "Measuring every ${st.pollSeconds}″"), fontSize = 13.sp)
                if (st?.scanRunning == true) {
                    Spacer(Modifier.height(6.dp))
                    Text(tr("Σάρωση δικτύου ${st.scanDone}/${st.scanTotal}…", "Network scan ${st.scanDone}/${st.scanTotal}…"), fontSize = 13.sp)
                    LinearProgressIndicator(progress = { if (st.scanTotal > 0) st.scanDone / st.scanTotal.toFloat() else 0f }, modifier = Modifier.fillMaxWidth())
                }
                Spacer(Modifier.height(8.dp))
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { vm.post("/api/poll") }) { Icon(Icons.Filled.Refresh, null); Spacer(Modifier.width(6.dp)); Text(tr("Μέτρηση", "Measure")) }
                    OutlinedButton(onClick = { vm.post("/api/scan") }) { Icon(Icons.Filled.Search, null); Spacer(Modifier.width(6.dp)); Text(tr("Σάρωση δικτύου", "Scan network")) }
                    OutlinedButton(onClick = { vm.post("/api/report") }) { Icon(Icons.Filled.Email, null); Spacer(Modifier.width(6.dp)); Text(tr("Email αναφορά", "Email report")) }
                    OutlinedButton(onClick = { openUrl(ctx, vm.webUrl()) }) { Icon(Icons.Filled.OpenInBrowser, null); Spacer(Modifier.width(6.dp)); Text("Web") }
                }
            }
        }
        // ── συσκευές ──
        item { SectionTitle(tr("Αισθητήρες", "Sensors")) }
        items(st?.devices ?: emptyList(), key = { it.id }) { d ->
            HCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(d.name, fontWeight = FontWeight.Bold)
                        Text("${d.ip} · ${d.type} · ${f(d.t)}°C ${f(d.h)}%", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Switch(checked = d.enabled, onCheckedChange = { on ->
                        vm.post("/api/device", JSONObject().put("id", d.id).put("enabled", on))
                    })
                }
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    AssistChip(onClick = { rename = d }, label = { Text(tr("Μετονομασία", "Rename")) }, leadingIcon = { Icon(Icons.Filled.Edit, null) })
                    AssistChip(onClick = { wifi = d }, label = { Text(tr("Αλλαγή WiFi", "Change WiFi")) }, leadingIcon = { Icon(Icons.Filled.Wifi, null) })
                    AssistChip(onClick = { remove = d }, label = { Text(tr("Αφαίρεση", "Remove")) }, leadingIcon = { Icon(Icons.Filled.Delete, null) })
                }
            }
        }
        // ── καιρός ──
        item { SectionTitle(tr("Καιρός (Open-Meteo)", "Weather (Open-Meteo)")) }
        item { WeatherLocationCard(vm, ui) }
        // ── ρυθμίσεις υπολογιστή ──
        item { SectionTitle(tr("Ρυθμίσεις υπολογιστή", "PC settings")) }
        item { PcSettingsCard(vm, ui) }
        // ── διαχειριστής ──
        item { SectionTitle(tr("Διαχειριστής", "Administrator")) }
        item {
            HCard {
                Text(tr("🔐 Βαθμονόμηση μετρήσεων", "🔐 Measurement calibration"), fontWeight = FontWeight.Bold)
                Text(
                    tr("Χρειάζεται τον κωδικό διαχειριστή που ορίστηκε στον υπολογιστή (Ctrl+Shift+A).",
                        "Requires the admin password set on the PC (Ctrl+Shift+A)."),
                    fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(Modifier.height(6.dp))
                Button(onClick = { adminOpen = true }) { Icon(Icons.Filled.Lock, null); Spacer(Modifier.width(6.dp)); Text(tr("Άνοιγμα", "Open")) }
            }
        }
        item { Spacer(Modifier.height(12.dp)) }
    }

    rename?.let { d -> RenameDialog(vm, d) { rename = null } }
    wifi?.let { d -> WifiDialog(vm, d) { wifi = null } }
    remove?.let { d ->
        AlertDialog(
            onDismissRequest = { remove = null },
            title = { Text(tr("Αφαίρεση «${d.name}»;", "Remove “${d.name}”?")) },
            text = { Text(tr("Οι παλιές μετρήσεις μένουν στη βάση του υπολογιστή.", "Old readings stay in the PC database.")) },
            confirmButton = { TextButton(onClick = { vm.post("/api/device", JSONObject().put("id", d.id).put("remove", true)); remove = null }) { Text(tr("Αφαίρεση", "Remove")) } },
            dismissButton = { TextButton(onClick = { remove = null }) { Text(tr("Άκυρο", "Cancel")) } }
        )
    }
    if (adminOpen) AdminDialog(vm, ui) { adminOpen = false }
}

@Composable
fun RenameDialog(vm: MainViewModel, d: Device, onDone: () -> Unit) {
    var name by remember { mutableStateOf(d.name) }
    AlertDialog(
        onDismissRequest = onDone,
        title = { Text(tr("Μετονομασία", "Rename")) },
        text = { OutlinedTextField(name, { name = it }, singleLine = true, label = { Text(tr("Όνομα", "Name")) }) },
        confirmButton = {
            TextButton(onClick = {
                if (name.isNotBlank()) vm.post("/api/device", JSONObject().put("id", d.id).put("name", name.trim()))
                onDone()
            }) { Text("OK") }
        },
        dismissButton = { TextButton(onClick = onDone) { Text(tr("Άκυρο", "Cancel")) } }
    )
}

@Composable
fun WifiDialog(vm: MainViewModel, d: Device, onDone: () -> Unit) {
    val scope = rememberCoroutineScope()
    var ssids by remember { mutableStateOf<List<String>>(emptyList()) }
    var ssid by remember { mutableStateOf("") }
    var pwd by remember { mutableStateOf("") }
    var info by remember { mutableStateOf("") }
    val en = LocalEn.current
    AlertDialog(
        onDismissRequest = onDone,
        title = { Text(tr("🔁 Αλλαγή WiFi — ${d.name}", "🔁 Change WiFi — ${d.name}")) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                Text(
                    tr("Ο αισθητήρας θα φύγει από το τωρινό δίκτυο. Μόνο 2.4 GHz. Αν ο κωδικός είναι λάθος θα χρειαστεί Reset.",
                        "The sensor will leave the current network. 2.4 GHz only. A wrong password requires a Reset."),
                    fontSize = 13.sp
                )
                Spacer(Modifier.height(8.dp))
                OutlinedButton(onClick = {
                    info = if (en) "Searching…" else "Αναζήτηση…"
                    scope.launch {
                        runCatching { vm.wifiScan(d.id) }
                            .onSuccess { ssids = it; info = (if (en) "Networks: " else "Δίκτυα: ") + it.size }
                            .onFailure { info = "❌ ${it.message}" }
                    }
                }) { Text(tr("🔍 Δίκτυα που βλέπει ο αισθητήρας", "🔍 Networks the sensor sees")) }
                if (info.isNotBlank()) Text(info, fontSize = 12.sp)
                for (s in ssids.take(12)) {
                    Text("📶 $s", Modifier.fillMaxWidth().clickable { ssid = s }.padding(vertical = 6.dp),
                        fontWeight = if (s == ssid) FontWeight.Bold else FontWeight.Normal)
                }
                OutlinedTextField(ssid, { ssid = it }, singleLine = true, label = { Text(tr("Νέο WiFi (SSID)", "New WiFi (SSID)")) })
                OutlinedTextField(pwd, { pwd = it }, singleLine = true, label = { Text(tr("Κωδικός", "Password")) },
                    visualTransformation = PasswordVisualTransformation())
            }
        },
        confirmButton = {
            TextButton(enabled = ssid.isNotBlank(), onClick = {
                vm.post("/api/device/wifi", JSONObject().put("id", d.id).put("ssid", ssid.trim()).put("pwd", pwd))
                onDone()
            }) { Text(tr("📤 Αποστολή", "📤 Send")) }
        },
        dismissButton = { TextButton(onClick = onDone) { Text(tr("Άκυρο", "Cancel")) } }
    )
}

@Composable
fun WeatherLocationCard(vm: MainViewModel, ui: UiState) {
    val scope = rememberCoroutineScope()
    var q by remember { mutableStateOf("") }
    var results by remember { mutableStateOf<List<Place>>(emptyList()) }
    var info by remember { mutableStateOf("") }
    val w = ui.weather
    HCard {
        Text("📍 " + (w?.place?.ifBlank { null } ?: tr("Δεν έχει οριστεί τοποθεσία", "No location set")), fontWeight = FontWeight.Bold)
        if (!w?.error.isNullOrBlank()) Text(w?.error ?: "", color = BadC, fontSize = 12.sp)
        Spacer(Modifier.height(8.dp))
        Button(onClick = { vm.post("/api/weather/auto") }, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Filled.MyLocation, null); Spacer(Modifier.width(6.dp)); Text(tr("Αυτόματα από τον υπολογιστή", "Automatically from the PC"))
        }
        Text(
            tr("Πρώτα τοποθεσία Windows (WiFi/GPS), αλλιώς από IP (κατά προσέγγιση — με Starlink μπορεί να βγει λάθος).",
                "Windows location (WiFi/GPS) first, else IP (approximate — may be wrong with Starlink)."),
            fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(Modifier.height(8.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(q, { q = it }, Modifier.weight(1f), singleLine = true, label = { Text(tr("Πόλη / χωριό", "City / village")) })
            Spacer(Modifier.width(6.dp))
            IconButton(onClick = {
                if (q.isNotBlank()) {
                    scope.launch {
                        runCatching { vm.geocode(q.trim()) }
                            .onSuccess { results = it; info = if (it.isEmpty()) "—" else "" }
                            .onFailure { info = "❌ ${it.message}" }
                    }
                }
            }) { Icon(Icons.Filled.Search, null) }
        }
        if (info.isNotBlank()) Text(info, fontSize = 12.sp)
        for (r in results) {
            Text(
                "📍 ${r.label}", Modifier.fillMaxWidth().clickable {
                    vm.post("/api/weather/location", JSONObject().put("place", r.label).put("lat", r.lat).put("lon", r.lon).put("enabled", true))
                    results = emptyList()
                }.padding(vertical = 8.dp)
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { vm.post("/api/weather/refresh") }) { Text(tr("⟳ Ανανέωση καιρού", "⟳ Refresh weather")) }
        }
    }
}

@Composable
fun PcSettingsCard(vm: MainViewModel, ui: UiState) {
    val c = ui.config
    if (c == null) {
        HCard { Text(tr("Φόρτωση…", "Loading…")) }
        return
    }
    var poll by remember(c) { mutableStateOf(c.pollSeconds.toString()) }
    var alarms by remember(c) { mutableStateOf(c.alarms.enabled) }
    var tMin by remember(c) { mutableStateOf(c.alarms.tempMin.toString()) }
    var tMax by remember(c) { mutableStateOf(c.alarms.tempMax.toString()) }
    var hMin by remember(c) { mutableStateOf(c.alarms.humMin.toString()) }
    var hMax by remember(c) { mutableStateOf(c.alarms.humMax.toString()) }
    var offline by remember(c) { mutableStateOf(c.alarms.offline) }
    var mail by remember(c) { mutableStateOf(c.email.enabled) }
    var daily by remember(c) { mutableStateOf(c.email.dailyReport) }
    var time by remember(c) { mutableStateOf(c.email.reportTime) }
    var alarmMails by remember(c) { mutableStateOf(c.email.alarmMails) }
    HCard {
        NumField(tr("Μέτρηση κάθε (δευτερόλεπτα)", "Measure every (seconds)"), poll, Modifier.fillMaxWidth()) { poll = it }
        SwitchRow(tr("Ειδοποιήσεις ορίων στον υπολογιστή", "Limit alarms on PC"), tr("+ email αν είναι ενεργό", "+ email if enabled"), alarms) { alarms = it }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            NumField("min °C", tMin, Modifier.weight(1f)) { tMin = it }
            NumField("max °C", tMax, Modifier.weight(1f)) { tMax = it }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            NumField("min %", hMin, Modifier.weight(1f)) { hMin = it }
            NumField("max %", hMax, Modifier.weight(1f)) { hMax = it }
        }
        SwitchRow(tr("Ειδοποίηση offline", "Offline alarm"), checked = offline) { offline = it }
        HorizontalDivider(Modifier.padding(vertical = 6.dp))
        if (!c.email.configured) {
            Text(tr("⚠ Το email δεν έχει ρυθμιστεί στον υπολογιστή (SMTP).", "⚠ Email (SMTP) not configured on the PC."), color = WarnC, fontSize = 12.sp)
        }
        SwitchRow(tr("Email ενεργό", "Email enabled"), checked = mail) { mail = it }
        SwitchRow(tr("Ημερήσια αναφορά", "Daily report"), checked = daily) { daily = it }
        OutlinedTextField(time, { time = it }, singleLine = true, label = { Text(tr("Ώρα αναφοράς (ΩΩ:ΛΛ)", "Report time (HH:MM)")) })
        SwitchRow(tr("Email σε ειδοποίηση ορίου", "Email on alarm"), checked = alarmMails) { alarmMails = it }
        Spacer(Modifier.height(8.dp))
        Button(onClick = {
            val a = JSONObject().put("enabled", alarms).put("offline", offline)
            tMin.toFloatSafe()?.let { a.put("temp_min", it.toDouble()) }
            tMax.toFloatSafe()?.let { a.put("temp_max", it.toDouble()) }
            hMin.toFloatSafe()?.let { a.put("hum_min", it.toDouble()) }
            hMax.toFloatSafe()?.let { a.put("hum_max", it.toDouble()) }
            val body = JSONObject().put("alarms", a)
                .put("email", JSONObject().put("enabled", mail).put("daily_report", daily).put("report_time", time.trim()).put("alarm_mails", alarmMails))
            poll.toIntOrNull()?.let { body.put("poll_seconds", it) }
            vm.saveConfig(body)
        }, modifier = Modifier.fillMaxWidth()) { Text(tr("💾 Αποθήκευση στον υπολογιστή", "💾 Save to PC")) }
    }
}

@Composable
fun AdminDialog(vm: MainViewModel, ui: UiState, onDone: () -> Unit) {
    val scope = rememberCoroutineScope()
    var pw by remember { mutableStateOf("") }
    var err by remember { mutableStateOf("") }
    val unlocked = vm.adminPw != null
    val en = LocalEn.current
    AlertDialog(
        onDismissRequest = onDone,
        title = { Text(tr("🔐 Διαχειριστής", "🔐 Administrator")) },
        text = {
            if (!unlocked) {
                Column {
                    OutlinedTextField(pw, { pw = it }, singleLine = true, label = { Text(tr("Κωδικός διαχειριστή", "Admin password")) },
                        visualTransformation = PasswordVisualTransformation())
                    if (err.isNotBlank()) Text(err, color = BadC, fontSize = 12.sp)
                }
            } else {
                Column(Modifier.verticalScroll(rememberScrollState())) {
                    Text(
                        tr("Τελική = αισθητήρας × πολλαπλασιαστής + offset. Η αρχική τιμή κρατιέται πάντα στον υπολογιστή.",
                            "Final = sensor × multiplier + offset. The original value is always kept on the PC."),
                        fontSize = 12.sp
                    )
                    for (d in ui.status?.devices ?: emptyList()) {
                        HorizontalDivider(Modifier.padding(vertical = 8.dp))
                        CalibEditor(vm, d)
                    }
                    HorizontalDivider(Modifier.padding(vertical = 8.dp))
                    LabelsEditor(vm, ui)
                }
            }
        },
        confirmButton = {
            if (!unlocked) TextButton(onClick = {
                scope.launch {
                    val ok = runCatching { vm.adminCheck(pw) }.getOrDefault(false)
                    if (ok) vm.adminPw = pw else err = if (en) "Wrong password or not set on PC" else "Λάθος κωδικός ή δεν έχει οριστεί στον υπολογιστή"
                }
            }) { Text(tr("Ξεκλείδωμα", "Unlock")) }
            else TextButton(onClick = onDone) { Text(tr("Κλείσιμο", "Close")) }
        },
        dismissButton = {
            if (unlocked) TextButton(onClick = { vm.adminPw = null; onDone() }) { Text(tr("Κλείδωμα", "Lock")) }
            else TextButton(onClick = onDone) { Text(tr("Άκυρο", "Cancel")) }
        }
    )
}

/** Λεκτικά «Μέσα» / «Έξω» — αποθηκεύονται στον υπολογιστή και φαίνονται παντού (PC, web, εφαρμογή). */
@Composable
fun LabelsEditor(vm: MainViewModel, ui: UiState) {
    val cur = ui.weather?.labels ?: gr.nikkpap.airsense.data.Labels()
    var li by remember(cur) { mutableStateOf(cur.inside) }
    var lo by remember(cur) { mutableStateOf(cur.outside) }
    Text(tr("🏷 Λεκτικά", "🏷 Labels"), fontWeight = FontWeight.Bold)
    Text(tr("π.χ. «Σαλόνι» / «Αυλή». Αλλάζουν στον υπολογιστή, στο web και εδώ.",
        "e.g. “Living room” / “Yard”. Changes on the PC, web and here."), fontSize = 12.sp)
    OutlinedTextField(li, { li = it.take(30) }, singleLine = true, label = { Text(tr("Αισθητήρας (μέσα)", "Sensor (inside)")) })
    OutlinedTextField(lo, { lo = it.take(30) }, singleLine = true, label = { Text(tr("Καιρός (έξω)", "Weather (outside)")) })
    Row {
        TextButton(onClick = {
            vm.post("/api/admin/labels", JSONObject().put("admin", vm.adminPw ?: "").put("inside", li).put("outside", lo))
        }) { Text(tr("💾 Αποθήκευση", "💾 Save")) }
        TextButton(onClick = {
            li = gr.nikkpap.airsense.data.Labels.DEF_IN; lo = gr.nikkpap.airsense.data.Labels.DEF_OUT
            vm.post("/api/admin/labels", JSONObject().put("admin", vm.adminPw ?: "").put("inside", li).put("outside", lo))
        }) { Text(tr("↺ Προεπιλογή", "↺ Default")) }
    }
}

@Composable
fun CalibEditor(vm: MainViewModel, d: Device) {
    var cal by remember(d.id) { mutableStateOf<Calib?>(null) }
    var tOff by remember(d.id) { mutableStateOf("0") }
    var tMul by remember(d.id) { mutableStateOf("1") }
    var hOff by remember(d.id) { mutableStateOf("0") }
    var hMul by remember(d.id) { mutableStateOf("1") }
    var recalc by remember(d.id) { mutableIntStateOf(0) }
    LaunchedEffect(d.id) {
        runCatching { vm.calib(d.id) }.onSuccess { c ->
            cal = c
            tOff = c.tOff.toString(); tMul = c.tMul.toString(); hOff = c.hOff.toString(); hMul = c.hMul.toString()
        }
    }
    Text(d.name, fontWeight = FontWeight.Bold)
    val rt = cal?.rawT
    val rh = cal?.rawH
    val nt = rt?.let { r -> (tMul.toFloatSafe() ?: 1f) * r + (tOff.toFloatSafe() ?: 0f) }
    val nh = rh?.let { r -> ((hMul.toFloatSafe() ?: 1f) * r + (hOff.toFloatSafe() ?: 0f)).coerceIn(0.0, 100.0) }
    Text("${tr("Αισθητήρας", "Sensor")}: ${f(rt, 2)}°C ${f(rh, 2)}%  →  ${f(nt, 2)}°C ${f(nh, 2)}%", fontSize = 12.sp, color = OkC)
    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        NumField("Offset °C", tOff, Modifier.weight(1f)) { tOff = it }
        NumField("× °C", tMul, Modifier.weight(1f)) { tMul = it }
    }
    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        NumField("Offset %", hOff, Modifier.weight(1f)) { hOff = it }
        NumField("× %", hMul, Modifier.weight(1f)) { hMul = it }
    }
    Text(tr("Εφαρμογή και στο ιστορικό:", "Apply to history too:"), fontSize = 12.sp)
    FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        for ((h, l) in listOf(0 to tr("Όχι", "No"), 24 to "24ώ", 168 to tr("7 ημ", "7 d"), 720 to tr("30 ημ", "30 d"))) {
            FilterChip(selected = recalc == h, onClick = { recalc = h }, label = { Text(l) })
        }
    }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(onClick = {
            val b = JSONObject().put("admin", vm.adminPw ?: "").put("id", d.id)
                .put("t_off", (tOff.toFloatSafe() ?: 0f).toDouble()).put("t_mul", (tMul.toFloatSafe() ?: 1f).toDouble())
                .put("h_off", (hOff.toFloatSafe() ?: 0f).toDouble()).put("h_mul", (hMul.toFloatSafe() ?: 1f).toDouble())
            if (recalc > 0) b.put("recalc_hours", recalc)
            vm.post("/api/admin/calib", b)
        }) { Text(tr("Εφαρμογή", "Apply")) }
        OutlinedButton(onClick = { tOff = "0"; tMul = "1"; hOff = "0"; hMul = "1" }) { Text(tr("Μηδενισμός", "Reset")) }
    }
}
