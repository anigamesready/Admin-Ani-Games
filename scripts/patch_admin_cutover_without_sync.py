from pathlib import Path
import re

HTML = Path("android/app/src/main/assets/web/admin.html")
GRADLE = Path("android/app/build.gradle")
html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")
marker = "V12.1.21-ROUTE-CUTOVER-WITHOUT-FORCED-SYNC"
if marker in html:
    print("PASS: Admin V12.1.21 route cutover patch already applied.")
    raise SystemExit(0)

if "V12.1.20-DB-ROUTE-AUTH-GATEWAY-READINESS" not in html:
    raise SystemExit("Expected Admin V12.1.20 gateway readiness source.")

def replace_function(source, signature, replacement, label):
    pattern = re.compile(r"(?ms)^" + re.escape(signature) + r".*?^\}")
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise SystemExit(f"{label}: expected one function, found {len(matches)}")
    return source[:matches[0].start()] + replacement.rstrip() + source[matches[0].end():]

# Auth/rental parity is informative but not a route-cutover blocker. Preserve schema,
# active-owner validation, cross-project route identity, gateway contract and sync lock.
html = replace_function(html, "function routeReadyForSwitch(r){", r"""
function routeReadyForSwitch(r){
 const schema=!!r?.schema_version&&r.schema_version===r.primary_schema_version&&r.schema_version===r.backup_schema_version;
 return !!r&&r.primary_ready===true&&r.backup_ready===true&&r.routing_gateway_ready===true&&r.sync_in_progress!==true&&schema;
}""", "Route-only readiness")

# The shared gateway readiness is checked on demand before a switch, so stale UI booleans
# from old builds must not prevent an authenticated owner from starting that check.
old_guard = " if(!dualDbRouteReady)throw new Error('GLOBAL_ROUTE_NOT_VERIFIED');"
if html.count(old_guard) != 2:
    raise SystemExit(f"Expected two stale UI readiness guards, found {html.count(old_guard)}")
html = html.replace(old_guard, "", 2)

new_switch = r"""
async function requestGlobalDbSwitch(){
 if(typeof ctx==='undefined'||ctx?.role!=='owner')return msg('Hanya owner yang dapat memindahkan seluruh sistem database.',true);
 const target=String($('globalDbTarget')?.value||''),button=$('globalDbSwitchButton');
 if(!['primary','backup'].includes(target))return msg('Target database tidak valid.',true);
 if(button){button.disabled=true;button.textContent='Memeriksa route…'}
 try{
  let [d1,d2]=await Promise.all([
   globalRouteStatus(DB1_URL,DB1_ROUTE_KEY,'wzkjpycjizexxcxrfdvr'),
   globalRouteStatus(DB2_URL,DB2_ROUTE_KEY,'xcdbipgsvohesxhxydep')
  ]);
  let a=d1.route,b=d2.route;
  const same=(x,y)=>x.active_target===y.active_target&&Number(x.epoch)===Number(y.epoch)&&String(x.switch_id||'')===String(y.switch_id||'');
  if(!same(a,b))throw new Error('GLOBAL_ROUTE_MISMATCH: DB1/DB2 belum kompak; tidak dipaksa.');
  if(a.sync_in_progress===true||b.sync_in_progress===true)throw new Error('CORE_SYNC_ALREADY_IN_PROGRESS');
  const current=a.active_target;
  if(current===target){dbSyncStatus('Seluruh sistem sudah aktif di '+(target==='backup'?'DB2':'DB1')+'.');await checkBothDbApis();return {ok:true,alreadyActive:true};}
  if(DB_TARGET!==current)throw new Error('ADMIN_TARGET_STALE_REFRESH_REQUIRED');
  const targetName=target==='backup'?'DB2':'DB1';
  if(!confirm('Pindahkan SELURUH SISTEM ke '+targetName+' sekarang?\\n\\nPerpindahan ini TIDAK menjalankan Sync dan TIDAK menyalin Auth. Data rental yang berbeda tetap tersimpan di DB asal sampai Sync dijalankan lewat menu terpisah. Backend akan memastikan route/epoch/switch ID, versi schema, owner, dan Gateway cocok. Kalau finalisasi gagal, sistem akan melaporkan gagal dan tidak mengklaim berhasil.'))return {ok:false,cancelled:true};
  dbSyncStatus('Memeriksa owner, schema, route kedua DB, dan Gateway…');
  const proof=await refreshGatewayReadiness();
  if(proof?.gatewayReady!==true||proof?.routeReady!==true)throw new Error('GLOBAL_ROUTE_NOT_READY');
  [d1,d2]=await Promise.all([
   globalRouteStatus(DB1_URL,DB1_ROUTE_KEY,'wzkjpycjizexxcxrfdvr'),
   globalRouteStatus(DB2_URL,DB2_ROUTE_KEY,'xcdbipgsvohesxhxydep')
  ]);
  a=d1.route;b=d2.route;
  if(!same(a,b)||a.active_target!==current||b.active_target!==current)throw new Error('ROUTE_CHANGED_DURING_GATEWAY_CHECK');
  if(a.sync_in_progress===true||b.sync_in_progress===true)throw new Error('CORE_SYNC_ALREADY_IN_PROGRESS');
  if(!routeReadyForSwitch(a)||!routeReadyForSwitch(b)||a.schema_version!==b.schema_version)throw new Error('ROUTE_SCHEMA_OR_GATEWAY_NOT_READY');
  dbSyncStatus('Readiness lolos. Memfinalisasi perpindahan global…');
  const switched=await requestSharedDbRouteSwitch(target,'Admin V12.1.21 route cutover without forced sync');
  if(switched.active_target!==target||switched.finalized!==true||!switched.switchId||!Number.isFinite(Number(switched.epoch)))throw new Error('CORE_SWITCH_FINALIZATION_MISSING');
  const [c1,c2]=await Promise.all([
   globalRouteStatus(DB1_URL,DB1_ROUTE_KEY,'wzkjpycjizexxcxrfdvr'),
   globalRouteStatus(DB2_URL,DB2_ROUTE_KEY,'xcdbipgsvohesxhxydep')
  ]);
  const expected='Coordinated global route finalized: '+target+' epoch '+Number(switched.epoch)+' switch '+String(switched.switchId);
  const confirmed=r=>r.active_target===target&&Number(r.epoch)===Number(switched.epoch)&&String(r.switch_id||'')===String(switched.switchId)&&String(r.cutover_test_note||'')===expected&&!!r.last_cutover_test_at&&r.sync_in_progress!==true;
  if(!confirmed(c1.route)||!confirmed(c2.route))throw new Error('ROUTE_FINAL_CONFIRMATION_FAILED');
  dbSyncStatus('Berhasil pindah ke '+targetName+' • epoch '+switched.epoch+'. DB1 dan DB2 mengonfirmasi route. Jalankan Sync terpisah untuk menyelaraskan rental, lalu aplikasi dimuat ulang…');
  try{localStorage.removeItem(DB_ROUTE_NOTICE_KEY);localStorage.removeItem(DB_SYNC_RUN_KEY);localStorage.removeItem('ani_games_db_sync_hold_quiesce_v1')}catch(_){}
  location.reload();
  return {ok:true,target,epoch:switched.epoch,switchId:switched.switchId};
 }catch(e){const detail=String(e?.message||e);dbSyncStatus('Perpindahan global gagal/diblokir: '+detail,true);msg('Pindah DB gagal atau belum terkonfirmasi: '+detail,true);try{await checkBothDbApis()}catch(_){}return {ok:false,error:detail}}
 finally{if(button){button.disabled=false;button.textContent='Pindah seluruh sistem'}}
}
"""
html = replace_function(html, "async function requestGlobalDbSwitch(){", new_switch, "Global switch without mandatory sync")

# This explicit marker is required by the workflow version gate and proves the
# intended V12.1.21 switch semantics were actually applied to the bundled HTML.
if marker not in html:
    marker_anchor = "async function requestGlobalDbSwitch(){"
    if html.count(marker_anchor) != 1:
        raise SystemExit("V12.1.21 marker insertion anchor missing or duplicated.")
    html = html.replace(marker_anchor, "// " + marker + "\n" + marker_anchor, 1)
if marker not in html:
    raise SystemExit("V12.1.21 workflow marker was not inserted.")

new_backup = r"""
function routeBackupReady(r){
 const schema=!!r?.schema_version&&r.schema_version===r.primary_schema_version&&r.schema_version===r.backup_schema_version;
 const epoch=Number(r?.epoch),switchId=String(r?.switch_id||'');
 const note='Coordinated global route finalized: backup epoch '+epoch+' switch '+switchId;
 const finalized=!!r?.last_cutover_test_at&&String(r?.cutover_test_note||'')===note;
 return !!r&&r.active_target==='backup'&&r.backup_ready===true&&r.routing_gateway_ready===true&&r.sync_in_progress!==true&&
  finalized&&Number.isFinite(epoch)&&epoch>0&&!!switchId&&schema;
}"""
html = replace_function(html, "function routeBackupReady(r){", new_backup, "Admin active-backup runtime route")

# UI text must make clear that parity sync is a separate action.
html = html.replace("const sync=await coreDbCall('sync-core');", "const sync=await coreDbCall('sync-core');")
if "coreDbCall('sync-core')" not in html:
    raise SystemExit("Standalone DB Sync handler unexpectedly missing.")
if "Perpindahan ini TIDAK menjalankan Sync" not in html:
    raise SystemExit("Switch confirmation does not explain the separate sync step.")
if "r.auth_parity_ready===true&&r.data_parity_ready===true&&r.routing_gateway_ready===true" in html:
    raise SystemExit("Strict legacy Admin active-backup runtime gate remains.")

old_code = "versionCode 48"
old_name = "versionName '12.1.20'"
if old_code not in gradle or old_name not in gradle:
    raise SystemExit("Expected Admin V12.1.20 Gradle version markers.")
gradle = gradle.replace(old_code, "versionCode 49", 1).replace(old_name, "versionName '12.1.21'", 1)
HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
Path("VERSION.txt").write_text("AniGames Admin Android V12.1.21 — route cutover without forced sync; Auth parity optional\n", encoding="utf-8")
print("PASS: Admin V12.1.21 allows owner-confirmed DB switch without forced data/Auth sync; gateway/schema/route proof remains mandatory.")
