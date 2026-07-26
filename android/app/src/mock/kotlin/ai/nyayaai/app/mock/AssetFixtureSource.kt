package ai.nyayaai.app.mock

import ai.nyayaai.core.network.fixture.FixtureSource
import android.content.Context
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Reads recorded contract responses from `app/src/mock/assets/fixtures/`.
 *
 * Only the mock flavor contributes this binding — `NetworkBindings` declares the
 * dependency as optional so staging and prod build without it.
 */
@Singleton
class AssetFixtureSource
    @Inject
    constructor(
        @ApplicationContext private val context: Context,
    ) : FixtureSource {
        override fun read(name: String): String? =
            runCatching {
                context.assets
                    .open("fixtures/$name.json")
                    .bufferedReader()
                    .use { it.readText() }
            }.getOrNull()
    }

@Module
@InstallIn(SingletonComponent::class)
abstract class MockFixtureModule {
    @Binds
    @Singleton
    abstract fun bindFixtureSource(impl: AssetFixtureSource): FixtureSource
}
