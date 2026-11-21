@file:OptIn(ExperimentalLayoutApi::class)

package gr.nikkpap.airsense.ui

import android.os.Build
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import gr.nikkpap.airsense.BuildConfig

@Composable
fun SettingsScreen(vm: MainViewModel, ui: UiState) {
    val ctx = LocalContext.current
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(14.dp)) {
        SectionTitle(tr("Σύνδεση με τον υπολογιστή", "Connection to PC"))
        HCard { ConnectionForm(vm) { vm.refreshNow() } }

        SectionTitle(tr("Εμφάνιση", "Appearance"))
        HCard {
            Text(tr("Γλώσσα", "Language"), fontWeight = FontWeight.Bold)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(selected = !ui.en, onClick = { vm.setLang(false) }, label = { Text("🇬🇷 Ελληνικά") })
                FilterChip(selected = ui.en, onClick = { vm.setLang(true) }, label = { Text("🇬🇧 English") })
            }
            Spacer(Modifier.height(8.dp))
            Text(tr("Θέμα", "Theme"), fontWeight = FontWeight.Bold)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for ((k, l) in listOf("system" to tr("Συστήματος", "System"), "dark" to tr("Σκούρο", "Dark"), "light" to tr("Φωτεινό", "Light"))) {
                    FilterChip(selected = ui.theme == k, onClick = { vm.setTheme(k) }, label = { Text(l) })
                }
            }
            if (Build.VERSION.SDK_INT >= 31) {
                SwitchRow(tr("Δυναμικά χρώματα (Material You)", "Dynamic colors (Material You)"),
                    tr("Χρώματα από την ταπετσαρία σου", "Colors from your wallpaper"), ui.dynamic) { vm.setDynamic(it) }
            }
        }

        SectionTitle(tr("Σχετικά", "About"))
        HCard {
            Text("💧 AirSense ${BuildConfig.VERSION_NAME}", fontWeight = FontWeight.Bold, fontSize = 18.sp)
            Text(tr("Εφαρμογή για το AirSense (BleBox humiditySensor)", "Companion app for AirSense (BleBox humiditySensor)"))
            Spacer(Modifier.height(8.dp))
            Text("Developer: Nikolaos K. Paridis (aka nikkpap)")
            Text("ALU DEV TEAM", color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            Text(tr("Καιρός: Open-Meteo.com (CC BY 4.0)", "Weather data: Open-Meteo.com (CC BY 4.0)"), fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(tr("Server: AirSense v1.4.1+ στον υπολογιστή (λεκτικά μέσα/έξω: v1.5.8+)", "Server: AirSense v1.4.1+ on the PC (in/out labels: v1.5.8+)"),
                fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = { vm.resetSetup() }) { Text(tr("Οδηγός σύνδεσης από την αρχή", "Run connection setup again")) }
        }
        Spacer(Modifier.height(20.dp))
    }
}
