package gr.nikkpap.airsense.work

import android.content.Context
import gr.nikkpap.airsense.data.Api
import gr.nikkpap.airsense.data.Parse
import gr.nikkpap.airsense.data.Prefs
import gr.nikkpap.airsense.data.Status
import gr.nikkpap.airsense.data.Weather
import gr.nikkpap.airsense.data.f
import org.json.JSONObject

data class CheckResult(val status: Status?, val weather: Weather?)

/** Κοινός έλεγχος για WorkManager και ζωντανή παρακολούθηση: διαβάζει τον server και βγάζει ειδοποιήσεις. */
object Checker {

    fun statusLabel(p: Prefs, s: String): String = if (p.lang != "en") s else when (s) {
        "Καταιγίδα" -> "Thunderstorm"; "Χιόνι" -> "Snow"; "Βροχή" -> "Rain"; "Ομίχλη" -> "Fog"
        "Νύχτα" -> "Night"; "Συννεφιά" -> "Cloudy"; "Ηλιοφάνεια" -> "Sunny"; else -> s
    }

    suspend fun run(ctx: Context): CheckResult {
        val p = Prefs(ctx)
        if (!p.configured) return CheckResult(null, null)
        val api = Api(p)
        val now = System.currentTimeMillis()

        val st = try {
            Parse.status(api.get("/api/status"))
        } catch (e: Exception) {
            p.failCount = p.failCount + 1
            if (p.notifEnabled && p.serverAlert && p.failCount >= 2 && !p.isActive("server")) {
                p.setActive("server", true)
                Notifier.alert(
                    ctx, "server", p.t("⚠ Ο υπολογιστής δεν απαντά", "⚠ Server not reachable"),
                    p.t("Το ALU AirSense στον υπολογιστή δεν απαντά. Είναι ανοιχτός ο υπολογιστής / το Tailscale;",
                        "ALU AirSense on the PC is not responding. Is the PC / Tailscale on?") + "\n" + (e.message ?: "")
                )
            }
            return CheckResult(null, cachedWeather(p))
        }
        p.failCount = 0
        if (p.isActive("server")) {
            p.setActive("server", false)
            if (p.notifEnabled) Notifier.info(ctx, "server", p.t("✅ Ο υπολογιστής απαντά ξανά", "✅ Server is back"), "")
        }

        // καιρός (το πολύ κάθε 10 λεπτά)
        var wx: Weather? = cachedWeather(p)
        if (now - p.lastWxFetch > 10 * 60_000L) {
            runCatching { api.get("/api/weather") }.onSuccess { j ->
                p.cachedWx = j.toString()
                p.lastWxFetch = now
                wx = Parse.weather(j)
            }
        }

        if (p.notifEnabled) {
            val cd = p.cooldownMin * 60_000L
            for (d in st.devices.filter { it.enabled }) {
                check(ctx, p, "${d.id}:off", p.offlineAlert && d.online == false, cd,
                    p.t("🔴 ${d.name}: εκτός σύνδεσης", "🔴 ${d.name}: offline"), d.error,
                    p.t("✅ ${d.name}: ξανά online", "✅ ${d.name}: back online"))
                val t = d.t
                val h = d.h
                if (t != null) {
                    check(ctx, p, "${d.id}:tlow", t < p.tMin, cd,
                        p.t("🥶 ${d.name}: χαμηλή θερμοκρασία ${f(t)}°C", "🥶 ${d.name}: low temperature ${f(t)}°C"),
                        p.t("Όριο ${f(p.tMin.toDouble())}°C", "Limit ${f(p.tMin.toDouble())}°C"),
                        p.t("✅ ${d.name}: θερμοκρασία ΟΚ (${f(t)}°C)", "✅ ${d.name}: temperature OK (${f(t)}°C)"))
                    check(ctx, p, "${d.id}:thigh", t > p.tMax, cd,
                        p.t("🔥 ${d.name}: υψηλή θερμοκρασία ${f(t)}°C", "🔥 ${d.name}: high temperature ${f(t)}°C"),
                        p.t("Όριο ${f(p.tMax.toDouble())}°C", "Limit ${f(p.tMax.toDouble())}°C"),
                        p.t("✅ ${d.name}: θερμοκρασία ΟΚ (${f(t)}°C)", "✅ ${d.name}: temperature OK (${f(t)}°C)"))
                }
                if (h != null) {
                    check(ctx, p, "${d.id}:hlow", h < p.hMin, cd,
                        p.t("🏜 ${d.name}: χαμηλή υγρασία ${f(h)}%", "🏜 ${d.name}: low humidity ${f(h)}%"),
                        p.t("Όριο ${f(p.hMin.toDouble())}%", "Limit ${f(p.hMin.toDouble())}%"),
                        p.t("✅ ${d.name}: υγρασία ΟΚ (${f(h)}%)", "✅ ${d.name}: humidity OK (${f(h)}%)"))
                    check(ctx, p, "${d.id}:hhigh", h > p.hMax, cd,
                        p.t("💦 ${d.name}: υψηλή υγρασία ${f(h)}%", "💦 ${d.name}: high humidity ${f(h)}%"),
                        p.t("Όριο ${f(p.hMax.toDouble())}%", "Limit ${f(p.hMax.toDouble())}%"),
                        p.t("✅ ${d.name}: υγρασία ΟΚ (${f(h)}%)", "✅ ${d.name}: humidity OK (${f(h)}%)"))
                }
            }

            // καιρός: αλλαγή σε βροχή / χιόνι / καταιγίδα, παγετός
            val c = wx?.current
            if (c != null) {
                if (p.weatherAlert && c.status != p.lastWxStatus) {
                    if (c.status in setOf("Βροχή", "Χιόνι", "Καταιγίδα") && p.lastWxStatus.isNotBlank()) {
                        Notifier.alert(
                            ctx, "wx", "${c.icon} ${statusLabel(p, c.status)} — ${wx?.place ?: ""}",
                            "${c.text} · ${f(c.temp)}°C · ${f(c.hum, 0)}% · " +
                                    p.t("βροχή ${f(c.rain)} mm, χιόνι ${f(c.snow)} cm", "rain ${f(c.rain)} mm, snow ${f(c.snow)} cm")
                        )
                    }
                }
                p.lastWxStatus = c.status
                val temp = c.temp
                if (temp != null) {
                    check(ctx, p, "frost", p.frostAlert && temp <= 0.0, 6 * 3600_000L,
                        p.t("🧊 Παγετός έξω: ${f(temp)}°C", "🧊 Frost outside: ${f(temp)}°C"), wx?.place ?: "",
                        p.t("✅ Τέλος παγετού (${f(temp)}°C)", "✅ Frost over (${f(temp)}°C)"))
                }
            }

            // προώθηση συμβάντων/ειδοποιήσεων του υπολογιστή
            if (p.lastEventTs <= 0f) {
                p.lastEventTs = st.time.toFloat()
            } else {
                runCatching { api.get("/api/events?since=${p.lastEventTs}") }.onSuccess { j: JSONObject ->
                    val evs = Parse.events(j.optJSONArray("events"))
                    if (p.forwardPc) {
                        evs.filter { it.level == "warn" || it.level == "err" }.takeLast(5).forEach { e ->
                            Notifier.alert(ctx, "pc:${e.ts}", p.t("💻 Υπολογιστής", "💻 PC"), e.msg)
                        }
                    }
                    evs.maxOfOrNull { it.ts }?.let { p.lastEventTs = it.toFloat() }
                }
            }
        }
        return CheckResult(st, wx)
    }

    private fun check(
        ctx: Context, p: Prefs, key: String, active: Boolean, cooldownMs: Long,
        title: String, text: String, okTitle: String
    ) {
        val was = p.isActive(key)
        val now = System.currentTimeMillis()
        if (active) {
            if (!was || now - p.lastNotified(key) > cooldownMs) {
                Notifier.alert(ctx, key, title, text)
                p.setNotified(key, now)
            }
            p.setActive(key, true)
        } else if (was) {
            p.setActive(key, false)
            Notifier.info(ctx, key, okTitle, "")
        }
    }

    private fun cachedWeather(p: Prefs): Weather? =
        p.cachedWx.takeIf { it.isNotBlank() }?.let { runCatching { Parse.weather(JSONObject(it)) }.getOrNull() }

    /** Κείμενο για τη μόνιμη ειδοποίηση ζωντανής παρακολούθησης. */
    fun liveText(p: Prefs, r: CheckResult?): Pair<String, String> {
        val noServer = "💧 AirSense" to p.t("Ο υπολογιστής δεν απαντά…", "Server not reachable…")
        val res = r ?: return noServer
        val st = res.status ?: return noServer
        val d = st.devices.firstOrNull { it.id == p.selected } ?: st.devices.firstOrNull()
        val title = if (d == null) "💧 AirSense" else "💧 ${d.name}: ${f(d.t)}°C · ${f(d.h)}%"
        val sb = StringBuilder()
        st.devices.filter { it.id != d?.id }.forEach { sb.append("${it.name}: ${f(it.t)}°C · ${f(it.h)}%\n") }
        res.weather?.current?.let { c ->
            sb.append(p.t("Έξω", "Outside")).append(": ${c.icon} ${f(c.temp)}°C · ${f(c.hum, 0)}% · ${statusLabel(p, c.status)}\n")
        }
        sb.append(p.t("Ενημέρωση ", "Updated ")).append(java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault()).format(java.util.Date()))
        return title to sb.toString().trim()
    }
}
