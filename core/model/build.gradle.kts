plugins {
    alias(libs.plugins.nyayaai.android.library)
}

android {
    namespace = "ai.nyayaai.core.model"
}

dependencies {
    api(libs.kotlinx.datetime)
}
