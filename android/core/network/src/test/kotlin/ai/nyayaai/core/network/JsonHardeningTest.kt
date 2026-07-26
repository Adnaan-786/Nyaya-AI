package ai.nyayaai.core.network

import ai.nyayaai.core.model.AiJobStatus
import ai.nyayaai.core.model.CaseStatus
import ai.nyayaai.core.model.UserRole
import ai.nyayaai.core.network.api.ApiEnvelope
import ai.nyayaai.core.network.dto.UserDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * B.13 permits the server to add fields and enum values additively after the contract
 * freeze. Each test here is a server change that ships without an app release — and must
 * not crash the installed app.
 */
class JsonHardeningTest {
    private val json = NyayaJson

    @Test
    fun `unknown fields added by the server are ignored`() {
        val body =
            """
            {"success":true,
             "data":{"id":"11111111-1111-4111-8111-111111111111",
                     "tenant_id":"22222222-2222-4222-8222-222222222222",
                     "name":"Adv. Meera Raghavan","phone":"+919812345678",
                     "role":"lawyer","language":"hi",
                     "created_at":"2026-07-23T10:30:00Z",
                     "practice_areas":["criminal","family"],
                     "seniority_years":12},
             "error":null}
            """.trimIndent()

        val envelope =
            json.decodeFromString(
                ApiEnvelope.serializer(UserDto.serializer()),
                body,
            )

        assertEquals("Adv. Meera Raghavan", envelope.data?.name)
    }

    @Test
    fun `snake_case wire names map to camelCase properties without SerialName`() {
        val body =
            """
            {"id":"11111111-1111-4111-8111-111111111111",
             "tenant_id":"22222222-2222-4222-8222-222222222222",
             "created_at":"2026-07-23T10:30:00Z"}
            """.trimIndent()

        val dto = json.decodeFromString(UserDto.serializer(), body)

        assertEquals("22222222-2222-4222-8222-222222222222", dto.tenantId)
        assertEquals("2026-07-23T10:30:00Z", dto.createdAt)
    }

    @Test
    fun `absent and explicitly null optional fields both decode to null`() {
        val absent = json.decodeFromString(UserDto.serializer(), """{"name":"A"}""")
        val explicit =
            json.decodeFromString(
                UserDto.serializer(),
                """{"name":"A","email":null}""",
            )

        assertNull(absent.email)
        assertNull(explicit.email)
    }

    @Test
    fun `unknown enum values fall back instead of throwing`() {
        // Every one of these is a plausible additive server change.
        assertEquals(CaseStatus.UNKNOWN, CaseStatus.from("under_appeal"))
        assertEquals(AiJobStatus.UNKNOWN, AiJobStatus.from("throttled"))
        assertEquals(UserRole.UNKNOWN, UserRole.from("paralegal"))
    }

    @Test
    fun `known enum values decode case-insensitively and across separators`() {
        assertEquals(CaseStatus.ACTIVE, CaseStatus.from("active"))
        assertEquals(CaseStatus.ACTIVE, CaseStatus.from("ACTIVE"))
        assertEquals(UserRole.FIRM_ADMIN, UserRole.from("firm_admin"))
        assertEquals(UserRole.FIRM_ADMIN, UserRole.from("firm-admin"))
    }

    @Test
    fun `null enum decodes to the safe default rather than crashing`() {
        assertEquals(CaseStatus.UNKNOWN, CaseStatus.from(null))
        assertEquals(UserRole.UNKNOWN, UserRole.from(null))
    }
}
