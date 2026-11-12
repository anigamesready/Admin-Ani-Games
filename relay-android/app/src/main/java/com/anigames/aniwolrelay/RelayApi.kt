package com.anigames.aniwolrelay

import android.os.Build
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.IOException
import java.util.concurrent.TimeUnit

object RelayApi {
    private const val BASE_URL = "https://wzkjpycjizexxcxrfdvr.supabase.co/functions/v1/ani-games-api"
    private const val ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind6a2pweWNqaXpleHhjeHJmZHZyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTEwMzc0OTUsImV4cCI6MjEwNjYxMzQ5NX0.lxjSt7CqWDJhKItPi1ckVRIcc-kM7etMzxTu3txANaI"
    const val APP_VERSION = "1.0.3"
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()
    private val client = OkHttpClient.Builder()
        .dns(RelayDns)
        .connectTimeout(12, TimeUnit.SECONDS)
        .writeTimeout(12, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .callTimeout(30, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    suspend fun register(code: String, installationId: String): RelayCredentials = withContext(Dispatchers.IO) {
        val body = JSONObject().put("code", code.trim().uppercase())
            .put("relayName", "Ani WoL Relay - " + Build.MODEL.take(40))
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

    private fun auth(credentials: RelayCredentials) =
        JSONObject().put("relayId", credentials.relayId).put("token", credentials.token)

    private fun post(path: String, body: JSONObject): JSONObject {
        val request = Request.Builder()
            .url("$BASE_URL/$path")
            .post(body.toString().toRequestBody(jsonMediaType))
            .header("apikey", ANON_KEY)
            .header("Accept", "application/json")
            .header("Cache-Control", "no-store")
            .build()
        client.newCall(request).execute().use { response ->
            val payload = response.body?.string().orEmpty()
            val json = try {
                if (payload.isBlank()) JSONObject() else JSONObject(payload)
            } catch (error: Exception) {
                throw IOException("Respons server bukan JSON valid (HTTP " + response.code + ")", error)
            }
            if (!response.isSuccessful) {
                throw IllegalStateException(
                    json.optString("error", json.optString("message", "HTTP " + response.code))
                )
            }
            return json
        }
    }
}
