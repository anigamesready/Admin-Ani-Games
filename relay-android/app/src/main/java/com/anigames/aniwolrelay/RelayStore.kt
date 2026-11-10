package com.anigames.aniwolrelay
import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

data class RelayCredentials(val relayId: String, val token: String)

object RelayStore {
    private const val PREFS = "ani_wol_relay_secure"
    private fun prefs(context: Context) = EncryptedSharedPreferences.create(
        context, PREFS,
        MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )
    fun credentials(context: Context): RelayCredentials? {
        val p = prefs(context)
        val id = p.getString("relay_id", null)
        val token = p.getString("relay_token", null)
        return if (!id.isNullOrBlank() && !token.isNullOrBlank()) RelayCredentials(id, token) else null
    }
    fun save(context: Context, value: RelayCredentials) {
        prefs(context).edit().putString("relay_id", value.relayId)
            .putString("relay_token", value.token).putBoolean("relay_enabled", true).apply()
    }
    fun clear(context: Context) { prefs(context).edit().clear().apply() }
    fun enabled(context: Context) = prefs(context).getBoolean("relay_enabled", false)
    fun setEnabled(context: Context, value: Boolean) { prefs(context).edit().putBoolean("relay_enabled", value).apply() }
    fun installationId(context: Context): String {
        val p = prefs(context)
        val old = p.getString("installation_id", null)
        if (!old.isNullOrBlank()) return old
        val value = java.util.UUID.randomUUID().toString()
        p.edit().putString("installation_id", value).apply()
        return value
    }
}
