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
    fun recordNetworkSuccess(context: Context, stage: String) {
        val p = prefs(context)
        val safe = stage.lowercase().filter { it.isLetterOrDigit() || it == '_' }.take(24)
        val edit = p.edit().putLong("last_${safe}_success", System.currentTimeMillis())
        if (p.getString("last_error_stage", null) == safe) {
            edit.remove("last_error_stage").remove("last_error_message").remove("last_error_at")
        }
        edit.apply()
    }
    fun recordNetworkError(context: Context, stage: String, error: Throwable) {
        val safe = stage.lowercase().filter { it.isLetterOrDigit() || it == '_' }.take(24)
        val message = (error.message ?: error.javaClass.simpleName).replace(Regex("\\s+"), " ").take(180)
        prefs(context).edit().putString("last_error_stage", safe)
            .putString("last_error_message", message)
            .putLong("last_error_at", System.currentTimeMillis()).apply()
    }
    fun runtimeDiagnostics(context: Context): String {
        val p = prefs(context)
        fun age(key: String): String {
            val at = p.getLong(key, 0L)
            if (at <= 0L) return "belum pernah"
            val seconds = ((System.currentTimeMillis() - at).coerceAtLeast(0L) / 1000L)
            return when {
                seconds < 60 -> "${seconds} dtk lalu"
                seconds < 3600 -> "${seconds / 60} mnt lalu"
                else -> "${seconds / 3600} jam lalu"
            }
        }
        val stage = p.getString("last_error_stage", null)
        val error = p.getString("last_error_message", null)
        val problem = if (!stage.isNullOrBlank() && !error.isNullOrBlank()) " • Error $stage: $error" else ""
        return "Heartbeat: ${age("last_heartbeat_success")} • Poll: ${age("last_poll_success")}$problem"
    }
}