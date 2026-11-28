package gr.nikkpap.airsense

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import gr.nikkpap.airsense.ui.App
import gr.nikkpap.airsense.ui.MainViewModel
import gr.nikkpap.airsense.work.MonitorService
import gr.nikkpap.airsense.work.Notifier

class MainActivity : ComponentActivity() {
    private val vm: MainViewModel by viewModels()

    private val notifPerm = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        if (Build.VERSION.SDK_INT >= 33 && !Notifier.canPost(this)) {
            notifPerm.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        if (vm.prefs.configured && vm.prefs.liveEnabled) runCatching { MonitorService.start(this) }
        handleInvite(intent)
        setContent { App(vm) }
    }

    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent)
        handleInvite(intent)
    }

    /** airsense://connect?url=…&pin=… → connect by itself */
    private fun handleInvite(i: android.content.Intent?) {
        val u = i?.data ?: return
        if (u.scheme == "airsense" && u.host == "connect") {
            vm.applyInvite(u.getQueryParameter("url").orEmpty(), u.getQueryParameter("pin"))
            i.data = null
        }
    }

    override fun onStart() {
        super.onStart()
        vm.setForeground(true)
    }

    override fun onStop() {
        if (!isChangingConfigurations) vm.setForeground(false)   // rotation is not "leaving the app"
        super.onStop()
    }
}
