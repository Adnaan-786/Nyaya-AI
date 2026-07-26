plugins {
    alias(libs.plugins.nyayaai.android.library)
    alias(libs.plugins.nyayaai.android.compose)
}

android {
    namespace = "ai.nyayaai.core.designsystem"
}

dependencies {
    implementation(projects.core.common)
    implementation(libs.androidx.core.ktx)
    api(libs.androidx.compose.material.icons.extended)
}
