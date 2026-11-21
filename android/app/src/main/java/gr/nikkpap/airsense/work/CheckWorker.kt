package gr.nikkpap.airsense.work

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import gr.nikkpap.airsense.data.Prefs
import java.util.concurrent.TimeUnit

/** Περιοδικός έλεγχος στο παρασκήνιο (ελάχιστο 15 λεπτά — όριο Android). */
class CheckWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result {
        runCatching { Checker.run(applicationContext) }
        return Result.success()
    }

    companion object {
        private const val NAME = "airsense-check"

        fun schedule(ctx: Context) {
            val p = Prefs(ctx)
            val wm = WorkManager.getInstance(ctx)
            if (!p.configured || !p.notifEnabled) {
                wm.cancelUniqueWork(NAME)
                return
            }
            val req = PeriodicWorkRequestBuilder<CheckWorker>(p.checkMinutes.coerceAtLeast(15).toLong(), TimeUnit.MINUTES)
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .build()
            wm.enqueueUniquePeriodicWork(NAME, ExistingPeriodicWorkPolicy.UPDATE, req)
        }
    }
}
