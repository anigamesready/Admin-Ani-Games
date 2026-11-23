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
        if (manager == null) return false;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N && !manager.areNotificationsEnabled()) return false;
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


# Make fetch failures identify the operation/project, and use bounded backoff for alert polling.
old_rpc = "async function rpc(name,args={}){const r=await sb.schema('api').rpc(name,args);if(r.error)throw r.error;return r.data}"
new_rpc = """async function rpc(name,args={}){
 try{
  const r=await sb.schema('api').rpc(name,args);
  if(r.error)throw r.error;
  return r.data;
 }catch(e){
  if(e instanceof TypeError && /failed to fetch/i.test(String(e.message||''))){
   const dbLabel=DB_TARGET==='backup'?'DB2':'DB1';
   const diagnostic=new Error('NETWORK_FETCH_FAILED • '+dbLabel+' • RPC '+String(name||'unknown')+' • Permintaan tidak mendapat respons jaringan. Cek internet, URL/proyek Supabase, lalu coba lagi.');
   diagnostic.name='NetworkFetchError';diagnostic.cause=e;throw diagnostic;
  }
  throw e;
 }
}"""
if 'NETWORK_FETCH_FAILED • ' not in html:
    if html.count(old_rpc) != 1:
        raise SystemExit("RPC wrapper anchor mismatch; refusing to patch.")
    html=html.replace(old_rpc,new_rpc,1)

poll_old = """let adminAlertsPolling=false;
async function pollPcAdminAlerts(){
 if(adminAlertsPolling||!session||!currentOrg)return;"""
poll_new = """let adminAlertsPolling=false,adminAlertPollFailureCount=0,adminAlertPollRetryAt=0,adminAlertPollLastNoticeAt=0;
async function pollPcAdminAlerts(){
 if(adminAlertsPolling||!session||!currentOrg||document.visibilityState==='hidden'||Date.now()<adminAlertPollRetryAt)return;"""
if 'adminAlertPollRetryAt' not in html:
    if html.count(poll_old) != 1:
        raise SystemExit("Alert poller start anchor mismatch; refusing to patch.")
    html=html.replace(poll_old,poll_new,1)

# Background WebView polling does not guarantee notification delivery when Android throttles
# or stops the WebView. Do not keep generating API/OPTIONS logs while the Admin UI is hidden.
poll_guard_backoff = "if(adminAlertsPolling||!session||!currentOrg||Date.now()<adminAlertPollRetryAt)return;"
poll_guard_foreground = "if(adminAlertsPolling||!session||!currentOrg||document.visibilityState==='hidden'||Date.now()<adminAlertPollRetryAt)return;"
if poll_guard_foreground not in html:
    if html.count(poll_guard_backoff) != 1:
        raise SystemExit("Alert poll visibility guard anchor mismatch; refusing to patch.")
    html=html.replace(poll_guard_backoff,poll_guard_foreground,1)

success_anchor = """  const rows=await rpc('admin_recent_alerts',{p_org_id:currentOrg.id,p_since:since});
  if(!Array.isArray(rows))return;"""
success_new = """  const rows=await rpc('admin_recent_alerts',{p_org_id:currentOrg.id,p_since:since});
  adminAlertPollFailureCount=0;adminAlertPollRetryAt=0;
  if(!Array.isArray(rows))return;"""
if 'adminAlertPollFailureCount=0;adminAlertPollRetryAt=0;' not in html:
    if html.count(success_anchor) != 1:
        raise SystemExit("Alert poller success anchor mismatch; refusing to patch.")
    html=html.replace(success_anchor,success_new,1)

catch_pattern=re.compile(r" \}catch\(e\)\{\n  const now=Date\.now\(\);[\s\S]*?\n \}finally\{adminAlertsPolling=false\}\n\}")
catch_new = """ }catch(e){
  const now=Date.now();
  adminAlertPollFailureCount=Math.min(8,adminAlertPollFailureCount+1);
  const retryMs=Math.min(120000,15000*Math.pow(2,Math.min(adminAlertPollFailureCount-1,3)));
  adminAlertPollRetryAt=now+retryMs;
  if(!adminAlertPollLastNoticeAt||now-adminAlertPollLastNoticeAt>60000){
   adminAlertPollLastNoticeAt=now;
   const detail=String(e?.message||e||'unknown_error').slice(0,260);
   console.warn('Gagal sinkron notifikasi rental:',detail,'retry_ms=',retryMs);
   const feed=$('adminAlertFeed');
   if(feed){feed.classList.remove('hidden');feed.style.borderLeftColor='#ff4d6d';feed.textContent='Sinkronisasi alert rental gagal • '+detail+' • coba ulang dalam '+Math.round(retryMs/1000)+' detik. Event yang belum terkirim tidak dianggap sudah diterima.';}
   const state=$('adminSoundState');if(state)state.textContent='Sinkronisasi alert rental bermasalah • '+(DB_TARGET==='backup'?'DB2':'DB1');
  }
 }finally{adminAlertsPolling=false}
}"""
if 'Event yang belum terkirim tidak dianggap sudah diterima.' not in html:
    html, n = catch_pattern.subn(catch_new, html, count=1)
    if n != 1: raise SystemExit("Alert poller catch anchor mismatch; refusing to patch.")

old_wrapper = """function installAdminNotificationBridge(){
 if(typeof msg==='function'&&!msg.__adminAlertWrapped){
  const original=msg;const wrapped=function(message,error){
   original.apply(this,arguments);
   const text=String(message||'');
   const important=!!error||/usage_exceeded|pairing gagal|enrollment gagal|offline|berakhir|rental.*(stop|end|habis)|ditolak|koneksi.*gagal/i.test(text);
   if(important)adminNotify(message,error?'error':'info');
  };
  wrapped.__adminAlertWrapped=true;msg=wrapped;
 }
}"""
new_wrapper = """function installAdminNotificationBridge(){
 if(typeof msg==='function'&&!msg.__adminAlertWrapped){
  const original=msg;const wrapped=function(message,error){
   const text=String(message||'');
   const networkFailure=/Failed to fetch|NETWORK_FETCH_FAILED|NetworkFetchError/i.test(text);
   if(networkFailure){
    const now=Date.now();
    window.__aniAdminFetchFailureCount=(window.__aniAdminFetchFailureCount||0)+1;
    const last=window.__aniAdminFetchNoticeAt||0;
    if(last&&now-last<60000){
     const state=$('adminSoundState');if(state)state.textContent='Koneksi Supabase gagal • '+(DB_TARGET==='backup'?'DB2':'DB1')+' • percobaan berulang dibatasi';
     original.apply(this,arguments);return;
    }
    window.__aniAdminFetchNoticeAt=now;
    original.apply(this,[text+' • notifikasi jaringan dibatasi 1x/menit',error]);
    adminNotify(text+' • '+(DB_TARGET==='backup'?'DB2':'DB1')+' • cek koneksi/proyek Supabase','error');
    return;
   }
   original.apply(this,arguments);
   const important=!!error||/usage_exceeded|pairing gagal|enrollment gagal|offline|berakhir|rental.*(stop|end|habis)|ditolak|koneksi.*gagal/i.test(text);
   if(important)adminNotify(message,error?'error':'info');
  };
  wrapped.__adminAlertWrapped=true;msg=wrapped;
 }
}"""
if 'window.__aniAdminFetchNoticeAt' not in html:
    if html.count(old_wrapper) != 1: raise SystemExit("Global alert bridge anchor mismatch; refusing to patch.")
    html=html.replace(old_wrapper,new_wrapper,1)

# Final APK patch version after the existing v12.1.9 hardening passes.
if "versionCode 37" in gradle and "versionName '12.1.9'" in gradle:
    gradle = gradle.replace("versionCode 37", "versionCode 40", 1).replace("versionName '12.1.9'", "versionName '12.1.12'", 1)
elif "versionCode 40" not in gradle or "versionName '12.1.12'" not in gradle:
    raise SystemExit("Unexpected Android baseline version; refusing to bump blindly")

html_path.write_text(html, encoding="utf-8")
activity_path.write_text(activity, encoding="utf-8")
gradle_path.write_text(gradle, encoding="utf-8")
(ROOT / "VERSION.txt").write_text("v12.1.12-foreground-only-low-noise-alert-polling\n", encoding="utf-8")

for token in ("ensureNativeNotificationPermission()", "admin_recent_alerts", "pollPcAdminAlerts"):
    if token not in html:
        raise SystemExit("Final notification regression check missing: " + token)
for token in ("areAdminNotificationsEnabled", "hasPostNotificationPermission", "POST_NOTIFICATIONS"):
    if token not in activity:
        raise SystemExit("Final native notification regression check missing: " + token)
if "document.visibilityState==='hidden'" not in html:
    raise SystemExit("Foreground-only alert polling guard missing.")
print("Patched Android permission/status detection, owner-login permission flow, foreground-only alert polling, retry backoff and visible diagnostics. Version 12.1.12 / versionCode 40.")
