package gr.nikkpap.airsense.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

class ApiException(msg: String, val code: Int = 0) : Exception(msg)

fun enc(s: String): String = URLEncoder.encode(s, "UTF-8")

/**
 * Client για τον server του ALU AirSense (.pyw).
 * Δοκιμάζει πρώτα τη διεύθυνση που δούλεψε τελευταία, μετά τοπική και Tailscale.
 */
class Api(private val p: Prefs) {

    fun normalize(u: String): String {
        var s = u.trim().trimEnd('/')
        if (s.isEmpty()) return ""
        if (!s.startsWith("http://") && !s.startsWith("https://")) s = "http://$s"
        val hostPart = s.substringAfter("://")
        if (!Regex(":\\d+$").containsMatchIn(hostPart)) s += ":8765"
        return s
    }

    fun bases(): List<String> {
        val list = listOf(p.localUrl, p.tsUrl).map { normalize(it) }.filter { it.isNotBlank() }.distinct()
        val lg = p.lastGood
        return if (lg.isNotBlank() && lg in list) listOf(lg) + list.filter { it != lg } else list
    }

    fun currentBase(): String = bases().firstOrNull() ?: ""

    suspend fun get(path: String): JSONObject = call("GET", path, null)
    suspend fun post(path: String, body: JSONObject = JSONObject()): JSONObject = call("POST", path, body)

    private suspend fun call(method: String, path: String, body: JSONObject?): JSONObject =
        withContext(Dispatchers.IO) {
            val bs = bases()
            if (bs.isEmpty()) throw ApiException(p.t("Δεν έχει οριστεί διεύθυνση υπολογιστή", "No server address set"))
            var last: Exception? = null
            for (b in bs) {
                try {
                    val r = request(b, method, path, body)
                    if (p.lastGood != b) p.lastGood = b
                    return@withContext r
                } catch (e: ApiException) {
                    if (e.code in 400..599) throw e
                    last = e
                } catch (e: Exception) {
                    last = e
                }
            }
            throw ApiException(
                p.t("Ο υπολογιστής δεν απαντά", "Server not reachable") +
                        (last?.message?.let { " ($it)" } ?: "")
            )
        }

    private fun request(base: String, method: String, path: String, body: JSONObject?): JSONObject {
        val c = URL(base + path).openConnection() as HttpURLConnection
        c.connectTimeout = 4000
        c.readTimeout = 30000
        c.requestMethod = method
        c.setRequestProperty("X-PIN", p.pin)
        c.setRequestProperty("Accept", "application/json")
        try {
            if (body != null) {
                c.doOutput = true
                c.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                c.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            val code = c.responseCode
            val stream = if (code in 200..299) c.inputStream else c.errorStream
            val txt = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: ""
            if (code == 401) throw ApiException(p.t("Λάθος PIN", "Wrong PIN"), 401)
            if (code !in 200..299) {
                val msg = runCatching {
                    val j = JSONObject(txt)
                    j.optString("msg").ifBlank { j.optString("error") }
                }.getOrDefault("")
                throw ApiException(msg.ifBlank { "HTTP $code" }, code)
            }
            return if (txt.isBlank()) JSONObject() else JSONObject(txt)
        } finally {
            c.disconnect()
        }
    }

    fun exportUrl(kind: String, hours: Int): String =
        "${currentBase()}/api/export.$kind?hours=$hours&id=all&pin=${enc(p.pin)}"

    fun webUrl(): String = currentBase() + "/"
}
