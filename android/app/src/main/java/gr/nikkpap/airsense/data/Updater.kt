package gr.nikkpap.airsense.data

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import gr.nikkpap.airsense.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * OTA: checks the latest GitHub release of nikkpap/AirSense for a newer signed APK
 * (AirSense-Android_vX.Y.Z.apk), downloads it and opens the Android installer.
 * Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM
 */
object Updater {
    private const val API = "https://api.github.com/repos/nikkpap/AirSense/releases/latest"
    private val APK_RE = Regex("""^AirSense-Android_v([0-9][0-9.]*)\.apk$""")   // signed only (no -debug)

    data class Info(val version: String, val url: String, val size: Long, val notes: String, val page: String)

    /** a > b ? (1.10.0 > 1.9.3) */
    fun newer(a: String, b: String): Boolean {
        val x = a.split('.').map { it.toIntOrNull() ?: 0 }
        val y = b.split('.').map { it.toIntOrNull() ?: 0 }
        for (i in 0 until maxOf(x.size, y.size)) {
            val p = x.getOrElse(i) { 0 }; val q = y.getOrElse(i) { 0 }
            if (p != q) return p > q
        }
        return false
    }

    private fun open(url: String, timeout: Int): HttpURLConnection =
        (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = timeout; readTimeout = timeout
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", "AirSense-Android/${BuildConfig.VERSION_NAME}")
            setRequestProperty("Accept", "application/vnd.github+json")
        }

    /** null = up to date. Throws on network errors. */
    suspend fun check(): Info? = withContext(Dispatchers.IO) {
        val c = open(API, 15000)
        try {
            if (c.responseCode != 200) throw RuntimeException("GitHub HTTP ${c.responseCode}")
            val js = JSONObject(c.inputStream.bufferedReader().readText())
            val assets = js.optJSONArray("assets") ?: return@withContext null
            var best: Info? = null
            for (i in 0 until assets.length()) {
                val a = assets.getJSONObject(i)
                val m = APK_RE.find(a.optString("name")) ?: continue
                val v = m.groupValues[1]
                if (best == null || newer(v, best.version)) {
                    best = Info(v, a.optString("browser_download_url"), a.optLong("size"),
                        js.optString("body").take(1500), js.optString("html_url"))
                }
            }
            best?.takeIf { newer(it.version, BuildConfig.VERSION_NAME) }
        } finally { c.disconnect() }
    }

    private fun apkFile(ctx: Context) = File(File(ctx.cacheDir, "updates").apply { mkdirs() }, "AirSense-update.apk")

    /** Downloads the APK; progress 0..1 (or -1 if the size is unknown). */
    suspend fun download(ctx: Context, info: Info, progress: (Float) -> Unit): File = withContext(Dispatchers.IO) {
        val out = apkFile(ctx)
        val tmp = File(out.parentFile, "dl.part")
        var url = info.url
        var c = open(url, 30000)
        // GitHub redirects to another host (objects.githubusercontent.com) — follow by hand if needed
        repeat(5) {
            val code = c.responseCode
            if (code in 300..399) {
                url = c.getHeaderField("Location") ?: throw RuntimeException("redirect without Location")
                c.disconnect(); c = open(url, 30000)
            } else return@repeat
        }
        try {
            if (c.responseCode != 200) throw RuntimeException("HTTP ${c.responseCode}")
            val total = c.contentLengthLong.takeIf { it > 0 } ?: info.size
            c.inputStream.use { inp ->
                tmp.outputStream().use { o ->
                    val buf = ByteArray(64 * 1024)
                    var done = 0L
                    while (true) {
                        val n = inp.read(buf); if (n < 0) break
                        o.write(buf, 0, n); done += n
                        progress(if (total > 0) (done.toFloat() / total).coerceIn(0f, 1f) else -1f)
                    }
                }
            }
            if (info.size > 0 && tmp.length() != info.size) throw RuntimeException("incomplete download")
            out.delete(); tmp.renameTo(out)
            out
        } finally { c.disconnect() }
    }

    /** Android 8+: "install unknown apps" must be allowed for AirSense. */
    fun canInstall(ctx: Context): Boolean =
        Build.VERSION.SDK_INT < 26 || ctx.packageManager.canRequestPackageInstalls()

    fun openInstallPermission(ctx: Context) {
        val i = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${ctx.packageName}"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        runCatching { ctx.startActivity(i) }
    }

    fun install(ctx: Context, apk: File) {
        val uri = FileProvider.getUriForFile(ctx, "${ctx.packageName}.files", apk)
        val i = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        ctx.startActivity(i)
    }

    fun cleanup(ctx: Context) { runCatching { File(ctx.cacheDir, "updates").deleteRecursively() } }
}
