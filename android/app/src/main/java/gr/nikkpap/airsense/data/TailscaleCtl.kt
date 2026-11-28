package gr.nikkpap.airsense.data

import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.InetSocketAddress
import java.net.Socket
import java.net.URL

/**
 * Tailscale on / off from AirSense.
 * The Tailscale app accepts the broadcasts com.tailscale.ipn.CONNECT_VPN / DISCONNECT_VPN
 * (receiver com.tailscale.ipn.IPNReceiver — the same ones Tasker / Home Assistant use).
 * The first time, Tailscale must have been opened once and logged in (Android asks for the VPN permission there).
 */
object TailscaleCtl {
    const val PKG = "com.tailscale.ipn"
    private const val RECEIVER = "com.tailscale.ipn.IPNReceiver"
    const val PLAY = "https://play.google.com/store/apps/details?id=com.tailscale.ipn"

    fun installed(ctx: Context): Boolean =
        runCatching { ctx.packageManager.getPackageInfo(PKG, 0); true }.getOrDefault(false)

    /** Is a VPN (Tailscale) active on the phone right now? */
    @Suppress("DEPRECATION")
    fun vpnOn(ctx: Context): Boolean = runCatching {
        val cm = ctx.getSystemService(ConnectivityManager::class.java) ?: return false
        cm.allNetworks.any { cm.getNetworkCapabilities(it)?.hasTransport(NetworkCapabilities.TRANSPORT_VPN) == true }
    }.getOrDefault(false)

    private fun send(ctx: Context, action: String): Boolean = runCatching {
        ctx.sendBroadcast(Intent(action).setClassName(PKG, RECEIVER))
        true
    }.getOrDefault(false)

    fun connect(ctx: Context) = send(ctx, "com.tailscale.ipn.CONNECT_VPN")
    fun disconnect(ctx: Context) = send(ctx, "com.tailscale.ipn.DISCONNECT_VPN")

    fun openApp(ctx: Context) {
        val i = ctx.packageManager.getLaunchIntentForPackage(PKG)
            ?: Intent(Intent.ACTION_VIEW, Uri.parse(PLAY))
        runCatching { ctx.startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
    }

    /** Quick check: does the board answer on the local address (same WiFi)? */
    suspend fun reachable(url: String, timeoutMs: Int = 800): Boolean = withContext(Dispatchers.IO) {
        if (url.isBlank()) return@withContext false
        runCatching {
            val u = URL(url)
            Socket().use { it.connect(InetSocketAddress(u.host, if (u.port > 0) u.port else 80), timeoutMs) }
            true
        }.getOrDefault(false)
    }
}
