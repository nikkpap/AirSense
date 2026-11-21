package gr.nikkpap.airsense

import android.app.Application
import gr.nikkpap.airsense.work.CheckWorker
import gr.nikkpap.airsense.work.Notifier

class HygroApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Notifier.createChannels(this)
        CheckWorker.schedule(this)
    }
}
