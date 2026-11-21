@file:OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)

package gr.nikkpap.airsense.ui

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import gr.nikkpap.airsense.data.Device
import gr.nikkpap.airsense.data.InOut
import gr.nikkpap.airsense.data.Labels
import gr.nikkpap.airsense.data.inOut
import gr.nikkpap.airsense.data.Weather
import gr.nikkpap.airsense.data.f
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

// ═════════════════════════ Ρίζα ═════════════════════════
@Composable
fun App(vm: MainViewModel) {
    val ui by vm.ui.collectAsState()
    HygroTheme(ui.theme, ui.dynamic) {
        CompositionLocalProvider(LocalEn provides ui.en) {
            Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                if (!ui.configured) SetupScreen(vm) else MainScaffold(vm, ui)
            }
        }
    }
}

@Composable
fun MainScaffold(vm: MainViewModel, ui: UiState) {
    var tab by rememberSaveable { mutableIntStateOf(0) }
    val snack = remember { SnackbarHostState() }
    LaunchedEffect(Unit) { vm.messages.collect { snack.showSnackbar(it) } }
    Scaffold(
        snackbarHost = { SnackbarHost(snack) },
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            Modifier.size(10.dp).clip(CircleShape).background(
                                when (ui.online) {
                                    true -> OkC; false -> BadC; else -> Color.Gray
                                }
                            )
                        )
                        Spacer(Modifier.width(10.dp))
                        Text("💧 AirSense", fontWeight = FontWeight.Bold)
                    }
                },
                actions = {
                    if (ui.busy) CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
                    IconButton(onClick = { vm.refreshNow() }) { Icon(Icons.Filled.Refresh, contentDescription = null) }
                }
            )
        },
        bottomBar = {
            NavigationBar {
                val items = listOf(
                    Triple(Icons.Filled.Home, tr("Αρχική", "Home"), 0),
                    Triple(Icons.Filled.Notifications, tr("Ειδοποιήσεις", "Alerts"), 1),
                    Triple(Icons.Filled.Tune, tr("Διαχείριση", "Manage"), 2),
                    Triple(Icons.Filled.Settings, tr("Ρυθμίσεις", "Settings"), 3),
                )
                for ((icon, label, i) in items) {
                    NavigationBarItem(
                        selected = tab == i, onClick = { tab = i },
                        icon = { Icon(icon, contentDescription = label) }, label = { Text(label) }
                    )
                }
            }
        }
    ) { pad ->
        Box(Modifier.padding(pad)) {
            when (tab) {
                0 -> HomeScreen(vm, ui)
                1 -> AlertsScreen(vm, ui)
                2 -> ManageScreen(vm, ui)
                else -> SettingsScreen(vm, ui)
            }
        }
    }
}

// ═════════════════════════ Κοινά ═════════════════════════
@Composable
fun SectionTitle(text: String) {
    Text(
        text.uppercase(), style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(start = 4.dp, top = 14.dp, bottom = 6.dp)
    )
}

@Composable
fun HCard(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Card(modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp)) {
        Column(Modifier.padding(16.dp), content = content)
    }
}

@Composable
fun StatusPill(text: String, color: Color) {
    Text(
        text, color = color, fontSize = 12.sp,
        modifier = Modifier.clip(RoundedCornerShape(50)).background(color.copy(alpha = 0.15f))
            .padding(horizontal = 10.dp, vertical = 3.dp)
    )
}

fun agoText(ts: Double?, en: Boolean): String {
    if (ts == null) return if (en) "never" else "ποτέ"
    val s = (System.currentTimeMillis() / 1000.0 - ts).toLong()
    return when {
        s < 60 -> if (en) "$s s ago" else "$s δευτ. πριν"
        s < 3600 -> if (en) "${s / 60} min ago" else "${s / 60} λεπτά πριν"
        else -> SimpleDateFormat("dd/MM HH:mm", Locale.getDefault()).format(Date((ts * 1000).toLong()))
    }
}

fun openUrl(ctx: android.content.Context, url: String) {
    runCatching { ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
}

fun isTailscaleHost(raw: String): Boolean {
    val host = raw.substringAfter("://").substringBefore("/").substringBefore(":")
    if (host.endsWith(".ts.net")) return true
    val parts = host.split(".")
    if (parts.size == 4 && parts[0] == "100") {
        val b = parts[1].toIntOrNull() ?: return false
        return b in 64..127
    }
    return false
}

// ═════════════════════════ Σύνδεση (πρώτη φορά + ρυθμίσεις) ═════════════════════════
@Composable
fun ConnectionForm(vm: MainViewModel, onConnected: () -> Unit = {}) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var local by remember { mutableStateOf(vm.prefs.localUrl) }
    var ts by remember { mutableStateOf(vm.prefs.tsUrl) }
    var pin by remember { mutableStateOf(vm.prefs.pin) }
    var result by remember { mutableStateOf<String?>(null) }
    var ok by remember { mutableStateOf(false) }
    var testing by remember { mutableStateOf(false) }
    val en = LocalEn.current

    fun scan() {
        val opts = GmsBarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE).build()
        GmsBarcodeScanning.getClient(ctx, opts).startScan()
            .addOnSuccessListener { b ->
                val raw = b.rawValue ?: return@addOnSuccessListener
                if (isTailscaleHost(raw)) ts = raw else local = raw
                result = (if (en) "QR read: " else "Διαβάστηκε QR: ") + raw
            }
            .addOnFailureListener { e -> result = e.message }
    }

    OutlinedTextField(
        local, { local = it }, Modifier.fillMaxWidth(), singleLine = true,
        label = { Text(tr("Διεύθυνση στο ίδιο WiFi", "Local address (same WiFi)")) },
        placeholder = { Text("http://192.168.1.10:8765") },
        leadingIcon = { Icon(Icons.Filled.Wifi, null) }
    )
    Spacer(Modifier.height(8.dp))
    OutlinedTextField(
        ts, { ts = it }, Modifier.fillMaxWidth(), singleLine = true,
        label = { Text(tr("Διεύθυνση Tailscale (από παντού)", "Tailscale address (anywhere)")) },
        placeholder = { Text("http://100.x.y.z:8765") },
        leadingIcon = { Icon(Icons.Filled.Public, null) }
    )
    Spacer(Modifier.height(8.dp))
    OutlinedTextField(
        pin, { pin = it }, Modifier.fillMaxWidth(), singleLine = true,
        label = { Text(tr("PIN (αν έχει οριστεί στον υπολογιστή)", "PIN (if set on PC)")) },
        visualTransformation = PasswordVisualTransformation(),
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
        leadingIcon = { Icon(Icons.Filled.Lock, null) }
    )
    Spacer(Modifier.height(12.dp))
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedButton(onClick = { scan() }) {
            Icon(Icons.Filled.QrCodeScanner, null); Spacer(Modifier.width(6.dp)); Text(tr("Σκανάρισμα QR", "Scan QR"))
        }
        Button(enabled = !testing, onClick = {
            vm.saveConnection(local, ts, pin)
            testing = true
            result = if (en) "Testing…" else "Δοκιμή…"
            scope.launch {
                val err = vm.testConnection()
                testing = false
                ok = err == null
                result = if (ok) (if (en) "✅ Connected!" else "✅ Συνδέθηκε!") else "❌ $err"
                if (ok) onConnected()
            }
        }) { Icon(Icons.Filled.Check, null); Spacer(Modifier.width(6.dp)); Text(tr("Δοκιμή & αποθήκευση", "Test & save")) }
    }
    result?.let {
        Spacer(Modifier.height(10.dp))
        Text(it, color = if (ok) OkC else MaterialTheme.colorScheme.onSurface)
    }
}

@Composable
fun SetupScreen(vm: MainViewModel) {
    var connected by remember { mutableStateOf(false) }
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).systemBarsPadding().padding(20.dp)
    ) {
        Text("💧", fontSize = 56.sp)
        Text(tr("Καλώς ήρθες στο AirSense", "Welcome to AirSense"), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(8.dp))
        Text(
            tr(
                "Βλέπεις θερμοκρασία, υγρασία και καιρό από τους αισθητήρες BleBox, με ειδοποιήσεις και διαχείριση.",
                "See temperature, humidity and weather from your BleBox sensors, with alerts and management."
            ), color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(Modifier.height(16.dp))
        HCard {
            Text(tr("Βήματα", "Steps"), fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(6.dp))
            Text(
                tr(
                    "1. Στον υπολογιστή άνοιξε το AirSense → καρτέλα «📱 Κινητό».\n" +
                            "2. Πάτα «Σκανάρισμα QR» εδώ και σκάναρε το QR από την οθόνη.\n" +
                            "3. Για πρόσβαση από παντού: Tailscale σε υπολογιστή + κινητό (ίδιος λογαριασμός) και σκάναρε και το QR «Tailscale».\n" +
                            "4. Πάτα «Δοκιμή & αποθήκευση».",
                    "1. On the PC open AirSense → tab “📱 Mobile”.\n" +
                            "2. Tap “Scan QR” here and scan the QR on the screen.\n" +
                            "3. For access from anywhere: Tailscale on PC + phone (same account), scan the “Tailscale” QR too.\n" +
                            "4. Tap “Test & save”."
                ), lineHeight = 22.sp
            )
        }
        Spacer(Modifier.height(16.dp))
        ConnectionForm(vm) { connected = true }
        Spacer(Modifier.height(20.dp))
        Button(onClick = { vm.finishSetup() }, enabled = connected, modifier = Modifier.fillMaxWidth().height(52.dp)) {
            Text(tr("Συνέχεια ▶", "Continue ▶"), fontSize = 16.sp)
        }
        Spacer(Modifier.height(16.dp))
        Text("Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
    }
}

// ═════════════════════════ Αρχική ═════════════════════════
@Composable
fun HomeScreen(vm: MainViewModel, ui: UiState) {
    val ctx = LocalContext.current
    val en = LocalEn.current
    val st = ui.status
    LazyColumn(contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if (ui.online == false) {
            item {
                HCard {
                    Text(tr("⚠ Ο υπολογιστής δεν απαντά", "⚠ PC not reachable"), color = BadC, fontWeight = FontWeight.Bold)
                    Text(ui.error ?: "", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
                    Text(
                        tr("Είναι ανοιχτός ο υπολογιστής και το AirSense; Είσαι στο ίδιο WiFi ή με Tailscale;",
                            "Is the PC and AirSense running? Same WiFi or Tailscale on?"), fontSize = 13.sp
                    )
                }
            }
        }
        ui.weather?.let { w -> if (w.enabled && w.current != null) item { WeatherCard(w) } }
        if (st != null && st.devices.isEmpty()) {
            item {
                HCard {
                    Text(tr("Δεν υπάρχουν αισθητήρες ακόμα.", "No sensors yet."), fontWeight = FontWeight.Bold)
                    Text(tr("Πάτα «Σάρωση δικτύου» ή χρησιμοποίησε τον Οδηγό στον υπολογιστή.",
                        "Tap “Scan network” or use the Wizard on the PC."))
                    Spacer(Modifier.height(8.dp))
                    Button(onClick = { vm.post("/api/scan") }) { Text(tr("📡 Σάρωση δικτύου", "📡 Scan network")) }
                }
            }
        }
        items(st?.devices ?: emptyList(), key = { it.id }) { d ->
            DeviceCard(d, d.id == ui.selected, en, ui.weather) { vm.select(d.id) }
        }
        if (st != null && st.devices.isNotEmpty()) {
            item {
                HCard {
                    Text(tr("Γράφημα", "Chart"), fontWeight = FontWeight.Bold)
                    if (st.devices.size > 1) {
                        LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            items(st.devices, key = { it.id }) { d ->
                                FilterChip(selected = d.id == ui.selected, onClick = { vm.select(d.id) }, label = { Text(d.name) })
                            }
                        }
                    }
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        for ((h, l) in listOf(1 to tr("1ώ", "1h"), 6 to tr("6ώ", "6h"), 24 to tr("24ώ", "24h"),
                            168 to tr("7 ημ", "7 d"), 720 to tr("30 ημ", "30 d"))) {
                            FilterChip(selected = ui.hours == h, onClick = { vm.setHours(h) }, label = { Text(l) })
                        }
                    }
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text("● " + tr("Θερμ.", "Temp") + " · " + lblIn(ui.weather?.labels), color = TempC, fontSize = 12.sp)
                        Text("● " + tr("Υγρασία", "Humidity") + " · " + lblIn(ui.weather?.labels), color = HumC, fontSize = 12.sp)
                        Text("┄ " + tr("Δρόσος", "Dew"), color = DewC, fontSize = 12.sp)
                        Text("┄ " + lblOut(ui.weather?.labels), color = OutTC, fontSize = 12.sp)
                        Text("▮ " + tr("Βροχή", "Rain"), color = HumC.copy(alpha = .7f), fontSize = 12.sp)
                    }
                    val ts = ui.points.mapNotNull { it.t }
                    val hs = ui.points.mapNotNull { it.h }
                    if (ts.isNotEmpty()) {
                        Text(
                            "${tr("Θερμ.", "Temp")} ${f(ts.min())}…${f(ts.max())} °C · ${tr("Υγρ.", "Hum.")} ${f(hs.minOrNull())}…${f(hs.maxOrNull())} %",
                            fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    Spacer(Modifier.height(6.dp))
                    HygroChart(ui.points, ui.wxPoints, outLabel = lblOut(ui.weather?.labels))
                }
            }
            item {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { vm.post("/api/poll") }) { Icon(Icons.Filled.Refresh, null); Spacer(Modifier.width(6.dp)); Text(tr("Μέτρηση τώρα", "Measure now")) }
                    OutlinedButton(onClick = { openUrl(ctx, vm.exportUrl("csv")) }) { Icon(Icons.Filled.Download, null); Spacer(Modifier.width(6.dp)); Text("CSV") }
                    OutlinedButton(onClick = { openUrl(ctx, vm.exportUrl("xml")) }) { Icon(Icons.Filled.Download, null); Spacer(Modifier.width(6.dp)); Text("XML") }
                    Button(onClick = { openUrl(ctx, vm.exportUrl("pdf")) }) { Icon(Icons.Filled.Download, null); Spacer(Modifier.width(6.dp)); Text("PDF") }
                }
            }
        }
        item { Spacer(Modifier.height(8.dp)) }
    }
}

@Composable
fun DeviceCard(d: Device, selected: Boolean, en: Boolean, w: Weather? = null, onClick: () -> Unit) {
    Card(
        Modifier.fillMaxWidth().clickable { onClick() }, shape = RoundedCornerShape(18.dp),
        border = if (selected) androidx.compose.foundation.BorderStroke(1.5.dp, Brand) else null
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(d.name, fontWeight = FontWeight.Bold, fontSize = 17.sp, modifier = Modifier.weight(1f))
                when (d.online) {
                    true -> StatusPill("online", OkC)
                    false -> StatusPill("offline", BadC)
                    else -> StatusPill("…", Color.Gray)
                }
            }
            Spacer(Modifier.height(10.dp))
            Row(verticalAlignment = Alignment.Bottom) {
                Text(f(d.t), color = TempC, fontSize = 42.sp, fontWeight = FontWeight.Bold)
                Text(" °C", color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(bottom = 8.dp))
                Spacer(Modifier.width(22.dp))
                Text(f(d.h), color = HumC, fontSize = 42.sp, fontWeight = FontWeight.Bold)
                Text(" %", color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(bottom = 8.dp))
            }
            Text(
                "${if (en) "Dew point" else "Σημείο δρόσου"} ${f(d.dp)} °C · ${if (en) "Abs." else "Απόλυτη"} ${f(d.ah)} g/m³",
                fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            val cw = w?.takeIf { it.enabled }?.current
            inOut(d.t, d.h, cw?.temp, cw?.hum)?.let { io -> InOutBox(io, w?.labels) }
            Text("${d.ip} · ${agoText(d.ts, en)}", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (d.online == false && d.error.isNotBlank()) Text(d.error, fontSize = 12.sp, color = BadC)
        }
    }
}

fun sg(x: Double, d: Int = 1): String = (if (x > 0.05) "+" else "") + f(x, d)

/** Διαφορά μέσα–έξω + συμβουλή αερισμού (με βάση την απόλυτη υγρασία) */
@Composable
fun InOutBox(io: InOut, l: Labels?) {
    val li = lblIn(l); val lo = lblOut(l)
    val (col, msg) = when (io.vent) {
        1 -> OkC to tr("Αερισμός → ΜΕΙΩΝΕΙ την υγρασία ($li)", "Ventilating → LOWERS humidity ($li)")
        -1 -> WarnC to tr("Αερισμός → ΑΥΞΑΝΕΙ την υγρασία ($li)", "Ventilating → RAISES humidity ($li)")
        else -> MaterialTheme.colorScheme.onSurfaceVariant to tr("Ο αερισμός δεν αλλάζει σχεδόν την υγρασία",
            "Ventilating barely changes humidity")
    }
    Column(
        Modifier.padding(vertical = 8.dp).fillMaxWidth().clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = .6f)).padding(10.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("↕ $li − $lo  ", fontSize = 13.sp, fontWeight = FontWeight.Bold)
            Text("${sg(io.dt)}°C", color = TempC, fontSize = 15.sp, fontWeight = FontWeight.Bold)
            Text("  ·  ", fontSize = 13.sp)
            Text("${sg(io.dh)}%", color = HumC, fontSize = 15.sp, fontWeight = FontWeight.Bold)
        }
        Text(
            "${tr("Απόλυτη", "Absolute")} ${f(io.ahIn)} / ${f(io.ahOut)} g/m³  ($li / $lo)",
            fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text("💨 $msg", fontSize = 13.sp, color = col, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
fun WeatherCard(w: Weather) {
    val c = w.current ?: return
    HCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(c.icon, fontSize = 52.sp)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text("${f(c.temp)}°C", fontSize = 32.sp, fontWeight = FontWeight.Bold, color = OutTC)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(c.text, fontSize = 14.sp)
                    Spacer(Modifier.width(8.dp))
                    StatusPill(wxStatus(c.status), Brand)
                }
            }
        }
        Spacer(Modifier.height(6.dp))
        Text("${lblOut(w.labels)} · 📍 ${w.place}", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(
            "${tr("Αίσθηση", "Feels")} ${f(c.feels)}°C · 💧 ${f(c.hum, 0)}% · 🌬 ${f(c.wind, 0)} km/h · ☁ ${f(c.cloud, 0)}%",
            fontSize = 13.sp
        )
        val sun = c.sunshine?.let { "${(it / 60).toInt()} ${tr("λεπτά/ώρα", "min/h")}" } ?: "—"
        Text("🌧 ${f(c.rain)} mm · ❄ ${f(c.snow)} cm · ☀ $sun", fontSize = 13.sp)
        Spacer(Modifier.height(10.dp))
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            items(w.daily) { d ->
                Column(
                    Modifier.clip(RoundedCornerShape(12.dp)).background(MaterialTheme.colorScheme.surfaceVariant)
                        .padding(10.dp).width(78.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(d.day, fontWeight = FontWeight.Bold, fontSize = 12.sp, textAlign = TextAlign.Center, maxLines = 1)
                    Text(d.icon, fontSize = 26.sp)
                    Text("${f(d.tmin, 0)}° / ${f(d.tmax, 0)}°", fontSize = 12.sp)
                    Text("🌧 ${f(d.precip)}", fontSize = 11.sp)
                    d.prob?.let { Text("${it.toInt()}%", fontSize = 11.sp, color = HumC) }
                    if ((d.snow ?: 0.0) > 0) Text("❄ ${f(d.snow)}", fontSize = 11.sp)
                    d.sunshine?.let { Text("☀ ${f(it / 3600)} ${tr("ώ", "h")}", fontSize = 11.sp) }
                }
            }
        }
        Text("Open-Meteo.com", fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 6.dp))
    }
}
