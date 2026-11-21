package gr.nikkpap.airsense.ui

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

val Brand = Color(0xFF2B6CFF)
val TempC = Color(0xFFFF9F43)
val HumC = Color(0xFF3FA7FF)
val DewC = Color(0xFFA78BFA)
val OutTC = Color(0xFF2ECC71)
val OutHC = Color(0xFF1ABC9C)
val OkC = Color(0xFF2ECC71)
val BadC = Color(0xFFFF5C5C)
val WarnC = Color(0xFFFFC04D)

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
    background = Color(0xFFF5F7FB), surface = Color(0xFFF5F7FB),
    surfaceContainer = Color(0xFFFFFFFF), surfaceContainerHigh = Color(0xFFFFFFFF),
    surfaceContainerHighest = Color(0xFFEDF1F8),
)

@Composable
fun HygroTheme(theme: String, dynamic: Boolean, content: @Composable () -> Unit) {
    val dark = when (theme) {
        "dark" -> true
        "light" -> false
        else -> isSystemInDarkTheme()
    }
    val ctx = LocalContext.current
    val scheme = if (dynamic && Build.VERSION.SDK_INT >= 31) {
        if (dark) dynamicDarkColorScheme(ctx) else dynamicLightColorScheme(ctx)
    } else if (dark) DarkScheme else LightScheme
    MaterialTheme(colorScheme = scheme, content = content)
}

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
