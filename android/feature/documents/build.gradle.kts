plugins {
    alias(libs.plugins.nyayaai.android.feature)
}

android {
    namespace = "ai.nyayaai.feature.documents"
}

dependencies {
    implementation(libs.mlkit.document.scanner)

    // D.7/B.9: the upload queue is a WorkManager CoroutineWorker so a scan survives app
    // kill and retries on connectivity restore, per the plan's "WorkManager-backed queue"
    // requirement — a plain suspend coroutine (what this used to be) dies with the process.
    implementation(libs.androidx.work.runtime.ktx)
    implementation(libs.androidx.hilt.work)
    ksp(libs.androidx.hilt.compiler)

    // ScanUploaderTest drives a real DocumentService against MockWebServer, the same way
    // core:network's own ApiCallerTest does — retrofit-core/okhttp-core are already `api`
    // dependencies of core:network so they resolve transitively, but the JSON converter
    // and MockWebServer itself are not.
    testImplementation(libs.retrofit.kotlinx.serialization)
    testImplementation(libs.okhttp.mockwebserver)
}
