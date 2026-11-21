package gr.nikkpap.airsense.data

import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale

// ── Βοηθητικά JSON (null-safe) ──
fun JSONObject.dbl(k: String): Double? = if (!has(k) || isNull(k)) null else optDouble(k).takeIf { !it.isNaN() }
fun JSONObject.int(k: String): Int? = if (!has(k) || isNull(k)) null else optInt(k)
fun JSONObject.bool(k: String): Boolean? = if (!has(k) || isNull(k)) null else optBoolean(k)
fun JSONObject.str(k: String): String = if (!has(k) || isNull(k)) "" else optString(k)
fun JSONArray.dblAt(i: Int): Double? = if (i >= length() || isNull(i)) null else optDouble(i).takeIf { !it.isNaN() }

fun f(v: Double?, d: Int = 1): String = v?.let { String.format(Locale.US, "%.${d}f", it) } ?: "—"

data class Device(
    val id: String, val name: String, val ip: String, val type: String, val enabled: Boolean,
    val online: Boolean?, val t: Double?, val h: Double?, val dp: Double?, val ah: Double?,
    val ts: Double?, val error: String
)

data class Event(val ts: Double, val level: String, val msg: String)

data class Alarms(
    val enabled: Boolean, val tempMin: Double, val tempMax: Double,
    val humMin: Double, val humMax: Double, val offline: Boolean, val cooldownMin: Int
)

data class Status(
    val version: String, val time: Double, val pollSeconds: Int, val devices: List<Device>, val log: List<Event>,
    val scanRunning: Boolean, val scanDone: Int, val scanTotal: Int, val scanFound: Int,
    val emailEnabled: Boolean, val adminSet: Boolean, val alarms: Alarms
)

data class HistPoint(val ts: Double, val t: Double?, val h: Double?, val dp: Double?)
data class WxPoint(
    val ts: Double, val t: Double?, val h: Double?, val precip: Double?, val snow: Double?,
    val code: Int?, val sunshine: Double?
)

data class WxCurrent(
    val temp: Double?, val hum: Double?, val feels: Double?, val rain: Double?, val snow: Double?,
    val code: Int?, val cloud: Double?, val wind: Double?, val gust: Double?, val pressure: Double?,
    val sunshine: Double?, val isDay: Int, val icon: String, val text: String, val status: String
)

data class WxDay(
    val day: String, val date: String, val icon: String, val text: String, val tmin: Double?, val tmax: Double?,
    val precip: Double?, val prob: Double?, val snow: Double?, val sunshine: Double?,
    val sunrise: String, val sunset: String
)

/** Λεκτικά «Μέσα» / «Έξω» όπως τα όρισε ο χρήστης στον υπολογιστή (server v1.5.8+). */
data class Labels(val inside: String = DEF_IN, val outside: String = DEF_OUT) {
    val isDefault get() = inside == DEF_IN && outside == DEF_OUT
    companion object { const val DEF_IN = "Μέσα"; const val DEF_OUT = "Έξω" }
}

data class Weather(
    val enabled: Boolean, val place: String, val current: WxCurrent?, val daily: List<WxDay>,
    val error: String, val updated: Double?, val labels: Labels = Labels()
)

/** Απόλυτη υγρασία (g/m³) — ίδιος τύπος με τον server. */
fun absHumidity(t: Double, rh: Double): Double =
    6.112 * Math.exp(17.67 * t / (t + 243.5)) * rh * 2.1674 / (273.15 + t)

/** Διαφορά μέσα–έξω. vent: 1 = ο αερισμός ξεραίνει, -1 = υγραίνει, 0 = σχεδόν ίδια. */
data class InOut(val dt: Double, val dh: Double, val ahIn: Double, val ahOut: Double, val vent: Int)

fun inOut(tIn: Double?, hIn: Double?, tOut: Double?, hOut: Double?): InOut? {
    if (tIn == null || hIn == null || tOut == null || hOut == null) return null
    val ai = absHumidity(tIn, hIn); val ao = absHumidity(tOut, hOut); val d = ai - ao
    return InOut(tIn - tOut, hIn - hOut, ai, ao, if (Math.abs(d) < 0.5) 0 else if (d > 0) 1 else -1)
}

data class EmailCfg(
    val enabled: Boolean, val dailyReport: Boolean, val reportTime: String,
    val alarmMails: Boolean, val configured: Boolean
)

data class PcConfig(val pollSeconds: Int, val alarms: Alarms, val email: EmailCfg)

data class Calib(
    val tOff: Double, val tMul: Double, val hOff: Double, val hMul: Double,
    val rawT: Double?, val rawH: Double?
)

data class Place(val label: String, val lat: Double, val lon: Double)

object Parse {
    fun alarms(j: JSONObject?): Alarms {
        val a = j ?: JSONObject()
        return Alarms(
            a.optBoolean("enabled"), a.dbl("temp_min") ?: 5.0, a.dbl("temp_max") ?: 35.0,
            a.dbl("hum_min") ?: 20.0, a.dbl("hum_max") ?: 80.0, a.optBoolean("offline", true),
            a.int("cooldown_min") ?: 60
        )
    }

    fun events(arr: JSONArray?): List<Event> {
        if (arr == null) return emptyList()
        return (0 until arr.length()).mapNotNull { i ->
            arr.optJSONObject(i)?.let { Event(it.dbl("ts") ?: 0.0, it.str("level"), it.str("msg")) }
        }
    }

    fun status(j: JSONObject): Status {
        val arr = j.optJSONArray("devices") ?: JSONArray()
        val devs = (0 until arr.length()).mapNotNull { i ->
            arr.optJSONObject(i)?.let { d ->
                Device(
                    d.str("id"), d.str("name").ifBlank { d.str("id") }, d.str("ip"), d.str("type"),
                    d.optBoolean("enabled", true), d.bool("online"), d.dbl("t"), d.dbl("h"), d.dbl("dp"),
                    d.dbl("ah"), d.dbl("ts"), d.str("error")
                )
            }
        }
        val sc = j.optJSONObject("scan") ?: JSONObject()
        return Status(
            j.str("version"), j.dbl("time") ?: 0.0, j.int("poll_seconds") ?: 60, devs, events(j.optJSONArray("log")),
            sc.optBoolean("running"), sc.optInt("done"), sc.optInt("total"), sc.optInt("found"),
            j.optBoolean("email_enabled"), j.optBoolean("admin_set"), alarms(j.optJSONObject("alarms"))
        )
    }

    fun history(j: JSONObject): Pair<List<HistPoint>, List<WxPoint>> {
        val p = j.optJSONArray("points") ?: JSONArray()
        val pts = (0 until p.length()).mapNotNull { i ->
            p.optJSONArray(i)?.let { a -> HistPoint(a.dblAt(0) ?: 0.0, a.dblAt(1), a.dblAt(2), a.dblAt(3)) }
        }
        val w = j.optJSONArray("wx") ?: JSONArray()
        val wx = (0 until w.length()).mapNotNull { i ->
            w.optJSONArray(i)?.let { a ->
                WxPoint(a.dblAt(0) ?: 0.0, a.dblAt(1), a.dblAt(2), a.dblAt(3), a.dblAt(4), a.dblAt(5)?.toInt(), a.dblAt(6))
            }
        }
        return pts to wx
    }

    fun weather(j: JSONObject): Weather {
        val c = j.optJSONObject("current")
        val cur = c?.let {
            WxCurrent(
                it.dbl("temp"), it.dbl("hum"), it.dbl("feels"), it.dbl("rain"), it.dbl("snow"), it.int("code"),
                it.dbl("cloud"), it.dbl("wind"), it.dbl("gust"), it.dbl("pressure"), it.dbl("sunshine"),
                it.int("is_day") ?: 1, it.str("icon"), it.str("text"), it.str("status")
            )
        }
        val d = j.optJSONArray("daily") ?: JSONArray()
        val days = (0 until d.length()).mapNotNull { i ->
            d.optJSONObject(i)?.let {
                WxDay(
                    it.str("day"), it.str("date"), it.str("icon"), it.str("text"), it.dbl("tmin"), it.dbl("tmax"),
                    it.dbl("precip"), it.dbl("prob"), it.dbl("snow"), it.dbl("sunshine"),
                    it.str("sunrise"), it.str("sunset")
                )
            }
        }
        val lb = j.optJSONObject("labels")
        val labels = Labels(
            lb?.str("inside")?.takeIf { it.isNotBlank() } ?: Labels.DEF_IN,
            lb?.str("outside")?.takeIf { it.isNotBlank() } ?: Labels.DEF_OUT
        )
        return Weather(j.optBoolean("enabled"), j.str("place"), cur, days, j.str("error"), j.dbl("updated"), labels)
    }

    fun config(j: JSONObject): PcConfig {
        val e = j.optJSONObject("email") ?: JSONObject()
        return PcConfig(
            j.int("poll_seconds") ?: 60, alarms(j.optJSONObject("alarms")),
            EmailCfg(
                e.optBoolean("enabled"), e.optBoolean("daily_report"), e.str("report_time").ifBlank { "08:00" },
                e.optBoolean("alarm_mails", true), e.optBoolean("configured")
            )
        )
    }

    fun calib(j: JSONObject): Calib {
        val c = j.optJSONObject("calib") ?: JSONObject()
        return Calib(
            c.dbl("t_off") ?: 0.0, c.dbl("t_mul") ?: 1.0, c.dbl("h_off") ?: 0.0, c.dbl("h_mul") ?: 1.0,
            j.dbl("raw_t"), j.dbl("raw_h")
        )
    }

    fun places(j: JSONObject): List<Place> {
        val a = j.optJSONArray("results") ?: JSONArray()
        return (0 until a.length()).mapNotNull { i ->
            a.optJSONObject(i)?.let { Place(it.str("label"), it.dbl("lat") ?: 0.0, it.dbl("lon") ?: 0.0) }
        }
    }

    fun strings(j: JSONObject, key: String): List<String> {
        val a = j.optJSONArray(key) ?: JSONArray()
        return (0 until a.length()).map { a.optString(it) }.filter { it.isNotBlank() }
    }
}
