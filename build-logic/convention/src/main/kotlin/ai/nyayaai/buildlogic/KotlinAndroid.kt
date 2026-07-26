package ai.nyayaai.buildlogic

import com.android.build.api.dsl.CommonExtension
import org.gradle.api.JavaVersion
import org.gradle.api.Project
import org.gradle.api.artifacts.VersionCatalog
import org.gradle.api.artifacts.VersionCatalogsExtension
import org.gradle.kotlin.dsl.getByType
import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import org.jetbrains.kotlin.gradle.dsl.KotlinAndroidProjectExtension

val Project.libs: VersionCatalog
    get() = extensions.getByType<VersionCatalogsExtension>().named("libs")

fun VersionCatalog.int(alias: String): Int = findVersion(alias).get().requiredVersion.toInt()

/**
 * Shared Android + Kotlin configuration applied to every module so the ~16 build files
 * stay three lines long.
 *
 * Written using **property access** (`defaultConfig.minSdk = ...`) rather than the
 * `defaultConfig { }` lambda form. Both work on AGP 8, but only property access exists on
 * `CommonExtension` in AGP 9 — so this file survives that upgrade untouched.
 */
internal fun Project.configureKotlinAndroid(extension: CommonExtension<*, *, *, *, *, *>) {
    extension.compileSdk = libs.int("compileSdk")
    extension.defaultConfig.minSdk = libs.int("minSdk")

    extension.compileOptions.sourceCompatibility = JavaVersion.VERSION_17
    extension.compileOptions.targetCompatibility = JavaVersion.VERSION_17
    extension.compileOptions.isCoreLibraryDesugaringEnabled = true

    // B.11 / D.4.3: every user-visible string must be localizable and translated. These
    // are the guardrails that keep EN/HI parity from rotting into a release-week scramble.
    extension.lint.error += setOf("HardcodedText", "MissingTranslation")
    extension.lint.abortOnError = true
    extension.lint.checkDependencies = true

    extensions.getByType<KotlinAndroidProjectExtension>().compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
        freeCompilerArgs.addAll(
            "-opt-in=kotlin.RequiresOptIn",
            // kotlin.time.Instant is the stdlib instant type we standardise on; the opt-in
            // is harmless once it is fully stable and saves an annotation on every file.
            "-opt-in=kotlin.time.ExperimentalTime",
            "-Xconsistent-data-class-copy-visibility",
        )
    }

    dependencies.add("coreLibraryDesugaring", "com.android.tools:desugar_jdk_libs:2.1.5")
}
