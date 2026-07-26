plugins {
    alias(libs.plugins.nyayaai.android.library)
    alias(libs.plugins.nyayaai.android.hilt)
}

android {
    namespace = "ai.nyayaai.core.common"
}

dependencies {
    api(projects.core.model)
    implementation(libs.androidx.core.ktx)
    implementation(libs.kotlinx.coroutines.android)
}
