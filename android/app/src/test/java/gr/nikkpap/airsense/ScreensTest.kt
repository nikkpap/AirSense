package gr.nikkpap.airsense

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onRoot
import androidx.test.core.app.ApplicationProvider
import com.github.takahirom.roborazzi.captureRoboImage
import gr.nikkpap.airsense.data.*
import gr.nikkpap.airsense.ui.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Screenshots of every screen on a small phone, a normal phone and a tablet, light + dark.
 * GitHub Actions uploads them as the artifact "android-screenshots" (UI review without a phone).
 */
const val SMALL = "w360dp-h740dp-xhdpi"
const val PHONE = "w411dp-h891dp-xxhdpi"
const val TABLET = "w900dp-h600dp-land-mdpi"

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], application = Application::class)
class ScreensTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private fun now() = System.currentTimeMillis() / 1000.0

    private fun state(theme: String, en: Boolean = false, online: Boolean? = true, devices: Int = 2): UiState {
        val n = now()
        val devs = listOf(
            Device("a", "My humiditySensor v2", "192.168.1.241", "multiSensor", true, true, 10.1, 61.7, 2.9, 5.9, n - 40, ""),
            Device("b", "Αποθήκη υπογείου", "192.168.1.88", "humiditySensor", true, false, -12.3, 100.0, -12.3, 1.9, n - 7200, "timeout"),
        ).take(devices)
        val alarms = Alarms(true, 5.0, 30.0, 25.0, 75.0, true, 60)
        val st = Status("1.7.5", n, 60, devs, listOf(
            Event(n - 60, "info", "Μέτρηση OK · My humiditySensor v2"),
            Event(n - 3600, "warn", "Αποθήκη υπογείου: δεν απαντά (timeout)"),
            Event(n - 7200, "err", "Email: λάθος κωδικός εφαρμογής"),
        ), false, 0, 0, 0, true, true, alarms)
        val wx = Weather(
            true, "Φιλώτας, Φλώρινα", WxCurrent(4.2, 88.0, 1.5, 0.4, 0.0, 61, 90.0, 12.0, 25.0, 1012.0, 0.0, 1, "🌧", "Ασθενής βροχή", "Βροχή"),
            (0..6).map { WxDay(listOf("Σήμ.", "Κυρ", "Δευ", "Τρι", "Τετ", "Πεμ", "Παρ")[it], "", "⛅", "", -1.0 + it, 8.0 + it, 2.4, 60.0, 0.0, 14400.0, "07:21", "17:05") },
            "", n
        )
        val pts = (0..96).map { i ->
            val ts = n - (96 - i) * 900.0
            HistPoint(ts, 9.0 + 2 * Math.sin(i / 10.0), 60.0 + 5 * Math.cos(i / 12.0), 2.5)
        }
        val wxp = (0..24).map { i -> WxPoint(n - (24 - i) * 3600.0, 3.0 + Math.sin(i / 4.0), 85.0, if (i in 10..14) 0.8 else 0.0, 0.0, 61, 0.0) }
        return UiState(
            configured = true, en = en, theme = theme, status = st, weather = wx, points = pts, wxPoints = wxp,
            selected = "a", hours = 24, online = online, error = if (online == false) "failed to connect to /192.168.1.29 (port 8765) after 4000ms" else null,
            config = PcConfig(60, alarms, EmailCfg(true, true, "08:00", true, true)), route = "tailscale",
            lastOk = System.currentTimeMillis() - 120_000, tsInstalled = true, tsVpn = online == true, tsAuto = "smart",
        )
    }

    private fun shot(name: String, theme: String, tab: Int, en: Boolean = false, online: Boolean? = true) {
        val vm = MainViewModel(ApplicationProvider.getApplicationContext())
        val s = state(theme, en, online)
        rule.setContent {
            HygroTheme(s.theme, false) {
                CompositionLocalProvider(LocalEn provides s.en) {
                    androidx.compose.material3.Surface(color = androidx.compose.material3.MaterialTheme.colorScheme.background) {
                        MainScaffold(vm, s, startTab = tab)
                    }
                }
            }
        }
        rule.waitForIdle()
        rule.onRoot().captureRoboImage("build/shots/$name.png")
    }


    @Test @Config(qualifiers = SMALL) fun home_small_dark() = shot("01_home_small_dark", "dark", 0)
    @Test @Config(qualifiers = SMALL) fun home_small_light() = shot("02_home_small_light", "light", 0)
    @Test @Config(qualifiers = PHONE) fun home_phone_offline_light() = shot("03_home_phone_offline_light", "light", 0, online = false)
    @Test @Config(qualifiers = TABLET) fun home_tablet_dark() = shot("04_home_tablet_dark", "dark", 0)
    @Test @Config(qualifiers = TABLET) fun home_tablet_light_en() = shot("05_home_tablet_light_en", "light", 0, en = true)
    @Test @Config(qualifiers = PHONE) fun alerts_phone_dark() = shot("06_alerts_phone_dark", "dark", 1)
    @Test @Config(qualifiers = PHONE) fun alerts_phone_light() = shot("07_alerts_phone_light", "light", 1)
    @Test @Config(qualifiers = PHONE) fun manage_phone_light() = shot("08_manage_phone_light", "light", 2)
    @Test @Config(qualifiers = TABLET) fun manage_tablet_dark() = shot("09_manage_tablet_dark", "dark", 2)
    @Test @Config(qualifiers = PHONE) fun settings_phone_dark() = shot("10_settings_phone_dark", "dark", 3)
    @Test @Config(qualifiers = SMALL) fun settings_small_light() = shot("11_settings_small_light", "light", 3)
    @Test @Config(qualifiers = TABLET) fun settings_tablet_light() = shot("12_settings_tablet_light", "light", 3)
}
