from pathlib import Path
import re

HTML = Path("android/app/src/main/assets/web/admin.html")
GRADLE = Path("android/app/build.gradle")
html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")
marker = "V12.1.22-FULL-12-TABLE-INCREMENTAL-SYNC"

if marker in html:
    if "versionCode 50" not in gradle or "versionName '12.1.22'" not in gradle:
        raise SystemExit("V12.1.22 marker exists but Gradle version differs.")
    print("PASS: Admin V12.1.22 full-table Sync patch already applied.")
    raise SystemExit(0)

if "V12.1.21-ROUTE-CUTOVER-WITHOUT-FORCED-SYNC" not in html:
    raise SystemExit("Expected V12.1.21 source; refusing to patch an unknown baseline.")
if "versionCode 49" not in gradle or "versionName '12.1.21'" not in gradle:
    raise SystemExit("Expected V12.1.21 Gradle markers.")

def replace_function(source, signature, replacement, label):
    pattern = re.compile(r"(?ms)^" + re.escape(signature) + r".*?^\}")
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise SystemExit(f"{label}: expected one function, found {len(matches)}")
    return source[:matches[0].start()] + replacement.rstrip() + source[matches[0].end():]

def replace_region(source, start_marker, end_marker, replacement, label):
    starts = [m.start() for m in re.finditer(re.escape(start_marker), source)]
    if len(starts) != 1:
        raise SystemExit(f"{label}: expected one start marker, found {len(starts)}")
    start = starts[0]
    end = source.find(end_marker, start + len(start_marker))
    if end < 0:
        raise SystemExit(f"{label}: end marker missing")
    return source[:start] + replacement.rstrip() + source[end:]

# The verification button was disabled unconditionally in the previous patch.
# Enable it for an Owner even before parity/Gateway pass; login testing is part of readiness work.
direction_pattern = re.compile(r"(?m)^function updateDbSyncDirection\(\)\{[^\n]*\}")
direction_replacement = r"""function updateDbSyncDirection(){
 const source=DB_TARGET==='backup'?'DB2':'DB1',target=DB_TARGET==='backup'?'DB1':'DB2';
 const sourceLabel=$('dbSyncSourceLabel'),targetLabel=$('dbSyncTargetLabel'),button=$('dbSyncExecute');
 const verify=$('dbSyncVerifyOwner'),passwordLabel=$('dbSyncOwnerPasswordLabel'),state=$('dbSyncRouteState');
 const route=dualDbRouteState?.route,syncing=route?.sync_in_progress===true;
 if(sourceLabel)sourceLabel.textContent=source+' • Sumber aktif';
 if(targetLabel)targetLabel.textContent=target+' • Standby tujuan • sync incremental 12 tabel';
 if(button){button.textContent='Sinkronkan '+source+' → '+target;button.disabled=syncing||ctx?.role!=='owner'}
 if(verify){verify.disabled=syncing||ctx?.role!=='owner';verify.textContent='Verifikasi login '+target}
 if(passwordLabel)passwordLabel.textContent='Uji password akun Owner di '+target+'. Tidak disimpan dan tidak ikut disalin.';
 if(state)state.textContent='Route aktif: '+source+' • standby: '+target+' • epoch '+DB_ROUTE_EPOCH+(syncing?' • SYNC BERJALAN':'');
}"""
html, count = direction_pattern.subn(direction_replacement, html, count=1)
if count != 1:
    raise SystemExit("Could not update Sync/login button enablement.")

new_preview = r"""async function previewDbSync(){
 if(typeof ctx==='undefined'||ctx?.role!=='owner')return msg('Hanya Owner yang dapat melihat preview DB Sync.',true);
 const button=document.querySelector('#databaseTools button[onclick="previewDbSync()"]');
 if(button){button.disabled=true;button.textContent='Membandingkan 12 tabel…'}
 try{
  const [d1,d2]=await Promise.all([
   globalRouteStatus(DB1_URL,DB1_ROUTE_KEY,'wzkjpycjizexxcxrfdvr'),
   globalRouteStatus(DB2_URL,DB2_ROUTE_KEY,'xcdbipgsvohesxhxydep')
  ]);
  const a=d1.route,b=d2.route;
  if(a.active_target!==b.active_target||Number(a.epoch)!==Number(b.epoch)||String(a.switch_id||'')!==String(b.switch_id||''))throw new Error('GLOBAL_ROUTE_MISMATCH');
  if(a.sync_in_progress===true||b.sync_in_progress===true)throw new Error('CORE_SYNC_ALREADY_IN_PROGRESS');
  if(DB_TARGET!==a.active_target)throw new Error('ADMIN_TARGET_STALE_REFRESH_REQUIRED');
  const result=await dbSyncCall('preview');
  const required=['organizations','themes','org_members','admin_accounts','devices','device_tokens','device_enrollments','admin_pc_access','rental_accounts','rental_sessions','billing_transactions','billing_control_accounts'];
  const names=(result.tables||[]).map(t=>t.table);
  const missing=required.filter(t=>!names.includes(t));
  if(missing.length)throw new Error('SYNC_PREVIEW_TABLES_MISSING:'+missing.join(','));
  const lines=(result.tables||[]).map(t=>{
   const diff=Number(t.sourceCount||0)-Number(t.targetCount||0);
   return t.table+': sumber '+Number(t.sourceCount||0)+' • target '+Number(t.targetCount||0)+' • selisih '+(diff>0?'+':'')+diff;
  });
  const summary=$('dbSyncPreviewSummary');
  if(summary)summary.textContent='Preview '+(DB_TARGET==='backup'?'DB2 → DB1':'DB1 → DB2')+'. 12 tabel allowlist, upsert incremental, tanpa DELETE. Auth user/password, secret, Edge Function config, heartbeat/diagnostik/log/command queue tidak disalin. '+lines.join(' | ');
  dbSyncStatus('Preview selesai • '+required.length+' tabel terdaftar. Tidak ada data yang diubah.');
  return {...result,ok:true,requiredTables:required};
 }catch(e){
  const detail=String(e?.message||e);dbSyncStatus('Preview gagal: '+detail,true);msg('Preview Sync gagal: '+detail,true);
  return {ok:false,error:detail};
 }finally{if(button){button.disabled=false;button.textContent='Preview perbedaan'}}
}"""
html = replace_region(html, "async function previewDbSync(){", "\n\nasync function requestDbSync(options={}){", new_preview, "Full 12-table read-only preview")

new_sync = r"""// V12.1.22-FULL-12-TABLE-INCREMENTAL-SYNC
async function requestDbSync(options={}){
 if(typeof ctx==='undefined'||ctx?.role!=='owner')return msg('Hanya Owner yang dapat menjalankan DB Sync.',true);
 const button=$('dbSyncExecute');if(button){button.disabled=true;button.textContent='Menyiapkan Sync…'}
 let runId='';
 try{
  const [d1,d2]=await Promise.all([
   globalRouteStatus(DB1_URL,DB1_ROUTE_KEY,'wzkjpycjizexxcxrfdvr'),
   globalRouteStatus(DB2_URL,DB2_ROUTE_KEY,'xcdbipgsvohesxhxydep')
  ]);
  const a=d1.route,b=d2.route;
  const same=(x,y)=>x.active_target===y.active_target&&Number(x.epoch)===Number(y.epoch)&&String(x.switch_id||'')===String(y.switch_id||'');
  if(!same(a,b))throw new Error('GLOBAL_ROUTE_MISMATCH: DB1/DB2 route belum sama.');
  if(a.sync_in_progress===true||b.sync_in_progress===true)throw new Error('CORE_SYNC_ALREADY_IN_PROGRESS');
  if(DB_TARGET!==a.active_target)throw new Error('ADMIN_TARGET_STALE_REFRESH_REQUIRED');
  const required=['organizations','themes','org_members','admin_accounts','devices','device_tokens','device_enrollments','admin_pc_access','rental_accounts','rental_sessions','billing_transactions','billing_control_accounts'];
  const sourceName=a.active_target==='backup'?'DB2':'DB1',targetName=a.active_target==='backup'?'DB1':'DB2';
  if(!confirm('Sinkronkan '+sourceName+' → '+targetName+' menggunakan Sync incremental 12 tabel?\\n\\nYang disalin: organisasi/akses, perangkat & pairing, rental, sesi rental, transaksi, dan akun reseller. Auth user/password, Supabase secrets, konfigurasi Edge Function, heartbeat, diagnosa, log, audit, dan antrean command tidak disalin. Tidak ada DELETE; data target yang tidak ada pada sumber tetap tersimpan. Route aktif tidak berubah.'))return {ok:false,cancelled:true};
  dbSyncStatus('Menghubungkan Sync backend '+sourceName+' → '+targetName+'…');
  const started=await dbSyncCall('start');
  runId=String(started.runId||'');
  if(!runId)throw new Error('SYNC_RUN_ID_MISSING');
  localStorage.setItem(DB_SYNC_RUN_KEY,runId);
  const tables=Array.isArray(started.tables)?started.tables:[];
  const names=tables.map(t=>String(t.table||''));
  const missing=required.filter(t=>!names.includes(t));
  if(tables.length!==required.length||missing.length)throw new Error('SYNC_TABLE_MANIFEST_MISMATCH: '+missing.join(','));
  const totalRows=tables.reduce((n,t)=>n+Math.max(0,Number(t.count)||0),0);
  let progressed=0;
  for(const item of tables){
   const table=String(item.table),tableTotal=Math.max(0,Number(item.count)||0);
   let offset=0,iterations=0;
   while(true){
    const page=await dbSyncCall('apply-page',{runId,table,offset,limit:250});
    const processed=Math.max(0,Number(page.processed)||0);
    if(String(page.table)!==table||Number(page.offset)!==offset)throw new Error('SYNC_PAGE_IDENTITY_MISMATCH:'+table);
    if(processed===0&&page.more===true)throw new Error('SYNC_PAGE_STALLED:'+table);
    offset+=processed;progressed+=processed;iterations++;
    const pct=totalRows?Math.min(99,Math.floor(progressed/totalRows*100)):99;
    dbSyncStatus('Sync '+sourceName+' → '+targetName+' • '+table+' • '+Math.min(offset,tableTotal)+'/'+tableTotal+' • total '+progressed+'/'+totalRows+' ('+pct+'%).');
    if(page.more!==true)break;
    if(iterations>1002||offset>tableTotal+500)throw new Error('SYNC_PAGE_LIMIT_OR_COUNT_MISMATCH:'+table);
   }
   if(offset!==tableTotal)throw new Error('SYNC_SOURCE_COUNT_CHANGED_DURING_SYNC:'+table+':'+offset+'/'+tableTotal);
  }
  dbSyncStatus('Semua halaman selesai. Memverifikasi row count + SHA-256 untuk 12 tabel…');
  const proofs=[];
  for(let i=0;i<required.length;i++){
   const table=required[i];
   const proof=await dbSyncCall('verify-table',{runId,table});
   if(proof.matched!==true)throw new Error('CORE_TABLE_HASH_MISMATCH:'+table);
   proofs.push(proof);
   dbSyncStatus('Verifikasi hash '+(i+1)+'/'+required.length+' • '+table+' • source '+Number(proof.sourceCount||0)+' / target '+Number(proof.targetCount||0)+' • cocok.');
  }
  const finalized=await dbSyncCall('mark-ready',{runId});
  if(finalized.dataVerified!==true||finalized.syncCompleted!==true||Number(finalized.verifiedTables)!==required.length)throw new Error('FULL_CORE_SYNC_FINALIZATION_NOT_CONFIRMED');
  localStorage.removeItem(DB_SYNC_RUN_KEY);
  const summary=$('dbSyncPreviewSummary');
  const rentalProof=proofs.find(p=>p.table==='rental_accounts'),sessionProof=proofs.find(p=>p.table==='rental_sessions');
  if(summary)summary.textContent='Sync hash lengkap PASS • '+required.length+' tabel • rental '+Number(rentalProof?.targetCount||0)+' baris • sesi '+Number(sessionProof?.targetCount||0)+' baris. Auth user/password dan secrets tidak disalin; pairing tetap memakai ID/token yang ada. Tidak ada DELETE.';
  dbSyncStatus('Data 12 tabel cocok dan terverifikasi. Route masih '+sourceName+'; Gateway readiness dan final hash saat write-quiesce tetap wajib sebelum cutover.');
  let gatewayNote='';
  try{
   const gateway=await refreshGatewayReadiness();
   if(gateway?.gatewayReady===true&&gateway?.routeReady===true)gatewayNote=' Gateway route berhasil diverifikasi; preflight global diperbarui.';
   else gatewayNote=' Gateway belum mengonfirmasi kesiapan; cutover tetap diblokir.';
  }catch(e){gatewayNote=' Gateway belum siap: '+String(e?.message||e)+'; cutover tetap diblokir.';}
  await checkBothDbApis();
  msg('Sync incremental '+required.length+' tabel + hash SHA-256 selesai. '+sourceName+' tetap aktif. '+gatewayNote, !gatewayNote.includes('preflight global diperbarui'));
  return {...finalized,ok:true,proofs,gatewayReady:gatewayNote.includes('preflight global diperbarui')};
 }catch(e){
  const detail=String(e?.message||e);
  if(runId)localStorage.setItem(DB_SYNC_RUN_KEY,runId);
  dbSyncStatus('Sync tidak selesai / diverifikasi: '+detail+'. DB aktif tetap dipertahankan. Bila run terkunci, gunakan Hentikan Sync lalu ulangi setelah penyebab diperbaiki.',true);
  msg('Sync gagal atau belum lengkap: '+detail+'. Tidak ada cutover yang dijalankan.',true);
  return {ok:false,error:detail,runId:runId||null};
 }finally{if(button){button.disabled=false;button.textContent='Sinkronkan DB aktif → DB standby'}}
}"""
html = replace_region(html, "async function requestDbSync(options={}){", "\n\nasync function requestSharedDbRouteSwitch(target,reason){", new_sync, "Full 12-table incremental Sync")

new_login = r"""async function verifyDb2OwnerLogin(){
 if(typeof ctx==='undefined'||ctx?.role!=='owner')return msg('Hanya Owner yang dapat memverifikasi login database tujuan.',true);
 const input=$('dbSyncOwnerPassword'),password=String(input?.value||'');
 if(!password)return msg('Masukkan password akun Owner yang berlaku di database tujuan. Password tidak disimpan.',true);
 const button=$('dbSyncVerifyOwner');if(button)button.disabled=true;
 try{
  const result=await dbSyncCall('verify-owner-login',{password});
  if(input)input.value='';
  if(result?.ok!==true||result?.verifiedUserCount===undefined)throw new Error('TARGET_OWNER_LOGIN_NOT_CONFIRMED');
  const ref=DB_TARGET==='backup'?'wzkjpycjizexxcxrfdvr':'xcdbipgsvohesxhxydep';
  window.__dbTargetLoginVerifiedAt=Date.now();
  window.__dbTargetLoginProjectRef=ref;
  const targetName=DB_TARGET==='backup'?'DB1':'DB2';
  dbSyncStatus('Login Owner '+targetName+' terverifikasi untuk akun ini. Auth user/password tidak disalin; pemeriksaan data, Gateway dan route tetap berdiri sendiri.');
  msg('Login Owner '+targetName+' berhasil diuji pada database tujuan. Tidak ada user Auth atau secret yang disalin.',false);
  return {...result,ok:true,targetProjectRef:ref};
 }catch(e){
  if(input)input.value='';
  const detail=String(e?.message||e);
  window.__dbTargetLoginVerifiedAt=0;window.__dbTargetLoginProjectRef='';
  dbSyncStatus('Verifikasi login database tujuan gagal: '+detail,true);
  msg('Verifikasi login gagal: '+detail,true);
  return {ok:false,error:detail};
 }finally{if(button)button.disabled=false}
}"""
html = replace_region(html, "async function verifyDb2OwnerLogin(){", "\nasync function abortDbSync(){", new_login, "Functional target Owner login test")

# Keep cutover fail-closed at the UI as well as at the backend. Auth parity is optional,
# but an actual Owner login on the intended target, fresh 12-table proof, Gateway and schema are required.
route_ready_pattern = re.compile(r"(?ms)^function routeReadyForSwitch\(r\)\{.*?^\}")
route_ready_replacement = r"""function routeReadyForSwitch(r){
 const t=Date.parse(String(r?.last_parity_check_at||'')),now=Date.now();
 const fresh=Number.isFinite(t)&&t<=now+60000&&now-t<=30*60*1000;
 const schema=!!r?.schema_version&&r.schema_version===r.primary_schema_version&&r.schema_version===r.backup_schema_version;
 const note=String(r?.last_parity_check_note||'');
 const hashProof=note.includes('CORE_PARITY_HASH_PASS')&&note.includes('ACTIVE_SESSION_HASH_PASS');
 return !!r&&r.primary_ready===true&&r.backup_ready===true&&r.data_parity_ready===true&&
  r.routing_gateway_ready===true&&r.sync_ready===true&&r.sync_in_progress!==true&&schema&&fresh&&hashProof;
}"""
html, count = route_ready_pattern.subn(route_ready_replacement, html, count=1)
if count != 1:
    raise SystemExit("Could not strengthen runtime cutover readiness.")

blockers_pattern = re.compile(r"(?ms)^function dbRouteBlockers\(routes\)\{.*?^\}")
blockers_replacement = r"""function dbRouteBlockers(routes){
 const problems=[];
 if(routes.length!==2||routes.some(x=>!x.route))return ['Status route dari kedua project wajib berhasil dibaca.'];
 const [a,b]=routes.map(x=>x.route);
 if(a.projectRef!=='wzkjpycjizexxcxrfdvr'||b.projectRef!=='xcdbipgsvohesxhxydep')problems.push('Project ref DB1/DB2 tidak sesuai.');
 if(a.activeTarget!==b.activeTarget||a.epoch!==b.epoch||a.switchId!==b.switchId)problems.push('Target route, epoch, atau switch ID DB1 dan DB2 tidak konsisten.');
 if(!a.primaryReady||!b.primaryReady)problems.push('Primary belum dinyatakan siap oleh kedua project.');
 if(a.syncInProgress||b.syncInProgress)problems.push('DB Sync sedang berjalan pada salah satu database.');
 if(!a.dataParityReady||!b.dataParityReady)problems.push('Hash data inti 12 tabel belum terverifikasi pada kedua project.');
 const now=Date.now(),maxAge=30*60*1000;
 for(const [label,r] of [['DB1',a],['DB2',b]]){
  const ts=Date.parse(r.parityAt||'');
  if(!Number.isFinite(ts)||now-ts>maxAge||ts>now+60000)problems.push(label+': bukti parity belum ada atau lebih dari 30 menit.');
  const note=String(r.parityNote||'');
  if(!note.includes('CORE_PARITY_HASH_PASS')||!note.includes('ACTIVE_SESSION_HASH_PASS'))problems.push(label+': bukti hash 12 tabel/sesi aktif belum lengkap.');
  if(!r.backupReady)problems.push(label+': backup readiness belum dinyatakan siap.');
  if(!r.routingGatewayReady||!r.syncReady)problems.push(label+': shared Gateway/route readiness belum lulus.');
 }
 if(!a.schemaVersion||!b.schemaVersion||a.schemaVersion!==b.schemaVersion)problems.push('Versi schema lintas DB kosong atau berbeda.');
 if(!a.primarySchemaVersion||!a.backupSchemaVersion||a.primarySchemaVersion!==a.backupSchemaVersion||
    !b.primarySchemaVersion||!b.backupSchemaVersion||b.primarySchemaVersion!==b.backupSchemaVersion)
  problems.push('Hasil pemeriksaan versi schema primary/backup belum sama dan lengkap.');
 return [...new Set(problems)];
}"""
html, count = blockers_pattern.subn(blockers_replacement, html, count=1)
if count != 1:
    raise SystemExit("Could not update exact preflight blockers.")

# A successful login test must be for the selected destination and still recent.
switch_anchor = "const targetName=target==='backup'?'DB2':'DB1';"
if html.count(switch_anchor) != 1:
    raise SystemExit("Expected one global-switch target label.")
login_guard = """const targetName=target==='backup'?'DB2':'DB1';
  const desiredRef=target==='backup'?'xcdbipgsvohesxhxydep':'wzkjpycjizexxcxrfdvr';
  if(window.__dbTargetLoginProjectRef!==desiredRef||!Number.isFinite(Number(window.__dbTargetLoginVerifiedAt))||Date.now()-Number(window.__dbTargetLoginVerifiedAt)>30*60*1000)
   throw new Error('TARGET_OWNER_LOGIN_TEST_REQUIRED: verifikasi login Owner pada '+targetName+' sebelum cutover.');
"""
html = html.replace(switch_anchor, login_guard.rstrip(), 1)

if "dbSyncCall('sync-core')" in html:
    raise SystemExit("Legacy two-table Sync call remains in the Admin HTML.")
for required in ["dbSyncCall('start')","dbSyncCall('apply-page'","dbSyncCall('verify-table'","dbSyncCall('mark-ready'","CORE_PARITY_HASH_PASS","TARGET_OWNER_LOGIN_TEST_REQUIRED",marker]:
    if required not in html:
        raise SystemExit("V12.1.22 required implementation marker missing: "+required)

old_code = "versionCode 49"
old_name = "versionName '12.1.21'"
if old_code not in gradle or old_name not in gradle:
    raise SystemExit("Expected V12.1.21 Gradle values.")
gradle = gradle.replace(old_code, "versionCode 50", 1).replace(old_name, "versionName '12.1.22'", 1)
HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
Path("VERSION.txt").write_text("AniGames Admin Android V12.1.22 — full incremental 12-table Sync, hash preflight, target Owner login, guarded Gateway cutover\n", encoding="utf-8")
print("PASS: Admin V12.1.22 uses the backend 12-table incremental upsert + row/hash verification flow; Owner login control is functional; Gateway/schema/hash/owner gates remain.")
