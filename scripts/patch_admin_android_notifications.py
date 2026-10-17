from pathlib import Path
import re

ROOT = Path(".")
html_path = ROOT / "android/app/src/main/assets/web/admin.html"
activity_path = ROOT / "android/app/src/main/java/com/anigames/billingadmin/MainActivity.java"
manifest_path = ROOT / "android/app/src/main/AndroidManifest.xml"
gradle_path = ROOT / "android/app/build.gradle"

html = html_path.read_text(encoding="utf-8")
activity = activity_path.read_text(encoding="utf-8")
manifest = manifest_path.read_text(encoding="utf-8")
gradle = gradle_path.read_text(encoding="utf-8")

# Web Audio alone is not an Android system notification. Add an explicit bridge.
if "function showNativeAdminNotification(" not in html:
    anchor = "function playAdminAlertSound(){"
    if html.count(anchor) != 1:
        raise SystemExit("playAdminAlertSound anchor mismatch; refusing to patch")
    helper = """function showNativeAdminNotification(message,urgent){
 try{
  const bridge=window.AniAdminNative;
  if(bridge&&typeof bridge.showNotification==='function'){
   bridge.showNotification(urgent?'Peringatan AniGames Admin':'AniGames Admin',String(message||'').slice(0,500),!!urgent);
  }
 }catch(e){console.warn('Native admin notification unavailable',e)}
}
function openAndroidNotificationSettings(){
 try{if(window.AniAdminNative&&typeof window.AniAdminNative.openNotificationSettings==='function'){window.AniAdminNative.openNotificationSettings();return;}}
 catch(e){}
 alert('Pengaturan notifikasi Android belum dapat dibuka dari aplikasi ini.');
}
window.onNativeNotificationPermission=function(granted){
 const state=$('adminSoundState');
 if(state)state.textContent=granted?'Notifikasi Android aktif':'Izin notifikasi belum diberikan';
 const feed=$('adminAlertFeed');
 if(feed&&!granted)feed.textContent='Izin notifikasi ditolak. Aktifkan notifikasi AniGames Admin di Pengaturan Android agar alert PC muncul di panel notifikasi.';
};
"""
    html = html.replace(anchor, helper + anchor, 1)

if "showNativeAdminNotification(safe,true)" not in html:
    old = "if(urgent)playAdminAlertSound();"
    if html.count(old) != 1:
        raise SystemExit("adminNotify sound anchor mismatch; refusing to patch")
    html = html.replace(old, "if(urgent){playAdminAlertSound();showNativeAdminNotification(safe,true);}", 1)

html = html.replace("🔊 Aktifkan & Tes Suara", "🔔 Aktifkan Notifikasi & Tes Suara", 1)
if "openAndroidNotificationSettings()" not in html.split("function openAndroidNotificationSettings()", 1)[0]:
    pass
button_anchor = '<button type="button" onclick="dismissAdminAlert()">Tutup Pesan</button>'
if "Pengaturan Notifikasi Android" not in html:
    if html.count(button_anchor) != 1:
        raise SystemExit("Admin alert settings button anchor mismatch; refusing to patch")
    html = html.replace(button_anchor, '<button type="button" onclick="openAndroidNotificationSettings()">⚙ Pengaturan Notifikasi Android</button>' + button_anchor, 1)

enable_pattern = re.compile(r"function enableAdminAlertSound\(\)\{[\s\S]*?\}\nfunction dismissAdminAlert")
enable_replacement = """function enableAdminAlertSound(){
 try{
  const AC=window.AudioContext||window.webkitAudioContext;
  if(AC){
   const ctx=window.__aniAdminAlertAudio||(window.__aniAdminAlertAudio=new AC());
   ctx.resume().then(function(){
    window.__aniAdminAlertSoundReady=true;
    const state=$('adminSoundState');if(state)state.textContent='Suara halaman aktif • meminta izin Android…';
    playAdminAlertSound();
   });
  }
 }catch(e){console.warn('Web Audio unavailable',e)}
 try{
  if(window.AniAdminNative&&typeof window.AniAdminNative.requestNotificationPermission==='function'){
   window.AniAdminNative.requestNotificationPermission();
  }else{
   const state=$('adminSoundState');if(state)state.textContent='Bridge notifikasi Android tidak tersedia';
   msg('APK ini belum memiliki bridge notifikasi Android. Build ulang APK dari source terbaru.',true);
  }
 }catch(e){msg('Gagal meminta izin notifikasi Android.',true)}
}
function dismissAdminAlert"""
html, enable_count = enable_pattern.subn(enable_replacement, html, count=1)
if enable_count != 1:
    raise SystemExit("enableAdminAlertSound function mismatch; refusing to patch")

# Poll only actual PC end/stop events. Read-only polling creates no database logs.
poll_anchor = "installAdminNotificationBridge();\nfunction renderRecoveryDeviceOptions()"
poll_code = """installAdminNotificationBridge();
let adminAlertsPolling=false;
async function pollPcAdminAlerts(){
 if(adminAlertsPolling||!session||!currentOrg||document.visibilityState==='hidden')return;
 adminAlertsPolling=true;
 const dbLabel=String(DB_TARGET||'primary');
 const seenKey='ani_admin_alert_seen_v1_'+dbLabel+'_'+String(currentOrg.id);
 const cursorKey=seenKey+'_cursor';
 try{
  let seen=[];try{seen=JSON.parse(localStorage.getItem(seenKey)||'[]')}catch(e){}
  const saved=localStorage.getItem(cursorKey);
  let since=new Date(Date.now()-120000).toISOString();
  if(saved){const n=Date.parse(saved);if(Number.isFinite(n))since=new Date(Math.max(n-60000,Date.now()-86400000)).toISOString();}
  const rows=await rpc('admin_recent_alerts',{p_org_id:currentOrg.id,p_since:since});
  if(!Array.isArray(rows))return;
  rows.sort((a,b)=>Date.parse(a.created_at||a.occurred_at||0)-Date.parse(b.created_at||b.occurred_at||0));
  let newest=Date.parse(saved||0)||0;
  for(const row of rows){
   const id=String(row.id||row.source_event_id||'');if(!id||seen.includes(id))continue;
   seen.push(id);
   const message=String(row.message||'Status rental dari PC berubah.').slice(0,500);
   adminNotify(message,'error');
   const stamp=Date.parse(row.created_at||row.occurred_at||'')||0;if(stamp>newest)newest=stamp;
  }
  localStorage.setItem(seenKey,JSON.stringify(seen.slice(-250)));
  if(newest>0)localStorage.setItem(cursorKey,new Date(newest).toISOString());
 }catch(e){
  // Keep polling errors silent; missing migration must not create one alert/log per poll.
 }finally{adminAlertsPolling=false}
}
function renderRecoveryDeviceOptions()"""
if "async function pollPcAdminAlerts()" not in html:
    if html.count(poll_anchor) != 1:
        raise SystemExit("Admin alert polling anchor mismatch; refusing to patch")
    html = html.replace(poll_anchor, poll_code, 1)

timer_anchor = "boot();setInterval(()=>{if(session&&currentOrg)loadDevices()},20000);"
timer_replacement = "boot();setInterval(()=>{if(session&&currentOrg)loadDevices()},20000);setInterval(()=>{if(session&&currentOrg)pollPcAdminAlerts()},15000);"
if "pollPcAdminAlerts()},15000" not in html:
    if html.count(timer_anchor) != 1:
        raise SystemExit("Admin polling timer anchor mismatch; refusing to patch")
    html = html.replace(timer_anchor, timer_replacement, 1)

# Native notification channel + JS bridge. The channel is intentionally new so Android
# creates a user-visible sound setting even if an older install had no channel.
required_import_anchor = "import org.json.JSONObject;"
extra_imports = """import org.json.JSONObject;
import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.pm.PackageManager;
import android.media.AudioAttributes;
import android.media.RingtoneManager;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.webkit.JavascriptInterface;"""
if "import android.app.NotificationChannel;" not in activity:
    if activity.count(required_import_anchor) != 1:
        raise SystemExit("MainActivity imports anchor mismatch; refusing to patch")
    activity = activity.replace(required_import_anchor, extra_imports, 1)

class_anchor = "public class MainActivity extends Activity {"
constants = """public class MainActivity extends Activity {
    private static final int REQ_POST_NOTIFICATIONS = 7401;
    private static final String NOTIFICATION_CHANNEL_ID = "ani_admin_alerts_sound_v1";
"""
if "NOTIFICATION_CHANNEL_ID" not in activity:
    if activity.count(class_anchor) != 1:
        raise SystemExit("MainActivity class anchor mismatch; refusing to patch")
    activity = activity.replace(class_anchor, constants, 1)

on_create_anchor = "        super.onCreate(savedInstanceState);"
if "ensureAdminNotificationChannel();" not in activity:
    if activity.count(on_create_anchor) != 1:
        raise SystemExit("MainActivity onCreate anchor mismatch; refusing to patch")
    activity = activity.replace(on_create_anchor, on_create_anchor + "\n        ensureAdminNotificationChannel();", 1)

web_anchor = "        web = new WebView(this);"
if "new AdminNotificationBridge()" not in activity:
    if activity.count(web_anchor) != 1:
        raise SystemExit("MainActivity WebView anchor mismatch; refusing to patch")
    activity = activity.replace(web_anchor, web_anchor + '\n        web.addJavascriptInterface(new AdminNotificationBridge(), "AniAdminNative");', 1)

methods_anchor = "    @Override public void onBackPressed() {"
native_methods = r'''
    private boolean hasAdminNotificationPermission() {
        return Build.VERSION.SDK_INT < 33 ||
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED;
    }

    private void ensureAdminNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (manager == null || manager.getNotificationChannel(NOTIFICATION_CHANNEL_ID) != null) return;
        NotificationChannel channel = new NotificationChannel(
            NOTIFICATION_CHANNEL_ID, "AniGames Admin — Alert Rental & PC",
            NotificationManager.IMPORTANCE_HIGH
        );
        channel.setDescription("Peringatan rental selesai/dihentikan, pairing, dan status PC.");
        channel.enableVibration(true);
        channel.setVibrationPattern(new long[]{0, 250, 160, 250});
        channel.enableLights(true);
        channel.setLightColor(android.graphics.Color.RED);
        Uri sound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION);
        AudioAttributes audio = new AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_NOTIFICATION)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build();
        channel.setSound(sound, audio);
        manager.createNotificationChannel(channel);
    }

    private void showAdminSystemNotification(String title, String message, boolean urgent) {
        if (!hasAdminNotificationPermission()) return;
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (manager == null) return;
        String safeTitle = title == null || title.trim().isEmpty() ? "AniGames Admin" : title.trim();
        String safeMessage = message == null ? "Ada pembaruan dari PC Billing." : message.trim();
        if (safeMessage.length() > 500) safeMessage = safeMessage.substring(0, 500);
        Intent intent = new Intent(this, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pending = PendingIntent.getActivity(
            this, 7402, intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
            ? new Notification.Builder(this, NOTIFICATION_CHANNEL_ID)
            : new Notification.Builder(this);
        builder.setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle(safeTitle)
            .setContentText(safeMessage)
            .setStyle(new Notification.BigTextStyle().bigText(safeMessage))
            .setContentIntent(pending)
            .setAutoCancel(true)
            .setCategory(urgent ? Notification.CATEGORY_ALARM : Notification.CATEGORY_STATUS)
            .setVisibility(Notification.VISIBILITY_PRIVATE)
            .setPriority(Notification.PRIORITY_HIGH);
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            builder.setSound(RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION));
            builder.setVibrate(new long[]{0, 250, 160, 250});
        }
        manager.notify((int)(System.currentTimeMillis() & 0x7fffffff), builder.build());
    }

    private void notifyWebNotificationPermission(boolean granted) {
        if (web == null) return;
        String js = "if(window.onNativeNotificationPermission){window.onNativeNotificationPermission(" + (granted ? "true" : "false") + ");}";
        web.post(() -> web.evaluateJavascript(js, null));
    }

    private class AdminNotificationBridge {
        @JavascriptInterface public boolean hasNotificationPermission() {
            return hasAdminNotificationPermission();
        }

        @JavascriptInterface public void requestNotificationPermission() {
            runOnUiThread(() -> {
                if (Build.VERSION.SDK_INT >= 33 && !hasAdminNotificationPermission()) {
                    requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_POST_NOTIFICATIONS);
                } else {
                    notifyWebNotificationPermission(true);
                    showAdminSystemNotification("AniGames Admin", "Notifikasi Android aktif. Suara dapat diatur dari setelan kanal aplikasi.", false);
                }
            });
        }

        @JavascriptInterface public void showNotification(String title, String message, boolean urgent) {
            runOnUiThread(() -> showAdminSystemNotification(title, message, urgent));
        }

        @JavascriptInterface public void openNotificationSettings() {
            runOnUiThread(() -> {
                Intent settingsIntent;
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    settingsIntent = new Intent(Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS)
                        .putExtra(Settings.EXTRA_APP_PACKAGE, getPackageName())
                        .putExtra(Settings.EXTRA_CHANNEL_ID, NOTIFICATION_CHANNEL_ID);
                } else {
                    settingsIntent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + getPackageName()));
                }
                startActivity(settingsIntent);
            });
        }
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQ_POST_NOTIFICATIONS) return;
        boolean granted = grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED;
        notifyWebNotificationPermission(granted);
        if (granted) {
            showAdminSystemNotification("AniGames Admin", "Notifikasi Android berhasil diaktifkan. Suara kanal siap diatur.", false);
        }
    }

'''
if "private class AdminNotificationBridge" not in activity:
    if activity.count(methods_anchor) != 1:
        raise SystemExit("MainActivity methods anchor mismatch; refusing to patch")
    activity = activity.replace(methods_anchor, native_methods + methods_anchor, 1)

permission_anchor = '<uses-permission android:name="android.permission.INTERNET" />'
if 'android.permission.POST_NOTIFICATIONS' not in manifest:
    if manifest.count(permission_anchor) != 1:
        raise SystemExit("Manifest INTERNET permission anchor mismatch; refusing to patch")
    manifest = manifest.replace(permission_anchor, permission_anchor + '\n    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />\n    <uses-permission android:name="android.permission.VIBRATE" />', 1)

if "versionCode 34" not in gradle or "versionName '12.1.6'" not in gradle:
    raise SystemExit("Unexpected Android baseline version; refusing to bump blindly")
gradle = gradle.replace("versionCode 34", "versionCode 35", 1).replace("versionName '12.1.6'", "versionName '12.1.7'", 1)

html_path.write_text(html, encoding="utf-8")
activity_path.write_text(activity, encoding="utf-8")
manifest_path.write_text(manifest, encoding="utf-8")
gradle_path.write_text(gradle, encoding="utf-8")
(ROOT / "VERSION.txt").write_text("v12.1.7-android-system-notifications-pc-alerts\n", encoding="utf-8")
print("Patched Android system notification channel/permission/bridge and read-only PC alert polling; version 12.1.7 / versionCode 35")
