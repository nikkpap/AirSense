import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "gr.nikkpap.airsense"
    compileSdk = 36

    defaultConfig {
        applicationId = "gr.nikkpap.airsense"
        minSdk = 26
        targetSdk = 36
        versionCode = 10
        versionName = "1.6.0"
    }

    // Υπογραφή: αν υπάρχει κλειδί (GitHub Secrets / μεταβλητές περιβάλλοντος) → σταθερή υπογραφή για ενημερώσεις,
    // αλλιώς το debug κλειδί ώστε το APK να εγκαθίσταται αμέσως.
    val ksFile = System.getenv("AIRSENSE_KEYSTORE")?.let { file(it) }?.takeIf { it.exists() }
    signingConfigs {
        if (ksFile != null) {
            create("release") {
                storeFile = ksFile
                storePassword = System.getenv("AIRSENSE_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("AIRSENSE_KEY_ALIAS") ?: "airsense"
                keyPassword = System.getenv("AIRSENSE_KEY_PASSWORD") ?: System.getenv("AIRSENSE_KEYSTORE_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = if (ksFile != null) signingConfigs.getByName("release") else signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    testOptions {
        unitTests {
            isIncludeAndroidResources = true
            all {
                it.systemProperties["roborazzi.test.record"] = "true"
                it.systemProperties["robolectric.pixelCopyRenderMode"] = "hardware"
                it.maxHeapSize = "2g"
            }
        }
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.06.00")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    debugImplementation("androidx.compose.ui:ui-tooling")

    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.fragment:fragment-ktx:1.8.8")   // νεότερο από αυτό που φέρνει το ML Kit (lint: ActivityResult)
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.9.1")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.1")
    implementation("androidx.work:work-runtime-ktx:2.10.2")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    // Σκανάρισμα QR χωρίς άδεια κάμερας (Google Play services)
    implementation("com.google.android.gms:play-services-code-scanner:16.1.0")

    // Screenshot tests (Robolectric + Roborazzi) — UI check in GitHub Actions, not in the APK
    testImplementation(composeBom)
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.14.1")
    testImplementation("androidx.test:core-ktx:1.6.1")
    testImplementation("androidx.compose.ui:ui-test-junit4")
    testImplementation("io.github.takahirom.roborazzi:roborazzi:1.44.0")
    testImplementation("io.github.takahirom.roborazzi:roborazzi-compose:1.44.0")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
