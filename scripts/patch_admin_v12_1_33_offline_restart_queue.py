from pathlib import Path

ROOT = Path("android/app/src/main")
WEB = ROOT / "assets/web"
ADMIN = WEB / "admin.html"
CONTROL = WEB / "admin-control.html"
GRADLE = Path("android/app/build.gradle")

MARKER = "V12.1.33-OFFLINE-RESTART-QUEUE"
OLD_MARKER = "V12.1.32-ROUTE-GET-NO-PREFLIGHT"

def replace_once(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{label} anchor mismatch: expected 1, got {count}")
    return source.replace(old, new, 1)

if not ADMIN.is_file() or not CONTROL.is_file() or not GRADLE.is_file():
    raise SystemExit("Required Android app assets or Gradle file are missing")

admin = ADMIN.read_text(encoding="utf-8")
control = CONTROL.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")

if MARKER in admin and MARKER in control:
    if "versionCode 61" in gradle and "versionName '12.1.33'" in gradle:
        print("PASS: Admin V12.1.33 offline restart queue patch already applied")
        raise SystemExit(0)
    raise SystemExit("V12.1.33 HTML marker exists but Gradle version does not match")

if OLD_MARKER not in admin:
    raise SystemExit("Expected Admin V12.1.32 base marker is missing; refusing unknown source")
if "versionCode 60" not in gradle or "versionName '12.1.32'" not in gradle:
    raise SystemExit("Expected exact Admin V12.1.32 package version; refusing patch")

admin = replace_once(
    admin,
    "async function cmd(device,command,seconds){try{const target=devicesCache.find(d=>d.id===device);if(!target)return msg('PC tidak ditemukan pada tenant aktif.',true);if(target.uiStatus!=='online')return msg('PC terpilih sedang OFFLINE. Kontrol tidak dikirim.',true);const payload={source:'dashboard-admin'};",
    """// V12.1.33-OFFLINE-RESTART-QUEUE
async function cmd(device,command,seconds){try{const target=devicesCache.find(d=>d.id===device);if(!target)return msg('PC tidak ditemukan pada tenant aktif.',true);const offlineRestart=command==='restart_billing'&&target.uiStatus!=='online';if(target.uiStatus!=='online'&&!offlineRestart)return msg('PC terpilih sedang OFFLINE. Kontrol ini tidak dikirim.',true);const payload={source:'dashboard-admin',...(offlineRestart?{queuedWhileOffline:true}: {})};""",
    "Main dashboard offline command guard",
)
admin = replace_once(
    admin,
    "await rpc('admin_command',{p_org_id:currentOrg.id,p_device_id:device,p_command:command,p_payload:payload});msg('Perintah '+command+' dikirim hanya ke '+target.device_name+'.');await loadDevices()}catch(e){msg(e.message,true)}}",
    "await rpc('admin_command',{p_org_id:currentOrg.id,p_device_id:device,p_command:command,p_payload:payload});msg(offlineRestart?'Perintah Restart Billing masuk antrean. Agen PC akan mengambilnya saat PC terhubung kembali; tunggu konfirmasi status.':'Perintah '+command+' dikirim hanya ke '+target.device_name+'.');await loadDevices()}catch(e){msg(e.message,true)}}",
    "Main dashboard offline restart acknowledgment",
)
old_control = ("async function sendCommand(command,payload={}){const d=devices.find(x=>x.id===selectedId);if(!d)return msg('Pilih PC terlebih dahulu.',true);if(!isOnline(d))return msg('PC OFFLINE — command tidak dikirim.',true);if(!confirm(" + chr(96) + "Kirim " + chr(36) + "{command} ke " + chr(36) + "{d.device_name||d.client_id}?" + chr(96) + "))return;try{await rpc('billing_command',{p_session_token:token,p_org_id:org.id,p_device_id:d.id,p_command:command,p_payload:{...payload,source:'billing-control'}});msg(" + chr(96) + "Perintah " + chr(36) + "{command} dikirim." + chr(96) + ");setTimeout(refreshAll,700)}catch(e){msg(e.message||'Perintah gagal.',true)}}")
new_control = """// V12.1.33-OFFLINE-RESTART-QUEUE
async function sendCommand(command,payload={}){const d=devices.find(x=>x.id===selectedId);if(!d)return msg('Pilih PC terlebih dahulu.',true);const offlineRestart=command==='restart_billing'&&!isOnline(d);if(!isOnline(d)&&!offlineRestart)return msg('PC OFFLINE — command tidak dikirim.',true);const question=offlineRestart?'PC '+(d.device_name||d.client_id)+' sedang OFFLINE. Antrekan Restart Billing agar watchdog mengambilnya saat PC terhubung kembali?':'Kirim '+command+' ke '+(d.device_name||d.client_id)+'?';if(!confirm(question))return;try{await rpc('billing_command',{p_session_token:token,p_org_id:org.id,p_device_id:d.id,p_command:command,p_payload:{...payload,source:'billing-control',...(offlineRestart?{queuedWhileOffline:true}:{})}});msg(offlineRestart?'Restart Billing masuk antrean. Status baru bisa dikonfirmasi saat PC kembali terhubung.':'Perintah '+command+' dikirim.');setTimeout(refreshAll,700)}catch(e){msg(e.message||'Perintah gagal.',true)}}"""
control = replace_once(control, old_control, new_control, "Billing Control offline command guard")

admin = admin.replace(OLD_MARKER, MARKER)
if MARKER not in admin or MARKER not in control:
    raise SystemExit("V12.1.33 markers were not added to both Admin views")
if "offlineRestart=command==='restart_billing'" not in admin or "offlineRestart=command==='restart_billing'" not in control:
    raise SystemExit("Offline restart exception not present on both Admin views")
if "if(target.uiStatus!=='online')return msg('PC terpilih sedang OFFLINE. Kontrol tidak dikirim.',true);" in admin:
    raise SystemExit("Main dashboard still blocks all offline commands")
if "if(!isOnline(d))return msg('PC OFFLINE — command tidak dikirim.',true);" in control:
    raise SystemExit("Billing Control still blocks all offline commands")

gradle = replace_once(gradle, "versionCode 60", "versionCode 61", "Admin versionCode")
gradle = replace_once(gradle, "versionName '12.1.32'", "versionName '12.1.33'", "Admin versionName")

ADMIN.write_text(admin, encoding="utf-8")
CONTROL.write_text(control, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
print("PASS: V12.1.33 allows only restart_billing to be queued while offline; all other offline commands remain blocked.")
