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
        setContent { App(vm) }
    }

    override fun onStart() {
        super.onStart()
        vm.setForeground(true)
    }

    override fun onStop() {
        vm.setForeground(false)
        super.onStop()
    }
}
