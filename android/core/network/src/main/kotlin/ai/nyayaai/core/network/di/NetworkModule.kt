package ai.nyayaai.core.network.di

import ai.nyayaai.core.network.NetworkConfig
import ai.nyayaai.core.network.NyayaJson
import ai.nyayaai.core.network.auth.EncryptedTokenStore
import ai.nyayaai.core.network.auth.TokenAuthenticator
import ai.nyayaai.core.network.auth.TokenStore
import ai.nyayaai.core.network.fixture.FixtureInterceptor
import ai.nyayaai.core.network.fixture.FixtureSource
import ai.nyayaai.core.network.interceptor.AuthInterceptor
import ai.nyayaai.core.network.interceptor.IdempotencyInterceptor
import ai.nyayaai.core.network.service.AiService
import ai.nyayaai.core.network.service.AuthRefreshService
import ai.nyayaai.core.network.service.AuthService
import ai.nyayaai.core.network.service.BillingService
import ai.nyayaai.core.network.service.CalendarService
import ai.nyayaai.core.network.service.CaseService
import ai.nyayaai.core.network.service.DocumentService
import ai.nyayaai.core.network.service.NotificationService
import ai.nyayaai.core.network.service.PortalService
import ai.nyayaai.core.network.service.UserService
import dagger.Binds
import dagger.BindsOptionalOf
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.Optional
import java.util.concurrent.TimeUnit
import javax.inject.Qualifier
import javax.inject.Singleton

/** The client used to refresh tokens — no authenticator, so it cannot recurse. */
@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class RefreshClient

@Module
@InstallIn(SingletonComponent::class)
abstract class NetworkBindings {
    /**
     * Only the mock flavor contributes a [FixtureSource]. Declaring it optional lets the
     * same DI graph compile for staging and prod, where no fixtures exist.
     */
    @BindsOptionalOf
    abstract fun optionalFixtureSource(): FixtureSource

    @Binds
    @Singleton
    abstract fun bindTokenStore(impl: EncryptedTokenStore): TokenStore
}

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {
    @Provides
    @Singleton
    fun provideJson(): Json = NyayaJson

    @Provides
    @Singleton
    @RefreshClient
    fun provideRefreshClient(config: NetworkConfig): OkHttpClient =
        OkHttpClient
            .Builder()
            .connectTimeout(CONNECT_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .readTimeout(READ_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .apply { if (config.enableHttpLogging) addInterceptor(loggingInterceptor()) }
            .build()

    @Provides
    @Singleton
    fun provideOkHttpClient(
        config: NetworkConfig,
        authInterceptor: AuthInterceptor,
        idempotencyInterceptor: IdempotencyInterceptor,
        authenticator: TokenAuthenticator,
        fixtureSource: Optional<FixtureSource>,
    ): OkHttpClient =
        OkHttpClient
            .Builder()
            .connectTimeout(CONNECT_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .readTimeout(READ_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .writeTimeout(WRITE_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .addInterceptor(authInterceptor)
            .addInterceptor(idempotencyInterceptor)
            .apply {
                if (config.enableHttpLogging) addInterceptor(loggingInterceptor())
                // Added last so the fixture response is what the interceptors above just
                // decorated — auth headers and idempotency keys are exercised, not bypassed.
                if (config.useFixtures && fixtureSource.isPresent) {
                    addInterceptor(FixtureInterceptor(fixtureSource.get()))
                }
            }.authenticator(authenticator)
            .build()

    @Provides
    @Singleton
    fun provideRetrofit(
        client: OkHttpClient,
        json: Json,
        config: NetworkConfig,
    ): Retrofit =
        Retrofit
            .Builder()
            .baseUrl(config.baseUrl)
            .client(client)
            .addConverterFactory(json.asConverterFactory(JSON_MEDIA_TYPE.toMediaType()))
            .build()

    @Provides
    @Singleton
    @RefreshClient
    fun provideRefreshRetrofit(
        @RefreshClient client: OkHttpClient,
        json: Json,
        config: NetworkConfig,
    ): Retrofit =
        Retrofit
            .Builder()
            .baseUrl(config.baseUrl)
            .client(client)
            .addConverterFactory(json.asConverterFactory(JSON_MEDIA_TYPE.toMediaType()))
            .build()

    @Provides
    @Singleton
    fun provideAuthService(retrofit: Retrofit): AuthService = retrofit.create(AuthService::class.java)

    @Provides
    @Singleton
    fun provideAuthRefreshService(
        @RefreshClient retrofit: Retrofit,
    ): AuthRefreshService = retrofit.create(AuthRefreshService::class.java)

    // Feature services. All share the one authenticated client above, so every feature
    // gets envelope unwrapping, token refresh and idempotency without opting in.
    @Provides
    @Singleton
    fun provideCaseService(retrofit: Retrofit): CaseService = retrofit.create(CaseService::class.java)

    @Provides
    @Singleton
    fun provideCalendarService(retrofit: Retrofit): CalendarService = retrofit.create(CalendarService::class.java)

    @Provides
    @Singleton
    fun provideDocumentService(retrofit: Retrofit): DocumentService = retrofit.create(DocumentService::class.java)

    @Provides
    @Singleton
    fun provideBillingService(retrofit: Retrofit): BillingService = retrofit.create(BillingService::class.java)

    @Provides
    @Singleton
    fun provideAiService(retrofit: Retrofit): AiService = retrofit.create(AiService::class.java)

    @Provides
    @Singleton
    fun providePortalService(retrofit: Retrofit): PortalService = retrofit.create(PortalService::class.java)

    @Provides
    @Singleton
    fun provideNotificationService(retrofit: Retrofit): NotificationService =
        retrofit.create(NotificationService::class.java)

    @Provides
    @Singleton
    fun provideUserService(retrofit: Retrofit): UserService = retrofit.create(UserService::class.java)

    private fun loggingInterceptor() =
        HttpLoggingInterceptor().apply {
            // BODY only ever runs in debug builds. Privileged legal documents and OTPs must
            // never reach logcat on a release build.
            level = HttpLoggingInterceptor.Level.BODY
            redactHeader("Authorization")
        }

    private const val JSON_MEDIA_TYPE = "application/json"
    private const val CONNECT_TIMEOUT_SECONDS = 15L
    private const val READ_TIMEOUT_SECONDS = 30L
    private const val WRITE_TIMEOUT_SECONDS = 30L
}
