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
)

class MainViewModel(app: Application) : AndroidViewModel(app) {
    val prefs = Prefs(app)
    val api = Api(prefs)

    private val _ui = MutableStateFlow(
        UiState(
            configured = prefs.configured, en = prefs.lang == "en", theme = prefs.theme, dynamic = prefs.dynamic,
            hours = prefs.hours, selected = prefs.selected.ifBlank { null }, autoUpdate = prefs.autoUpdateCheck
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
        if (f && _ui.value.configured) viewModelScope.launch { refresh(true) }
    }

    suspend fun refresh(silent: Boolean = false) {
        try {
            val st = Parse.status(api.get("/api/status"))
            var sel = _ui.value.selected
            if (sel == null || st.devices.none { it.id == sel }) sel = st.devices.firstOrNull()?.id
            update { it.copy(status = st, online = true, error = null, selected = sel) }
            runCatching { gr.nikkpap.airsense.widget.AirSenseWidget.save(getApplication(), st) }
            val now = System.currentTimeMillis()
            if (now - lastWx > 5 * 60_000L) {
                lastWx = now
                runCatching { Parse.weather(api.get("/api/weather")) }.onSuccess { w -> update { it.copy(weather = w) } }
            }
            if (now - lastHist > 60_000L) loadHistory()
        } catch (e: Exception) {
            update { it.copy(online = false, error = e.message) }
            if (!silent) say(t("Σφάλμα: ", "Error: ") + e.message)
        }
    }

    fun refreshNow(): Job = viewModelScope.launch {
        lastWx = 0
        lastHist = 0
        refresh(false)
    }

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
            val st = Parse.status(api.get("/api/status"))
            update { it.copy(status = st, online = true) }
            null
        } catch (e: Exception) {
            e.message ?: "?"
        }
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
