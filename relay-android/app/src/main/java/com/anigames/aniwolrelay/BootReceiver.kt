package com.anigames.aniwolrelay
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.content.ContextCompat

class BootReceiver : BroadcastReceiver() {
    companion object { const val ACTION_RECOVER = "com.anigames.aniwolrelay.RECOVER" }
    override fun onReceive(context: Context, intent: Intent?) {
        val action = intent?.action
        if (action != Intent.ACTION_BOOT_COMPLETED &&
            action != Intent.ACTION_MY_PACKAGE_REPLACED &&
            action != ACTION_RECOVER) return
        if (!RelayStore.enabled(context) || RelayStore.credentials(context) == null) return
        val service = Intent(context, RelayService::class.java).setAction(RelayService.ACTION_START)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) ContextCompat.startForegroundService(context, service)
        else context.startService(service)
    }
}