package com.anigames.aniwolrelay
import android.os.Build
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

object RelayApi {
    private const val BASE_URL = "https://wzkjpycjizexxcxrfdvr.supabase.co/functions/v1/ani-games-api"
    private const val ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind6a2pweWNqaXpleHhjeHJmZHZyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTEwMzc0OTUsImV4cCI6MjEwNjYxMzQ5NX0.lxjSt7CqWDJhKItPi1ckVRIcc-kM7etMzxTu3txANaI"
    const val APP_VERSION = "1.0.2"

    suspend fun register(code: String, installationId: String): RelayCredentials = withContext(Dispatchers.IO) {
        val body = JSONObject().put("code", code.trim().uppercase())
            .put("relayName", "Ani WoL Relay - ${Build.MODEL.take(40)}")
            .put("installationId", installationId).put("appVersion", APP_VERSION).put("model", Build.MODEL)
        val response = post("wol/relay/register", body)
        if (!response.optBoolean("ok")) throw IllegalStateException(response.optString("error", "Pairing ditolak"))
        val id = response.optString("relayId")
        val token = response.optString("relayToken")
        if (id.isBlank() || token.length < 32) throw IllegalStateException("Respons pairing tidak lengkap")
        RelayCredentials(id, token)
    }

    suspend fun heartbeat(credentials: RelayCredentials, metrics: JSONObject) = withContext(Dispatchers.IO) {
        post("wol/relay/heartbeat", auth(credentials).put("metrics", metrics))
    }
    suspend fun poll(credentials: RelayCredentials): JSONObject = withContext(Dispatchers.IO) {
        post("wol/relay/poll", auth(credentials))
    }
    suspend fun acknowledge(credentials: RelayCredentials, commandId: String, status: String, result: JSONObject) = withContext(Dispatchers.IO) {
        post("wol/relay/ack", auth(credentials).put("commandId", commandId).put("status", status).put("result", result))
    }

    suspend fun acknowledgeProbe(credentials: RelayCredentials, probeId: String, nonce: String, metrics: JSONObject) = withContext(Dispatchers.IO) {
        post("wol/relay/probe-ack", auth(credentials)
            .put("probeId", probeId)
            .put("nonce", nonce)
            .put("metrics", metrics))
    }
    private fun auth(c: RelayCredentials) = JSONObject().put("relayId", c.relayId).put("token", c.token)

    private fun post(path: String, body: JSONObject): JSONObject {
        val c = URL("$BASE_URL/$path").openConnection() as HttpURLConnection
        c.requestMethod = "POST"
        c.connectTimeout = 10000
        c.readTimeout = 20000
        c.doOutput = true
        c.setRequestProperty("apikey", ANON_KEY)
        c.setRequestProperty("Content-Type", "application/json")
        c.setRequestProperty("Accept", "application/json")
        c.setRequestProperty("Cache-Control", "no-store")
        try {
            c.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            val stream = if (c.responseCode in 200..299) c.inputStream else c.errorStream
            val text = BufferedReader(InputStreamReader(stream, Charsets.UTF_8)).use { it.readText() }
            val json = if (text.isBlank()) JSONObject() else JSONObject(text)
            if (c.responseCode !in 200..299) throw IllegalStateException(
                json.optString("error", json.optString("message", "HTTP ${c.responseCode}")))
            return json
        } finally { c.disconnect() }
    }
}
