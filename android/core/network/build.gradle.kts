plugins {
    alias(libs.plugins.nyayaai.android.library)
    alias(libs.plugins.nyayaai.android.hilt)
    alias(libs.plugins.kotlin.serialization)
}

android {
    namespace = "ai.nyayaai.core.network"
    buildFeatures.buildConfig = true
}

dependencies {
    api(projects.core.model)
    implementation(projects.core.common)

    api(libs.retrofit.core)
    implementation(libs.retrofit.kotlinx.serialization)
    api(libs.okhttp.core)
    implementation(libs.okhttp.logging)
    api(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.android)

    implementation(libs.androidx.security.crypto)
    implementation(libs.androidx.datastore.preferences)

    testImplementation(libs.okhttp.mockwebserver)
}
