package com.anigames.aniwolrelay
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action != Intent.ACTION_BOOT_COMPLETED && intent?.action != Intent.ACTION_MY_PACKAGE_REPLACED) return
        if (!RelayStore.enabled(context) || RelayStore.credentials(context) == null) return
        val service = Intent(context, RelayService::class.java).setAction(RelayService.ACTION_START)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) context.startForegroundService(service) else context.startService(service)
    }
}
