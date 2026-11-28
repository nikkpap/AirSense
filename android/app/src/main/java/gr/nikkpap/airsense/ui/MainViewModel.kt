package gr.nikkpap.airsense.ui

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import gr.nikkpap.airsense.data.Api
import gr.nikkpap.airsense.data.Calib
import gr.nikkpap.airsense.data.HistPoint
import gr.nikkpap.airsense.data.Parse
import gr.nikkpap.airsense.data.PcConfig
import gr.nikkpap.airsense.data.Place
import gr.nikkpap.airsense.data.Prefs
import gr.nikkpap.airsense.data.Status
import gr.nikkpap.airsense.data.Weather
import gr.nikkpap.airsense.data.WxPoint
import gr.nikkpap.airsense.data.enc
import gr.nikkpap.airsense.work.CheckWorker
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import gr.nikkpap.airsense.data.Updater
import gr.nikkpap.airsense.BuildConfig
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.json.JSONObject

data class UiState(
    val configured: Boolean = false,
    val en: Boolean = false,
    val theme: String = "system",
    val dynamic: Boolean = false,
    val status: Status? = null,
    val weather: Weather? = null,
    val points: List<HistPoint> = emptyList(),
    val wxPoints: List<WxPoint> = emptyList(),
    val selected: String? = null,
    val hours: Int = 24,
    val online: Boolean? = null,
    val error: String? = null,
    val config: PcConfig? = null,
    val busy: Boolean = false,
    // OTA
    val update: Updater.Info? = null,       // a newer APK on GitHub
    val updateDialog: Boolean = false,      // show the "new version" dialog
    val updateProgress: Float? = null,      // null = not downloading · 0..1 · -1 = unknown size
    val updateChecking: Boolean = false,
    val updateMsg: String? = null,
    val autoUpdate: Boolean = true,
    // connection / Tailscale
    val route: String? = null,              // "local" · "tailscale" · null
    val lastOk: Long = 0L,                  // last successful refresh (ms)
    val refreshing: Boolean = false,
    val tsInstalled: Boolean = false,
    val tsVpn: Boolean = false,
    val tsAuto: String = "smart",           // smart · always · off
    val tsAutoOff: Boolean = true,
    // server (board) update — admin only
    val srvCheck: SrvUpdate? = null,
    val srvChecking: Boolean = false,
    val srvUpdating: Boolean = false,
    val srvLog: String = "",
    // invitation
    val inviteSeq: Int = 0,                 // changes when an invitation filled the connection fields
    val invite: InviteInfo? = null,
)

data class InviteInfo(val tailscale: String, val apk: String, val tsApp: String, val joinBase: String, val hasPin: Boolean)

data class SrvUpdate(val ok: Boolean, val current: String, val latest: String, val newer: Boolean,
                     val board: Boolean, val notes: String, val msg: String)

class MainViewModel(app: Application) : AndroidViewModel(app) {
    val prefs = Prefs(app)
    val api = Api(prefs)

    private val _ui = MutableStateFlow(
        UiState(
            configured = prefs.configured, en = prefs.lang == "en", theme = prefs.theme, dynamic = prefs.dynamic,
            hours = prefs.hours, selected = prefs.selected.ifBlank { null }, autoUpdate = prefs.autoUpdateCheck,
            tsAuto = prefs.tsAuto, tsAutoOff = prefs.tsAutoOff
        )
    )
    val ui: StateFlow<UiState> = _ui.asStateFlow()

    private val _msg = MutableSharedFlow<String>(extraBufferCapacity = 8)
    val messages = _msg.asSharedFlow()

    /** Κωδικός διαχειριστή (μόνο στη μνήμη, όσο είναι ανοιχτή η εφαρμογή). */
    var adminPw by mutableStateOf<String?>(null)

    private var foreground = true
    private var lastHist = 0L
    private var lastWx = 0L

    init {
        Updater.cleanup(app)
        // OTA: automatic check on start, at most every 12 hours
        if (prefs.autoUpdateCheck && System.currentTimeMillis() - prefs.lastUpdateCheck > 12 * 3600_000L) {
            viewModelScope.launch { delay(4000); checkUpdate(manual = false) }
        }
        viewModelScope.launch {
            while (true) {
                if (foreground && _ui.value.configured) refresh(silent = true)
                delay(10_000)
            }
        }
    }

    fun t(gr: String, en: String) = if (_ui.value.en) en else gr
    private fun update(f: (UiState) -> UiState) {
        _ui.value = f(_ui.value)
    }

    fun say(m: String) {
        _msg.tryEmit(m)
    }

    fun setForeground(f: Boolean) {
        foreground = f
        if (f) {
            tsOffJob?.cancel()
            viewModelScope.launch {
                autoTailscale()
                if (_ui.value.configured) refresh(true)
            }
        } else scheduleTailscaleOff()
    }

    // ═════════ Tailscale: on when the app opens (if needed), off when you leave ═════════
    private var tsStartedByUs = false
    private var tsOffJob: Job? = null

    fun updateTs() {
        val ctx = getApplication<Application>()
        update { it.copy(tsInstalled = gr.nikkpap.airsense.data.TailscaleCtl.installed(ctx),
            tsVpn = gr.nikkpap.airsense.data.TailscaleCtl.vpnOn(ctx)) }
    }

    private suspend fun autoTailscale() {
        val ctx = getApplication<Application>()
        val ts = gr.nikkpap.airsense.data.TailscaleCtl
        updateTs()
        if (prefs.tsAuto == "off" || !_ui.value.configured || !_ui.value.tsInstalled || _ui.value.tsVpn) return
        if (prefs.tsUrl.isBlank() && prefs.magicUrl.isBlank()) return            // no Tailscale address → nothing to do
        if (prefs.tsAuto == "smart" && ts.reachable(api.normalize(prefs.localUrl))) return   // same WiFi → not needed
        startTailscale()
    }

    private suspend fun startTailscale() {
        val ctx = getApplication<Application>()
        val ts = gr.nikkpap.airsense.data.TailscaleCtl
        if (!ts.connect(ctx)) return
        tsStartedByUs = true
        say(t("🌍 Ενεργοποίηση Tailscale…", "🌍 Turning Tailscale on…"))
        repeat(10) {
            delay(1000)
            if (ts.vpnOn(ctx)) {
                updateTs()
                prefs.lastGood = ""
                refresh(true)
                return
            }
        }
        updateTs()
        say(t("Το Tailscale δεν άνοιξε — άνοιξέ το μία φορά από την εφαρμογή του (σύνδεση + άδεια VPN)",
            "Tailscale did not start — open its app once (log in + allow VPN)"))
    }

    private fun scheduleTailscaleOff() {
        if (!tsStartedByUs || !prefs.tsAutoOff || prefs.liveEnabled) return
        tsOffJob = viewModelScope.launch {
            delay(5000)                       // short grace time (e.g. a quick look at another app)
            if (!foreground) stopTailscaleIfOurs()
        }
    }

    private fun stopTailscaleIfOurs() {
        if (tsStartedByUs && prefs.tsAutoOff && !prefs.liveEnabled) {
            gr.nikkpap.airsense.data.TailscaleCtl.disconnect(getApplication())
            tsStartedByUs = false
        }
    }

    /** App closed (swiped away / back) → Tailscale off immediately if AirSense turned it on. */
    override fun onCleared() {
        stopTailscaleIfOurs()
        super.onCleared()
    }

    /** Button in the top bar: Tailscale on ↔ off */
    fun toggleTailscale(): Job = viewModelScope.launch {
        val ctx = getApplication<Application>()
        val ts = gr.nikkpap.airsense.data.TailscaleCtl
        updateTs()
        when {
            !_ui.value.tsInstalled -> ts.openApp(ctx)
            _ui.value.tsVpn -> {
                ts.disconnect(ctx)
                tsStartedByUs = false
                say(t("Tailscale: απενεργοποίηση", "Tailscale: off"))
                delay(1500); updateTs(); prefs.lastGood = ""; refresh(true)
            }
            else -> startTailscale()
        }
    }

    fun setTsAuto(m: String) { prefs.tsAuto = m; update { it.copy(tsAuto = m) } }
    fun setTsAutoOff(v: Boolean) { prefs.tsAutoOff = v; update { it.copy(tsAutoOff = v) } }

    suspend fun refresh(silent: Boolean = false) {
        try {
            val sj = api.get("/api/status")
            val st = Parse.status(sj)
            learnUrls(sj)
            var sel = _ui.value.selected
            if (sel == null || st.devices.none { it.id == sel }) sel = st.devices.firstOrNull()?.id
            val lg = prefs.lastGood
            val route = when {
                lg.isBlank() -> null
                lg == api.normalize(prefs.localUrl) -> "local"
                isTailscaleHost(lg) -> "tailscale"
                else -> "local"
            }
            update { it.copy(status = st, online = true, error = null, selected = sel, route = route,
                lastOk = System.currentTimeMillis()) }
            runCatching { gr.nikkpap.airsense.widget.AirSenseWidget.save(getApplication(), st) }
            val now = System.currentTimeMillis()
            if (now - lastWx > 5 * 60_000L) {
                lastWx = now
                runCatching { Parse.weather(api.get("/api/weather")) }.onSuccess { w -> update { it.copy(weather = w) } }
            }
            if (now - lastHist > 60_000L) loadHistory()
        } catch (e: Exception) {
            update { it.copy(online = false, error = e.message, route = null) }
            if (!silent) say(t("Σφάλμα: ", "Error: ") + e.message)
        }
    }

    fun refreshNow(): Job = viewModelScope.launch {
        lastWx = 0
        lastHist = 0
        update { it.copy(refreshing = true) }
        try { refresh(false) } finally { update { it.copy(refreshing = false) } }
        updateTs()
    }

    // ═════════ Ενημέρωση server / πλακέτας (κωδικός διαχειριστή) ═════════
    private fun adminBody() = JSONObject().put("admin", adminPw ?: "")

    fun checkServerUpdate(): Job = viewModelScope.launch {
        update { it.copy(srvChecking = true) }
        try {
            val r = api.post("/api/admin/update/check", adminBody())
            update {
                it.copy(srvCheck = SrvUpdate(r.optBoolean("ok"), r.optString("current"), r.optString("latest"),
                    r.optBoolean("newer"), r.optBoolean("board"), r.optString("notes"), r.optString("msg")))
            }
        } catch (e: Exception) {
            if (e is gr.nikkpap.airsense.data.ApiException && e.code == 403) adminPw = null
            say(t("Σφάλμα: ", "Error: ") + e.message)
        } finally {
            update { it.copy(srvChecking = false) }
        }
    }

    fun loadServerUpdateLog(): Job = viewModelScope.launch {
        runCatching { api.post("/api/admin/update/log", adminBody()).optString("log") }
            .onSuccess { l -> update { it.copy(srvLog = l.ifBlank { "—" }) } }
            .onFailure { say(t("Σφάλμα: ", "Error: ") + it.message) }
    }

    /** ⬇ Update the board's AirSense now, then wait until the server comes back with the new version. */
    fun startServerUpdate(): Job = viewModelScope.launch {
        val old = _ui.value.status?.version ?: _ui.value.srvCheck?.current ?: ""
        try {
            val r = api.post("/api/admin/update", adminBody())
            say(r.optString("msg").ifBlank { "OK" })
            if (!r.optBoolean("ok")) return@launch
        } catch (e: Exception) {
            say(t("Σφάλμα: ", "Error: ") + e.message)
            return@launch
        }
        update { it.copy(srvUpdating = true) }
        try {
            repeat(48) { i ->                       // up to 4 minutes
                delay(5000)
                refresh(true)
                val v = _ui.value.status?.version
                if (_ui.value.online == true && v != null && v != old) {
                    say(t("✔ Ο server ενημερώθηκε: v$v", "✔ Server updated: v$v"))
                    update { it.copy(srvCheck = it.srvCheck?.copy(current = v, newer = false, msg = "v$v")) }
                    loadServerUpdateLog()
                    return@launch
                }
                if (i % 4 == 3 && _ui.value.online == true) {
                    val log = runCatching { api.post("/api/admin/update/log", adminBody()).optString("log") }.getOrDefault("")
                    update { it.copy(srvLog = log) }
                    val last = log.trim().lines().lastOrNull() ?: ""
                    if (last.contains("✖") || last.contains("Up to date")) {
                        say(t("Η ενημέρωση σταμάτησε: ", "Update stopped: ") + last.substringAfter(" ").substringAfter(" "))
                        return@launch
                    }
                }
            }
            say(t("Ο server δεν γύρισε ακόμα — δες το «Ιστορικό»", "The server is not back yet — see “Log”"))
        } finally {
            update { it.copy(srvUpdating = false) }
        }
    }

    // ═════════ Πρόσκληση άλλων ═════════
    /** From an invitation link: fill the address (+ PIN), test, and finish setup by itself. */
    fun applyInvite(url: String, pin: String?) {
        val u = api.normalize(url)
        if (u.isBlank()) return
        if (isTailscaleHost(u)) prefs.tsUrl = u else prefs.localUrl = u
        if (pin != null) prefs.pin = pin
        prefs.lastGood = ""
        update { it.copy(inviteSeq = it.inviteSeq + 1) }
        viewModelScope.launch {
            say(t("📨 Πρόσκληση: σύνδεση με $u…", "📨 Invitation: connecting to $u…"))
            val err = testConnection()
            if (err == null) {
                if (!_ui.value.configured) finishSetup() else refreshNow()
                say(t("✔ Συνδέθηκε!", "✔ Connected!"))
            } else say(t("Δεν συνδέθηκε: ", "Not connected: ") + err +
                    t(" — είναι ανοιχτό το Tailscale;", " — is Tailscale on?"))
        }
    }

    fun loadInvite(): Job = viewModelScope.launch {
        runCatching { api.get("/api/invite") }.onSuccess { j ->
            val urls = (0 until (j.optJSONArray("urls")?.length() ?: 0)).mapNotNull { j.optJSONArray("urls")?.optJSONObject(it)?.optString("url") }
            val join = urls.firstOrNull { it.contains(".ts.net") } ?: urls.firstOrNull { isTailscaleHost(it) }
                ?: prefs.magicUrl.ifBlank { null } ?: prefs.tsUrl.ifBlank { null } ?: urls.firstOrNull() ?: api.currentBase()
            update { it.copy(invite = InviteInfo(j.optString("tailscale"), j.optString("apk"), j.optString("ts_app"),
                api.normalize(join), j.optBoolean("has_pin"))) }
        }.onFailure { say(t("Σφάλμα: ", "Error: ") + it.message) }
    }

    fun saveInviteLink(link: String): Job = viewModelScope.launch {
        try {
            val r = api.post("/api/admin/invite", JSONObject().put("admin", adminPw ?: "").put("tailscale", link.trim()))
            say(r.optString("msg").ifBlank { "OK" })
            loadInvite()
        } catch (e: Exception) {
            if (e is gr.nikkpap.airsense.data.ApiException && e.code == 403) adminPw = null
            say(t("Σφάλμα: ", "Error: ") + e.message)
        }
    }

    fun inviteText(withPin: Boolean): String {
        val i = _ui.value.invite ?: return ""
        val pin = if (withPin) prefs.pin else ""
        val join = i.joinBase + "/join" + (if (pin.isNotBlank()) "?p=" + java.net.URLEncoder.encode(pin, "UTF-8") else "")
        val en = _ui.value.en
        val b = StringBuilder()
        var n = 1
        if (!en) {
            b.append("👋 Σε προσκαλώ στο AirSense — θερμοκρασία & υγρασία στο κινητό σου.\n\n")
            if (i.tailscale.isNotBlank()) {
                b.append("$n) Εγκατάστησε το Tailscale: ${i.tsApp}\n"); n++
                b.append("$n) Άνοιξε την πρόσκληση και κάνε login (Google / Microsoft): ${i.tailscale}\n"); n++
            }
            b.append("$n) Εγκατάστησε το AirSense (AirSense-Android_vX.apk): ${i.apk}\n"); n++
            b.append("$n) ${if (i.tailscale.isNotBlank()) "Με ανοιχτό το Tailscale, άνοιξε" else "Στο ίδιο WiFi, άνοιξε"}: $join\n")
            b.append("   → «📲 Άνοιγμα στην εφαρμογή» = έτοιμο!\n")
            if (pin.isNotBlank()) b.append("PIN: $pin\n")
        } else {
            b.append("👋 You're invited to AirSense — temperature & humidity on your phone.\n\n")
            if (i.tailscale.isNotBlank()) {
                b.append("$n) Install Tailscale: ${i.tsApp}\n"); n++
                b.append("$n) Open the invitation and log in (Google / Microsoft): ${i.tailscale}\n"); n++
            }
            b.append("$n) Install AirSense (AirSense-Android_vX.apk): ${i.apk}\n"); n++
            b.append("$n) ${if (i.tailscale.isNotBlank()) "With Tailscale on, open" else "On the same WiFi, open"}: $join\n")
            b.append("   → “📲 Open in the app” = done!\n")
            if (pin.isNotBlank()) b.append("PIN: $pin\n")
        }
        return b.toString()
    }

    /** For screenshot tests only: show a prepared state. */
    @androidx.annotation.VisibleForTesting
    fun setStateForTest(s: UiState) { _ui.value = s }

    suspend fun loadHistory() {
        val sel = _ui.value.selected ?: return
        lastHist = System.currentTimeMillis()
        runCatching { Parse.history(api.get("/api/history?id=${enc(sel)}&hours=${_ui.value.hours}")) }
            .onSuccess { (p, w) -> update { it.copy(points = p, wxPoints = w) } }
    }

    fun select(id: String) {
        prefs.selected = id
        update { it.copy(selected = id) }
        _ui.value.status?.let { st -> runCatching { gr.nikkpap.airsense.widget.AirSenseWidget.save(getApplication(), st) } }
        viewModelScope.launch { loadHistory() }
    }

    fun setHours(h: Int) {
        prefs.hours = h
        update { it.copy(hours = h) }
        viewModelScope.launch { loadHistory() }
    }

    /** POST προς τον υπολογιστή, μήνυμα αποτελέσματος και ανανέωση. */
    fun post(path: String, body: JSONObject = JSONObject(), after: suspend (JSONObject) -> Unit = {}): Job =
        viewModelScope.launch {
            update { it.copy(busy = true) }
            try {
                val r = api.post(path, body)
                say(r.optString("msg").ifBlank { "OK" })
                after(r)
                delay(1500)
                lastHist = 0
                lastWx = 0
                refresh(true)
            } catch (e: Exception) {
                say(t("Σφάλμα: ", "Error: ") + e.message)
            } finally {
                update { it.copy(busy = false) }
            }
        }

    fun loadConfig(): Job = viewModelScope.launch {
        runCatching { Parse.config(api.get("/api/config")) }
            .onSuccess { c -> update { it.copy(config = c) } }
            .onFailure { say(t("Σφάλμα: ", "Error: ") + it.message) }
    }

    fun saveConfig(body: JSONObject): Job = post("/api/config", body) { r ->
        r.optJSONObject("config")?.let { c -> update { it.copy(config = Parse.config(c)) } }
    }

    // ── σύνδεση ──
    fun saveConnection(local: String, ts: String, pin: String) {
        prefs.localUrl = api.normalize(local)
        prefs.tsUrl = api.normalize(ts)
        prefs.pin = pin.trim()
        prefs.lastGood = ""
    }

    suspend fun testConnection(): String? {
        return try {
            val j = api.get("/api/status")
            val st = Parse.status(j)
            learnUrls(j)
            update { it.copy(status = st, online = true) }
            null
        } catch (e: Exception) {
            e.message ?: "?"
        }
    }

    /** The server tells its own addresses → fill the missing Tailscale / local address by itself. */
    private fun learnUrls(j: org.json.JSONObject) {
        val ts = gr.nikkpap.airsense.data.Discovery.tailscaleUrl(j)
        val lan = gr.nikkpap.airsense.data.Discovery.localUrl(j)
        val magic = gr.nikkpap.airsense.data.Discovery.magicDnsUrl(j)
        val typedMagic = prefs.tsUrl.contains(".ts.net")          // the user typed the MagicDNS name → keep it
        if (ts != null && !typedMagic && prefs.tsUrl != ts) prefs.tsUrl = ts
        if (magic != null && prefs.magicUrl != magic) prefs.magicUrl = magic
        if (typedMagic && ts != null && prefs.magicUrl != ts) prefs.magicUrl = ts   // then the 100.x IP is the extra fallback
        if (lan != null && prefs.localUrl.isBlank()) prefs.localUrl = lan
    }

    /** 🔍 Find the server on this WiFi, save it and test it — one tap. → null = OK, else the message */
    suspend fun autoFind(progress: (Int, Int) -> Unit): Pair<String?, String?> {
        val found = gr.nikkpap.airsense.data.Discovery.find(progress)
        if (found.isEmpty()) return null to t(
            "Δεν βρέθηκε server στο WiFi σου. Είναι το κινητό στο ίδιο WiFi με την πλακέτα / το PC; Είναι αναμμένος ο server;",
            "No server found on your WiFi. Is the phone on the same WiFi as the board / PC? Is the server on?")
        val url = found.first()
        prefs.localUrl = url
        prefs.lastGood = ""
        val err = testConnection()
        return url to err
    }

    fun finishSetup() {
        prefs.configured = true
        update { it.copy(configured = true) }
        CheckWorker.schedule(getApplication())
        refreshNow()
    }

    fun resetSetup() {
        prefs.configured = false
        update { it.copy(configured = false) }
    }

    // ── εμφάνιση ──
    fun setLang(en: Boolean) {
        prefs.lang = if (en) "en" else "el"
        update { it.copy(en = en) }
    }

    fun setTheme(t: String) {
        prefs.theme = t
        update { it.copy(theme = t) }
    }

    fun setDynamic(d: Boolean) {
        prefs.dynamic = d
        update { it.copy(dynamic = d) }
    }

    // ── βοηθητικά για διαλόγους ──
    suspend fun wifiScan(id: String): List<String> = Parse.strings(api.get("/api/device/wifiscan?id=${enc(id)}"), "ssids")
    suspend fun geocode(name: String): List<Place> = Parse.places(api.get("/api/geocode?name=${enc(name)}&lang=${if (_ui.value.en) "en" else "el"}"))
    suspend fun adminCheck(pw: String): Boolean = api.post("/api/admin/check", JSONObject().put("admin", pw)).optBoolean("ok")
    suspend fun calib(id: String): Calib = Parse.calib(api.get("/api/calib?id=${enc(id)}"))

    fun exportUrl(kind: String) = api.exportUrl(kind, _ui.value.hours)
    fun webUrl() = api.webUrl()

    // ═════════ OTA (GitHub Releases) ═════════
    fun checkUpdate(manual: Boolean = true): Job = viewModelScope.launch {
        update { it.copy(updateChecking = true, updateMsg = null) }
        try {
            val info = Updater.check()
            prefs.lastUpdateCheck = System.currentTimeMillis()
            update {
                it.copy(update = info, updateChecking = false, updateDialog = info != null,
                    updateMsg = if (info == null) t("✔ Έχεις την τελευταία έκδοση", "✔ You have the latest version") else null)
            }
            if (info == null && manual) say(t("✔ Έχεις την τελευταία έκδοση (${BuildConfig.VERSION_NAME})",
                "✔ You have the latest version (${BuildConfig.VERSION_NAME})"))
        } catch (e: Exception) {
            update { it.copy(updateChecking = false, updateMsg = t("Δεν έγινε έλεγχος: ", "Check failed: ") + e.message) }
            if (manual) say(t("Δεν έγινε έλεγχος ενημέρωσης (internet;)", "Update check failed (internet?)"))
        }
    }

    fun dismissUpdateDialog() = update { it.copy(updateDialog = false) }

    fun setAutoUpdateCheck(v: Boolean) {
        prefs.autoUpdateCheck = v
        update { it.copy(autoUpdate = v) }
    }

    fun downloadAndInstall(): Job = viewModelScope.launch {
        val info = _ui.value.update ?: return@launch
        val ctx = getApplication<Application>()
        if (!Updater.canInstall(ctx)) {
            say(t("Επίτρεψε «Εγκατάσταση άγνωστων εφαρμογών» για το AirSense και ξαναπάτα Ενημέρωση",
                "Allow \"Install unknown apps\" for AirSense, then tap Update again"))
            Updater.openInstallPermission(ctx)
            return@launch
        }
        update { it.copy(updateProgress = 0f, updateDialog = false) }
        try {
            val apk = Updater.download(ctx, info) { p -> update { it.copy(updateProgress = p) } }
            update { it.copy(updateProgress = null) }
            Updater.install(ctx, apk)
        } catch (e: Exception) {
            update { it.copy(updateProgress = null) }
            say(t("Η λήψη απέτυχε: ", "Download failed: ") + e.message)
        }
    }
}
