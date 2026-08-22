import java.util.Properties

plugins {
    alias(libs.plugins.nyayaai.android.application)
    alias(libs.plugins.nyayaai.android.compose)
    alias(libs.plugins.nyayaai.android.hilt)
}

// Release signing, kept out of the repository. `keystore.properties` and the keystore it
// points at are gitignored: the upload key is the one credential that cannot be rotated
// — lose it and this applicationId can never be updated on Play again, by anyone.
//
// Absent (CI, a fresh clone, anyone who is not publishing), the release variant simply
// builds unsigned, exactly as before, rather than failing the build for everyone who
// does not need to sign.
val keystorePropertiesFile = rootProject.file("keystore.properties")
val keystoreProperties =
    Properties().apply {
        if (keystorePropertiesFile.exists()) {
            keystorePropertiesFile.inputStream().use(::load)
        }
    }

// The google-services plugin hard-fails in two different ways, and both would stop
// people building this app:
//
//   1. google-services.json missing entirely -> every variant fails.
//   2. The file present but with no client for that variant's applicationId -> only
//      that variant fails ("No matching client found for package name ...").
//
// Case 2 is the normal state while a Firebase project is being filled in one package at
// a time, and it would break `assembleMockDebug` in CI purely because nobody had yet
// registered ai.nyayaai.mock. So the plugin is applied when the file exists, and its
// processing task is switched off for exactly the variants the file does not cover —
// those build fine and simply have no FCM, which is the honest outcome.
val firebaseConfig = file("google-services.json")
val firebasePackages: Set<String> =
    if (firebaseConfig.exists()) {
        Regex("\"package_name\"\\s*:\\s*\"([^\"]+)\"")
            .findAll(firebaseConfig.readText())
            .map { it.groupValues[1] }
            .toSet()
    } else {
        emptySet()
    }

if (firebaseConfig.exists()) {
    apply(
        plugin =
            libs.plugins.google.services
                .get()
                .pluginId,
    )
} else {
    logger.lifecycle("google-services.json not found — building without FCM. See docs/INTEGRATIONS.md")
}

android {
    namespace = "ai.nyayaai.app"

    defaultConfig {
        applicationId = "ai.nyayaai"
        versionCode = 1
        versionName = "0.1.0"
        // Hilt needs its own Application during instrumented tests.
        testInstrumentationRunner = "ai.nyayaai.app.HiltTestRunner"
    }

    signingConfigs {
        if (keystorePropertiesFile.exists()) {
            create("release") {
                storeFile = file(keystoreProperties.getProperty("storeFile"))
                storePassword = keystoreProperties.getProperty("storePassword")
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
            }
        } else {
            logger.lifecycle(
                "keystore.properties not found — release builds will be unsigned. " +
                    "See docs/RELEASING.md to publish.",
            )
        }
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
        }
        release {
            // findByName, not getByName: null leaves the variant unsigned, which is the
            // documented state for anyone without the key. Deliberately never falls back
            // to the debug key — that produces an APK that installs happily in testing
            // and is then rejected by Play, after the build has already claimed success.
            signingConfig = signingConfigs.findByName("release")
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
}

// Flavor -> the applicationId that flavor produces, which is what google-services
// matches against.
val flavorApplicationIds =
    mapOf(
        "mock" to "ai.nyayaai.mock",
        "staging" to "ai.nyayaai.staging",
        "prod" to "ai.nyayaai",
    )

tasks
    .matching { it.name.startsWith("process") && it.name.endsWith("GoogleServices") }
    .configureEach {
        val flavor = flavorApplicationIds.keys.firstOrNull { name.contains(it, ignoreCase = true) }
        val applicationId = flavorApplicationIds[flavor]

        if (applicationId != null && applicationId !in firebasePackages) {
            enabled = false
            logger.lifecycle(
                "No Firebase client for $applicationId — building that variant without FCM. " +
                    "Add the package in the Firebase console to enable push there.",
            )
        }
    }

dependencies {
    implementation(projects.core.common)
    implementation(projects.core.model)
    implementation(projects.core.network)
    implementation(projects.core.database)
    implementation(projects.core.designsystem)

    implementation(projects.feature.auth)
    implementation(projects.feature.dashboard)
    implementation(projects.feature.cases)
    implementation(projects.feature.documents)
    implementation(projects.feature.ai)
    implementation(projects.feature.calendar)
    implementation(projects.feature.billing)
    implementation(projects.feature.tasks)
    implementation(projects.feature.clients)
    implementation(projects.feature.portal)
    implementation(projects.feature.settings)
    implementation(projects.feature.notifications)
    implementation(projects.feature.team)

    // MainActivity implements Razorpay's PaymentResultWithDataListener: the SDK
    // reports to the Activity, not to the screen that opened Checkout.
    implementation(libs.razorpay.checkout)

    implementation(platform(libs.firebase.bom))
    implementation(libs.firebase.messaging)
    implementation(libs.kotlinx.coroutines.play.services)

    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.androidx.compose.material.icons.extended)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.hilt.navigation.compose)

    // D.7: NyayaApplication supplies the HiltWorkerFactory that lets ScanUploadWorker
    // (feature:documents) be constructed with its real dependencies. See NyayaApplication.
    implementation(libs.androidx.work.runtime.ktx)
    implementation(libs.androidx.hilt.work)

    androidTestImplementation(libs.androidx.test.junit)
    androidTestImplementation(libs.androidx.test.espresso.core)
    androidTestImplementation(libs.hilt.android.testing)
    kspAndroidTest(libs.hilt.compiler)
}
