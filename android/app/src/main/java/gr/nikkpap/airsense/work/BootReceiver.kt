package gr.nikkpap.airsense.work

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import gr.nikkpap.airsense.data.Prefs

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return
        CheckWorker.schedule(context)
        val p = Prefs(context)
        if (p.configured && p.liveEnabled) runCatching { MonitorService.start(context) }
    }
}
