package ai.nyayaai.core.common

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class DeepLinkTest {
    private val id = "6f1c8d20-9a3b-4c5d-8e7f-0a1b2c3d4e5f"

    @Test
    fun `parses every link in the B8 table`() {
        assertEquals(DeepLink.Case(id), DeepLink.parse("nyayaai://case/$id"))
        assertEquals(DeepLink.Job(id), DeepLink.parse("nyayaai://job/$id"))
        assertEquals(DeepLink.Invoice(id), DeepLink.parse("nyayaai://invoice/$id"))
        assertEquals(DeepLink.Task(id), DeepLink.parse("nyayaai://task/$id"))
        assertEquals(DeepLink.Today, DeepLink.parse("nyayaai://today"))
    }

    @Test
    fun `round-trips through toUri`() {
        listOf(
            DeepLink.Case(id),
            DeepLink.Job(id),
            DeepLink.Invoice(id),
            DeepLink.Task(id),
            DeepLink.Today,
        ).forEach { link ->
            assertEquals(link, DeepLink.parse(link.toUri()))
        }
    }

    @Test
    fun `tolerates trailing slashes and query strings`() {
        assertEquals(DeepLink.Today, DeepLink.parse("nyayaai://today/"))
        assertEquals(DeepLink.Case(id), DeepLink.parse("nyayaai://case/$id?from=push"))
    }

    @Test
    fun `an unknown target resolves to null instead of crashing`() {
        // A server shipping a new push type ahead of this client release (B.13) must
        // degrade to "open Today", never to a crash on a cold-start intent.
        assertNull(DeepLink.parse("nyayaai://hearing/$id"))
        assertNull(DeepLink.parse("nyayaai://"))
        assertNull(DeepLink.parse("nyayaai://case/"))
        assertNull(DeepLink.parse("nyayaai://case"))
    }

    @Test
    fun `rejects links that are not ours`() {
        assertNull(DeepLink.parse("https://nyayaai.in/case/$id"))
        assertNull(DeepLink.parse("nyaya://case/$id"))
        assertNull(DeepLink.parse(""))
        assertNull(DeepLink.parse(null))
    }
}
