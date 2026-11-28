package gr.nikkpap.airsense.data

import android.content.Context

/** Ρυθμίσεις εφαρμογής (SharedPreferences). */
class Prefs(ctx: Context) {
    private val sp = ctx.applicationContext.getSharedPreferences("airsense", Context.MODE_PRIVATE)

    private fun str(k: String, d: String = "") = sp.getString(k, d) ?: d
    private fun putStr(k: String, v: String) = sp.edit().putString(k, v).apply()
    private fun bool(k: String, d: Boolean) = sp.getBoolean(k, d)
    private fun putBool(k: String, v: Boolean) = sp.edit().putBoolean(k, v).apply()
    private fun flt(k: String, d: Float) = sp.getFloat(k, d)
    private fun putFlt(k: String, v: Float) = sp.edit().putFloat(k, v).apply()
    private fun int(k: String, d: Int) = sp.getInt(k, d)
    private fun putInt(k: String, v: Int) = sp.edit().putInt(k, v).apply()

    // ── σύνδεση ──
    var configured: Boolean get() = bool("configured", false); set(v) = putBool("configured", v)
    var localUrl: String get() = str("localUrl"); set(v) = putStr("localUrl", v)
    var tsUrl: String get() = str("tsUrl"); set(v) = putStr("tsUrl", v)
    /** Tailscale MagicDNS name (e.g. http://airsense.tailXXXX.ts.net:8765) — learned from the server, extra fallback */
    var magicUrl: String get() = str("magicUrl"); set(v) = putStr("magicUrl", v)
    var pin: String get() = str("pin"); set(v) = putStr("pin", v)
    var lastGood: String get() = str("lastGood"); set(v) = putStr("lastGood", v)

    // ── εμφάνιση ──
    var lang: String get() = str("lang", "el"); set(v) = putStr("lang", v)
    var theme: String get() = str("theme", "system"); set(v) = putStr("theme", v)
    var dynamic: Boolean get() = bool("dynamic", false); set(v) = putBool("dynamic", v)
    var hours: Int get() = int("hours", 24); set(v) = putInt("hours", v)
    var selected: String get() = str("selected"); set(v) = putStr("selected", v)

    // ── ειδοποιήσεις ──
    var notifEnabled: Boolean get() = bool("notifEnabled", true); set(v) = putBool("notifEnabled", v)
    var tMin: Float get() = flt("tMin", 5f); set(v) = putFlt("tMin", v)
    var tMax: Float get() = flt("tMax", 35f); set(v) = putFlt("tMax", v)
    var hMin: Float get() = flt("hMin", 20f); set(v) = putFlt("hMin", v)
    var hMax: Float get() = flt("hMax", 80f); set(v) = putFlt("hMax", v)
    var offlineAlert: Boolean get() = bool("offlineAlert", true); set(v) = putBool("offlineAlert", v)
    var serverAlert: Boolean get() = bool("serverAlert", true); set(v) = putBool("serverAlert", v)
    var weatherAlert: Boolean get() = bool("weatherAlert", true); set(v) = putBool("weatherAlert", v)
    var frostAlert: Boolean get() = bool("frostAlert", true); set(v) = putBool("frostAlert", v)
    var forwardPc: Boolean get() = bool("forwardPc", false); set(v) = putBool("forwardPc", v)
    var cooldownMin: Int get() = int("cooldownMin", 60); set(v) = putInt("cooldownMin", v)
    var checkMinutes: Int get() = int("checkMinutes", 15); set(v) = putInt("checkMinutes", v)
    var liveEnabled: Boolean get() = bool("liveEnabled", false); set(v) = putBool("liveEnabled", v)
    var liveSeconds: Int get() = int("liveSeconds", 60); set(v) = putInt("liveSeconds", v)

    // ── εσωτερική κατάσταση ειδοποιήσεων ──
    var lastEventTs: Float get() = flt("lastEventTs", 0f); set(v) = putFlt("lastEventTs", v)
    var failCount: Int get() = int("failCount", 0); set(v) = putInt("failCount", v)
    var lastWxStatus: String get() = str("lastWxStatus"); set(v) = putStr("lastWxStatus", v)
    var lastWxFetch: Long get() = sp.getLong("lastWxFetch", 0L); set(v) = sp.edit().putLong("lastWxFetch", v).apply()
    var cachedWx: String get() = str("cachedWx"); set(v) = putStr("cachedWx", v)

    // ── Tailscale ──
    /** smart = only when the board is not on this WiFi · always · off */
    var tsAuto: String get() = str("tsAuto", "smart"); set(v) = putStr("tsAuto", v)
    /** turn Tailscale off again when leaving the app (only if AirSense turned it on) */
    var tsAutoOff: Boolean get() = bool("tsAutoOff", true); set(v) = putBool("tsAutoOff", v)

    // ── OTA ──
    var autoUpdateCheck: Boolean get() = bool("autoUpdateCheck", true); set(v) = putBool("autoUpdateCheck", v)
    var lastUpdateCheck: Long get() = sp.getLong("lastUpdateCheck", 0L); set(v) = sp.edit().putLong("lastUpdateCheck", v).apply()

    fun isActive(k: String) = bool("act_$k", false)
    fun setActive(k: String, v: Boolean) = putBool("act_$k", v)
    fun lastNotified(k: String) = sp.getLong("ln_$k", 0L)
    fun setNotified(k: String, t: Long) = sp.edit().putLong("ln_$k", t).apply()

    fun t(gr: String, en: String) = if (lang == "en") en else gr
}
