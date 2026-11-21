package gr.nikkpap.airsense.work

import android.Manifest
import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import gr.nikkpap.airsense.MainActivity
import gr.nikkpap.airsense.R

object Notifier {
    const val CH_ALERT = "alerts"
    const val CH_INFO = "info"
    const val CH_LIVE = "live"
    private const val COLOR = 0xFF2B6CFF.toInt()

    fun createChannels(ctx: Context) {
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return
        nm.createNotificationChannel(
            NotificationChannel(CH_ALERT, "Ειδοποιήσεις ορίων / Alerts", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "Θερμοκρασία, υγρασία, offline, καιρός"
            }
        )
        nm.createNotificationChannel(
            NotificationChannel(CH_INFO, "Ενημερώσεις / Info", NotificationManager.IMPORTANCE_DEFAULT)
        )
        nm.createNotificationChannel(
            NotificationChannel(CH_LIVE, "Ζωντανή παρακολούθηση / Live", NotificationManager.IMPORTANCE_LOW).apply {
                setShowBadge(false)
            }
        )
    }

    fun canPost(ctx: Context): Boolean =
        Build.VERSION.SDK_INT < 33 ||
                ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

    fun openAppIntent(ctx: Context): PendingIntent = PendingIntent.getActivity(
        ctx, 0,
        Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
    )

    fun alert(ctx: Context, key: String, title: String, text: String) = post(ctx, CH_ALERT, key, title, text, true)
    fun info(ctx: Context, key: String, title: String, text: String) = post(ctx, CH_INFO, key, title, text, false)

    @SuppressLint("MissingPermission")
    private fun post(ctx: Context, ch: String, key: String, title: String, text: String, high: Boolean) {
        if (!canPost(ctx)) return
        val n = NotificationCompat.Builder(ctx, ch)
            .setSmallIcon(R.drawable.ic_stat_drop)
            .setColor(COLOR)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setAutoCancel(true)
            .setContentIntent(openAppIntent(ctx))
            .setPriority(if (high) NotificationCompat.PRIORITY_HIGH else NotificationCompat.PRIORITY_DEFAULT)
            .setCategory(if (high) NotificationCompat.CATEGORY_ALARM else NotificationCompat.CATEGORY_STATUS)
            .build()
        NotificationManagerCompat.from(ctx).notify(key.hashCode(), n)
    }
}
