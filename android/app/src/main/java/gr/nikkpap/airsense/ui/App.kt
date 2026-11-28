@file:OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)

package gr.nikkpap.airsense.ui

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.text.TextAutoSize
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.grid.items
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
import androidx.compose.ui.zIndex
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

/** Tablet / foldable / landscape: side rail + several columns. */
@Composable
@ReadOnlyComposable
fun isWide(): Boolean = LocalConfiguration.current.screenWidthDp >= 600

private data class NavItem(val icon: androidx.compose.ui.graphics.vector.ImageVector, val label: String)

@Composable
fun MainScaffold(vm: MainViewModel, ui: UiState, startTab: Int = 0) {
    var tab by rememberSaveable { mutableIntStateOf(startTab) }
    val snack = remember { SnackbarHostState() }
    LaunchedEffect(Unit) { vm.messages.collect { snack.showSnackbar(it) } }
    // OTA: "new version" dialog (automatic check on start)
    val up = ui.update
    if (ui.updateDialog && up != null) {
        AlertDialog(
            onDismissRequest = { vm.dismissUpdateDialog() },
            title = { Text(tr("🆕 Νέα έκδοση AirSense v${up.version}", "🆕 New AirSense version v${up.version}")) },
            text = {
                Column(Modifier.heightIn(max = 320.dp).verticalScroll(rememberScrollState())) {
                    Text(tr("Έχεις τη v${gr.nikkpap.airsense.BuildConfig.VERSION_NAME}. Θες να την ενημερώσεις τώρα;",
                        "You have v${gr.nikkpap.airsense.BuildConfig.VERSION_NAME}. Update now?"))
                    if (up.notes.isNotBlank()) {
                        Spacer(Modifier.height(8.dp))
                        Text(up.notes, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            },
            confirmButton = { Button(onClick = { vm.downloadAndInstall() }) { Text(tr("Ενημέρωση", "Update")) } },
            dismissButton = { TextButton(onClick = { vm.dismissUpdateDialog() }) { Text(tr("Αργότερα", "Later")) } }
        )
    }
    val wide = isWide()
    val items = listOf(
        NavItem(Icons.Filled.Home, tr("Αρχική", "Home")),
        NavItem(Icons.Filled.Notifications, tr("Ειδοποιήσεις", "Alerts")),
        NavItem(Icons.Filled.Tune, tr("Διαχείριση", "Manage")),
        NavItem(Icons.Filled.Settings, tr("Ρυθμίσεις", "Settings")),
    )
    Scaffold(
        snackbarHost = { SnackbarHost(snack) },
        topBar = { AppTopBar(vm, ui) },
        bottomBar = {
            if (!wide) NavigationBar {
                items.forEachIndexed { i, it ->
                    NavigationBarItem(
                        selected = tab == i, onClick = { tab = i },
                        icon = { Icon(it.icon, contentDescription = it.label) },
                        label = { Text(it.label, maxLines = 1, overflow = TextOverflow.Ellipsis, fontSize = 11.sp) }
                    )
                }
            }
        }
    ) { pad ->
        Row(Modifier.padding(pad).fillMaxSize()) {
            if (wide) {
                NavigationRail(containerColor = MaterialTheme.colorScheme.surfaceContainerLow) {
                    Spacer(Modifier.height(8.dp))
                    items.forEachIndexed { i, it ->
                        NavigationRailItem(
                            selected = tab == i, onClick = { tab = i },
                            icon = { Icon(it.icon, contentDescription = it.label) },
                            label = { Text(it.label, maxLines = 1, fontSize = 11.sp) }
                        )
                    }
                }
            }
            Box(Modifier.weight(1f).fillMaxHeight(), contentAlignment = Alignment.TopCenter) {
                Box(Modifier.widthIn(max = 1280.dp).fillMaxSize()) {
                    when (tab) {
                        0 -> HomeScreen(vm, ui) { tab = 3 }
                        1 -> AlertsScreen(vm, ui)
                        2 -> ManageScreen(vm, ui)
                        else -> SettingsScreen(vm, ui)
                    }
                    ui.updateProgress?.let { p ->
                        if (p >= 0f) LinearProgressIndicator(progress = { p }, modifier = Modifier.fillMaxWidth().zIndex(1f))
                        else LinearProgressIndicator(Modifier.fillMaxWidth().zIndex(1f))
                    }
                }
            }
        }
    }
}

/** Top bar: status dot + how we are connected (🏠 / 🌍) + Tailscale, theme, refresh. */
@Composable
fun AppTopBar(vm: MainViewModel, ui: UiState) {
    val en = LocalEn.current
    val dot = when (ui.online) { true -> OkC; false -> BadC; else -> MaterialTheme.colorScheme.outline }
    val sub = when {
        ui.online == true && ui.route == "tailscale" -> "🌍 Tailscale"
        ui.online == true -> tr("🏠 Τοπικό δίκτυο", "🏠 Local network")
        ui.online == false -> tr("Εκτός σύνδεσης", "Offline") + if (ui.lastOk > 0) " · " + agoText(ui.lastOk / 1000.0, en) else ""
        else -> tr("Σύνδεση…", "Connecting…")
    }
    TopAppBar(
        colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(10.dp).clip(CircleShape).background(dot))
                Spacer(Modifier.width(10.dp))
                Column {
                    Text("AirSense", fontWeight = FontWeight.Bold, fontSize = 20.sp, maxLines = 1)
                    Text(sub, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1,
                        overflow = TextOverflow.Ellipsis)
                }
            }
        },
        actions = {
            if (ui.busy) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
            if (ui.tsInstalled) {
                IconButton(onClick = { vm.toggleTailscale() }) {
                    Icon(Icons.Filled.VpnKey, contentDescription = "Tailscale",
                        tint = if (ui.tsVpn) OkC else MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            IconButton(onClick = { vm.setTheme(nextTheme(ui.theme)) }) {
                Icon(
                    when (ui.theme) {
                        "dark" -> Icons.Filled.DarkMode; "light" -> Icons.Filled.LightMode
                        "time" -> Icons.Filled.Schedule; else -> Icons.Filled.BrightnessAuto
                    },
                    contentDescription = tr("Θέμα", "Theme")
                )
            }
            IconButton(onClick = { vm.refreshNow() }) { Icon(Icons.Filled.Refresh, contentDescription = tr("Ανανέωση", "Refresh")) }
        }
    )
}

// ═════════════════════════ Κοινά ═════════════════════════
@Composable
fun SectionTitle(text: String) {
    Text(
        text.uppercase(), style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold,
        color = MaterialTheme.colorScheme.onSurfaceVariant, letterSpacing = 0.8.sp,
        modifier = Modifier.padding(start = 4.dp, top = 6.dp)
    )
}

@Composable
fun HCard(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHighest),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)
    ) {
        Column(Modifier.padding(16.dp), content = content)
    }
}

/** Responsive list: 1 column on phones, 2–3 on tablets / landscape (each card min 340 dp). */
@Composable
fun ResponsiveGrid(content: androidx.compose.foundation.lazy.grid.LazyGridScope.() -> Unit) {
    androidx.compose.foundation.lazy.grid.LazyVerticalGrid(
        columns = androidx.compose.foundation.lazy.grid.GridCells.Adaptive(340.dp),
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        content = content
    )
}

/** A grid item that takes the whole row (titles, charts, lists). */
fun androidx.compose.foundation.lazy.grid.LazyGridScope.full(key: Any? = null, content: @Composable () -> Unit) =
    item(key = key, span = { androidx.compose.foundation.lazy.grid.GridItemSpan(maxLineSpan) }) { content() }

@Composable
fun StatusPill(text: String, color: Color) {
    Text(
        text, color = color, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, maxLines = 1,
        modifier = Modifier.clip(RoundedCornerShape(50)).background(color.copy(alpha = 0.14f))
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
        label = { Text(tr("Tailscale (από παντού): 100.x ή όνομα .ts.net", "Tailscale (anywhere): 100.x or .ts.net name")) },
        placeholder = { Text("airsense.tailXXXX.ts.net  ή / or  100.x.y.z") },
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
    // 🔍 one tap: find the server on this WiFi, save, test
    Button(
        enabled = !testing, modifier = Modifier.fillMaxWidth(),
        onClick = {
            testing = true
            ok = false
            result = if (en) "🔍 Looking on your WiFi…" else "🔍 Ψάχνω στο WiFi σου…"
            scope.launch {
                val (url, err) = vm.autoFind { d, n ->
                    if (d % 16 == 0 || d == n) scope.launch { result = (if (en) "🔍 Looking… " else "🔍 Ψάχνω… ") + "$d/$n" }
                }
                testing = false
                if (url != null) { local = url; ts = vm.prefs.tsUrl }
                ok = url != null && err == null
                result = when {
                    url == null -> "❌ $err"
                    err == null -> (if (en) "✅ Found and connected: " else "✅ Βρέθηκε και συνδέθηκε: ") + url +
                            (if (vm.prefs.tsUrl.isNotBlank()) (if (en) "\n🌍 Tailscale too: " else "\n🌍 Και Tailscale: ") + vm.prefs.tsUrl else "")
                    err.contains("PIN", ignoreCase = true) -> (if (en) "🔒 Found $url — type the PIN and tap Test & save" else "🔒 Βρέθηκε $url — γράψε το PIN και πάτα Δοκιμή & αποθήκευση")
                    else -> "❌ $url: $err"
                }
                if (ok) onConnected()
            }
        }
    ) { Icon(Icons.Filled.Search, null); Spacer(Modifier.width(6.dp)); Text(tr("Βρες αυτόματα (ίδιο WiFi)", "Find automatically (same WiFi)")) }
    Spacer(Modifier.height(8.dp))
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
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) { Column(
        Modifier.widthIn(max = 640.dp).fillMaxSize().verticalScroll(rememberScrollState()).systemBarsPadding().imePadding().padding(20.dp)
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
                    "1. Το κινητό στο ίδιο WiFi με την πλακέτα / τον υπολογιστή του AirSense.\n" +
                            "2. Πάτα «🔍 Βρες αυτόματα» — τα υπόλοιπα (και τη διεύθυνση Tailscale) τα βρίσκει μόνο του.\n" +
                            "3. Αν ζητήσει PIN, γράψ' το και πάτα «Δοκιμή & αποθήκευση».\n" +
                            "Εναλλακτικά: «Σκανάρισμα QR» από το PC (καρτέλα «📱 Κινητό») ή από `airsense qr`.",
                    "1. Phone on the same WiFi as the AirSense board / PC.\n" +
                            "2. Tap “🔍 Find automatically” — it finds the rest by itself (the Tailscale address too).\n" +
                            "3. If it asks for a PIN, type it and tap “Test & save”.\n" +
                            "Or: “Scan QR” from the PC (tab “📱 Mobile”) or from `airsense qr`."
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
    } }
}

// ═════════════════════════ Αρχική ═════════════════════════
@Composable
fun HomeScreen(vm: MainViewModel, ui: UiState, onOpenSettings: () -> Unit = {}) {
    val ctx = LocalContext.current
    val en = LocalEn.current
    val st = ui.status
    PullToRefreshBox(isRefreshing = ui.refreshing, onRefresh = { vm.refreshNow() }, modifier = Modifier.fillMaxSize()) {
        ResponsiveGrid {
            if (ui.online == false) full("offline") { OfflineCard(vm, ui, onOpenSettings) }
            ui.weather?.let { w -> if (w.enabled && w.current != null) item(key = "wx") { WeatherCard(w) } }
            if (st != null && st.devices.isEmpty()) {
                full("empty") {
                    HCard {
                        Text(tr("Δεν υπάρχουν αισθητήρες ακόμα", "No sensors yet"), fontWeight = FontWeight.Bold)
                        Text(tr("Πάτα «Σάρωση δικτύου» ή χρησιμοποίησε τον Οδηγό στον υπολογιστή.",
                            "Tap “Scan network” or use the Wizard on the PC."),
                            fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.height(10.dp))
                        Button(onClick = { vm.post("/api/scan") }) {
                            Icon(Icons.Filled.Search, null); Spacer(Modifier.width(8.dp)); Text(tr("Σάρωση δικτύου", "Scan network"))
                        }
                    }
                }
            }
            if (st == null && ui.online == null) full("loading") {
                Box(Modifier.fillMaxWidth().padding(40.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            }
            items(st?.devices ?: emptyList(), key = { it.id }) { d ->
                DeviceCard(d, d.id == ui.selected && (st?.devices?.size ?: 0) > 1, en, ui.weather) { vm.select(d.id) }
            }
            if (st != null && st.devices.isNotEmpty()) {
                full("chart") { ChartCard(vm, ui) }
                full("actions") {
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = { vm.post("/api/poll") }) {
                            Icon(Icons.Filled.Refresh, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text(tr("Μέτρηση τώρα", "Measure now"))
                        }
                        for (k in listOf("pdf", "csv", "xml")) {
                            OutlinedButton(onClick = { openUrl(ctx, vm.exportUrl(k)) }) {
                                Icon(Icons.Filled.Download, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text(k.uppercase())
                            }
                        }
                    }
                }
            }
            full("end") { Spacer(Modifier.height(8.dp)) }
        }
    }
}

/** The PC / board does not answer: why, and one-tap fixes. */
@Composable
fun OfflineCard(vm: MainViewModel, ui: UiState, onOpenSettings: () -> Unit) {
    val bad = BadC
    Card(
        Modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = bad.copy(alpha = 0.10f)),
        border = BorderStroke(1.dp, bad.copy(alpha = 0.45f))
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.CloudOff, null, tint = bad)
                Spacer(Modifier.width(10.dp))
                Text(tr("Ο server του AirSense δεν απαντά", "AirSense server not reachable"), color = bad, fontWeight = FontWeight.Bold)
            }
            if (!ui.error.isNullOrBlank()) {
                Text(ui.error, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp, maxLines = 2,
                    overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 4.dp))
            }
            Text(
                if (ui.tsInstalled && !ui.tsVpn)
                    tr("Είσαι εκτός σπιτιού; Άνοιξε το Tailscale.", "Away from home? Turn Tailscale on.")
                else tr("Είναι αναμμένη η πλακέτα / το PC; Είσαι στο ίδιο WiFi ή με Tailscale;",
                    "Is the board / PC on? Same WiFi or Tailscale on?"),
                fontSize = 13.sp, modifier = Modifier.padding(top = 6.dp)
            )
            Spacer(Modifier.height(10.dp))
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (ui.tsInstalled && !ui.tsVpn) {
                    Button(onClick = { vm.toggleTailscale() }) {
                        Icon(Icons.Filled.VpnKey, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text(tr("Άνοιγμα Tailscale", "Turn on Tailscale"))
                    }
                }
                OutlinedButton(onClick = { vm.refreshNow() }) {
                    Icon(Icons.Filled.Refresh, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text(tr("Ξανά", "Retry"))
                }
                TextButton(onClick = onOpenSettings) { Text(tr("Ρυθμίσεις σύνδεσης", "Connection settings")) }
            }
        }
    }
}

@Composable
fun ChartCard(vm: MainViewModel, ui: UiState) {
    val st = ui.status ?: return
    HCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(tr("Γράφημα", "Chart"), fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
            val ts = ui.points.mapNotNull { it.t }
            val hs = ui.points.mapNotNull { it.h }
            if (ts.isNotEmpty()) {
                Text("${f(ts.min())}…${f(ts.max())}°C · ${f(hs.minOrNull(), 0)}…${f(hs.maxOrNull(), 0)}%",
                    fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
            }
        }
        if (st.devices.size > 1) {
            Spacer(Modifier.height(6.dp))
            LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                items(st.devices, key = { it.id }) { d ->
                    FilterChip(selected = d.id == ui.selected, onClick = { vm.select(d.id) },
                        label = { Text(d.name, maxLines = 1, overflow = TextOverflow.Ellipsis) })
                }
            }
        }
        Spacer(Modifier.height(4.dp))
        val ranges = listOf(1 to tr("1ώ", "1h"), 6 to tr("6ώ", "6h"), 24 to tr("24ώ", "24h"), 168 to tr("7 ημ", "7 d"), 720 to tr("30 ημ", "30 d"))
        LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            items(ranges) { (h, l) ->
                FilterChip(selected = ui.hours == h, onClick = { vm.setHours(h) }, label = { Text(l) })
            }
        }
        FlowRow(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.padding(vertical = 4.dp)) {
            Legend("●", tr("Θερμ.", "Temp") + " · " + lblIn(ui.weather?.labels), TempC)
            Legend("●", tr("Υγρασία", "Humidity"), HumC)
            Legend("┄", tr("Δρόσος", "Dew"), DewC)
            Legend("┄", lblOut(ui.weather?.labels), OutTC)
            Legend("▮", tr("Βροχή", "Rain"), HumC.copy(alpha = .75f))
        }
        HygroChart(ui.points, ui.wxPoints, outLabel = lblOut(ui.weather?.labels))
        Text(tr("Άγγιξε ή σύρε στο γράφημα για τιμές", "Touch or drag on the chart for values"),
            fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun Legend(mark: String, text: String, color: Color) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(mark, color = color, fontSize = 12.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.width(4.dp))
        Text(text, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
    }
}

/** Big value that shrinks by itself so it never overflows (narrow phones, -12.3, 100.0). */
@Composable
fun Metric(modifier: Modifier, label: String, value: String, unit: String, color: Color) {
    Column(
        modifier.clip(RoundedCornerShape(14.dp)).background(color.copy(alpha = if (LocalDark.current) 0.12f else 0.08f))
            .padding(horizontal = 12.dp, vertical = 10.dp)
    ) {
        Text(label, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Row(verticalAlignment = Alignment.Bottom) {
            BasicText(
                value, modifier = Modifier.weight(1f, fill = false), maxLines = 1,
                style = TextStyle(color = color, fontWeight = FontWeight.Bold),
                autoSize = TextAutoSize.StepBased(minFontSize = 18.sp, maxFontSize = 38.sp)
            )
            Text(unit, color = color, fontSize = 15.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(start = 2.dp, bottom = 4.dp))
        }
    }
}

@Composable
private fun SmallStat(modifier: Modifier, label: String, value: String) {
    Column(modifier) {
        Text(label, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Text(value, fontSize = 14.sp, fontWeight = FontWeight.SemiBold, maxLines = 1)
    }
}

@Composable
fun DeviceCard(d: Device, selected: Boolean, en: Boolean, w: Weather? = null, onClick: () -> Unit) {
    Card(
        Modifier.fillMaxWidth().clickable { onClick() }, shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHighest),
        border = BorderStroke(if (selected) 2.dp else 1.dp, if (selected) Brand else MaterialTheme.colorScheme.outlineVariant)
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(d.name, fontWeight = FontWeight.Bold, fontSize = 17.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text("${d.ip} · ${agoText(d.ts, en)}", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                Spacer(Modifier.width(8.dp))
                when (d.online) {
                    true -> StatusPill("online", OkC)
                    false -> StatusPill("offline", BadC)
                    else -> StatusPill("…", MaterialTheme.colorScheme.outline)
                }
            }
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Metric(Modifier.weight(1f), tr("Θερμοκρασία", "Temperature"), f(d.t), "°C", TempC)
                Metric(Modifier.weight(1f), tr("Υγρασία", "Humidity"), f(d.h), "%", HumC)
            }
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                SmallStat(Modifier.weight(1f), tr("Σημείο δρόσου", "Dew point"), "${f(d.dp)} °C")
                SmallStat(Modifier.weight(1f), tr("Απόλυτη υγρασία", "Absolute humidity"), "${f(d.ah)} g/m³")
            }
            val cw = w?.takeIf { it.enabled }?.current
            inOut(d.t, d.h, cw?.temp, cw?.hum)?.let { io -> InOutBox(io, w?.labels) }
            if (d.online == false && d.error.isNotBlank()) Text(d.error, fontSize = 12.sp, color = BadC, maxLines = 2, overflow = TextOverflow.Ellipsis)
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
        Modifier.padding(top = 10.dp).fillMaxWidth().clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.secondaryContainer.copy(alpha = .45f)).padding(10.dp)
    ) {
        FlowRow(verticalArrangement = Arrangement.Center) {
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
                FlowRow(verticalArrangement = Arrangement.spacedBy(4.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(c.text, fontSize = 14.sp)
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
                    Modifier.clip(RoundedCornerShape(12.dp)).background(MaterialTheme.colorScheme.secondaryContainer.copy(alpha = .45f))
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
