plugins {
    alias(libs.plugins.nyayaai.android.feature)
}

android {
    namespace = "ai.nyayaai.feature.cases"
}

dependencies {
    implementation(projects.feature.clients)
}
