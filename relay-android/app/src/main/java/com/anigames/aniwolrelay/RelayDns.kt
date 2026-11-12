package com.anigames.aniwolrelay

import okhttp3.Dns
import okhttp3.HttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.IOException
import java.net.InetAddress
import java.net.UnknownHostException
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit

/** Wi-Fi DNS first, then HTTPS DNS-over-HTTPS via Cloudflare and Google. */
internal object RelayDns : Dns {
    internal data class LookupResult(val addresses: List<InetAddress>, val ttlSeconds: Long)
    private data class CacheEntry(val addresses: List<InetAddress>, val expiresAtNanos: Long)
    private data class Provider(val host: String, val path: String)

    private val providers = listOf(
        Provider("cloudflare-dns.com", "dns-query"),
        Provider("dns.google", "resolve")
    )
    private val bootstrapDns = Dns { hostname ->
        when (hostname.lowercase(Locale.US)) {
            "cloudflare-dns.com" -> listOf(ipv4(1, 1, 1, 1), ipv4(1, 0, 0, 1))
            "dns.google" -> listOf(ipv4(8, 8, 8, 8), ipv4(8, 8, 4, 4))
            else -> throw UnknownHostException("No safe bootstrap address for " + hostname)
        }
    }
    private val dohClient = OkHttpClient.Builder()
        .dns(bootstrapDns)
        .connectTimeout(6, TimeUnit.SECONDS)
        .readTimeout(6, TimeUnit.SECONDS)
        .callTimeout(9, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()
    private val cache = ConcurrentHashMap<String, CacheEntry>()

    override fun lookup(hostname: String): List<InetAddress> {
        val host = hostname.trim().trimEnd('.').lowercase(Locale.US)
        if (host.isBlank()) throw UnknownHostException("Nama host kosong")
        if (isIpLiteral(host)) return listOf(InetAddress.getByName(host))

        val now = System.nanoTime()
        cache[host]?.let { entry ->
            if (entry.expiresAtNanos > now) return entry.addresses
            cache.remove(host, entry)
        }

        var systemError: Exception? = null
        try {
            val result = Dns.SYSTEM.lookup(hostname)
            if (result.isNotEmpty()) {
                cache[host] = CacheEntry(result, now + TimeUnit.MINUTES.toNanos(2))
                return result
            }
        } catch (error: Exception) {
            systemError = error
        }

        val result = try {
            resolveWithDoh(host)
        } catch (error: Exception) {
            val failure = UnknownHostException(
                "DNS Wi-Fi gagal; resolver aman Cloudflare/Google juga gagal untuk " + host
            )
            failure.initCause(error)
            throw failure
        }
        if (result.addresses.isEmpty()) {
            val failure = UnknownHostException("DNS aman tidak menemukan alamat untuk " + host)
            if (systemError != null) failure.initCause(systemError)
            throw failure
        }

        cache[host] = CacheEntry(
            result.addresses,
            now + TimeUnit.SECONDS.toNanos(result.ttlSeconds.coerceIn(30, 600))
        )
        return result.addresses
    }

    private fun resolveWithDoh(hostname: String): LookupResult {
        var lastError: Exception? = null
        for (provider in providers) {
            try {
                val url = HttpUrl.Builder()
                    .scheme("https")
                    .host(provider.host)
                    .addPathSegment(provider.path)
                    .addQueryParameter("name", hostname)
                    .addQueryParameter("type", "A")
                    .build()
                val request = Request.Builder()
                    .url(url)
                    .header("Accept", "application/dns-json")
                    .get()
                    .build()
                dohClient.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) {
                        throw IOException("DNS " + provider.host + " HTTP " + response.code)
                    }
                    val payload = response.body?.string()
                        ?: throw IOException("Jawaban DNS " + provider.host + " kosong")
                    val parsed = parseDnsJson(payload)
                    if (parsed.addresses.isNotEmpty()) return parsed
                }
            } catch (error: Exception) {
                lastError = error
            }
        }
        val failure = UnknownHostException("Semua resolver DNS aman gagal untuk " + hostname)
        if (lastError != null) failure.initCause(lastError)
        throw failure
    }

    internal fun parseDnsJson(payload: String): LookupResult {
        val root = JSONObject(payload)
        if (root.optInt("Status", -1) != 0) return LookupResult(emptyList(), 60)
        val answers = root.optJSONArray("Answer") ?: return LookupResult(emptyList(), 60)
        val found = LinkedHashMap<String, InetAddress>()
        var ttl = 600L
        for (index in 0 until answers.length()) {
            val answer = answers.optJSONObject(index) ?: continue
            val value = answer.optString("data", "").trim().trimEnd('.')
            val address = when (answer.optInt("type", -1)) {
                1 -> parseIpv4(value)
                28 -> parseIpv6(value)
                else -> null
            } ?: continue
            found[address.hostAddress] = address
            ttl = minOf(ttl, answer.optLong("TTL", 60L).coerceAtLeast(1L))
        }
        return LookupResult(found.values.toList(), ttl.coerceIn(30L, 600L))
    }

    private fun parseIpv4(value: String): InetAddress? {
        val parts = value.split(".")
        if (parts.size != 4) return null
        val bytes = ByteArray(4)
        for (i in parts.indices) {
            val n = parts[i].toIntOrNull() ?: return null
            if (n !in 0..255) return null
            bytes[i] = n.toByte()
        }
        return InetAddress.getByAddress(bytes)
    }

    private fun parseIpv6(value: String): InetAddress? {
        if (!value.contains(":") || !value.matches(Regex("^[0-9a-fA-F:.]+$"))) return null
        return try { InetAddress.getByName(value) } catch (_: Exception) { null }
    }

    private fun isIpLiteral(value: String): Boolean {
        if (value.contains(":")) return value.matches(Regex("^[0-9a-fA-F:.]+$"))
        val p = value.split(".")
        return p.size == 4 && p.all { it.toIntOrNull() in 0..255 }
    }

    private fun ipv4(a: Int, b: Int, c: Int, d: Int): InetAddress =
        InetAddress.getByAddress(byteArrayOf(a.toByte(), b.toByte(), c.toByte(), d.toByte()))
}
