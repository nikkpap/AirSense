package gr.nikkpap.airsense.ui

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

val Brand = Color(0xFF2B6CFF)

/** Data colours, tuned per theme so small text stays readable (contrast) on light and dark cards. */
data class DataColors(
    val temp: Color, val hum: Color, val dew: Color, val outT: Color, val outH: Color,
    val ok: Color, val bad: Color, val warn: Color,
)

val DarkData = DataColors(
    temp = Color(0xFFFFA552), hum = Color(0xFF4DB0FF), dew = Color(0xFFB39DFF), outT = Color(0xFF3DD68C),
    outH = Color(0xFF2CC9AE), ok = Color(0xFF3DD68C), bad = Color(0xFFFF6B6B), warn = Color(0xFFFFC857),
)
val LightData = DataColors(
    temp = Color(0xFFC25E00), hum = Color(0xFF0B6FC7), dew = Color(0xFF6A4BD6), outT = Color(0xFF13804A),
    outH = Color(0xFF0B7F6C), ok = Color(0xFF13804A), bad = Color(0xFFC62828), warn = Color(0xFF8A5A00),
)
val LocalData = staticCompositionLocalOf { DarkData }

val TempC: Color @Composable @ReadOnlyComposable get() = LocalData.current.temp
val HumC: Color @Composable @ReadOnlyComposable get() = LocalData.current.hum
val DewC: Color @Composable @ReadOnlyComposable get() = LocalData.current.dew
val OutTC: Color @Composable @ReadOnlyComposable get() = LocalData.current.outT
val OutHC: Color @Composable @ReadOnlyComposable get() = LocalData.current.outH
val OkC: Color @Composable @ReadOnlyComposable get() = LocalData.current.ok
val BadC: Color @Composable @ReadOnlyComposable get() = LocalData.current.bad
val WarnC: Color @Composable @ReadOnlyComposable get() = LocalData.current.warn

private val DarkScheme = darkColorScheme(
    primary = Brand, onPrimary = Color.White,
    primaryContainer = Color(0xFF1C3A80), onPrimaryContainer = Color(0xFFDCE6FF),
    secondaryContainer = Color(0xFF233A6B), onSecondaryContainer = Color(0xFFDCE6FF),
    background = Color(0xFF0F131A), onBackground = Color(0xFFE6EBF5),
    surface = Color(0xFF0F131A), onSurface = Color(0xFFE6EBF5),
    surfaceVariant = Color(0xFF1E2533), onSurfaceVariant = Color(0xFF8B96AB),
    surfaceContainerLowest = Color(0xFF0B0E14), surfaceContainerLow = Color(0xFF131822),
    surfaceContainer = Color(0xFF161B25), surfaceContainerHigh = Color(0xFF1A202B),
    surfaceContainerHighest = Color(0xFF1E2533),
    outline = Color(0xFF3A4458), outlineVariant = Color(0xFF262D3B),
)

private val LightScheme = lightColorScheme(
    primary = Brand, onPrimary = Color.White,
    primaryContainer = Color(0xFFDCE6FF), onPrimaryContainer = Color(0xFF0B2A6B),
    secondaryContainer = Color(0xFFE2E9F7), onSecondaryContainer = Color(0xFF1B2A45),
    background = Color(0xFFF3F5F9), onBackground = Color(0xFF141A24),
    surface = Color(0xFFF3F5F9), onSurface = Color(0xFF141A24),
    surfaceVariant = Color(0xFFE6EBF3), onSurfaceVariant = Color(0xFF4A5568),
    surfaceContainerLowest = Color(0xFFFFFFFF), surfaceContainerLow = Color(0xFFF8F9FC),
    surfaceContainer = Color(0xFFFFFFFF), surfaceContainerHigh = Color(0xFFFFFFFF),
    surfaceContainerHighest = Color(0xFFFFFFFF),
    outline = Color(0xFF8A94A6), outlineVariant = Color(0xFFD9DFEA),
    error = Color(0xFFC62828),
)

/** «time» mode: dark from 20:00 to 07:00 */
fun isNightNow(): Boolean {
    val h = java.util.Calendar.getInstance().get(java.util.Calendar.HOUR_OF_DAY)
    return h >= 20 || h < 7
}

@Composable
fun HygroTheme(theme: String, dynamic: Boolean, content: @Composable () -> Unit) {
    // «time»: re-check every minute so it switches by itself at 20:00 / 07:00
    var night by remember { mutableStateOf(isNightNow()) }
    if (theme == "time") {
        LaunchedEffect(Unit) { while (true) { night = isNightNow(); kotlinx.coroutines.delay(60_000) } }
    }
    val dark = when (theme) {
        "dark" -> true
        "light" -> false
        "time" -> night
        else -> isSystemInDarkTheme()
    }
    val ctx = LocalContext.current
    val scheme = if (dynamic && Build.VERSION.SDK_INT >= 31) {
        if (dark) dynamicDarkColorScheme(ctx) else dynamicLightColorScheme(ctx)
    } else if (dark) DarkScheme else LightScheme
    // status / navigation bar icons follow the APP theme (not only the phone's)
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val w = (view.context as? Activity)?.window ?: return@SideEffect
            val c = WindowCompat.getInsetsController(w, view)
            c.isAppearanceLightStatusBars = !dark
            c.isAppearanceLightNavigationBars = !dark
            w.decorView.setBackgroundColor(scheme.background.toArgb())
        }
    }
    androidx.compose.runtime.CompositionLocalProvider(LocalData provides if (dark) DarkData else LightData, LocalDark provides dark) {
        MaterialTheme(colorScheme = scheme, content = content)
    }
}

/** next theme for the quick toggle: system → time → dark → light → system */
fun nextTheme(t: String): String = when (t) {
    "system" -> "time"; "time" -> "dark"; "dark" -> "light"; else -> "system"
}

val LocalDark = staticCompositionLocalOf { true }

/** Γλώσσα: Ελληνικά / English */
val LocalEn = staticCompositionLocalOf { false }

@Composable
@ReadOnlyComposable
fun tr(gr: String, en: String): String = if (LocalEn.current) en else gr

/** Λεκτικό «Μέσα» (τα προεπιλεγμένα μεταφράζονται στα Αγγλικά, τα δικά σου μένουν όπως τα έγραψες) */
@Composable
@ReadOnlyComposable
fun lblIn(l: gr.nikkpap.airsense.data.Labels?): String =
    l?.inside?.takeIf { it != gr.nikkpap.airsense.data.Labels.DEF_IN } ?: tr("Μέσα", "Inside")

@Composable
@ReadOnlyComposable
fun lblOut(l: gr.nikkpap.airsense.data.Labels?): String =
    l?.outside?.takeIf { it != gr.nikkpap.airsense.data.Labels.DEF_OUT } ?: tr("Έξω", "Outside")

/** Μετάφραση κατάστασης καιρού του server (ελληνικά) */
@Composable
@ReadOnlyComposable
fun wxStatus(s: String): String = if (!LocalEn.current) s else when (s) {
    "Καταιγίδα" -> "Thunderstorm"; "Χιόνι" -> "Snow"; "Βροχή" -> "Rain"; "Ομίχλη" -> "Fog"
    "Νύχτα" -> "Night"; "Συννεφιά" -> "Cloudy"; "Ηλιοφάνεια" -> "Sunny"; else -> s
}
