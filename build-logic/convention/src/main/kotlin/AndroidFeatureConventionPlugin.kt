import ai.nyayaai.buildlogic.libs
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.dependencies
import org.gradle.kotlin.dsl.project

/**
 * D.2 rule: features depend on core, never on each other. This plugin wires exactly the
 * core modules a feature is allowed to see — adding a `feature:*` dependency to a feature
 * module is a review-blocking mistake, not a convenience.
 */
class AndroidFeatureConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            pluginManager.apply("nyayaai.android.library")
            pluginManager.apply("nyayaai.android.compose")
            pluginManager.apply("nyayaai.android.hilt")

            dependencies {
                add("implementation", project(":core:common"))
                add("implementation", project(":core:model"))
                add("implementation", project(":core:designsystem"))
                add("implementation", project(":core:network"))

                add("implementation", libs.findLibrary("androidx-core-ktx").get())
                add("implementation", libs.findLibrary("androidx-lifecycle-runtime-ktx").get())
                add("implementation", libs.findLibrary("androidx-navigation-compose").get())
                add("implementation", libs.findLibrary("androidx-hilt-navigation-compose").get())
                add("implementation", libs.findLibrary("kotlinx-datetime").get())
            }
        }
    }
}
