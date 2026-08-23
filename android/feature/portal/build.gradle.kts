plugins {
    alias(libs.plugins.nyayaai.android.feature)
}

android {
    namespace = "ai.nyayaai.feature.portal"
}

dependencies {
    implementation(project(":feature:billing"))
}
