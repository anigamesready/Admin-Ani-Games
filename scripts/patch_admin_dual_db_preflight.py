from pathlib import Path
import re

ROOT = Path('.')
html_path = ROOT / 'android/app/src/main/assets/web/admin.html'
gradle_path = ROOT / 'android/app/build.gradle'
html = html_path.read_text(encoding='utf-8')
gradle = gradle_path.read_text(encoding='utf-8')

# Remove the previous one-line API-only checker so it cannot override this route-aware preflight.
html = re.sub(r"async function checkBothDbApis\(\)\{[^\n]*\}", "", html)

# Read-only, dual-project readiness panel. This is deliberately not a DB switch button.
panel_heading = 'Sinkronisasi DB1 ↔ DB2'
panel_index = html.find(panel_heading)
panel_anchor_index = html.rfind('<div class="card" style="margin-top:12px">', 0, panel_index)
panel = ''' <div class="card" id="dualDbReadinessPanel" style="margin-top:12px;border:1px solid var(--a)">
  <div class="top"><div><h2 style="margin:0">🛡️ Preflight Integrasi 2 DB</h2><div class="muted">Pemeriksaan baca-saja ke DB1 dan DB2. Tidak mengubah target, tidak menyalin data, dan tidak mengirim perintah ke PC.</div></div><span id="dualDbReadinessBadge" class="pill">BELUM DICEK</span></div>
  <div class="cards2" style="margin-top:10px">
   <div class="sync-status"><b>DB1 • Status route</b><div id="db1RouteStatus" class="muted" style="margin-top:7px">Belum diperiksa</div></div>
   <div class="sync-status"><b>DB2 • Status route</b><div id="db2RouteStatus" class="muted" style="margin-top:7px">Belum diperiksa</div></div>
  </div>
  <div id="dualDbReadinessMessage" class="msg" role="status" aria-live="polite">Gunakan “Periksa Kesiapan DB1 & DB2” untuk memvalidasi parity data, schema, target route, epoch, dan gateway.</div>
  <div class="muted">Catatan: tombol pergantian DB pada aplikasi ini hanya mengganti target login Admin lokal. Status preflight tidak otomatis memindahkan PC Billing atau reseller.</div>
 </div>
'''
if 'id="dualDbReadinessPanel"' not in html:
    if panel_index < 0 or panel_anchor_index < 0:
        raise SystemExit('Dual DB panel insertion anchor mismatch; refusing to patch')
    html = html[:panel_anchor_index] + panel + html[panel_anchor_index:]

html = html.replace('Periksa Koneksi DB1 & DB2', 'Periksa Kesiapan DB1 & DB2', 1)

# Explicit route checks against the read-only edge function deployed on each project.
health_anchor = "async function checkOneDbHealth(url,key){const response=await fetch(url+'/auth/v1/health',{method:'GET',headers:{apikey:key},cache:'no-store'});if(!response.ok)throw new Error('HTTP '+response.status);return true}"
route_helpers = r'''async function checkOneDbHealth(url,key){const response=await fetch(url+'/auth/v1/health',{method:'GET',headers:{apikey:key},cache:'no-store'});if(!response.ok)throw new Error('HTTP '+response.status);return true}\nasync function fetchDbRouteStatus(url,key,expectedRef){
 const response=await fetch(url+'/functions/v1/db-route-status',{method:'GET',headers:{apikey:key},cache:'no-store'});
 const data=await response.json().catch(()=>({}));
 if(!response.ok||data?.ok!==true||!data?.route)throw new Error(String(data?.error||('route HTTP '+response.status)));
 if(data.projectRef!==expectedRef)throw new Error('Project ref tidak sesuai: '+String(data.projectRef||'unknown'));
 const source=data.route;
 return {projectRef:data.projectRef,activeTarget:String(source.active_target||''),epoch:Number(source.epoch),switchId:source.switch_id||null,schemaVersion:source.schema_version||null,primarySchemaVersion:source.primary_schema_version||null,backupSchemaVersion:source.backup_schema_version||null,primaryReady:source.primary_ready===true,backupReady:source.backup_ready===true,dataParityReady:source.data_parity_ready===true,routingGatewayReady:source.routing_gateway_ready===true,syncReady:source.sync_ready===true,parityAt:source.last_parity_check_at||null,schemaAt:source.last_schema_check_at||null,canSwitchToBackup:source.can_switch_to_backup===true,parityNote:source.last_parity_check_note||null,cutoverAt:source.last_cutover_test_at||null,cutoverNote:source.cutover_test_note||null};
}
function renderDbRouteStatus(id,route,error){
 const el=$(id);if(!el)return;
 if(error){el.textContent='GAGAL: '+String(error.message||error);el.style.color='var(--bad)';return;}
 const stamp=route.parityAt?new Date(route.parityAt).toLocaleString('id-ID'):'belum ada';
 el.textContent='Project '+route.projectRef+' • target '+(route.activeTarget||'unknown')+' • epoch '+route.epoch+' • primary '+(route.primaryReady?'OK':'NO')+' • backup '+(route.backupReady?'OK':'NO')+' • parity '+(route.dataParityReady?'OK':'NO')+' • gateway '+(route.routingGatewayReady?'OK':'NO')+' • cek parity: '+stamp;
 el.style.color=route.backupReady&&route.dataParityReady&&route.routingGatewayReady?'var(--ok)':'var(--warn)';
}
function dbRouteBlockers(routes){
 const problems=[];
 if(routes.length!==2||routes.some(x=>!x.route))return ['Status route dari kedua project wajib berhasil dibaca.'];
 const [a,b]=routes.map(x=>x.route);
 if(a.projectRef!=='wzkjpycjizexxcxrfdvr'||b.projectRef!=='xcdbipgsvohesxhxydep')problems.push('Project ref DB1/DB2 tidak sesuai.');
 if(a.activeTarget!==b.activeTarget||a.epoch!==b.epoch||a.switchId!==b.switchId)problems.push('Target route, epoch, atau switch ID DB1 dan DB2 tidak konsisten.');
 if(!a.primaryReady||!b.primaryReady)problems.push('Primary belum dinyatakan siap oleh kedua project.');
 if(!a.backupReady||!b.backupReady)problems.push('Backup belum dinyatakan siap pada kedua project.');
 if(!a.dataParityReady||!b.dataParityReady)problems.push('Parity isi data belum dinyatakan lolos pada kedua project.');
 if(!a.routingGatewayReady||!b.routingGatewayReady)problems.push('Gateway routing bersama belum dinyatakan siap pada kedua project.');
 if(!a.schemaVersion||!b.schemaVersion||a.schemaVersion!==b.schemaVersion)problems.push('Versi schema lintas DB kosong atau berbeda.');
 if(!a.primarySchemaVersion||!a.backupSchemaVersion||a.primarySchemaVersion!==a.backupSchemaVersion||!b.primarySchemaVersion||!b.backupSchemaVersion||b.primarySchemaVersion!==b.backupSchemaVersion)problems.push('Hasil pemeriksaan versi schema primary/backup belum sama dan lengkap.');
 const now=Date.now(),maxAge=30*60*1000;
 for(const [label,r] of [['DB1',a],['DB2',b]]){const ts=Date.parse(r.parityAt||'');if(!Number.isFinite(ts)||now-ts>maxAge||ts>now+60000)problems.push(label+': pemeriksaan parity belum ada atau sudah lebih dari 30 menit.');}
 return problems;
}
async function checkBothDbApis(){
 const btn=document.querySelector('#databaseTools button.primary'),healthMessage=$('dbHealthMessage'),routeMessage=$('dualDbReadinessMessage'),badge=$('dualDbReadinessBadge');
 if(btn){btn.disabled=true;btn.textContent='Memeriksa…'}
 if(healthMessage)healthMessage.textContent='Memeriksa health endpoint dan status route resmi DB1/DB2…';
 if(badge){badge.textContent='MEMERIKSA…';badge.style.color='var(--warn)'}
 const checks=[{name:'DB1',url:DB1_URL,key:DB1_KEY,ref:'wzkjpycjizexxcxrfdvr',healthId:'db1Health',routeId:'db1RouteStatus'},{name:'DB2',url:DB2_URL,key:DB2_KEY,ref:'xcdbipgsvohesxhxydep',healthId:'db2Health',routeId:'db2RouteStatus'}];
 try{
  const results=await Promise.all(checks.map(async c=>{
   const out={name:c.name,apiOk:false,route:null,error:null};
   try{await checkOneDbHealth(c.url,c.key);out.apiOk=true;const h=$(c.healthId);if(h){h.textContent='API terjangkau';h.style.color='var(--ok)'}}catch(e){out.error='API: '+(e.message||'fetch');const h=$(c.healthId);if(h){h.textContent='Gagal: '+(e.message||'fetch');h.style.color='var(--bad)'}}
   try{out.route=await fetchDbRouteStatus(c.url,c.key,c.ref)}catch(e){out.routeError=e;}
   renderDbRouteStatus(c.routeId,out.route,out.routeError);
   return out;
  }));
  const apiCount=results.filter(x=>x.apiOk).length,routeCount=results.filter(x=>x.route).length;
  if(healthMessage)healthMessage.textContent='Health API: '+apiCount+'/2 • route status: '+routeCount+'/2. Health API saja tidak cukup untuk menyatakan DB siap pindah.';
  const problems=dbRouteBlockers(results);
  const ready=problems.length===0;
  if(badge){badge.textContent=ready?'PREFLIGHT LOLOS':'CUTOVER DIBLOKIR';badge.style.color=ready?'var(--ok)':'var(--bad)'}
  if(routeMessage){routeMessage.textContent=ready?'Route preflight lulus pada saat pemeriksaan ini. Ini belum berarti sinkronisasi lintas DB aktif; backend harus tetap mengotorisasi cutover dan perpindahan data.':'Belum aman mengaktifkan perpindahan DB. '+problems.join(' ');routeMessage.style.borderLeftColor=ready?'var(--ok)':'var(--bad)'}
  return {ok:ready,problems,results};
 }catch(e){if(badge){badge.textContent='PREFLIGHT GAGAL';badge.style.color='var(--bad)'}if(routeMessage)routeMessage.textContent='Pemeriksaan gagal: '+(e.message||'error');return {ok:false,problems:[e.message||'error'],results:[]};}
 finally{if(btn){btn.disabled=false;btn.textContent='Periksa Kesiapan DB1 & DB2'}}
}'''
if 'async function fetchDbRouteStatus(' not in html:
    if html.count(health_anchor) != 1:
        raise SystemExit('checkOneDbHealth anchor mismatch; refusing to patch')
    html = html.replace(health_anchor, route_helpers, 1)

# Sync is intentionally disabled until the shared backend implements an authenticated, idempotent cross-project transaction.
mode_pattern = re.compile(r"function updateDbSyncDirection\(\)\{[^\n]*\}")
mode_replacement = "function updateDbSyncDirection(){const a=$('dbSyncSource')?.value||'primary',b=$('dbSyncDestination')?.value||'backup',label=$('dbSyncDirectionLabel'),button=$('dbSyncExecute');if(label)label.textContent=a===b?'Sumber dan tujuan sama — tidak valid':(a==='primary'?'DB1':'DB2')+' → '+(b==='primary'?'DB1':'DB2');if(button){button.disabled=true;button.title='Menunggu endpoint backend sinkronisasi lintas-project yang tervalidasi';button.textContent='Sinkronisasi menunggu backend';}}"
html, count = mode_pattern.subn(mode_replacement, html, count=1)
if count != 1:
    raise SystemExit('updateDbSyncDirection function mismatch; refusing to patch')

request_pattern = re.compile(r"async function requestDbSync\(\)\{[^\n]*\}")
request_replacement = "async function requestDbSync(){showDbSyncSafetyDetails();return {ok:false,code:'BACKEND_NOT_READY'};}"
html, count = request_pattern.subn(request_replacement, html, count=1)
if count != 1:
    raise SystemExit('requestDbSync function mismatch; refusing to patch')

# Re-run read-only preflight whenever the database tools tab is opened.
tab_old = "if(id==='databaseTools'){updateDbSyncDirection();updateDbSyncModeNote();const b=$('dbToolsBadge');if(b)b.textContent=DB_TARGET==='backup'?'DB2 • Cadangan aktif':'DB1 • Utama aktif'}"
tab_new = "if(id==='databaseTools'){updateDbSyncDirection();updateDbSyncModeNote();const b=$('dbToolsBadge');if(b)b.textContent=DB_TARGET==='backup'?'DB2 • Cadangan aktif':'DB1 • Utama aktif';checkBothDbApis()}"
if 'checkBothDbApis()}' not in html:
    if html.count(tab_old) != 1:
        raise SystemExit('databaseTools tab initialization anchor mismatch; refusing to patch')
    html = html.replace(tab_old, tab_new, 1)

html_path.write_text(html, encoding='utf-8')

# Build version bump after v12.1.7 so this feature is distinguishable from the prior notifications APK.
if "versionCode 35" not in gradle or "versionName '12.1.7'" not in gradle:
    raise SystemExit('Unexpected Android baseline version; expected v12.1.7 / code 35')
gradle = gradle.replace('versionCode 35', 'versionCode 36', 1).replace("versionName '12.1.7'", "versionName '12.1.8'", 1)
gradle_path.write_text(gradle, encoding='utf-8')
(ROOT / 'VERSION.txt').write_text('v12.1.8-dual-db-readiness-preflight\n', encoding='utf-8')
print('Added read-only DB1/DB2 route preflight, strict cutover blockers, and disabled cross-project sync until the shared backend is ready; version 12.1.8 / code 36')
