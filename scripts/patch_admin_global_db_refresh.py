from pathlib import Path

ROOT = Path(".")
HTML = ROOT / "android/app/src/main/assets/web/admin.html"
GRADLE = ROOT / "android/app/build.gradle"
VERSION = ROOT / "VERSION.txt"
html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")

def replace_once(source, old, new, label):
    count = source.count(old)
    if count == 0:
        if new in source: return source
        raise SystemExit(f"{label}: expected anchor not found")
    if count != 1: raise SystemExit(f"{label}: expected one anchor, found {count}")
    return source.replace(old, new, 1)

# Keep a separate DB1 Auth session available because the global coordinator authorizes route changes against DB1.
coordinator_helper = r'''let coordinatorAuthRefreshPromise=null;
async function adminCoordinatorAccessToken(){
 const key='sb-wzkjpycjizexxcxrfdvr-auth-token';let saved=null;
 try{saved=JSON.parse(localStorage.getItem(key)||'null')}catch(_){}
 let accessToken=String(saved?.access_token||''),expiresAt=Number(saved?.expires_at||0);
 if(accessToken&&(!expiresAt||expiresAt>Date.now()/1000+60))return accessToken;
 const refreshToken=String(saved?.refresh_token||'');
 if(!refreshToken)return '';
 if(coordinatorAuthRefreshPromise)return coordinatorAuthRefreshPromise;
 coordinatorAuthRefreshPromise=(async()=>{
  const response=await fetch(DB1_URL+'/auth/v1/token?grant_type=refresh_token',{method:'POST',headers:{apikey:DB1_KEY,'content-type':'application/json'},body:JSON.stringify({refresh_token:refreshToken}),cache:'no-store'});
  const data=await response.json().catch(()=>({}));
  if(!response.ok||!data?.access_token||!data?.refresh_token)throw new Error('DB1_OWNER_SESSION_REFRESH_FAILED');
  const updated={...(saved||{}),...data,expires_at:Math.floor(Date.now()/1000)+Number(data.expires_in||3600)};
  try{localStorage.setItem(key,JSON.stringify(updated))}catch(_){}
  return String(updated.access_token);
 })();
 try{return await coordinatorAuthRefreshPromise}finally{coordinatorAuthRefreshPromise=null}
}
'''
anchor = "async function requestGlobalDbSwitch(){"
if "async function adminCoordinatorAccessToken()" not in html:
    html = replace_once(html, anchor, coordinator_helper + "\n" + anchor, "DB1 coordinator token helper")
html = replace_once(
    html,
    "const token=await adminAccessToken().catch(()=> '');",
    "const token=await adminCoordinatorAccessToken().catch(()=> '');",
    "DB1 coordinator authorization token"
)
html = html.replace(
    "if(!token)return msg('Sesi Admin tidak valid. Login kembali untuk mengubah route global.',true);",
    "if(!token)return msg('Sesi owner DB1 untuk coordinator tidak tersedia. Login ke DB1 sekali agar perpindahan global tetap bisa dilakukan dari DB2.',true);",
    1
)

old_backup = "return !!r&&r.active_target==='backup'&&r.backup_ready===true&&r.auth_parity_ready===true&&r.data_parity_ready===true&&r.routing_gateway_ready===true&&r.can_switch_to_backup===true&&Number.isFinite(Number(r.epoch))&&Number(r.epoch)>0&&typeof r.switch_id==='string'&&r.switch_id.length>0&&parityFresh&&schemasMatch;"
new_backup = "return !!r&&r.active_target==='backup'&&r.data_parity_ready===true&&r.sync_in_progress!==true&&r.can_switch_to_backup===true&&Number.isFinite(Number(r.epoch))&&Number(r.epoch)>0&&typeof r.switch_id==='string'&&r.switch_id.length>0&&parityFresh&&schemasMatch;"
html = replace_once(html, old_backup, new_backup, "Admin active-backup route resolver")
old_switch = "return r.backup_ready===true&&r.auth_parity_ready===true&&r.data_parity_ready===true&&r.routing_gateway_ready===true&&fresh&&schema;"
new_switch = "return !!r&&r.data_parity_ready===true&&r.sync_in_progress!==true&&fresh&&schema;"
html = replace_once(html, old_switch, new_switch, "Admin switch readiness")
old_mismatch = "const dataMismatch=!a.data_parity_ready||!b.data_parity_ready||!a.backup_ready||!b.backup_ready||!a.auth_parity_ready||!b.auth_parity_ready;"
new_mismatch = "const dataMismatch=!a.data_parity_ready||!b.data_parity_ready||a.sync_in_progress===true||b.sync_in_progress===true;"
html = replace_once(html, old_mismatch, new_mismatch, "Admin switch data gate")
html = html.replace(
    "DB Sync melakukan upsert dari database aktif ke database standby. Tidak menghapus baris target yang tidak ada pada sumber; kesiapan cutover ditentukan parity data terbaru dan kesamaan schema.",
    "DB Sync melakukan upsert dari database aktif ke database standby. Tidak menghapus baris target yang tidak ada pada sumber; kesiapan cutover ditentukan parity data terbaru dan kesamaan schema.",
    1
)
html = html.replace(
    "Perpindahan ini hanya mengubah aplikasi Admin pada perangkat ini; PC Billing dan Reseller TIDAK ikut berpindah.",
    "Perpindahan ini memperbarui route global; klien yang mendukung route-control membaca target dan epoch terbaru saat refresh.",
    1
)
html = html.replace("Data/auth ditandai cocok, tetapi gateway bersama, versi schema, atau pemeriksaan parity terbaru belum lulus. Pindah DB tetap dikunci sampai pemeriksaan tersebut lulus.", "Parity data, pemeriksaan parity terbaru, atau kesamaan versi schema belum lulus. Pindah DB tetap dikunci sampai pemeriksaan inti tersebut lulus.", 1)
html = html.replace("Cutover ditolak: salah satu DB belum lulus auth/data/gateway/schema parity terbaru. Route aktif tetap seperti sebelumnya.", "Cutover ditolak: salah satu DB belum lulus parity data terbaru atau kesamaan schema. Route aktif tetap seperti sebelumnya.", 1)

if "versionCode 44" in gradle and "versionName '12.1.16'" in gradle:
    gradle = gradle.replace("versionCode 44", "versionCode 45", 1)
    gradle = gradle.replace("versionName '12.1.16'", "versionName '12.1.17'", 1)
elif "versionCode 45" not in gradle or "versionName '12.1.17'" not in gradle:
    raise SystemExit("Unexpected Admin version after base V12.1.16 patches; refusing to bump blindly")
if "async function monitorDualDbRoute()" not in html or "function resolveDualDbRoute(" not in html:
    raise SystemExit("Admin global route monitor/resolver not found")
for forbidden in (
    "return r.backup_ready===true&&r.auth_parity_ready===true&&r.data_parity_ready===true&&r.routing_gateway_ready===true&&fresh&&schema;",
    "const dataMismatch=!a.data_parity_ready||!b.data_parity_ready||!a.backup_ready||!b.backup_ready||!a.auth_parity_ready||!b.auth_parity_ready;"
):
    if forbidden in html: raise SystemExit("Obsolete UI-only cutover guard remains")
HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
VERSION.write_text("v12.1.17-global-db-route-refresh\n", encoding="utf-8")
print("PASS: Admin route monitor retained; parity freshness/schema/sync guard retained; v12.1.17/code45")
