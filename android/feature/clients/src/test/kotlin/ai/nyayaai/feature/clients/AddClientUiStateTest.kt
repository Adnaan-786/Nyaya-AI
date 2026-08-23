package ai.nyayaai.feature.clients

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AddClientUiStateTest {

    @Test
    fun `isValid validates E164 format correctly`() {
        // Missing name
        assertFalse(AddClientUiState(name = "", phone = "+919812345678").isValid)

        // Valid with plus
        assertTrue(AddClientUiState(name = "John", phone = "+919812345678").isValid)
        
        // Valid without plus (local format fallback)
        assertTrue(AddClientUiState(name = "John", phone = "9812345678").isValid)
        
        // Invalid: too short (under 10 digits)
        assertFalse(AddClientUiState(name = "John", phone = "+919812").isValid)
        
        // Invalid: too long (over 15 digits)
        assertFalse(AddClientUiState(name = "John", phone = "+1234567890123456").isValid)
        
        // Invalid: contains letters
        assertFalse(AddClientUiState(name = "John", phone = "+9198ABC45678").isValid)
    }
}
