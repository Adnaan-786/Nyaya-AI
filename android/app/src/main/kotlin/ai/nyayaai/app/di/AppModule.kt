package ai.nyayaai.app.di

import ai.nyayaai.app.BuildConfig
import ai.nyayaai.core.network.NetworkConfig
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * The one place the flavor's BuildConfig crosses into the rest of the app.
 *
 * `core:network` takes the environment as injected data rather than reading BuildConfig
 * itself, which is what lets the whole network stack be exercised in unit tests against a
 * MockWebServer URL — and what keeps the mock/staging/prod difference to one object.
 */
@Module
@InstallIn(SingletonComponent::class)
object AppModule {
    @Provides
    @Singleton
    fun provideNetworkConfig(): NetworkConfig =
        NetworkConfig(
            baseUrl = BuildConfig.BASE_URL,
            useFixtures = BuildConfig.USE_FIXTURES,
            appVersionCode = BuildConfig.VERSION_CODE,
            appVersionName = BuildConfig.VERSION_NAME,
            enableHttpLogging = BuildConfig.DEBUG,
        )
}
