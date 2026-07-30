import ai.nyayaai.buildlogic.configureKotlinAndroid
import ai.nyayaai.buildlogic.int
import ai.nyayaai.buildlogic.libs
import com.android.build.api.dsl.ApplicationExtension
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.configure
import org.gradle.kotlin.dsl.dependencies

/**
 * B.2 environments as build flavors. Combining with Part 1 at the end of the project is
 * selecting the `prod` flavor — there is no code change, by design (D.2).
 */
class AndroidApplicationConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            pluginManager.apply("com.android.application")
            pluginManager.apply("org.jetbrains.kotlin.android")

            extensions.configure<ApplicationExtension> {
                configureKotlinAndroid(this)
                defaultConfig {
                    targetSdk = libs.int("targetSdk")
                    testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
                }

                buildFeatures.buildConfig = true

                flavorDimensions += "env"
                productFlavors {
                    create("mock") {
                        dimension = "env"
                        applicationIdSuffix = ".mock"
                        versionNameSuffix = "-mock"
                        // Fixtures are served by an OkHttp interceptor, but the base URL is
                        // still real so that swapping to `prism mock openapi.yaml` on
                        // localhost:4010 is a one-line change. 10.0.2.2 is the host from
                        // inside the emulator.
                        buildConfigField("String", "BASE_URL", "\"http://10.0.2.2:4010/v1/\"")
                        buildConfigField("boolean", "USE_FIXTURES", "true")
                        buildConfigField("String", "RAZORPAY_KEY_ID", "\"rzp_test_placeholder\"")
                    }
                    create("staging") {
                        dimension = "env"
                        applicationIdSuffix = ".staging"
                        versionNameSuffix = "-staging"
                        buildConfigField(
                            "String",
                            "BASE_URL",
                            // The deployed staging server (Render + Neon). HTTPS, so the
                            // cleartext exception in the staging network-security config
                            // is now only there for a local 10.0.2.2 server.
                            "\"https://nyayaai-api.onrender.com/v1/\"",
                        )
                        buildConfigField("boolean", "USE_FIXTURES", "false")
                        buildConfigField("String", "RAZORPAY_KEY_ID", "\"rzp_test_placeholder\"")
                    }
                    create("prod") {
                        dimension = "env"
                        buildConfigField("String", "BASE_URL", "\"https://api.nyayaai.in/v1/\"")
                        buildConfigField("boolean", "USE_FIXTURES", "false")
                        // Replaced from keystore.properties at release time (W15 handoff).
                        buildConfigField("String", "RAZORPAY_KEY_ID", "\"rzp_live_placeholder\"")
                    }
                }
            }

            dependencies {
                add("testImplementation", libs.findLibrary("junit").get())
                add("testImplementation", libs.findLibrary("kotlinx-coroutines-test").get())
                add("testImplementation", libs.findLibrary("turbine").get())
            }
        }
    }
}
