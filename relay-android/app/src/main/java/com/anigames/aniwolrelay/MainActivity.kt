package com.anigames.aniwolrelay

import android.Manifest
import android.app.ActivityManager
import android.content.ComponentName
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.text.InputFilter
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.MainScope
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {
    companion object {
        private const val REQUEST_BATTERY_SETUP = 4703
    }

    private val uiScope = MainScope()
    private lateinit var status: TextView
    private lateinit var code: EditText
    private lateinit var pairButton: Button
    private lateinit var startButton: Button
    private lateinit var stopButton: Button
    private lateinit var relayInfo: TextView
    private lateinit var powerStatus: TextView
    private lateinit var standbyButton: Button
    private lateinit var autoStartButton: Button
    private lateinit var batterySaverButton: Button
    private var openAutoStartAfterBatterySetup = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestNotificationPermission()
        buildUi()
        refreshUi()
        if (RelayStore.credentials(this) != null && RelayStore.enabled(this)) {
            startRelayService()
            refreshUi()
        }
    }

    private fun buildUi() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 24, 24, 24)
            setBackgroundColor(0xFFF5F7F6.toInt())
        }
        setContentView(ScrollView(this).apply { addView(root) })

        root.addView(TextView(this).apply {
            text = "ANI GAMES READY"
            textSize = 13f
            setTextColor(0xFF176B55.toInt())
        })
        root.addView(TextView(this).apply {
            text = "WoL Relay Gateway"
            textSize = 27f
            setTextColor(0xFF17231F.toInt())
            setPadding(0, 4, 0, 8)
        })
        root.addView(TextView(this).apply {
            text = "HP menerima perintah dari Admin dan mengirim Magic Packet ke PC melalui Wi-Fi lokal. Aplikasi boleh ditinggalkan di Home dan layar boleh dikunci."
            textSize = 14f
            setTextColor(0xFF52615B.toInt())
            setPadding(0, 0, 0, 18)
        })

        status = TextView(this).apply {
            textSize = 16f
            setTextColor(0xFF176B55.toInt())
            setPadding(14, 14, 14, 14)
            setBackgroundColor(0xFFE3F1EC.toInt())
        }
        root.addView(status, matchWidth())

        relayInfo = TextView(this).apply {
            textSize = 14f
            setTextColor(0xFF293630.toInt())
            setPadding(0, 16, 0, 12)
        }
        root.addView(relayInfo)

        root.addView(TextView(this).apply {
            text = "MODE SIAGA 24 JAM"
            textSize = 14f
            setTextColor(0xFF176B55.toInt())
            setPadding(0, 8, 0, 6)
        })
        powerStatus = TextView(this).apply {
            textSize = 13f
            setTextColor(0xFF293630.toInt())
            setPadding(12, 12, 12, 12)
            setBackgroundColor(0xFFEAF0ED.toInt())
        }
        root.addView(powerStatus, matchWidth())

        standbyButton = Button(this).apply {
            text = "Aktifkan Mode Siaga 24 Jam"
            setOnClickListener { setupStandbyMode() }
        }
        root.addView(standbyButton, matchWidth())

        autoStartButton = Button(this).apply {
            text = "Buka Pengaturan Autostart Xiaomi"
            setOnClickListener { openXiaomiAutoStartSettings() }
        }
        root.addView(autoStartButton, matchWidth())

        batterySaverButton = Button(this).apply {
            text = "Buka Pengaturan Hemat Baterai Xiaomi"
            setOnClickListener { openXiaomiBatterySaverSettings() }
        }
        root.addView(batterySaverButton, matchWidth())

        root.addView(TextView(this).apply {
            text = "Petunjuk: pada halaman Xiaomi, aktifkan Autostart untuk Ani WoL Relay dan pilih Tanpa Batasan / No restrictions pada penghemat baterai. Android mengharuskan pengguna menekan tombol izin sendiri; aplikasi tidak boleh mengubah sakelar keamanan sistem secara diam-diam."
            textSize = 12f
            setTextColor(0xFF52615B.toInt())
            setPadding(0, 4, 0, 18)
        })

        root.addView(TextView(this).apply {
            text = "PAIRING DARI ADMIN APK"
            textSize = 13f
            setTextColor(0xFF176B55.toInt())
        })
        code = EditText(this).apply {
            hint = "Masukkan kode pairing 12 karakter"
            setSingleLine(true)
            textSize = 17f
            filters = arrayOf(InputFilter.AllCaps(), InputFilter.LengthFilter(12))
        }
        root.addView(code, matchWidth())

        pairButton = Button(this).apply {
            text = "Hubungkan ke Ani Games Ready"
            setOnClickListener { pairRelay() }
        }
        root.addView(pairButton, matchWidth())

        startButton = Button(this).apply {
            text = "Jalankan / Pulihkan Relay"
            setOnClickListener {
                RelayStore.setEnabled(this@MainActivity, true)
                startRelayService()
                refreshUi()
            }
        }
        root.addView(startButton, matchWidth())

        stopButton = Button(this).apply {
            text = "Hentikan Relay"
            setOnClickListener {
                RelayStore.setEnabled(this@MainActivity, false)
                stopService(Intent(this@MainActivity, RelayService::class.java).setAction(RelayService.ACTION_STOP))
                refreshUi()
            }
        }
        root.addView(stopButton, matchWidth())

        root.addView(Button(this).apply {
            text = "Buka Info Aplikasi"
            setOnClickListener { openApplicationSettings() }
        }, matchWidth())

        root.addView(TextView(this).apply {
            text = "DAYA & KESELAMATAN\n• Relay memakai notifikasi permanen dan CPU Wake Lock agar polling tetap berjalan saat layar mati.\n• Penggunaan daya dapat meningkat; gunakan charger berkualitas dan letakkan HP di tempat berventilasi.\n• Monitoring baterai dan suhu hanya-baca. Aplikasi tidak mengatur arus charger atau batas pengisian."
            textSize = 12f
            setTextColor(0xFF52615B.toInt())
            setPadding(0, 18, 0, 0)
        })
    }

    private fun pairRelay() {
        val pairingCode = code.text.toString().trim().uppercase()
        if (!pairingCode.matches(Regex("^[0-9A-F]{12}$"))) {
            status.text = "Kode pairing harus 12 karakter heksadesimal."
            return
        }
        pairButton.isEnabled = false
        status.text = "Menghubungkan relay..."
        uiScope.launch {
            try {
                val credentials = RelayApi.register(pairingCode, RelayStore.installationId(this@MainActivity))
                RelayStore.save(this@MainActivity, credentials)
                startRelayService()
                status.text = "Relay berhasil dipasangkan."
                refreshUi()
            } catch (error: Exception) {
                status.text = "Gagal pairing: ${error.message ?: "periksa koneksi"}"
            } finally {
                pairButton.isEnabled = true
            }
        }
    }

    private fun startRelayService() {
        val intent = Intent(this, RelayService::class.java).setAction(RelayService.ACTION_START)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                ContextCompat.startForegroundService(this, intent)
            } else {
                startService(intent)
            }
        } catch (error: Exception) {
            status.text = "Relay belum dapat dijalankan: ${error.message ?: error.javaClass.simpleName}"
        }
    }

    private fun setupStandbyMode() {
        if (RelayStore.credentials(this) == null) {
            status.text = "Pasangkan HP dari Admin terlebih dahulu."
            return
        }

        RelayStore.setEnabled(this, true)
        startRelayService()
        refreshUi()

        val power = getSystemService(POWER_SERVICE) as PowerManager
        if (!power.isIgnoringBatteryOptimizations(packageName)) {
            openAutoStartAfterBatterySetup = true
            requestBatteryOptimizationExemption()
        } else {
            openXiaomiAutoStartSettings()
        }
    }

    private fun requestBatteryOptimizationExemption() {
        val request = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
            .setData(Uri.parse("package:$packageName"))
        try {
            startActivityForResult(request, REQUEST_BATTERY_SETUP)
        } catch (_: Exception) {
            try {
                startActivityForResult(
                    Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS),
                    REQUEST_BATTERY_SETUP
                )
            } catch (_: Exception) {
                openApplicationSettings()
            }
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_BATTERY_SETUP && openAutoStartAfterBatterySetup) {
            openAutoStartAfterBatterySetup = false
            openXiaomiAutoStartSettings()
        }
        refreshUi()
    }

    private fun openXiaomiAutoStartSettings() {
        val manufacturer = Build.MANUFACTURER.lowercase()
        val brand = Build.BRAND.lowercase()
        if (manufacturer.contains("xiaomi") || brand.contains("xiaomi") ||
            brand.contains("redmi") || brand.contains("poco")) {
            val candidates = listOf(
                Intent().setComponent(
                    ComponentName(
                        "com.miui.securitycenter",
                        "com.miui.permcenter.autostart.AutoStartManagementActivity"
                    )
                ),
                Intent("miui.intent.action.POWER_HIDE_MODE_APP_LIST")
            )
            for (candidate in candidates) {
                try {
                    startActivity(candidate)
                    return
                } catch (_: Exception) {
                    // Try the next MIUI settings entry point.
                }
            }
        }
        openApplicationSettings()
    }

    private fun openXiaomiBatterySaverSettings() {
        val intent = Intent("miui.intent.action.HIDDEN_APPS_CONFIG_ACTIVITY")
            .putExtra("package_name", packageName)
            .putExtra("package_label", "Ani WoL Relay")
        try {
            startActivity(intent)
        } catch (_: Exception) {
            openApplicationSettings()
        }
    }

    private fun openApplicationSettings() {
        try {
            startActivity(
                Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
                    .setData(Uri.parse("package:$packageName"))
            )
        } catch (_: Exception) {
            startActivity(Intent(Settings.ACTION_SETTINGS))
        }
    }

    private fun refreshUi() {
        val credentials = RelayStore.credentials(this)
        val enabled = RelayStore.enabled(this)
        val running = isRelayServiceRunning()
        val power = getSystemService(POWER_SERVICE) as PowerManager
        val batteryExempt = power.isIgnoringBatteryOptimizations(packageName)

        status.text = when {
            credentials == null -> "Belum dipasangkan • Buat kode dari Admin APK"
            running -> "Relay aktif • boleh kembali ke Home dan kunci layar"
            enabled -> "Relay disiapkan • service sedang dipulihkan"
            else -> "Sudah terdaftar • relay belum dijalankan"
        }

        relayInfo.text = if (credentials == null) {
            "Perangkat: ${Build.MANUFACTURER} ${Build.MODEL}\nVersi aplikasi: ${RelayApi.APP_VERSION}"
        } else {
            "Relay ID: ${credentials.relayId}\nPerangkat: ${Build.MANUFACTURER} ${Build.MODEL}\nVersi aplikasi: ${RelayApi.APP_VERSION}\n${RelayStore.runtimeDiagnostics(this)}"
        }

        powerStatus.text = buildString {
            append("Foreground Service: ")
            append(if (running) "AKTIF" else "BELUM TERDETEKSI")
            append("\nOptimasi baterai Android: ")
            append(if (batteryExempt) "TANPA PEMBATASAN" else "MASIH DIBATASI")
            append("\nAutostart Xiaomi: perlu diaktifkan sekali melalui tombol di bawah.")
        }

        pairButton.visibility = if (credentials == null) View.VISIBLE else View.GONE
        code.visibility = if (credentials == null) View.VISIBLE else View.GONE
        startButton.visibility = if (credentials != null && (!enabled || !running)) View.VISIBLE else View.GONE
        stopButton.visibility = if (credentials != null && enabled) View.VISIBLE else View.GONE
        standbyButton.visibility = if (credentials != null) View.VISIBLE else View.GONE
        autoStartButton.visibility = if (credentials != null) View.VISIBLE else View.GONE
        batterySaverButton.visibility = if (credentials != null) View.VISIBLE else View.GONE
    }

    private fun isRelayServiceRunning(): Boolean {
        return try {
            val manager = getSystemService(ACTIVITY_SERVICE) as ActivityManager
            manager.getRunningServices(Int.MAX_VALUE).any {
                it.service.className == RelayService::class.java.name
            }
        } catch (_: Exception) {
            false
        }
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), 4702)
        }
    }

    private fun matchWidth() = LinearLayout.LayoutParams(
        ViewGroup.LayoutParams.MATCH_PARENT,
        ViewGroup.LayoutParams.WRAP_CONTENT
    ).apply { bottomMargin = 10 }

    override fun onResume() {
        super.onResume()
        if (RelayStore.credentials(this) != null && RelayStore.enabled(this) && !isRelayServiceRunning()) {
            startRelayService()
        }
        refreshUi()
    }

    override fun onDestroy() {
        uiScope.cancel()
        super.onDestroy()
    }
}
