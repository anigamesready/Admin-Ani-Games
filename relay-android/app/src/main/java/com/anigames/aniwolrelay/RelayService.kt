package com.anigames.aniwolrelay

import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.wifi.WifiManager
import android.os.BatteryManager
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.time.OffsetDateTime

class RelayService : Service() {
    companion object {
        const val ACTION_START = "com.anigames.aniwolrelay.START"
        const val ACTION_STOP = "com.anigames.aniwolrelay.STOP"
        private const val CHANNEL_ID = "ani_wol_relay"
        private const val NOTIFICATION_ID = 4701
        private const val POLL_INTERVAL_MS = 15_000L
        private const val HEARTBEAT_INTERVAL_MS = 45_000L
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var loopStarted = false
    private var wifiLock: WifiManager.WifiLock? = null
    private var standbyCpuWakeLock: PowerManager.WakeLock? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
        ensureWifiLock()
    }

    private fun ensureWifiLock() {
        try {
            val wifi = getSystemService(Context.WIFI_SERVICE) as WifiManager
            if (wifi.isWifiEnabled && wifiLock?.isHeld != true) {
                if (wifiLock == null) {
                    wifiLock = wifi.createWifiLock(WifiManager.WIFI_MODE_FULL, "AniWoLRelay:WiFi")
                    wifiLock?.setReferenceCounted(false)
                }
                wifiLock?.acquire()
            }
        } catch (error: Exception) {
            RelayStore.recordNetworkError(this, "wifi_wake_lock", error)
        }
    }

    private fun acquireStandbyCpuWakeLock() {
        try {
            if (standbyCpuWakeLock?.isHeld == true) return
            val power = getSystemService(Context.POWER_SERVICE) as PowerManager
            standbyCpuWakeLock = power.newWakeLock(
                PowerManager.PARTIAL_WAKE_LOCK,
                "AniWoLRelay:Standby"
            ).apply {
                setReferenceCounted(false)
                acquire()
            }
        } catch (error: Exception) {
            RelayStore.recordNetworkError(this, "cpu_wake_lock", error)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            RelayStore.setEnabled(this, false)
            stopSelf()
            return START_NOT_STICKY
        }
        if (RelayStore.credentials(this) == null || !RelayStore.enabled(this)) {
            stopSelf()
            return START_NOT_STICKY
        }

        startForeground(NOTIFICATION_ID, notification("Relay aktif • layar boleh mati"))
        acquireStandbyCpuWakeLock()
        ensureWifiLock()

        if (!loopStarted) {
            loopStarted = true
            scope.launch { runRelayLoop() }
        }
        return START_STICKY
    }

    private suspend fun runRelayLoop() {
        var lastWarning = 0L
        var lastHeartbeatAttempt = 0L

        while (scope.isActive) {
            val credentials = RelayStore.credentials(this)
            if (credentials == null || !RelayStore.enabled(this)) break

            try {
                // Keep the user-visible service, Wi-Fi lock, and CPU wake lock alive
                // even after Home / screen lock. The Activity is not part of the poll loop.
                acquireStandbyCpuWakeLock()
                ensureWifiLock()

                val metrics = batteryMetrics()
                val now = System.currentTimeMillis()
                val temperature = metrics.optDouble("batteryTemperatureC", 0.0)
                val thermalProtection = temperature >= 50.0

                // The current server poll RPC leases commands/probes but deliberately does
                // not refresh last_seen_at. A 45-second authenticated heartbeat is required
                // for the Admin's 90-second ONLINE window.
                if (now - lastHeartbeatAttempt >= HEARTBEAT_INTERVAL_MS) {
                    lastHeartbeatAttempt = now
                    try {
                        withNetworkWakeLock { RelayApi.heartbeat(credentials, metrics) }
                        RelayStore.recordNetworkSuccess(this, "heartbeat")
                    } catch (error: Exception) {
                        RelayStore.recordNetworkError(this, "heartbeat", error)
                    }
                }

                try {
                    val response = withNetworkWakeLock { RelayApi.poll(credentials) }
                    RelayStore.recordNetworkSuccess(this, "poll")

                    // Admin direct test creates a 45-second probe. Acknowledge it explicitly;
                    // merely receiving HTTP 200 from poll is not proof the relay is online.
                    response.optJSONObject("probe")?.let { processProbe(credentials, it, metrics) }

                    response.optJSONObject("command")?.let { command ->
                        if (thermalProtection) {
                            rejectCommandForThermalProtection(credentials, command, temperature)
                        } else {
                            processCommand(credentials, command)
                        }
                    }
                } catch (error: Exception) {
                    RelayStore.recordNetworkError(this, "poll", error)
                }

                val hasError = RelayStore.runtimeDiagnostics(this).contains(" • Error ")
                val notificationText = when {
                    thermalProtection -> "Relay tersambung • perlindungan suhu aktif"
                    hasError -> "Relay aktif • mencoba pulihkan koneksi"
                    else -> "Relay ONLINE • menunggu perintah"
                }
                updateNotification(notificationText)

                if (thermalProtection && now - lastWarning > 60_000L) {
                    notifyUser("Suhu baterai tinggi (${temperature}°C). Relay menahan pengiriman Magic Packet sampai suhu turun.")
                    lastWarning = now
                }

                delay(POLL_INTERVAL_MS)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                RelayStore.recordNetworkError(this, "loop", error)
                updateNotification("Relay mencoba pulih • cek detail koneksi")
                delay(20_000L)
            }
        }

        if (RelayStore.credentials(this) == null || !RelayStore.enabled(this)) stopSelf()
    }

    private suspend fun processProbe(
        credentials: RelayCredentials,
        probe: JSONObject,
        metrics: JSONObject
    ) {
        val probeId = probe.optString("id")
        val nonce = probe.optString("nonce")
        if (probeId.isBlank() || nonce.isBlank()) {
            throw IllegalStateException("Probe dari Admin tidak lengkap")
        }

        val expires = try {
            OffsetDateTime.parse(probe.optString("expiresAt")).toInstant().toEpochMilli()
        } catch (error: Exception) {
            throw IllegalStateException("Waktu kedaluwarsa probe tidak valid", error)
        }
        if (expires <= System.currentTimeMillis()) return

        withNetworkWakeLock {
            RelayApi.acknowledgeProbe(credentials, probeId, nonce, metrics)
        }
        RelayStore.recordNetworkSuccess(this, "probe")
        updateNotification("Relay ONLINE • tes Admin berhasil")
    }

    private suspend fun rejectCommandForThermalProtection(
        credentials: RelayCredentials,
        command: JSONObject,
        temperature: Double
    ) {
        val id = command.optString("id")
        if (id.isBlank()) return
        withNetworkWakeLock {
            RelayApi.acknowledge(
                credentials,
                id,
                "failed",
                JSONObject()
                    .put("error", "RELAY_THERMAL_LIMIT")
                    .put("message", "Magic Packet ditahan karena suhu baterai ${temperature}°C")
            )
        }
        notifyUser("Perintah WoL ditahan demi keselamatan baterai (${temperature}°C)")
    }

    private suspend fun processCommand(credentials: RelayCredentials, command: JSONObject) {
        val id = command.optString("id")
        if (id.isBlank()) return
        val mac = command.optString("targetMac")
        val name = command.optString("targetDeviceName", "PC target")
        val expires = try {
            OffsetDateTime.parse(command.optString("expiresAt")).toInstant().toEpochMilli()
        } catch (_: Exception) {
            0L
        }
        if (expires <= System.currentTimeMillis()) {
            withNetworkWakeLock {
                RelayApi.acknowledge(credentials, id, "failed", JSONObject().put("error", "COMMAND_EXPIRED"))
            }
            return
        }
        try {
            val result = MagicPacketSender.send(mac)
            withNetworkWakeLock {
                RelayApi.acknowledge(
                    credentials,
                    id,
                    "packet_sent",
                    JSONObject()
                        .put("message", "Magic Packet dikirim; PC belum dikonfirmasi menyala")
                        .put("targetDeviceName", name)
                        .put("broadcasts", result.destinations)
                        .put("attempts", result.sent)
                )
            }
            RelayStore.recordNetworkSuccess(this, "command")
            notifyUser("Magic Packet dikirim ke $name")
        } catch (error: Exception) {
            RelayStore.recordNetworkError(this, "command", error)
            withNetworkWakeLock {
                RelayApi.acknowledge(
                    credentials,
                    id,
                    "failed",
                    JSONObject()
                        .put("error", "WOL_SEND_FAILED")
                        .put("message", error.message ?: "Gagal mengirim Magic Packet")
                )
            }
            throw error
        }
    }

    private suspend fun <T> withNetworkWakeLock(block: suspend () -> T): T {
        val lock = (getSystemService(Context.POWER_SERVICE) as PowerManager)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "AniWoLRelay:Network")
        lock.acquire(25_000L)
        return try {
            block()
        } finally {
            if (lock.isHeld) lock.release()
        }
    }

    private fun batteryMetrics(): JSONObject {
        val intent = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = intent?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = intent?.getIntExtra(BatteryManager.EXTRA_SCALE, 100) ?: 100
        val percent = if (level >= 0 && scale > 0) level * 100 / scale else -1
        val temp = intent?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1) ?: -1
        val state = intent?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        val health = intent?.getIntExtra(BatteryManager.EXTRA_HEALTH, -1) ?: -1
        val charging = state == BatteryManager.BATTERY_STATUS_CHARGING || state == BatteryManager.BATTERY_STATUS_FULL
        val healthText = when (health) {
            BatteryManager.BATTERY_HEALTH_GOOD -> "good"
            BatteryManager.BATTERY_HEALTH_OVERHEAT -> "overheat"
            BatteryManager.BATTERY_HEALTH_DEAD -> "dead"
            BatteryManager.BATTERY_HEALTH_COLD -> "cold"
            else -> "unknown"
        }
        return JSONObject()
            .put("batteryPercent", percent)
            .put("batteryTemperatureC", if (temp >= 0) temp / 10.0 else JSONObject.NULL)
            .put("charging", charging)
            .put("batteryHealth", healthText)
            .put("model", Build.MODEL)
            .put("appVersion", RelayApi.APP_VERSION)
    }

    private fun scheduleTaskRemovalRecovery() {
        if (!RelayStore.enabled(this) || RelayStore.credentials(this) == null) return
        try {
            val intent = Intent(this, BootReceiver::class.java).setAction(BootReceiver.ACTION_RECOVER)
            val flags = PendingIntent.FLAG_UPDATE_CURRENT or
                if (Build.VERSION.SDK_INT >= 23) PendingIntent.FLAG_IMMUTABLE else 0
            val pending = PendingIntent.getBroadcast(this, 4703, intent, flags)
            val alarm = getSystemService(Context.ALARM_SERVICE) as AlarmManager
            alarm.setAndAllowWhileIdle(
                AlarmManager.ELAPSED_REALTIME_WAKEUP,
                SystemClock.elapsedRealtime() + 20_000L,
                pending
            )
        } catch (error: Exception) {
            RelayStore.recordNetworkError(this, "recovery_alarm", error)
        }
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        scheduleTaskRemovalRecovery()
        super.onTaskRemoved(rootIntent)
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            getSystemService(NotificationManager::class.java).createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "Ani WoL Relay", NotificationManager.IMPORTANCE_LOW)
                    .apply { description = "Status relay Wake-on-LAN" }
            )
        }
    }

    private fun notification(text: String): Notification {
        val flags = PendingIntent.FLAG_UPDATE_CURRENT or
            if (Build.VERSION.SDK_INT >= 23) PendingIntent.FLAG_IMMUTABLE else 0
        val pending = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), flags)
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_upload_done)
            .setContentTitle("Ani Games Ready • WoL Relay")
            .setContentText(text)
            .setContentIntent(pending)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun updateNotification(text: String) {
        getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification(text))
    }

    private fun notifyUser(text: String) {
        getSystemService(NotificationManager::class.java).notify(
            NOTIFICATION_ID + 1,
            NotificationCompat.Builder(this, CHANNEL_ID)
                .setSmallIcon(android.R.drawable.stat_sys_upload_done)
                .setContentTitle("Ani WoL Relay")
                .setContentText(text)
                .setAutoCancel(true)
                .setPriority(NotificationCompat.PRIORITY_DEFAULT)
                .build()
        )
    }

    override fun onDestroy() {
        scope.cancel()
        try {
            if (wifiLock?.isHeld == true) wifiLock?.release()
        } catch (_: Exception) {
        }
        wifiLock = null
        try {
            if (standbyCpuWakeLock?.isHeld == true) standbyCpuWakeLock?.release()
        } catch (_: Exception) {
        }
        standbyCpuWakeLock = null
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
