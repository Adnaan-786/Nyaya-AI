plugins {
    alias(libs.plugins.nyayaai.android.application)
    alias(libs.plugins.nyayaai.android.compose)
    alias(libs.plugins.nyayaai.android.hilt)
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

    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.hilt.navigation.compose)

    androidTestImplementation(libs.androidx.test.junit)
    androidTestImplementation(libs.androidx.test.espresso.core)
    androidTestImplementation(libs.hilt.android.testing)
    kspAndroidTest(libs.hilt.compiler)
}
