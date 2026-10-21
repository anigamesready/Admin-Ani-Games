from pathlib import Path
import re

html_path = Path("android/app/src/main/assets/web/admin.html")
gradle_path = Path("android/app/build.gradle")
html = html_path.read_text(encoding="utf-8")
gradle = gradle_path.read_text(encoding="utf-8")

def replace_region(source, start_marker, end_marker, replacement, label):
    starts = [m.start() for m in re.finditer(re.escape(start_marker), source)]
    if len(starts) != 1:
        raise SystemExit(f"{label}: expected one start marker, found {len(starts)}")
    start = starts[0]
    end = source.find(end_marker, start + len(start_marker))
    if end < 0:
        raise SystemExit(f"{label}: end marker missing")
    return source[:start] + replacement + source[end:]

# The core backend synchronizes only rental_accounts + billing_control_accounts.
# It deliberately does not copy Auth users, secrets, function config, command queues,
# history, or pairing tokens. Pairing/token fingerprints already matched in the audit.
helper = r"""
async function coreDbCall(action,payload={}){
 const token=await adminAccessToken();
 const cfg=DB_TARGET==='backup'?{url:DB2_URL,key:DB2_KEY,ref:'xcdbipgsvohesxhxydep'}:{url:DB1_URL,key:DB1_KEY,ref:'wzkjpycjizexxcxrfdvr'};
 const response=await fetch(cfg.url+'/functions/v1/db-core-sync',{method:'POST',headers:{apikey:cfg.key,'content-type':'application/json',authorization:'Bearer '+token},body:JSON.stringify({action,...payload}),cache:'no-store'});
 const data=await response.json().catch(()=>({}));
 if(!response.ok||data?.ok!==true)throw new Error(String(data?.error||('CORE_DB_HTTP_'+response.status)));
 return data;
}
"""
if "async function coreDbCall(action,payload={})" not in html:
    anchor = "const DB_SYNC_RUN_KEY='ani_games_db_sync_active_run_v1'"
    i = html.find(anchor)
    if i < 0:
        raise SystemExit("Core DB helper insertion point missing")
    html = html[:i] + helper + html[i:]

new_preview = r"""async function previewDbSync(){
 if(typeof ctx==='undefined'||ctx?.role!=='owner')return msg('Hanya owner yang dapat menjalankan DB Sync.',true);
 const button=document.querySelector('#databaseTools button[onclick="previewDbSync()"]');
 if(button)button.disabled=true;
 try{
  const [d1,d2]=await Promise.all([
   globalRouteStatus(DB1_URL,DB1_ROUTE_KEY,'wzkjpycjizexxcxrfdvr'),
   globalRouteStatus(DB2_URL,DB2_ROUTE_KEY,'xcdbipgsvohesxhxydep')
  ]);
  const a=d1.route,b=d2.route;
  if(a.active_target!==b.active_target||Number(a.epoch)!==Number(b.epoch)||String(a.switch_id||'')!==String(b.switch_id||''))throw new Error('GLOBAL_ROUTE_MISMATCH');
  if(a.sync_in_progress===true||b.sync_in_progress===true)throw new Error('CORE_SYNC_ALREADY_IN_PROGRESS');
  const sourceName=a.active_target==='backup'?'DB2':'DB1',targetName=a.active_target==='backup'?'DB1':'DB2';
  const summary=$('dbSyncPreviewSummary');
  if(summary)summary.textContent='Preview '+sourceName+' → '+targetName+': hanya rental + user reseller. PC pairing/token sudah cocok dan tidak disalin; Admin/Auth, secrets, fungsi/API, riwayat, log, transaksi, dan command queue tidak dibawa. Sync hanya tambah/update; tidak menghapus data tujuan.';
  dbSyncStatus('Preview hanya membaca route-control. Belum ada perubahan data.');
  return {ok:true,source:sourceName,target:targetName,tables:['rental_accounts','billing_control_accounts'],deleted:0};
 }catch(e){const detail=String(e?.message||e);dbSyncStatus('Preview gagal: '+detail,true);msg('Preview Sync gagal: '+detail,true);return null}
 finally{if(button)button.disabled=false}
}
"""
html = replace_region(html, "async function previewDbSync(){", "\nasync function requestDbSync", new_preview, "Simplified scoped sync preview")

new_sync = r"""async function requestDbSync(options={}){
 if(typeof ctx==='undefined'||ctx?.role!=='owner')return msg('Hanya owner yang dapat menjalankan DB Sync.',true);
 const button=$('dbSyncExecute');if(button)button.disabled=true;
 try{
  const [d1,d2]=await Promise.all([
   globalRouteStatus(DB1_URL,DB1_ROUTE_KEY,'wzkjpycjizexxcxrfdvr'),
   globalRouteStatus(DB2_URL,DB2_ROUTE_KEY,'xcdbipgsvohesxhxydep')
  ]);
  const a=d1.route,b=d2.route;
  if(a.active_target!==b.active_target||Number(a.epoch)!==Number(b.epoch)||String(a.switch_id||'')!==String(b.switch_id||''))throw new Error('GLOBAL_ROUTE_MISMATCH');
  if(a.sync_in_progress===true||b.sync_in_progress===true)throw new Error('CORE_SYNC_ALREADY_IN_PROGRESS');
  if(DB_TARGET!==a.active_target)throw new Error('ADMIN_TARGET_STALE_REFRESH_REQUIRED');
  const sourceName=a.active_target==='backup'?'DB2':'DB1',targetName=a.active_target==='backup'?'DB1':'DB2';
  if(!confirm('Sinkronkan '+sourceName+' → '+targetName+' sekarang?\\n\\nHanya tambah/update rental dan akun user reseller. Tidak ada penghapusan. Auth Admin, secrets, API/function config, riwayat rental, transaksi, log, command queue, dan pairing tidak ikut dibawa.'))return {ok:false,cancelled:true};
  if(button)button.textContent='Sync data inti…';
  const result=await coreDbCall('sync-core');
  if(result.deleted!==0)throw new Error('UNEXPECTED_DELETE_REPORTED');
  const tables=result.tables||{};
  const rental=tables.rental_accounts||{},reseller=tables.billing_control_accounts||{};
  const summary=$('dbSyncPreviewSummary');
  const counts='Rental +'+Number(rental.inserted||0)+' / update '+Number(rental.updated||0)+' / tetap '+Number(rental.unchanged||0)+'; reseller +'+Number(reseller.inserted||0)+' / update '+Number(reseller.updated||0)+' / tetap '+Number(reseller.unchanged||0)+'.';
  if(summary)summary.textContent=sourceName+' → '+targetName+' selesai. '+counts+' Tidak ada baris dihapus.';
  dbSyncStatus('Sync inti berhasil. Data pairing tetap utuh; cutover harus dijalankan lewat tombol Pindah Seluruh Sistem.',false);
  msg('Sync inti selesai. '+counts);
  await checkBothDbApis();
  return {...result,ok:true,ready:true};
 }catch(e){const detail=String(e?.message||e);dbSyncStatus('Sync inti gagal: '+detail,true);msg('Sync inti gagal: '+detail,true);return {ok:false,error:detail}}
 finally{if(button){button.disabled=false;button.textContent='Sinkronkan DB aktif → DB standby'}}
}
"""
html = replace_region(html, "async function requestDbSync(options={}){", "\nasync function verifyDb2OwnerLogin(){", new_sync, "Core-only incremental sync")

# The ordinary data-sync button must remain available when parity is stale; syncing is what refreshes parity.
mode_pattern = re.compile(r"function updateDbSyncDirection\(\)\{[^\n]*\}")
mode_replacement = r"""function updateDbSyncDirection(){const source=DB_TARGET==='backup'?'DB2':'DB1',target=DB_TARGET==='backup'?'DB1':'DB2',sourceLabel=$('dbSyncSourceLabel'),targetLabel=$('dbSyncTargetLabel'),button=$('dbSyncExecute'),verify=$('dbSyncVerifyOwner'),passwordLabel=$('dbSyncOwnerPasswordLabel'),state=$('dbSyncRouteState'),route=dualDbRouteState?.route,syncing=route?.sync_in_progress===true;if(sourceLabel)sourceLabel.textContent=source+' • Sumber aktif';if(targetLabel)targetLabel.textContent=target+' • Standby tujuan (upsert, tanpa delete)';if(button){button.textContent='Sinkronkan '+source+' → '+target;button.disabled=!route||syncing||ctx?.role!=='owner'}if(verify)verify.disabled=true;if(passwordLabel)passwordLabel.textContent='Auth Admin dikelola backend; tidak ikut Sync';if(state)state.textContent='Route global aktif: '+source+' • standby: '+target+' • epoch '+DB_ROUTE_EPOCH+(syncing?' • SYNC BERJALAN':'');}"""
html, mode_count = mode_pattern.subn(mode_replacement, html, count=1)
if mode_count != 1:
    raise SystemExit("Sync button enablement patch anchor mismatch")

route_ready = r"""function routeReadyForSwitch(r){
 const t=Date.parse(r?.last_parity_check_at||''),fresh=Number.isFinite(t)&&Date.now()-t<=30*60*1000&&t<=Date.now()+60000;
 const schema=!!r?.schema_version&&r.schema_version===r.primary_schema_version&&r.schema_version===r.backup_schema_version;
 return !!r&&r.data_parity_ready===true&&r.sync_in_progress!==true&&fresh&&schema;
}
"""
html = replace_region(html, "function routeReadyForSwitch(r){", "\nasync function requestGlobalDbSwitch(){", route_ready, "Minimal core route readiness")

new_switch = r"""async function requestGlobalDbSwitch(){
 if(typeof ctx==='undefined'||ctx?.role!=='owner')return msg('Hanya owner yang dapat memindahkan seluruh sistem database.',true);
 const target=String($('globalDbTarget')?.value||''),button=$('globalDbSwitchButton');
 if(!['primary','backup'].includes(target))return msg('Target database tidak valid.',true);
 if(button){button.disabled=true;button.textContent='Memeriksa…'}
 try{
  let [d1,d2]=await Promise.all([
   globalRouteStatus(DB1_URL,DB1_ROUTE_KEY,'wzkjpycjizexxcxrfdvr'),
   globalRouteStatus(DB2_URL,DB2_ROUTE_KEY,'xcdbipgsvohesxhxydep')
  ]);
  let a=d1.route,b=d2.route;
  if(a.active_target!==b.active_target||Number(a.epoch)!==Number(b.epoch)||String(a.switch_id||'')!==String(b.switch_id||''))throw new Error('GLOBAL_ROUTE_MISMATCH: DB1/DB2 belum kompak; jangan paksa pindah.');
  const current=a.active_target;
  if(current===target){dbSyncStatus('Seluruh sistem sudah aktif di '+(target==='backup'?'DB2':'DB1')+'.');await checkBothDbApis();return {ok:true,alreadyActive:true};}
  if(a.sync_in_progress===true||b.sync_in_progress===true)throw new Error('CORE_SYNC_ALREADY_IN_PROGRESS');
  if(DB_TARGET!==current)throw new Error('ADMIN_TARGET_STALE_REFRESH_REQUIRED');
  const sourceName=current==='backup'?'DB2':'DB1',targetName=target==='backup'?'DB2':'DB1';
  if(!confirm('Pindahkan SELURUH SISTEM ke '+targetName+'?\\n\\nBackend akan menyinkronkan rental + user reseller secara incremental, lalu mengganti route di kedua DB dengan epoch/switch ID yang sama. Tidak menyalin Auth/secrets/fungsi, pairing sudah dipertahankan, dan tidak ada penghapusan. Kalau verifikasi route gagal, sistem tidak akan mengklaim switch berhasil.'))return {ok:false,cancelled:true};
  dbSyncStatus('Sinkronisasi akhir '+sourceName+' → '+targetName+'…');
  const sync=await coreDbCall('sync-core');
  if(sync.deleted!==0)throw new Error('UNEXPECTED_DELETE_REPORTED');
  [d1,d2]=await Promise.all([
   globalRouteStatus(DB1_URL,DB1_ROUTE_KEY,'wzkjpycjizexxcxrfdvr'),
   globalRouteStatus(DB2_URL,DB2_ROUTE_KEY,'xcdbipgsvohesxhxydep')
  ]);
  a=d1.route;b=d2.route;
  if(a.active_target!==current||b.active_target!==current||Number(a.epoch)!==Number(b.epoch)||String(a.switch_id||'')!==String(b.switch_id||''))throw new Error('ROUTE_CHANGED_DURING_SYNC');
  if(a.sync_in_progress===true||b.sync_in_progress===true||!routeReadyForSwitch(a)||!routeReadyForSwitch(b)||a.schema_version!==b.schema_version)throw new Error('CORE_SYNC_READINESS_NOT_FRESH');
  dbSyncStatus('Data inti lolos pemeriksaan. Mengganti route global…');
  const switched=await coreDbCall('switch-global',{target,reason:'Admin V12.1.17 simple scoped DB switch'});
  if(switched.active_target!==target||switched.finalized!==true||!switched.switchId||!Number.isFinite(Number(switched.epoch)))throw new Error('CORE_SWITCH_FINALIZATION_MISSING');
  const [c1,c2]=await Promise.all([
   globalRouteStatus(DB1_URL,DB1_ROUTE_KEY,'wzkjpycjizexxcxrfdvr'),
   globalRouteStatus(DB2_URL,DB2_ROUTE_KEY,'xcdbipgsvohesxhxydep')
  ]);
  const expected='Coordinated global route finalized: '+target+' epoch '+Number(switched.epoch)+' switch '+String(switched.switchId);
  const confirmed=r=>r.active_target===target&&Number(r.epoch)===Number(switched.epoch)&&String(r.switch_id||'')===String(switched.switchId)&&String(r.cutover_test_note||'')===expected&&!!r.last_cutover_test_at&&r.sync_in_progress!==true;
  if(!confirmed(c1.route)||!confirmed(c2.route))throw new Error('ROUTE_FINAL_CONFIRMATION_FAILED');
  dbSyncStatus('Berhasil pindah seluruh sistem ke '+targetName+' • epoch '+switched.epoch+'. DB1 dan DB2 sudah mengonfirmasi route; aplikasi dimuat ulang…');
  try{localStorage.removeItem(DB_ROUTE_NOTICE_KEY);localStorage.removeItem(DB_SYNC_RUN_KEY);localStorage.removeItem('ani_games_db_sync_hold_quiesce_v1')}catch(_){}
  location.reload();
  return {ok:true,target,epoch:switched.epoch,switchId:switched.switchId};
 }catch(e){const detail=String(e?.message||e);dbSyncStatus('Perpindahan global ditolak: '+detail,true);msg('Pindah DB gagal atau belum terkonfirmasi: '+detail,true);try{await checkBothDbApis()}catch(_){}return {ok:false,error:detail}}
 finally{if(button){button.disabled=false;button.textContent='Pindah seluruh sistem'}}
}
"""
switch_pattern = r"async function requestGlobalDbSwitch\(\)\{.*?^\}"
html, switch_count = re.subn(switch_pattern, new_switch.rstrip(), html, count=1, flags=re.S | re.M)
if switch_count != 1:
    raise SystemExit("Direct core-db global route switch: function boundary not found")

# Remove outdated manual Auth-verification UI. Auth identities are separate-project concerns,
# not part of the business-data sync action.
html = html.replace('<button type="button" id="dbSyncVerifyOwner" onclick="verifyDb2OwnerLogin()">Verifikasi login DB tujuan</button>', '<span class="muted">Auth Admin dikelola backend/per project; tidak ikut Sync.</span>')
html = html.replace('<button type="button" id="dbSyncAbort" onclick="abortDbSync()">Hentikan sync (tetap blokir pindah DB)</button>', '')
html = html.replace('Sinkronisasi DB1 → DB2', 'Sinkronkan DB aktif → DB standby')
html = html.replace('DB1 → DB2 (upsert tanpa menghapus)', 'DB aktif → DB standby (upsert tanpa menghapus)')
# Remove auth/gateway/backup status from the cutover-blocker list; keep locks, freshness, schema and scoped data.
patterns = [
 r"if\(!a\.authParityReady\|\|!b\.authParityReady\)problems\.push\('[^']*'\);",
 r"if\(!a\.routingGatewayReady\|\|!b\.routingGatewayReady\)problems\.push\('[^']*'\);",
 r"if\(!a\.backupReady\|\|!b\.backupReady\)problems\.push\('[^']*'\);",
 r"if\(!a\.backupReady\|\|!b\.backupReady\|\|!a\.authParityReady\|\|!b\.authParityReady\|\|!a\.routingGatewayReady\|\|!b\.routingGatewayReady\)problems\.push\('[^']*'\);"
]
for pat in patterns:
    html = re.sub(pat, "", html)
# Clarify backend-managed config in the displayed route line instead of calling unset flags a cutover blocker.
html = html.replace("' • auth '+(route.authParityReady?'OK':'NO')+' • parity '+(route.dataParityReady?'OK':'NO')+' • gateway '+(route.routingGatewayReady?'OK':'NO')",
                    "' • data '+(route.dataParityReady?'OK':'PERLU SYNC')+' • auth/gateway: backend'")
# Keep data freshness as an explicit requirement; never force readiness flags in UI.
marker = "if(!a.dataParityReady||!b.dataParityReady)problems.push('Parity isi data belum dinyatakan lolos pada kedua project.');"
if marker in html and "CORE_PARITY_STALE" not in html:
    html = html.replace(marker, marker + "\n const freshRoute=r=>{const t=Date.parse(r.last_parity_check_at||'');return Number.isFinite(t)&&Date.now()-t<=30*60*1000&&t<=Date.now()+60000;};\n if(!freshRoute(a)||!freshRoute(b))problems.push('Parity data sync inti belum diperbarui dalam 30 menit. Jalankan Sync sebelum pindah DB.');", 1)

# Runtime route acceptance must follow a coordinated finalization, not unrelated Auth/gateway flags.
route_backup_pattern = r"function routeBackupReady\(r\)\{.*?^\}"
route_backup_replacement = r"""function routeBackupReady(r){
 const parityAt=Date.parse(r?.last_parity_check_at||''),fresh=Number.isFinite(parityAt)&&Date.now()-parityAt<=30*60*1000&&parityAt<=Date.now()+60000;
 const schema=!!r?.schema_version&&r.schema_version===r.primary_schema_version&&r.schema_version===r.backup_schema_version;
 const epoch=Number(r?.epoch),switchId=String(r?.switch_id||''),note='Coordinated global route finalized: backup epoch '+epoch+' switch '+switchId;
 const finalized=epoch>=2&&!!switchId&&String(r?.cutover_test_note||'')===note&&!!r?.last_cutover_test_at;
 return !!r&&r.active_target==='backup'&&finalized&&r.data_parity_ready===true&&r.sync_in_progress!==true&&fresh&&schema;
}"""
html, route_backup_count = re.subn(route_backup_pattern, route_backup_replacement, html, count=1, flags=re.S | re.M)
if route_backup_count != 1:
    raise SystemExit("Admin runtime route still has a strict legacy backup/auth/gateway gate.")
if "r.auth_parity_ready===true&&r.data_parity_ready===true&&r.routing_gateway_ready===true&&r.can_switch_to_backup===true" in html:
    raise SystemExit("Strict legacy backup/auth/gateway gate remains after route patch.")

# Simplify explanation but retain owner authorization and explicit cutover confirmation.
html = html.replace('DB Sync memerlukan verifikasi login owner/admin di kedua project dan gateway bersama.',
                    'DB Sync hanya membawa rental dan user reseller. Auth Admin, secrets, fungsi/API, dan pairing tidak ikut dipindahkan.')
html = html.replace('gateway bersama BELUM terverifikasi; cutover tetap diblokir.',
                    'route-control langsung dipakai; gateway eksternal tidak diperlukan untuk sync inti.')
html = html.replace('Login owner/admin aktif belum diverifikasi pada kedua project.',
                    'Auth Admin dikelola terpisah di backend dan tidak ikut Sync.')
# Keep build/version contract isolated to the new branch.
if "versionCode 44" not in gradle or "versionName '12.1.16'" not in gradle:
    raise SystemExit("Expected locked Admin V12.1.16 build inputs; refusing to patch a mismatched source.")
gradle = gradle.replace("versionCode 44", "versionCode 47", 1).replace("versionName '12.1.16'", "versionName '12.1.19'", 1)
if "async function coreDbCall(action,payload={})" not in html:
    raise SystemExit("Core backend caller was not inserted.")
if "CORE_SYNC_ALREADY_IN_PROGRESS" not in html or "ROUTE_FINAL_CONFIRMATION_FAILED" not in html:
    raise SystemExit("Expected sync/route guards are missing.")
if "action:'switch'" in html and "routeCoordinatorCall(p.url,p.key,token" in html:
    raise SystemExit("Legacy db-route-coordinator cutover path remains active.")
# No claims of copying secrets/Auth or full historical parity.
if "coreDbCall('sync-core')" not in html or "coreDbCall('switch-global'" not in html:
    raise SystemExit("Admin is not wired to the scoped core DB backend.")
html_path.write_text(html, encoding="utf-8")
gradle_path.write_text(gradle, encoding="utf-8")
Path("VERSION.txt").write_text("AniGames Admin Android V12.1.19 — global route continuity + scoped sync\n", encoding="utf-8")
print("PASS: Admin V12.1.19 accepts only coordinated global route finalization; auth/gateway flags are not runtime route gates.")
