plugins {
    alias(libs.plugins.nyayaai.android.feature)
}

android {
    namespace = "ai.nyayaai.feature.settings"
}

dependencies {
    implementation(libs.androidx.appcompat)
}
