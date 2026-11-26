package gr.nikkpap.airsense.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.Inet4Address
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.net.Socket
import java.net.URL

/**
 * Finds AirSense servers on the phone's WiFi: every address of the /24 on port 8765,
 * then /api/status (200 = AirSense, 401/403 = AirSense with a PIN).
 * Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM
 */
object Discovery {

    /** The phone's own IPv4 addresses on WiFi / Ethernet (no loopback, no Tailscale 100.64/10, no mobile data CGNAT). */
    fun myIps(): List<String> = runCatching {
        NetworkInterface.getNetworkInterfaces().toList()
            .filter { it.isUp && !it.isLoopback }
            .flatMap { it.inetAddresses.toList() }
            .filterIsInstance<Inet4Address>()
            .filter { it.isSiteLocalAddress }
            .map { it.hostAddress ?: "" }
            .filter { it.isNotBlank() }
            .distinct()
    }.getOrDefault(emptyList())

    private fun portOpen(ip: String, port: Int, ms: Int): Boolean = runCatching {
        Socket().use { it.connect(InetSocketAddress(ip, port), ms) }
        true
    }.getOrDefault(false)

    private fun isAirSense(ip: String): Boolean = runCatching {
        val c = URL("http://$ip:8765/api/status").openConnection() as HttpURLConnection
        c.connectTimeout = 1500; c.readTimeout = 2500
        try {
            val code = c.responseCode
            if (code == 401 || code == 403) return@runCatching true
            if (code != 200) return@runCatching false
            val txt = c.inputStream.bufferedReader().use { it.readText() }
            JSONObject(txt).optString("app").contains("AirSense", ignoreCase = true)
        } finally { c.disconnect() }
    }.getOrDefault(false)

    /** → list of base URLs, e.g. ["http://192.168.1.29:8765"] */
    suspend fun find(progress: (Int, Int) -> Unit = { _, _ -> }): List<String> = withContext(Dispatchers.IO) {
        val nets = myIps().map { it.substringBeforeLast('.') }.distinct()
        val hosts = nets.flatMap { n -> (1..254).map { "$n.$it" } }.filter { it !in myIps() }
        val sem = Semaphore(64)
        var done = 0
        coroutineScope {
            hosts.map { ip ->
                async {
                    sem.withPermit {
                        val ok = portOpen(ip, 8765, 450) && isAirSense(ip)
                        synchronized(this@Discovery) { done++; progress(done, hosts.size) }
                        if (ok) "http://$ip:8765" else null
                    }
                }
            }.awaitAll().filterNotNull()
        }
    }

    /** From /api/status "urls": the Tailscale address of the server (100.x), if any. */
    fun tailscaleUrl(status: JSONObject): String? {
        val arr = status.optJSONArray("urls") ?: return null
        for (i in 0 until arr.length()) {
            val u = arr.optJSONObject(i)?.optString("url") ?: continue
            if (Regex("""^http://100\.\d+\.\d+\.\d+:\d+$""").matches(u)) return u
        }
        return null
    }

    fun localUrl(status: JSONObject): String? {
        val arr = status.optJSONArray("urls") ?: return null
        for (i in 0 until arr.length()) {
            val u = arr.optJSONObject(i)?.optString("url") ?: continue
            if (Regex("""^http://(192\.168|10\.|172\.(1[6-9]|2\d|3[01]))[\d.]*:\d+$""").containsMatchIn(u)) return u
        }
        return null
    }
}
