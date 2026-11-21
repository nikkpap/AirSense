package gr.nikkpap.airsense.work

import android.annotation.SuppressLint
import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import gr.nikkpap.airsense.R
import gr.nikkpap.airsense.data.Prefs
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/** Ζωντανή παρακολούθηση: μόνιμη ειδοποίηση με τις τιμές + έλεγχος ορίων κάθε Ν δευτερόλεπτα. */
class MonitorService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var job: Job? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            Prefs(this).liveEnabled = false
            ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
            stopSelf()
            return START_NOT_STICKY
        }
        val p = Prefs(this)
        ServiceCompat.startForeground(
            this, ID, build("💧 AirSense", p.t("Σύνδεση…", "Connecting…")),
            if (Build.VERSION.SDK_INT >= 34) ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE else 0
        )
        if (job?.isActive != true) {
            job = scope.launch {
                while (isActive) {
                    val pr = Prefs(this@MonitorService)
                    val r = runCatching { Checker.run(this@MonitorService) }.getOrNull()
                    val (title, text) = Checker.liveText(pr, r)
                    update(title, text)
                    delay(pr.liveSeconds.coerceAtLeast(15) * 1000L)
                }
            }
        }
        return START_STICKY
    }

    @SuppressLint("MissingPermission")
    private fun update(title: String, text: String) {
        if (Notifier.canPost(this)) NotificationManagerCompat.from(this).notify(ID, build(title, text))
    }

    private fun build(title: String, text: String): Notification {
        val stop = PendingIntent.getService(
            this, 1, Intent(this, MonitorService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        return NotificationCompat.Builder(this, Notifier.CH_LIVE)
            .setSmallIcon(R.drawable.ic_stat_drop)
            .setColor(0xFF2B6CFF.toInt())
            .setContentTitle(title)
            .setContentText(text.lineSequence().firstOrNull() ?: "")
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setSilent(true)
            .setContentIntent(Notifier.openAppIntent(this))
            .addAction(0, Prefs(this).t("Διακοπή", "Stop"), stop)
            .build()
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    companion object {
        private const val ID = 4711
        const val ACTION_STOP = "gr.nikkpap.airsense.STOP_LIVE"

        fun start(ctx: Context) = ContextCompat.startForegroundService(ctx, Intent(ctx, MonitorService::class.java))
        fun stop(ctx: Context) {
            ctx.stopService(Intent(ctx, MonitorService::class.java))
        }
    }
}
