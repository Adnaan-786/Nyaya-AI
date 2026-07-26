import ai.nyayaai.buildlogic.libs
import com.android.build.api.dsl.CommonExtension
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.dependencies

class AndroidComposeConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            pluginManager.apply("org.jetbrains.kotlin.plugin.compose")

            // The `android` extension is registered as BaseAppModuleExtension or
            // LibraryExtension depending on the module, so it cannot be looked up by the
            // CommonExtension supertype — fetch it by name and narrow.
            @Suppress("UNCHECKED_CAST")
            val extension = extensions.getByName("android") as CommonExtension<*, *, *, *, *, *>
            extension.buildFeatures.compose = true

            dependencies {
                val bom = libs.findLibrary("androidx-compose-bom").get()
                add("implementation", platform(bom))
                add("androidTestImplementation", platform(bom))

                add("implementation", libs.findLibrary("androidx-compose-ui").get())
                add("implementation", libs.findLibrary("androidx-compose-ui-graphics").get())
                add(
                    "implementation",
                    libs.findLibrary("androidx-compose-ui-tooling-preview").get(),
                )
                add("implementation", libs.findLibrary("androidx-compose-material3").get())
                add(
                    "implementation",
                    libs.findLibrary("androidx-lifecycle-runtime-compose").get(),
                )
                add(
                    "implementation",
                    libs.findLibrary("androidx-lifecycle-viewmodel-compose").get(),
                )

                add("debugImplementation", libs.findLibrary("androidx-compose-ui-tooling").get())
                add(
                    "debugImplementation",
                    libs.findLibrary("androidx-compose-ui-test-manifest").get(),
                )
                add(
                    "androidTestImplementation",
                    libs.findLibrary("androidx-compose-ui-test-junit4").get(),
                )
            }
        }
    }
}
