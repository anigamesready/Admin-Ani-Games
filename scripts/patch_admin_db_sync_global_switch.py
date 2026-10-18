from pathlib import Path
import re

ROOT = Path(".")
html_path = ROOT / "android/app/src/main/assets/web/admin.html"
gradle_path = ROOT / "android/app/build.gradle"
version_path = ROOT / "VERSION.txt"
html = html_path.read_text(encoding="utf-8")
gradle = gradle_path.read_text(encoding="utf-8")

def replace_once(source, old, new, label):
    count = source.count(old)
    if count == 0:
        if new in source:
            return source  # Idempotent rerun: the intended replacement is already present.
        raise SystemExit(f"{label}: neither the original nor the replacement anchor exists; refusing to patch")
    # Some legacy Admin pages contain the same badge/text in a visible panel and a compact panel.
    # Replace one deterministic occurrence per patch call rather than aborting or changing unrelated UI.
    return source.replace(old, new, 1)

# Make the route readiness result explicitly include authentication parity.
old_route_ready = "r.backup_ready===true&&r.data_parity_ready===true&&r.routing_gateway_ready===true&&r.can_switch_to_backup===true"
new_route_ready = "r.backup_ready===true&&r.auth_parity_ready===true&&r.data_parity_ready===true&&r.routing_gateway_ready===true&&r.can_switch_to_backup===true"
if old_route_ready in html:
    html = replace_once(html, old_route_ready, new_route_ready, "Admin backup readiness auth guard")
elif new_route_ready not in html:
    raise SystemExit("Admin backup readiness condition missing; refusing to weaken the cutover guard")
route_status_with_sync = "backupReady:source.backup_ready===true,syncInProgress:source.sync_in_progress===true,authParityReady:source.auth_parity_ready===true,authVerifiedUserIds:Array.isArray(source.auth_verified_user_ids)?source.auth_verified_user_ids:[],dataParityReady:source.data_parity_ready===true,routingGatewayReady:source.routing_gateway_ready===true"
route_status_without_sync = "backupReady:source.backup_ready===true,authParityReady:source.auth_parity_ready===true,authVerifiedUserIds:Array.isArray(source.auth_verified_user_ids)?source.auth_verified_user_ids:[],dataParityReady:source.data_parity_ready===true,routingGatewayReady:source.routing_gateway_ready===true"
if route_status_with_sync not in html:
    if route_status_without_sync not in html:
        raise SystemExit("Route status mapping anchor missing; refusing to remove sync lock checks")
    html = replace_once(html, route_status_without_sync, route_status_with_sync, "Route status sync lock field")
html = replace_once(
    html,
    "' • parity '+(route.dataParityReady?'OK':'NO')+' • gateway '",
    "' • auth '+(route.authParityReady?'OK':'NO')+' • parity '+(route.dataParityReady?'OK':'NO')+' • gateway '",
    "Route status auth label"
)
html = replace_once(
    html,
    "if(!a.dataParityReady||!b.dataParityReady)problems.push('Parity isi data belum dinyatakan lolos pada kedua project.');",
    "if(a.syncInProgress||b.syncInProgress)problems.push('DB Sync sedang berjalan pada salah satu database. Perpindahan global ditahan.');\n if(!a.authParityReady||!b.authParityReady)problems.push('Login owner/admin aktif belum diverifikasi pada kedua project.');\n if(!a.dataParityReady||!b.dataParityReady)problems.push('Parity isi data belum dinyatakan lolos pada kedua project.');",
    "Preflight auth blocker"
)

# Keep the DB sync panel direction in sync with the globally active database.
# Prominent system-wide active database badge and global switch selector.
old_badge_heading = '<b>DB yang sedang diakses Admin:</b><span id="dbActiveBadge" class="pill">DB1 • Utama</span>'
new_badge_heading = '<b>Database aktif seluruh sistem:</b><span id="dbActiveBadge" class="pill">DB1 • Utama</span>'
if old_badge_heading in html:
    # The source HTML has this heading in both DB tools and the route-status panel; update one occurrence per patch run.
    html = html.replace(old_badge_heading, new_badge_heading, 1)
elif new_badge_heading not in html:
    raise SystemExit("Active database badge heading anchor missing")
html = replace_once(
    html,
    '<span id="dbRouteStatusHint" class="muted">Memeriksa route-control DB1/DB2…</span></div><div class="muted" style="margin-top:5px">',
    '<span id="dbRouteStatusHint" class="muted">Memeriksa route-control DB1/DB2…</span><select id="globalDbTarget" aria-label="Target database sistem" style="max-width:150px"><option value="backup">Pindah ke DB2</option><option value="primary">Pindah ke DB1</option></select><button id="globalDbSwitchButton" type="button" onclick="requestGlobalDbSwitch()">Pindah seluruh sistem</button></div><div class="muted" style="margin-top:5px">',
    "Global switch selector"
)
html = html.replace('title="Status global belum terkoordinasi dengan PC Billing dan Reseller"', 'title="Target global yang dibaca oleh versi Admin dan PC Billing yang mendukung route-control"', 1)
html = replace_once(
    html,
    '<button type="button" onclick="openDbSelector()">Ganti DB Aktif</button>',
    '<button type="button" onclick="requestGlobalDbSwitch()">Pindah DB Seluruh Sistem</button>',
    "Database tools global switch button"
)
html = replace_once(
    html,
    '<div class="muted">Pilih DB aktif tanpa memasukkan key publik. Pergantian DB tidak otomatis menyalin data.</div>',
    '<div class="muted">Badge menampilkan route global. Sinkronisasi DB1 → DB2 dan verifikasi login harus lulus sebelum perpindahan global tersedia.</div>',
    "Database tools description"
)
html = replace_once(
    html,
    '<div class="muted">Catatan: tombol pergantian DB pada aplikasi ini hanya mengganti target login Admin lokal. Status preflight tidak otomatis memindahkan PC Billing atau reseller.</div>',
    '<div class="muted">Perpindahan memakai epoch dan switch ID yang sama di kedua proyek. PC Billing dan reseller versi yang mendukung route-control akan mengikuti target setelah refresh.</div>',
    "Global route explanation"
)

# DB Sync interface is intentionally one-way, non-destructive and auditable.
sync_start = html.find('  <div class="sync-options" style="margin-top:12px">')
sync_end = html.find('\n </div>\n</section>', sync_start)
if sync_start < 0 or sync_end < 0:
    raise SystemExit("DB Sync UI anchors not found; refusing to patch")
sync_ui = r'''  <div class="sync-options" style="margin-top:12px">
   <div class="field"><label>Sumber</label><div class="pill" id="dbSyncSourceLabel">DB1 • Utama (sumber kanonis)</div></div>
   <div class="field"><label>Tujuan</label><div class="pill" id="dbSyncTargetLabel">DB2 • Cadangan (upsert tanpa menghapus)</div></div>
   <div class="field"><label>Mode</label><div class="pill">Update berdasarkan ID + audit hash</div></div>
   <div class="field"><label>Status route</label><div id="dbSyncRouteState" class="muted">DB1 tetap aktif selama sinkronisasi dan validasi.</div></div>
  </div>
  <div id="dbSyncPreviewSummary" class="msg" role="status" aria-live="polite">Tekan “Preview perbedaan” untuk membandingkan jumlah baris sebelum menulis data.</div>
  <div class="field" style="margin-top:10px"><label for="dbSyncOwnerPassword" id="dbSyncOwnerPasswordLabel">Password DB2 untuk akun yang sedang login</label><input id="dbSyncOwnerPassword" type="password" autocomplete="current-password" placeholder="Password akun yang sedang diuji pada DB tujuan; tidak disimpan"></div>
  <div class="muted" style="margin-top:6px">Password hanya dipakai untuk mencoba login nyata pada DB tujuan. Proses ini tidak menyalin atau mengubah password dan tidak menyimpan token database tujuan.</div>
  <div id="dbSyncSafetyNotice" class="msg">DB Sync melakukan upsert dari database aktif ke database standby. Tidak menghapus baris tujuan; sesi aktif pada sumber tetap berjalan; route baru dapat berubah setelah hash tabel dan login owner/admin lulus.</div>
  <div id="dbSyncProgress" class="msg" role="status" aria-live="polite">Belum ada sinkronisasi dalam sesi ini.</div>
  <div class="row" style="flex-wrap:wrap"><button type="button" onclick="previewDbSync()">Preview perbedaan</button><button type="button" id="dbSyncExecute" class="primary" onclick="requestDbSync()">Sinkronkan DB1 → DB2</button><button type="button" id="dbSyncVerifyOwner" onclick="verifyDb2OwnerLogin()">Verifikasi login DB tujuan</button><button type="button" onclick="checkBothDbApis()">Refresh status global</button><button type="button" id="dbSyncAbort" onclick="abortDbSync()">Hentikan sync (tetap blokir pindah DB)</button></div>'''
html = html[:sync_start] + sync_ui + html[sync_end:]

# Compatibility: the old menu entry must use the new global route button, not a removed local selector.
html, count = re.subn(r"function openDbSelector\(\)\{[^\n]*\}", "function openDbSelector(){requestGlobalDbSwitch()}", html, count=1)
if count != 1:
    raise SystemExit("openDbSelector compatibility patch failed")

old_placeholder = "async function requestDbSync(){showDbSyncSafetyDetails();return {ok:false,code:'BACKEND_NOT_READY'};}\nfunction showDbSyncSafetyDetails(){alert('Sinkronisasi data lintas Supabase belum boleh dijalankan dari UI saja. Dibutuhkan backend aman yang memiliki akses ke dua project dan melakukan preflight: kesamaan schema, mapping ID organisasi/perangkat, sesi rental aktif, command nonterminal, heartbeat, akun/Auth, Edge Functions, secrets, dan scheduler. DB2 sebelumnya belum memiliki data heartbeat/command seperti DB1; menimpa sembarang dapat memutus pairing atau menggandakan perintah. Tombol eksekusi dikunci sampai backend ini tersedia. Tidak ada data yang berubah dari panel ini.')}"
new_functions = r'''const DB_SYNC_RUN_KEY='ani_games_db_sync_active_run_v1';
async function adminAccessToken(){
 let token=String(session?.access_token||'');
 try{const result=await sb.auth.getSession();token=String(result?.data?.session?.access_token||token)}catch(_){}
 if(!token)throw new Error('Sesi Admin DB1 kedaluwarsa. Login kembali sebelum menjalankan DB Sync.');
 return token;
}
async function dbSyncCall(action,payload={}){
 const token=await adminAccessToken();
 const destination=DB_TARGET==='backup'?{url:DB1_URL,key:DB1_KEY,ref:'wzkjpycjizexxcxrfdvr'}:{url:DB2_URL,key:DB2_KEY,ref:'xcdbipgsvohesxhxydep'};
 const response=await fetch(destination.url+'/functions/v1/db-sync-apply',{method:'POST',headers:{apikey:destination.key,'content-type':'application/json',authorization:'Bearer '+token},body:JSON.stringify({action,...payload}),cache:'no-store'});
 const data=await response.json().catch(()=>({}));
 if(!response.ok||data?.ok!==true)throw new Error(String(data?.error||('DB_SYNC_HTTP_'+response.status)));
 return data;
}
function dbSyncStatus(text,error=false){
 const el=$('dbSyncProgress');if(el){el.textContent=text;el.style.borderLeftColor=error?'var(--bad)':'var(--ok)';el.setAttribute('aria-live','polite')}
}
function showDbSyncSafetyDetails(){
 alert('Sinkronisasi berjalan dari DB yang sedang aktif ke DB standby. Baris dengan ID sama diperbarui; baris target yang tidak ada pada sumber tidak otomatis dihapus. Sesudah upsert, sistem memeriksa hash. Target tetap tidak dapat menjadi aktif bila tabel penting berbeda atau login owner/admin belum terverifikasi.');
}
async function previewDbSync(){
 const button=document.querySelector('#databaseTools button[onclick="previewDbSync()"]');
 if(!dualDbRouteReady)return msg('Route global belum terverifikasi. Refresh status sebelum preview.',true);
 if(typeof ctx==='undefined'||ctx?.role!=='owner')return msg('Hanya owner yang dapat menjalankan DB Sync.',true);
 if(button)button.disabled=true;
 try{
  const data=await dbSyncCall('preview'),rows=data.tables||[],different=rows.filter(x=>Number(x.sourceCount)!==Number(x.targetCount));
  const sourceTotal=rows.reduce((n,x)=>n+Number(x.sourceCount||0),0),targetTotal=rows.reduce((n,x)=>n+Number(x.targetCount||0),0);
  const summary=$('dbSyncPreviewSummary');
  const sourceName=DB_TARGET==='backup'?'DB2':'DB1',targetName=DB_TARGET==='backup'?'DB1':'DB2';
  if(summary)summary.textContent='Preview '+sourceName+' → '+targetName+': '+rows.length+' tabel • sumber '+sourceTotal.toLocaleString('id-ID')+' baris • tujuan '+targetTotal.toLocaleString('id-ID')+' baris • '+different.length+' tabel berbeda jumlah. Hash akan diperiksa setelah upsert.';
  dbSyncStatus('Preview hanya membaca data. '+(DB_TARGET==='backup'?'DB2':'DB1')+' tetap aktif; belum ada perubahan data.');
  return data;
 }catch(e){const text=String(e?.message||e);dbSyncStatus('Preview gagal: '+text,true);msg('Preview DB Sync gagal: '+text,true);return null}
 finally{if(button)button.disabled=false}
}
async function requestDbSync(){
 if(!dualDbRouteReady)return msg('Route global belum terverifikasi. Refresh status sebelum sinkronisasi.',true);
 if(typeof ctx==='undefined'||ctx?.role!=='owner')return msg('Hanya owner yang dapat menjalankan DB Sync.',true);
 const button=$('dbSyncExecute');if(button)button.disabled=true;let activeRunId='';
 try{
  const start=await dbSyncCall('start'),runId=String(start.runId||'');
  if(!runId)throw new Error('SYNC_RUN_ID_MISSING');
  activeRunId=runId;localStorage.setItem(DB_SYNC_RUN_KEY,runId);
  const tables=start.tables||[];let totalRows=0,mismatches=[],advisoryMismatches=[];
  const sourceName=DB_TARGET==='backup'?'DB2':'DB1',targetName=DB_TARGET==='backup'?'DB1':'DB2';
  dbSyncStatus('Sinkronisasi '+sourceName+' → '+targetName+' dimulai. '+sourceName+' tetap aktif. Memproses '+tables.length+' tabel…');
  for(let i=0;i<tables.length;i++){
   const table=String(tables[i].table||''),count=Math.max(0,Number(tables[i].count)||0);let offset=0;
   while(offset<count){
    const page=await dbSyncCall('apply-page',{runId,table,offset,limit:250});
    const processed=Math.max(0,Number(page.processed)||0);
    if(processed===0&&offset<count)throw new Error('SYNC_PAGE_EMPTY:'+table+':'+offset);
    offset+=processed;totalRows+=processed;
    dbSyncStatus('Sinkronisasi '+(i+1)+'/'+tables.length+' • '+table+' '+Math.min(offset,count).toLocaleString('id-ID')+'/'+count.toLocaleString('id-ID')+' baris • total '+totalRows.toLocaleString('id-ID'));
   }
   const verification=await dbSyncCall('verify-table',{runId,table});
   if(verification.required!==false&&!verification.matched)mismatches.push(table);else if(!verification.matched)advisoryMismatches.push(table);
   dbSyncStatus('Verifikasi '+(i+1)+'/'+tables.length+' • '+table+' • '+(verification.matched?'HASH COCOK':'HASH BERBEDA'));
  }
  // Catch up critical rows after the first pass to reduce races with live writes on the active database.
  if(mismatches.length){
   const retryTables=[...mismatches];mismatches=[];
   for(const table of retryTables){
    const def=tables.find(x=>String(x.table)===table),count=Math.max(0,Number(def?.count)||0);let offset=0;
    while(offset<count){const page=await dbSyncCall('apply-page',{runId,table,offset,limit:250});const processed=Math.max(0,Number(page.processed)||0);if(processed===0&&offset<count)throw new Error('SYNC_CATCHUP_EMPTY:'+table+':'+offset);offset+=processed;totalRows+=processed;}
    const verification=await dbSyncCall('verify-table',{runId,table});
    if(verification.required!==false&&!verification.matched)mismatches.push(table);else if(!verification.matched)advisoryMismatches.push(table);
    dbSyncStatus('Catch-up '+table+' • '+(verification.matched?'HASH COCOK':'MASIH BERBEDA'));
   }
  }
  const summary=$('dbSyncPreviewSummary');
  if(mismatches.length){
   let released=false;
   try{await dbSyncCall('abort',{runId});localStorage.removeItem(DB_SYNC_RUN_KEY);activeRunId='';released=true}catch(_){}
   if(summary)summary.textContent='Penulisan selesai, tetapi hash belum cocok pada: '+mismatches.join(', ')+'. DB tetap aktif; target diblokir sampai perbedaan diperbaiki.';
   dbSyncStatus('Hash belum cocok. '+(released?'Kunci sync dilepas dengan aman; jalankan ulang setelah memeriksa data.':'Kunci sync belum terlepas; gunakan Hentikan sync sebelum mencoba lagi.'),true);
   return {ok:false,mismatches,lockReleased:released};
  }
  if(summary)summary.textContent='Upsert selesai untuk '+tables.length+' tabel. Verifikasi hash data dan login owner/admin '+targetName+' akan menentukan kesiapan database standby.';
  try{
   const ready=await dbSyncCall('mark-ready',{runId});
   localStorage.removeItem(DB_SYNC_RUN_KEY);activeRunId='';
   const advisoryText=advisoryMismatches.length?' Riwayat/telemetri yang berubah saat sinkronisasi (non-blocking): '+advisoryMismatches.join(', ')+'.':'';
   dbSyncStatus('Verifikasi data selesai: '+ready.verifiedTables+' tabel utama lolos hash; '+ready.verifiedOwners+' owner/admin terverifikasi. '+(ready.gatewayReady?'Gateway bersama juga terverifikasi.':'Gateway bersama BELUM terverifikasi; cutover tetap diblokir.')+' '+sourceName+' tetap aktif.'+advisoryText,ready.gatewayReady!==true);
   msg(ready.gatewayReady?sourceName+' → '+targetName+' selesai dan siap sebagai standby; route aktif tetap tidak berubah.':sourceName+' → '+targetName+' data/schema/auth parity lulus, tetapi gateway bersama belum siap sehingga perpindahan DB tetap diblokir.',ready.gatewayReady!==true);
   await checkBothDbApis();return ready;
  }catch(e){
   const detail=String(e?.message||e);
   if(detail.includes('AUTH_VERIFICATION_REQUIRED')){
    dbSyncStatus('Hash data cocok. Setiap akun owner/admin aktif perlu login-test '+targetName+' dari akunnya sendiri. Masukkan password target untuk akun yang sedang login lalu tekan Verifikasi login database tujuan.');
    msg('Data telah disinkronkan; verifikasi login owner/admin belum lengkap.',true);return {ok:false,authVerificationRequired:true};
   }
   throw e;
  }
 }catch(e){
  const text=String(e?.message||e);let lockReleased=false;
  if(activeRunId&&!text.includes('AUTH_VERIFICATION_REQUIRED')){
   try{await dbSyncCall('abort',{runId:activeRunId});localStorage.removeItem(DB_SYNC_RUN_KEY);lockReleased=true}catch(_){}
  }
  dbSyncStatus('DB Sync terhenti: '+text+'. '+(lockReleased?'Kunci sinkronisasi dilepas; route aktif tidak berubah.':'Jika proses masih terkunci, gunakan Hentikan sync; route aktif tidak berubah.'),true);
  msg('DB Sync terhenti: '+text,true);return {ok:false,error:text,lockReleased}
 }
 finally{if(button)button.disabled=false}
}
async function verifyDb2OwnerLogin(){
 if(!dualDbRouteReady)return msg('Route global belum terverifikasi. Refresh status sebelum login-test.',true);
 if(typeof ctx==='undefined'||ctx?.role!=='owner')return msg('Hanya owner yang dapat memverifikasi login DB2.',true);
 const input=$('dbSyncOwnerPassword'),password=String(input?.value||'');
 if(!password)return msg('Masukkan password yang saat ini berlaku untuk akun ini di DB2. Password tidak disimpan.',true);
 const button=$('dbSyncVerifyOwner');if(button)button.disabled=true;
 let readyGatewayAfterAuth=false;
 try{
  const result=await dbSyncCall('verify-owner-login',{password});if(input)input.value='';
  dbSyncStatus('Login '+(DB_TARGET==='backup'?'DB1':'DB2')+' berhasil untuk akun ini • '+result.verifiedUserCount+'/'+result.requiredUserCount+' akun aktif terverifikasi.');
  const runId=localStorage.getItem(DB_SYNC_RUN_KEY)||'';
  if(runId){
   try{
    const ready=await dbSyncCall('mark-ready',{runId});readyGatewayAfterAuth=ready.gatewayReady===true;
    if(ready.dataVerified===true)localStorage.removeItem(DB_SYNC_RUN_KEY);
    dbSyncStatus(ready.gatewayReady?'Database tujuan SIAP sebagai standby. '+ready.verifiedTables+' tabel utama cocok; '+ready.verifiedOwners+' akun owner/admin login-test lulus. Route aktif tidak berubah sampai perpindahan global dipilih.':'Data/schema/auth parity lolos, tetapi gateway bersama belum terverifikasi. Database tujuan TIDAK boleh diaktifkan.',ready.gatewayReady!==true);
    await checkBothDbApis();
   }catch(e){
    const detail=String(e?.message||e);
    if(detail.includes('AUTH_VERIFICATION_REQUIRED'))dbSyncStatus('Akun ini terverifikasi. Akun owner/admin aktif lainnya harus login-test dengan akunnya sendiri sebelum DB2 siap.');
    else if(detail.includes('TABLE_PARITY_NOT_VERIFIED'))dbSyncStatus('Login terverifikasi, tetapi hash semua tabel belum lengkap. Jalankan Sinkronkan DB1 → DB2 lagi.',true);
    else throw e;
   }
  }
  const verifiedGateway=readyGatewayAfterAuth;
  msg(result.authParityReady&&verifiedGateway?'Login terverifikasi untuk semua akun aktif dan gateway bersama siap.':result.authParityReady?'Login semua akun aktif terverifikasi, tetapi gateway bersama belum terverifikasi; pindah DB tetap diblokir.':'Login database tujuan berhasil untuk akun ini; verifikasi akun aktif lainnya masih diperlukan.',!result.authParityReady||!verifiedGateway);
  return result;
 }catch(e){if(input)input.value='';const text=String(e?.message||e);dbSyncStatus('Verifikasi login DB2 gagal: '+text,true);msg('Verifikasi login DB2 gagal: '+text,true);return {ok:false,error:text}}
 finally{if(button)button.disabled=false}
}
async function abortDbSync(){
 if(typeof ctx==='undefined'||ctx?.role!=='owner')return msg('Hanya owner yang dapat menghentikan DB Sync.',true);
 const runId=localStorage.getItem(DB_SYNC_RUN_KEY)||'';
 if(!runId)return msg('Tidak ada run DB Sync aktif yang tercatat pada perangkat ini.',true);
 if(!confirm('Hentikan proses sinkronisasi saat ini? Data yang sudah ter-upsert tidak dihapus. Database aktif tetap berjalan, tetapi kesiapan cutover akan tetap gagal sampai sinkronisasi dan verifikasi hash diulang.'))return {ok:false,cancelled:true};
 const button=$('dbSyncAbort');if(button)button.disabled=true;
 try{const result=await dbSyncCall('abort',{runId});localStorage.removeItem(DB_SYNC_RUN_KEY);dbSyncStatus('Sinkronisasi dihentikan. Route aktif tidak berubah; pindah database tetap diblokir sampai sinkronisasi ulang dan hash lulus.');msg('Sync dihentikan dengan aman. DB aktif tetap berjalan.',true);await checkBothDbApis();return result}
 catch(e){const text=String(e?.message||e);dbSyncStatus('Tidak bisa menghentikan sync: '+text,true);msg('Tidak bisa menghentikan sync: '+text,true);return {ok:false,error:text}}
 finally{if(button)button.disabled=false}
}
async function globalRouteStatus(url,key,ref){
 const response=await fetch(url+'/functions/v1/db-route-status',{headers:{apikey:key},cache:'no-store'});
 const data=await response.json().catch(()=>({}));
 if(!response.ok||data?.ok!==true||data?.projectRef!==ref||!data?.route)throw new Error('Tidak bisa membaca route-control '+ref);
 return {url,key,ref,route:data.route};
}
async function routeCoordinatorCall(url,key,token,body){
 const response=await fetch(url+'/functions/v1/db-route-coordinator',{method:'POST',headers:{apikey:key,'content-type':'application/json',authorization:'Bearer '+token},body:JSON.stringify(body),cache:'no-store'});
 const data=await response.json().catch(()=>({}));
 if(!response.ok||data?.ok!==true)throw new Error(String(data?.error||('ROUTE_SWITCH_HTTP_'+response.status)));
 return data;
}
function routeReadyForSwitch(r){
 const t=Date.parse(r.last_parity_check_at||''),fresh=Number.isFinite(t)&&Date.now()-t<=30*60*1000&&t<=Date.now()+60000;
 const schema=!!r.schema_version&&r.schema_version===r.primary_schema_version&&r.schema_version===r.backup_schema_version;
 return r.backup_ready===true&&r.auth_parity_ready===true&&r.data_parity_ready===true&&r.routing_gateway_ready===true&&fresh&&schema;
}
async function requestGlobalDbSwitch(){
 // Read both authoritative route rows directly below. Do not gate interrupted-switch recovery on the cached UI resolver.
 if(typeof ctx==='undefined'||ctx?.role!=='owner')return msg('Hanya owner yang dapat memindahkan seluruh sistem database.',true);
 const target=String($('globalDbTarget')?.value||''),button=$('globalDbSwitchButton');
 if(!['primary','backup'].includes(target))return msg('Target database tidak valid.',true);
 const token=await adminAccessToken().catch(()=> '');
 if(!token)return msg('Sesi Admin tidak valid. Login kembali untuk mengubah route global.',true);
 if(button){button.disabled=true;button.textContent='Memeriksa…'}
 try{
  let [d1,d2]=await Promise.all([
   globalRouteStatus(DB1_URL,DB1_ROUTE_KEY,'wzkjpycjizexxcxrfdvr'),
   globalRouteStatus(DB2_URL,DB2_ROUTE_KEY,'xcdbipgsvohesxhxydep')
  ]);
  if(d1.route.sync_in_progress===true||d2.route.sync_in_progress===true)throw new Error('DB Sync sedang berjalan. Tunggu sinkronisasi selesai sebelum memindahkan route global.');
  const a0=d1.route,b0=d2.route,aligned0=a0.active_target===b0.active_target&&Number(a0.epoch)===Number(b0.epoch)&&String(a0.switch_id||'')===String(b0.switch_id||'');
  const aAhead0=a0.active_target===target&&!!a0.switch_id&&Number(a0.epoch)===Number(b0.epoch)+1;
  const bAhead0=b0.active_target===target&&!!b0.switch_id&&Number(b0.epoch)===Number(a0.epoch)+1;
  const recoveringPartial=!aligned0&&(aAhead0||bAhead0);
  if(aligned0&&a0.active_target===target){dbSyncStatus('Seluruh sistem sudah aktif di '+(target==='backup'?'DB2':'DB1')+'.');await checkBothDbApis();return {ok:true,alreadyActive:true}}
  if(!aligned0&&!recoveringPartial)throw new Error('Route DB1/DB2 tidak selaras dan tidak cocok untuk pemulihan otomatis. Jangan paksa pindah; audit route-control terlebih dahulu.');
  const confirmText=recoveringPartial
   ? 'Terdeteksi perpindahan sebelumnya yang terhenti setelah satu database diperbarui. Lanjutkan switch ID/epoch yang sama pada target '+(target==='backup'?'DB2':'DB1')+'? Kesiapan kedua DB tetap akan diperiksa.'
   : 'Pindahkan SELURUH SISTEM ke '+(target==='backup'?'DB2':'DB1')+'? Sistem akan melakukan sinkronisasi akhir dari database aktif ke standby, memeriksa hash data dan login parity, lalu menyamakan epoch/switch ID pada kedua project. Route tidak berubah jika salah satu pemeriksaan gagal.';
  if(!confirm(confirmText))return {ok:false,cancelled:true};

  if(!recoveringPartial){
   // A fresh catch-up sync is required before starting a new epoch/switch ID.
   const sync=await requestDbSync();
   if(!sync||sync.ok===false||sync.ready!==true)throw new Error('SYNC_NOT_READY: final sync/hash/auth/gateway verification did not complete; active database was not switched.');
   [d1,d2]=await Promise.all([
    globalRouteStatus(DB1_URL,DB1_ROUTE_KEY,'wzkjpycjizexxcxrfdvr'),
    globalRouteStatus(DB2_URL,DB2_ROUTE_KEY,'xcdbipgsvohesxhxydep')
   ]);
  }else{
   dbSyncStatus('Memulihkan perpindahan yang terhenti dengan switch ID/epoch yang sama. Tidak memulai sync baru saat route tidak selaras.');
  }
  const a=d1.route,b=d2.route;
  if(a.sync_in_progress===true||b.sync_in_progress===true)throw new Error('SYNC_IN_PROGRESS: final DB Sync has not released both route locks.');
  const needsParity=target==='backup'||a.active_target==='backup'||b.active_target==='backup';
  if(needsParity&&(!routeReadyForSwitch(a)||!routeReadyForSwitch(b)||a.schema_version!==b.schema_version)){
   throw new Error('Cutover ditolak: salah satu DB belum lulus auth/data/gateway/schema parity terbaru. Route aktif tetap seperti sebelumnya.');
  }
  let epoch,switchId;
  const aligned=a.active_target===b.active_target&&Number(a.epoch)===Number(b.epoch)&&String(a.switch_id||'')===String(b.switch_id||'');
  if(aligned){
   if(a.active_target===target){dbSyncStatus('Sistem sudah aktif pada target setelah sinkronisasi akhir.');await checkBothDbApis();return {ok:true,alreadyActive:true}}
   epoch=Math.max(Number(a.epoch)||0,Number(b.epoch)||0)+1;switchId=crypto.randomUUID();
  }else{
   const aAhead=a.active_target===target&&a.switch_id&&Number(a.epoch)===Number(b.epoch)+1;
   const bAhead=b.active_target===target&&b.switch_id&&Number(b.epoch)===Number(a.epoch)+1;
   if(aAhead){epoch=Number(a.epoch);switchId=String(a.switch_id)}
   else if(bAhead){epoch=Number(b.epoch);switchId=String(b.switch_id)}
   else throw new Error('Route DB1/DB2 belum konsisten dan tidak cocok untuk pemulihan aman. Jangan paksa pindah; periksa route-control terlebih dahulu.');
  }
  const payload={target,epoch,switchId,reason:'Admin global database switch'};
  const order=target==='backup'?[d2,d1]:[d1,d2];
  for(const p of order)await routeCoordinatorCall(p.url,p.key,token,{action:'switch',...payload});
  const finalOrder=target==='backup'?[d1,d2]:[d2,d1];
  for(const p of finalOrder)await routeCoordinatorCall(p.url,p.key,token,{action:'finalize',...payload});
  // Never report success based on coordinator responses alone; re-read both authoritative route rows.
  const [confirmD1,confirmD2]=await Promise.all([
   globalRouteStatus(DB1_URL,DB1_ROUTE_KEY,'wzkjpycjizexxcxrfdvr'),
   globalRouteStatus(DB2_URL,DB2_ROUTE_KEY,'xcdbipgsvohesxhxydep')
  ]);
  const r1=confirmD1.route,r2=confirmD2.route;
  const confirmed=(r)=>r.active_target===target&&Number(r.epoch)===epoch&&String(r.switch_id||'')===switchId;
  if(!confirmed(r1)||!confirmed(r2))throw new Error('ROUTE_FINAL_CONFIRMATION_FAILED: DB1 and DB2 did not both confirm the same target, epoch, and switch ID. No successful cutover is reported.');
  if(target==='backup'&&(!routeReadyForSwitch(r1)||!routeReadyForSwitch(r2)||r1.schema_version!==r2.schema_version))throw new Error('ROUTE_FINAL_PARITY_CHECK_FAILED: DB2 is not ready on both projects after finalization.');
  if(target==='primary'&&(r1.primary_ready!==true||r2.primary_ready!==true))throw new Error('ROUTE_PRIMARY_CONFIRMATION_FAILED: primary readiness failed after route finalization.');
  dbSyncStatus('Berhasil pindah seluruh sistem ke '+(target==='backup'?'DB2':'DB1')+' • epoch '+epoch+'. Kedua DB mengonfirmasi route. Menyegarkan aplikasi…');
  try{localStorage.removeItem(DB_ROUTE_NOTICE_KEY)}catch(_){}
  location.reload();return {ok:true,target,epoch,switchId};
 }catch(e){
  const text=String(e?.message||e);dbSyncStatus('Perpindahan global ditolak atau belum lengkap: '+text,true);msg('Perpindahan database tidak diklaim berhasil: '+text,true);
  try{await checkBothDbApis()}catch(_){}
  return {ok:false,error:text};
 }finally{if(button){button.disabled=false;button.textContent='Pindah seluruh sistem'}}
}
'''
html = replace_once(html, old_placeholder, new_functions, "Active DB sync implementation")

mode_pattern = re.compile(r"function updateDbSyncDirection\(\)\{[^\n]*\}")
mode_replacement = r"""function updateDbSyncDirection(){const source=DB_TARGET==='backup'?'DB2':'DB1',target=DB_TARGET==='backup'?'DB1':'DB2',sourceLabel=$('dbSyncSourceLabel'),targetLabel=$('dbSyncTargetLabel'),button=$('dbSyncExecute'),verify=$('dbSyncVerifyOwner'),passwordLabel=$('dbSyncOwnerPasswordLabel'),state=$('dbSyncRouteState');if(sourceLabel)sourceLabel.textContent=source+' • Sumber aktif';if(targetLabel)targetLabel.textContent=target+' • Standby tujuan (upsert, tanpa delete)';if(button){button.textContent='Sinkronkan '+source+' → '+target;button.disabled=!dualDbRouteReady||ctx?.role!=='owner'}if(verify){verify.textContent='Verifikasi login '+target;verify.disabled=!dualDbRouteReady||ctx?.role!=='owner'}if(passwordLabel)passwordLabel.textContent='Password '+target+' untuk akun owner yang sedang login';const syncing=dualDbRouteState?.route?.syncInProgress===true;if(state)state.textContent='Route global aktif: '+source+' • standby: '+target+' • epoch '+DB_ROUTE_EPOCH+(syncing?' • SYNC BERJALAN':'');if(button&&syncing)button.disabled=true;if(verify&&syncing)verify.disabled=true;}"""
html, count = mode_pattern.subn(mode_replacement, html, count=1)
if count != 1:
    raise SystemExit("updateDbSyncDirection function anchor mismatch")

# Reflect the actual target in the badge and make the selector propose the opposite target.
html = replace_once(
    html,
    "if(badge)badge.textContent=DB_TARGET==='backup'?'DB2 • Rute aktif':'DB1 • Rute aktif';",
    "if(badge)badge.textContent=DB_TARGET==='backup'?'DB2 • AKTIF SELURUH SISTEM':'DB1 • AKTIF SELURUH SISTEM';const targetSelect=$('globalDbTarget'),globalButton=$('globalDbSwitchButton');if(targetSelect)targetSelect.value=DB_TARGET==='backup'?'primary':'backup';if(globalButton)globalButton.textContent='Pindah seluruh sistem';",
    "Global badge target display"
)
html = replace_once(
    html,
    "function v12InitDbSwitch(){const badge=$('dbActiveBadge'),hint=$('dbRouteStatusHint');if(badge)badge.textContent=DB_TARGET==='backup'?'DB2 • Rute aktif':'DB1 • Rute aktif';if(hint&&dualDbRouteState)hint.textContent='Target otomatis • epoch '+DB_ROUTE_EPOCH+' • '+(DB_ROUTE_SWITCH_ID||'route awal');}",
    "function v12InitDbSwitch(){const badge=$('dbActiveBadge'),hint=$('dbRouteStatusHint'),target=$('globalDbTarget');if(badge)badge.textContent=DB_TARGET==='backup'?'DB2 • AKTIF SELURUH SISTEM':'DB1 • AKTIF SELURUH SISTEM';if(target)target.value=DB_TARGET==='backup'?'primary':'backup';if(hint&&dualDbRouteState)hint.textContent='Target otomatis • epoch '+DB_ROUTE_EPOCH+' • '+(DB_ROUTE_SWITCH_ID||'route awal');}",
    "Global switch selector initial target"
)
html = replace_once(
    html,
    "if(system){system.textContent='RUTE GLOBAL TERVERIFIKASI';system.style.color='var(--ok)';system.style.borderColor='var(--ok)'}",
    "if(system){system.textContent=DB_TARGET==='backup'?'SISTEM GLOBAL: DB2 AKTIF':'SISTEM GLOBAL: DB1 AKTIF';system.style.color='var(--ok)';system.style.borderColor='var(--ok)'}",
    "Global status badge"
)

# The supplied Admin ZIP can contain a stale v12 script with a TypeScript-only callback annotation.
# Normalize it to plain browser JavaScript before the syntax regression check.
html = html.replace(".find((run:any)=>", ".find(run=>")
if "(run:any)" in html:
    raise SystemExit("TypeScript annotation remains in browser Admin JavaScript")

# The route must be stable before the owner sees the sync/switch actions as active.
if "function requestGlobalDbSwitch()" not in html or "function previewDbSync()" not in html or "function verifyDb2OwnerLogin()" not in html or "function abortDbSync()" not in html:
    raise SystemExit("DB Sync/global switch implementation incomplete")
if "DB_TARGET!== 'primary'" in html:
    raise SystemExit("Unexpected malformed DB target guard")
for required in ["db-sync-apply","db-route-coordinator","auth_parity_ready","dbSyncPreviewSummary","globalDbTarget","DB_SYNC_RUN_KEY","abortDbSync","ROUTE_FINAL_CONFIRMATION_FAILED","confirmD1","confirmD2","recoveringPartial","aAhead0","bAhead0"]:
    if required not in html:
        raise SystemExit("Missing required dual-DB UI token: "+required)

if "versionCode 41" not in gradle or "versionName '12.1.13'" not in gradle:
    raise SystemExit("Unexpected baseline version; expected v12.1.13 / code 41")
gradle=gradle.replace("versionCode 41","versionCode 42",1).replace("versionName '12.1.13'","versionName '12.1.14'",1)
html_path.write_text(html,encoding="utf-8")
gradle_path.write_text(gradle,encoding="utf-8")
version_path.write_text("v12.1.14-admin-db-sync-global-switch\n",encoding="utf-8")
print("Applied active DB1→DB2 sync UI, owner DB2 login verification, global route coordinator controls and DB badge; Android v12.1.14 / code 42")
