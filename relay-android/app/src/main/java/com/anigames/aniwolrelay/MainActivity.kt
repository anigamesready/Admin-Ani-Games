package com.anigames.aniwolrelay
import android.Manifest
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
    private val uiScope = MainScope()
    private lateinit var status: TextView
    private lateinit var code: EditText
    private lateinit var pairButton: Button
    private lateinit var startButton: Button
    private lateinit var stopButton: Button
    private lateinit var relayInfo: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestNotificationPermission()
        buildUi()
        refreshUi()
        if (RelayStore.credentials(this) != null && RelayStore.enabled(this)) startRelayService()
    }

    private fun buildUi() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 24, 24, 24)
            setBackgroundColor(0xFFF5F7F6.toInt())
        }
        setContentView(ScrollView(this).apply { addView(root) })
        root.addView(TextView(this).apply { text = "ANI GAMES READY"; textSize = 13f; setTextColor(0xFF176B55.toInt()) })
        root.addView(TextView(this).apply {
            text = "WoL Relay Gateway"; textSize = 27f; setTextColor(0xFF17231F.toInt()); setPadding(0, 4, 0, 8)
        })
        root.addView(TextView(this).apply {
            text = "HP menerima perintah aman dari Admin, lalu mengirim Magic Packet ke PC melalui Wi-Fi lokal. Layar boleh dimatikan."
            textSize = 14f; setTextColor(0xFF52615B.toInt()); setPadding(0, 0, 0, 18)
        })
        status = TextView(this).apply {
            textSize = 16f; setTextColor(0xFF176B55.toInt()); setPadding(14, 14, 14, 14); setBackgroundColor(0xFFE3F1EC.toInt())
        }
        root.addView(status, matchWidth())
        relayInfo = TextView(this).apply { textSize = 14f; setTextColor(0xFF293630.toInt()); setPadding(0, 16, 0, 16) }
        root.addView(relayInfo)
        root.addView(TextView(this).apply { text = "PAIRING DARI ADMIN APK"; textSize = 13f; setTextColor(0xFF176B55.toInt()) })
        code = EditText(this).apply {
            hint = "Masukkan kode pairing 12 karakter"; setSingleLine(true); textSize = 17f
            filters = arrayOf(InputFilter.AllCaps(), InputFilter.LengthFilter(12))
        }
        root.addView(code, matchWidth())
        pairButton = Button(this).apply { text = "Hubungkan ke Ani Games Ready"; setOnClickListener { pairRelay() } }
        root.addView(pairButton, matchWidth())
        startButton = Button(this).apply {
            text = "Jalankan Relay"
            setOnClickListener { RelayStore.setEnabled(this@MainActivity, true); startRelayService(); refreshUi() }
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
            text = "Izinkan berjalan tanpa optimasi baterai"; setOnClickListener { requestBatteryOptimizationExemption() }
        }, matchWidth())
        root.addView(Button(this).apply {
            text = "Buka pengaturan aplikasi / Autostart"
            setOnClickListener { openApplicationSettings() }
        }, matchWidth())
        root.addView(TextView(this).apply {
            text = "DAYA & KESELAMATAN\\n• Monitoring baterai dan suhu hanya-baca.\\n• Charge limit 50–80% tidak dapat dikendalikan aplikasi Android biasa; aplikasi tidak memutus arus charger.\\n• Gunakan baterai sehat, charger berkualitas, dan ventilasi terbuka.\\n• Foreground service menampilkan notifikasi saat relay aktif."
            textSize = 13f; setTextColor(0xFF52615B.toInt()); setPadding(0, 22, 0, 0)
        })
    }

    private fun pairRelay() {
        val pairingCode = code.text.toString().trim().uppercase()
        if (!pairingCode.matches(Regex("^[0-9A-F]{12}$"))) { status.text = "Kode pairing harus 12 karakter heksadesimal."; return }
        pairButton.isEnabled = false
        status.text = "Menghubungkan relay..."
        uiScope.launch {
            try {
                val credentials = RelayApi.register(pairingCode, RelayStore.installationId(this@MainActivity))
                RelayStore.save(this@MainActivity, credentials)
                startRelayService()
                status.text = "Relay berhasil dipasangkan."
                code.visibility = View.GONE
                pairButton.visibility = View.GONE
                refreshUi()
            } catch (error: Exception) {
                status.text = "Gagal pairing: ${error.message ?: "periksa koneksi"}"
            } finally { pairButton.isEnabled = true }
        }
    }
    private fun startRelayService() {
        val intent = Intent(this, RelayService::class.java).setAction(RelayService.ACTION_START)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) ContextCompat.startForegroundService(this, intent) else startService(intent)
    }
    private fun refreshUi() {
        val credentials = RelayStore.credentials(this)
        val enabled = RelayStore.enabled(this)
        status.text = when {
            credentials == null -> "Belum dipasangkan • Buat kode dari Admin APK"
            enabled -> "Relay aktif • layar boleh mati"
            else -> "Sudah terdaftar • relay belum dijalankan"
        }
        relayInfo.text = if (credentials == null) {
            "Perangkat: ${Build.MANUFACTURER} ${Build.MODEL}\\nVersi aplikasi: ${RelayApi.APP_VERSION}"
        } else {
            "Relay ID: ${credentials.relayId}\\nPerangkat: ${Build.MANUFACTURER} ${Build.MODEL}\\nVersi aplikasi: ${RelayApi.APP_VERSION}\\nStatus server terlihat di Admin APK."
        }
        pairButton.visibility = if (credentials == null) View.VISIBLE else View.GONE
        code.visibility = if (credentials == null) View.VISIBLE else View.GONE
        startButton.visibility = if (credentials != null && !enabled) View.VISIBLE else View.GONE
        stopButton.visibility = if (credentials != null && enabled) View.VISIBLE else View.GONE
    }
    private fun openApplicationSettings() {
        try {
            startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).setData(Uri.parse("package:$packageName")))
        } catch (_: Exception) {
            startActivity(Intent(Settings.ACTION_SETTINGS))
        }
    }

    private fun requestBatteryOptimizationExemption() {
        try {
            val pm = getSystemService(POWER_SERVICE) as PowerManager
            if (!pm.isIgnoringBatteryOptimizations(packageName)) {
                startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).setData(Uri.parse("package:$packageName")))
            } else status.text = "Optimasi baterai sudah dikecualikan."
        } catch (_: Exception) { startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) }
    }
    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), 4702)
        }
    }
    private fun matchWidth() = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { bottomMargin = 10 }
    override fun onResume() {
        super.onResume()
        refreshUi()
        if (RelayStore.credentials(this) != null && RelayStore.enabled(this)) startRelayService()
    }
    override fun onDestroy() { uiScope.cancel(); super.onDestroy() }
}
