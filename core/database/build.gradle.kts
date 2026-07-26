plugins {
    alias(libs.plugins.nyayaai.android.library)
    alias(libs.plugins.nyayaai.android.hilt)
    alias(libs.plugins.room)
}

android {
    namespace = "ai.nyayaai.core.database"
}

room {
    schemaDirectory("$projectDir/schemas")
}

dependencies {
    api(projects.core.model)
    implementation(projects.core.common)

    api(libs.androidx.room.runtime)
    api(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)
}
