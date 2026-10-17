from pathlib import Path
import re

ROOT = Path(".")
html_path = ROOT / "android/app/src/main/assets/web/admin.html"
activity_path = ROOT / "android/app/src/main/java/com/anigames/billingadmin/MainActivity.java"
gradle_path = ROOT / "android/app/build.gradle"

html = html_path.read_text(encoding="utf-8")
activity = activity_path.read_text(encoding="utf-8")
gradle = gradle_path.read_text(encoding="utf-8")

# Android 13+ permissions were only requested after the user pressed a sound button.
# Trigger the permission check after a successful owner login, without sending a test
# notification every time the dashboard opens.
helper_anchor = "function showNativeAdminNotification(message,urgent){"
helper = """let nativeNotificationPermissionRequested=false;
function ensureNativeNotificationPermission(){
 if(nativeNotificationPermissionRequested)return;
 nativeNotificationPermissionRequested=true;
 const bridge=window.AniAdminNative;
 if(!bridge)return;
 try{
  if(typeof bridge.hasNotificationPermission==='function'&&bridge.hasNotificationPermission()){
   if(typeof window.onNativeNotificationPermission==='function')window.onNativeNotificationPermission(true);
   return;
  }
  if(typeof bridge.requestNotificationPermission==='function'){
   bridge.requestNotificationPermission();
  }else{
   const feed=$('adminAlertFeed');
   if(feed){feed.classList.remove('hidden');feed.textContent='Bridge notifikasi Android tidak tersedia. Perbarui APK Admin.';}
  }
 }catch(e){console.warn('Notification permission check failed',e)}
}
"""
if "function ensureNativeNotificationPermission()" not in html:
    if html.count(helper_anchor) != 1:
        raise SystemExit("Native notification helper anchor mismatch; refusing to patch")
    html = html.replace(helper_anchor, helper + helper_anchor, 1)

permission_callback = re.compile(r"window\.onNativeNotificationPermission=function\(granted\)\{[\s\S]*?\n\};")
permission_replacement = """window.onNativeNotificationPermission=function(granted){
 const state=$('adminSoundState');
 if(state)state.textContent=granted?'Notifikasi Android aktif':'Notifikasi Android belum aktif';
 const feed=$('adminAlertFeed');
 if(feed&&!granted){
  feed.classList.remove('hidden');
  feed.style.borderLeftColor='#ff4d6d';
  feed.textContent='Notifikasi rental tidak bisa ditampilkan karena izin atau kanal Android belum aktif. Tekan Pengaturan Notifikasi Android pada panel ini, aktifkan notifikasi AniGames Admin, lalu kembali ke aplikasi.';
 }
};"""
if "Notifikasi Android belum aktif" not in html:
    html, n = permission_callback.subn(permission_replacement, html, count=1)
    if n != 1:
        raise SystemExit("Native notification permission callback mismatch; refusing to patch")

owner_anchor = "if(ctx.role==='owner')refreshIoTStatus();"
owner_replacement = "if(ctx.role==='owner'){refreshIoTStatus();ensureNativeNotificationPermission();}"
if owner_replacement not in html:
    if html.count(owner_anchor) != 1:
        raise SystemExit("Owner boot permission anchor mismatch; refusing to patch")
    html = html.replace(owner_anchor, owner_replacement, 1)

# Keep polling while the WebView is backgrounded; otherwise notifications stop exactly
# when the admin switches away from the app. Android may still throttle a background WebView.
hidden_guard = "if(adminAlertsPolling||!session||!currentOrg||document.visibilityState==='hidden')return;"
if hidden_guard in html:
    html = html.replace(hidden_guard, "if(adminAlertsPolling||!session||!currentOrg)return;", 1)
elif "async function pollPcAdminAlerts()" not in html:
    raise SystemExit("PC alert poller missing; refusing to patch")

# Do not hide all failures. Surface one actionable warning per minute, without creating
# a native notification or database/log record for every poll attempt.
silent_catch = """ }catch(e){
  // Keep polling errors silent; missing migration must not create one alert/log per poll.
 }finally{adminAlertsPolling=false}
}"""
visible_catch = """ }catch(e){
  const now=Date.now();
  if(!window.__aniAdminAlertPollErrorAt||now-window.__aniAdminAlertPollErrorAt>60000){
   window.__aniAdminAlertPollErrorAt=now;
   console.warn('Gagal sinkron notifikasi rental:',e);
   const feed=$('adminAlertFeed');
   if(feed){feed.classList.remove('hidden');feed.style.borderLeftColor='#ff4d6d';feed.textContent='Notifikasi rental belum tersambung ke database. Periksa koneksi/login Admin dan status DB.';}
   const state=$('adminSoundState');if(state)state.textContent='Sinkronisasi alert rental bermasalah';
  }
 }finally{adminAlertsPolling=false}
}"""
if visible_catch not in html:
    if silent_catch in html:
        html = html.replace(silent_catch, visible_catch, 1)
    elif "window.__aniAdminAlertPollErrorAt" not in html:
        raise SystemExit("Alert poll error handler mismatch; refusing to patch")

# Distinguish the Android runtime permission from app/channel notification toggles.
old_permission = """    private boolean hasAdminNotificationPermission() {
        return Build.VERSION.SDK_INT < 33 ||
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED;
    }
"""
new_permission = """    private boolean hasPostNotificationPermission() {
        return Build.VERSION.SDK_INT < 33 ||
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED;
    }

    private boolean areAdminNotificationsEnabled() {
        if (!hasPostNotificationPermission()) return false;
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (manager == null || !manager.areNotificationsEnabled()) return false;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = manager.getNotificationChannel(NOTIFICATION_CHANNEL_ID);
            if (channel != null && channel.getImportance() == NotificationManager.IMPORTANCE_NONE) return false;
        }
        return true;
    }

    private boolean hasAdminNotificationPermission() {
        return areAdminNotificationsEnabled();
    }
"""
if "private boolean areAdminNotificationsEnabled()" not in activity:
    if activity.count(old_permission) != 1:
        raise SystemExit("MainActivity notification permission method mismatch; refusing to patch")
    activity = activity.replace(old_permission, new_permission, 1)

activity = activity.replace("if (!hasAdminNotificationPermission()) return;", "if (!areAdminNotificationsEnabled()) return;", 1)
activity = activity.replace("@JavascriptInterface public boolean hasNotificationPermission() {\n            return hasAdminNotificationPermission();\n        }",
                            "@JavascriptInterface public boolean hasNotificationPermission() {\n            return areAdminNotificationsEnabled();\n        }", 1)

old_request = """                if (Build.VERSION.SDK_INT >= 33 && !hasAdminNotificationPermission()) {
                    requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_POST_NOTIFICATIONS);
                } else {
                    notifyWebNotificationPermission(true);
                    showAdminSystemNotification("AniGames Admin", "Notifikasi Android aktif. Suara dapat diatur dari setelan kanal aplikasi.", false);
                }"""
new_request = """                if (Build.VERSION.SDK_INT >= 33 && !hasPostNotificationPermission()) {
                    requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_POST_NOTIFICATIONS);
                } else if (!areAdminNotificationsEnabled()) {
                    notifyWebNotificationPermission(false);
                } else {
                    notifyWebNotificationPermission(true);
                    showAdminSystemNotification("AniGames Admin", "Notifikasi Android aktif. Suara dapat diatur dari setelan kanal aplikasi.", false);
                }"""
if new_request not in activity:
    if activity.count(old_request) != 1:
        raise SystemExit("MainActivity permission request flow mismatch; refusing to patch")
    activity = activity.replace(old_request, new_request, 1)

old_result = """        boolean granted = grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED;
        notifyWebNotificationPermission(granted);
        if (granted) {
            showAdminSystemNotification("AniGames Admin", "Notifikasi Android berhasil diaktifkan. Suara kanal siap diatur.", false);
        }"""
new_result = """        boolean granted = grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED;
        boolean enabled = granted && areAdminNotificationsEnabled();
        notifyWebNotificationPermission(enabled);
        if (enabled) {
            showAdminSystemNotification("AniGames Admin", "Notifikasi Android berhasil diaktifkan. Suara kanal siap diatur.", false);
        }"""
if new_result not in activity:
    if activity.count(old_result) != 1:
        raise SystemExit("MainActivity permission-result flow mismatch; refusing to patch")
    activity = activity.replace(old_result, new_result, 1)

# Final APK patch version after the existing v12.1.9 hardening passes.
if "versionCode 37" in gradle and "versionName '12.1.9'" in gradle:
    gradle = gradle.replace("versionCode 37", "versionCode 38", 1).replace("versionName '12.1.9'", "versionName '12.1.10'", 1)
elif "versionCode 38" not in gradle or "versionName '12.1.10'" not in gradle:
    raise SystemExit("Unexpected Android baseline version; refusing to bump blindly")

html_path.write_text(html, encoding="utf-8")
activity_path.write_text(activity, encoding="utf-8")
gradle_path.write_text(gradle, encoding="utf-8")
(ROOT / "VERSION.txt").write_text("v12.1.10-notification-permission-and-poll-reliability\n", encoding="utf-8")

for token in ("ensureNativeNotificationPermission()", "admin_recent_alerts", "pollPcAdminAlerts"):
    if token not in html:
        raise SystemExit("Final notification regression check missing: " + token)
for token in ("areAdminNotificationsEnabled", "hasPostNotificationPermission", "POST_NOTIFICATIONS"):
    if token not in activity:
        raise SystemExit("Final native notification regression check missing: " + token)
print("Patched Android permission/status detection, owner-login permission flow, background poll guard and visible poll diagnostics. Version 12.1.10 / versionCode 38.")
