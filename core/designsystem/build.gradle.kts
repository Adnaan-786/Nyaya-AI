plugins {
    alias(libs.plugins.nyayaai.android.library)
    alias(libs.plugins.nyayaai.android.compose)
}

android {
    namespace = "ai.nyayaai.core.designsystem"
}

dependencies {
    // `api`, not `implementation`: components take domain types (CourtDate, Paise) in their
    // public signatures, so features must see them transitively.
    api(projects.core.common)
    implementation(libs.androidx.core.ktx)
    api(libs.androidx.compose.material.icons.extended)
}
