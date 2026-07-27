plugins {
    alias(libs.plugins.nyayaai.android.application)
    alias(libs.plugins.nyayaai.android.compose)
    alias(libs.plugins.nyayaai.android.hilt)
}

// The google-services plugin hard-fails the build when google-services.json is absent,
// which would mean nobody could build or demo this app until a Firebase project existed.
// Applying it only when the file is present keeps push opt-in: drop the file in and FCM
// starts working, leave it out and everything else still runs.
val hasFirebaseConfig = file("google-services.json").exists()
if (hasFirebaseConfig) {
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

    buildTypes {
        debug {
            isMinifyEnabled = false
        }
        release {
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
    implementation(projects.feature.portal)
    implementation(projects.feature.settings)

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

    androidTestImplementation(libs.androidx.test.junit)
    androidTestImplementation(libs.androidx.test.espresso.core)
    androidTestImplementation(libs.hilt.android.testing)
    kspAndroidTest(libs.hilt.compiler)
}
