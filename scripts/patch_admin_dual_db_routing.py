from pathlib import Path
import re

ROOT = Path('.')
html_path = ROOT / 'android/app/src/main/assets/web/admin.html'
gradle_path = ROOT / 'android/app/build.gradle'
html = html_path.read_text(encoding='utf-8')
gradle = gradle_path.read_text(encoding='utf-8')

if 'async function resolveDualDbRoute(' in html:
    raise SystemExit('Dual-DB route patch already applied; refusing to apply twice')

# Replace the old per-install DB selector runtime with a guarded route resolver.
start = html.find("const DB_CONFIG_KEY='ani_games_v12_db_config'")
end = html.find('const $=id=>document.getElementById(id);', start)
if start < 0 or end < 0:
    raise SystemExit('Admin DB config block not found exactly; refusing to patch')
config = r'''const DB_CONFIG_KEY='ani_games_v12_db_config',DB_ROUTE_NOTICE_KEY='ani_games_v12_db_route_notice_v1';
const DB1_URL='https://wzkjpycjizexxcxrfdvr.supabase.co',DB1_KEY='sb_publishable_DobdCrOd43-vluON5gV7hg_6Js2Ea5V';
const DB2_URL='https://xcdbipgsvohesxhxydep.supabase.co',DB2_KEY='sb_publishable_FjhnRZeXPnomlGRw75YLxw_d46R2Lag';
// Public legacy anon keys are used only to read the no-store route-status endpoints.
const DB1_ROUTE_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind6a2pweWNqaXpleHhjeHJmZHZyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTEwMzc0OTUsImV4cCI6MjEwNjYxMzQ5NX0.lxjSt7CqWDJhKItPi1ckVRIcc-kM7etMzxTu3txANaI';
const DB2_ROUTE_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhjZGJpcGdzdm9oZXN4aHh5ZGVwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTIwNjI5ODUsImV4cCI6MjEwNzYzODk4NX0.kHymS-T8a_PcKk-oQBYMGhHy3SSW1kAKStOBJVzMoSI';
const DB_ROUTE_CACHE_MS=5000;
function readDbConfig(){try{return JSON.parse(localStorage.getItem(DB_CONFIG_KEY)||'{}')}catch(_){return {}}}
function activeDbConfig(){return {target:'primary',url:DB1_URL,key:DB1_KEY}}
let DB_TARGET='primary',SB_URL=DB1_URL,SB_KEY=DB1_KEY,SB_FUNCTION_URL=DB1_URL+'/functions/v1/ani-games-api',sb=supabase.createClient(DB1_URL,DB1_KEY);
let DB_ROUTE_EPOCH=0,DB_ROUTE_SWITCH_ID=null,dualDbRouteState=null,dualDbRouteCheckedAt=0,dualDbRoutePromise=null,dualDbRouteReady=false,dualDbRouteMonitorStarted=false,dualDbRouteLocked=false;
function routeBackupReady(r){
 const parityAt=Date.parse(r?.last_parity_check_at||'');
 const parityFresh=Number.isFinite(parityAt)&&Date.now()-parityAt<=30*60*1000&&parityAt<=Date.now()+60000;
 const schemasMatch=!!r?.schema_version&&!!r?.primary_schema_version&&!!r?.backup_schema_version&&r.primary_schema_version===r.backup_schema_version&&r.schema_version===r.primary_schema_version;
 return !!r&&r.active_target==='backup'&&r.backup_ready===true&&r.auth_parity_ready===true&&r.data_parity_ready===true&&r.routing_gateway_ready===true&&r.can_switch_to_backup===true&&Number.isFinite(Number(r.epoch))&&Number(r.epoch)>0&&typeof r.switch_id==='string'&&r.switch_id.length>0&&parityFresh&&schemasMatch;
}
async function readDualDbRoute(target){
 const cfg=target==='backup'?{ref:'xcdbipgsvohesxhxydep',url:DB2_URL,key:DB2_ROUTE_KEY}:{ref:'wzkjpycjizexxcxrfdvr',url:DB1_URL,key:DB1_ROUTE_KEY};
 const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),4500);
 try{const response=await fetch(cfg.url+'/functions/v1/db-route-status',{method:'GET',headers:{apikey:cfg.key},cache:'no-store',signal:ctl.signal});const data=await response.json().catch(()=>({}));if(!response.ok||data?.ok!==true||data?.readOnly!==true||data?.projectRef!==cfg.ref||!data?.route)throw new Error('DB_ROUTE_STATUS_UNAVAILABLE:'+target);return data.route}
 finally{clearTimeout(timer)}
}
function rememberDualDbRoute(target,route){dualDbRouteState={target,epoch:Number(route.epoch)||0,switchId:route.switch_id||null,route};dualDbRouteCheckedAt=Date.now();return dualDbRouteState}
async function resolveDualDbRoute(force=false){
 if(!force&&dualDbRouteState&&Date.now()-dualDbRouteCheckedAt<DB_ROUTE_CACHE_MS)return dualDbRouteState;
 if(dualDbRoutePromise)return dualDbRoutePromise;
 dualDbRoutePromise=(async()=>{
  let primary=null;try{primary=await readDualDbRoute('primary')}catch(_){}
  if(!primary)throw new Error('DB_ROUTE_STATUS_UNAVAILABLE: DB1 route authority cannot be verified; automatic failover is disabled');
  const route=primary;
  if(!['primary','backup'].includes(route.active_target))throw new Error('DB_ROUTE_INVALID_TARGET');
  if(route.active_target==='primary'&&route.primary_ready!==true)throw new Error('DB_ROUTE_PRIMARY_NOT_READY');
  if(route.active_target==='backup'&&!routeBackupReady(route))throw new Error('DB_ROUTE_CUTOVER_BLOCKED: parity/readiness/schema/gateway checks are not current');
  let backup;try{backup=await readDualDbRoute('backup')}catch(_){throw new Error('DB_ROUTE_CUTOVER_INCOMPLETE: DB2 route endpoint is unavailable; refusing split-brain writes')}
  if(backup.active_target!==route.active_target||Number(backup.epoch)!==Number(route.epoch)||String(backup.switch_id||'')!==String(route.switch_id||''))throw new Error('DB_ROUTE_CUTOVER_INCOMPLETE: DB1 and DB2 target, epoch, or switch ID differ');
  if(route.active_target==='primary'){
   if(backup.primary_ready!==true)throw new Error('DB_ROUTE_PRIMARY_NOT_READY_ON_BOTH_PROJECTS');
   return rememberDualDbRoute('primary',route);
  }
  if(!routeBackupReady(backup))throw new Error('DB_ROUTE_CUTOVER_BLOCKED: parity/readiness/schema/gateway checks are not current on both projects');
  return rememberDualDbRoute('backup',backup);
 })();
 try{return await dualDbRoutePromise}finally{dualDbRoutePromise=null}
}
function configureDbTarget(target,route){
 const config=target==='backup'?{url:DB2_URL,key:DB2_KEY}:{url:DB1_URL,key:DB1_KEY};
 const changed=DB_TARGET!==target;DB_TARGET=target;SB_URL=config.url;SB_KEY=config.key;SB_FUNCTION_URL=SB_URL+'/functions/v1/ani-games-api';DB_ROUTE_EPOCH=Number(route?.epoch)||0;DB_ROUTE_SWITCH_ID=route?.switch_id||null;
 if(changed||!sb)sb=supabase.createClient(SB_URL,SB_KEY);
 try{localStorage.setItem(DB_CONFIG_KEY,JSON.stringify({target:DB_TARGET,epoch:DB_ROUTE_EPOCH,switchId:DB_ROUTE_SWITCH_ID,routedAt:new Date().toISOString()}))}catch(_){}
 const badge=$('dbActiveBadge'),system=$('dbSystemStatusBadge'),hint=$('dbRouteStatusHint');
 if(badge)badge.textContent=DB_TARGET==='backup'?'DB2 • Rute aktif':'DB1 • Rute aktif';
 if(system){system.textContent='RUTE GLOBAL TERVERIFIKASI';system.style.color='var(--ok)';system.style.borderColor='var(--ok)'}
 if(hint)hint.textContent='Target mengikuti route-control Supabase • epoch '+DB_ROUTE_EPOCH+' • switch '+(DB_ROUTE_SWITCH_ID||'awal')
}
function routeFailureText(e){const message=String(e?.message||e||'');if(message.includes('DB_ROUTE_CUTOVER_BLOCKED'))return 'Perpindahan DB diblokir: DB2 belum lulus pemeriksaan parity terbaru dan gateway. Database aktif tidak diubah.';if(message.includes('DB_ROUTE_CUTOVER_INCOMPLETE'))return 'Perpindahan DB belum konsisten antara DB1 dan DB2. Operasi cloud dihentikan sampai target dan epoch route-control selaras.';return 'Status route database tidak dapat diverifikasi. Operasi cloud belum diaktifkan untuk mencegah penulisan ke DB yang salah.'}
function setAdminAuthEnabled(enabled){document.querySelectorAll('#login button').forEach(button=>{button.disabled=!enabled})}
async function monitorDualDbRoute(){if(!dualDbRouteReady||dualDbRouteLocked)return;try{const route=await resolveDualDbRoute(true);if(route.target!==DB_TARGET||route.epoch!==DB_ROUTE_EPOCH||route.switchId!==DB_ROUTE_SWITCH_ID){try{localStorage.setItem(DB_ROUTE_NOTICE_KEY,'Rute database berubah ke '+(route.target==='backup'?'DB2':'DB1')+'. Dashboard memuat ulang agar sesi dan operasi memakai project yang benar.')}catch(_){}location.reload()}}catch(e){if(/DB_ROUTE_CUTOVER_BLOCKED|DB_ROUTE_CUTOVER_INCOMPLETE|DB_ROUTE_INVALID_TARGET/.test(String(e?.message||''))){dualDbRouteLocked=true;try{localStorage.setItem(DB_ROUTE_NOTICE_KEY,routeFailureText(e))}catch(_){}location.reload()}}}
const GLOBAL_DEVICE_KEY='ani_games_admin_selected_device_v1';
'''
html = html[:start] + config + html[end:]

# Remove the manual per-device target selector. Route control, not a local dropdown, chooses the active project.
selector = re.compile(r'<select id="dbTargetApp" onchange="v12DbTargetChanged\(this\.value\)" style="max-width:280px"><option value="primary">DB1 • Utama</option><option value="backup">DB2 • Cadangan</option></select><button onclick="v12SaveDbTarget\(\'app\'\)">Ganti DB & login ulang</button><span id="dbSwitchStatusApp" class="muted"></span>')
html, count = selector.subn('<span id="dbRouteStatusHint" class="muted">Memeriksa route-control DB1/DB2…</span>', html, count=1)
if count != 1:
    raise SystemExit(f'Manual DB selector replacement count was {count}; refusing to patch')
old_warning = '<div class="muted" style="margin-top:5px">PENTING: pilihan ini hanya DB yang diakses Admin. Status aktif global belum terkoordinasi dan PC Billing/Reseller tidak otomatis berpindah. PC Billing dan Reseller tidak otomatis berpindah. Jangan gunakan DB tujuan untuk input operasional sebelum data dan kesiapan DB diverifikasi.</div>'
if html.count(old_warning) != 1:
    raise SystemExit('Obsolete manual-switch warning text not found exactly once')
html = html.replace(old_warning, '<div class="muted" style="margin-top:5px">Target DB ditentukan otomatis. Cutover ke DB2 hanya diizinkan setelah kedua route-control sepakat pada target dan epoch serta guard schema, parity terbaru, dan gateway lulus.</div>', 1)

old_functions = "function v12DbTargetChanged(target){const label=target==='backup'?'DB2 • Cadangan dipilih':'DB1 • Utama dipilih';['dbSwitchStatusApp','dbSwitchStatusLogin'].forEach(id=>{const status=document.getElementById(id);if(status)status.textContent=label;});}\nfunction v12InitDbSwitch(){const a=document.getElementById('dbTargetApp'),badge=document.getElementById('dbActiveBadge');if(a)a.value=DB_TARGET;if(badge)badge.textContent=DB_TARGET==='backup'?'DB2 • Cadangan':'DB1 • Utama';}\nasync function v12SaveDbTarget(where){const select=document.getElementById('dbTargetApp');const target=select?.value||'primary';const status=document.getElementById('dbSwitchStatusApp');if(target===DB_TARGET){if(status)status.textContent='DB ini sudah aktif.';return;}const targetLabel=target==='backup'?'DB2 • Cadangan':'DB1 • Utama';const url=target==='backup'?DB2_URL:DB1_URL,key=target==='backup'?DB2_KEY:DB1_KEY;if(status)status.textContent='Memeriksa koneksi '+targetLabel+'…';try{await checkOneDbHealth(url,key)}catch(e){if(status)status.textContent=targetLabel+' tidak dapat dijangkau; perpindahan dibatalkan.';alert('Tidak bisa pindah ke '+targetLabel+'. Koneksi health check gagal. Tidak ada perubahan DB yang disimpan.');return;}if(!confirm('PERINGATAN PERPINDAHAN DATABASE\\n\\nDB tujuan: '+targetLabel+'\\nDB ini mungkin belum sinkron atau bukan DB aktif sistem. Pastikan data PC, pairing, rental aktif, dan akun Admin tersedia.\\n\\nPerpindahan ini hanya mengubah aplikasi Admin pada perangkat ini; PC Billing dan Reseller TIDAK ikut berpindah. Anda akan logout dan perlu login dengan akun yang terdaftar di DB tujuan. Lanjutkan?'))return;localStorage.setItem(DB_CONFIG_KEY,JSON.stringify({target,changedAt:new Date().toISOString()}));try{await sb.auth.signOut()}catch(_){}sessionStorage.clear();location.reload();}"
new_functions = "function v12DbTargetChanged(){const hint=$('dbRouteStatusHint');if(hint)hint.textContent='Target DB dikelola otomatis oleh route-control.';}\nfunction v12InitDbSwitch(){const badge=$('dbActiveBadge'),hint=$('dbRouteStatusHint');if(badge)badge.textContent=DB_TARGET==='backup'?'DB2 • Rute aktif':'DB1 • Rute aktif';if(hint&&dualDbRouteState)hint.textContent='Target otomatis • epoch '+DB_ROUTE_EPOCH+' • '+(DB_ROUTE_SWITCH_ID||'route awal');}\nasync function v12SaveDbTarget(){msg('Pergantian DB manual dinonaktifkan. Aplikasi mengikuti route-control global yang sudah lolos readiness guard.',true);}"
if html.count(old_functions) != 1:
    raise SystemExit(f'Old selector function block count was {html.count(old_functions)}')
html = html.replace(old_functions, new_functions, 1)

# Guard login/signup/password-reset until the route has been verified.
for name in ('login', 'signup', 'resetPassword'):
    pattern = re.compile(r'(async function '+name+r'\(\)\{)')
    html, n = pattern.subn(r"\1if(!dualDbRouteReady)return loginMsg('Rute database belum terverifikasi. Login dan perubahan akun ditahan demi keamanan.');", html, count=1)
    if n != 1:
        raise SystemExit(f'Could not add route-ready guard to {name}()')

old_bottom = "v12InitDbSwitch();updateDbSyncDirection();updateDbSyncModeNote();$('from').value=new Date(Date.now()-29*864e5).toISOString().slice(0,10);$('to').value=new Date().toISOString().slice(0,10);sb.auth.onAuthStateChange(()=>setTimeout(boot,0));boot();setInterval(()=>{if(session&&currentOrg)loadDevices()},20000);"
old_bottom_with_alert_poll = old_bottom.replace("setInterval(()=>{if(session&&currentOrg)loadDevices()},20000);", "setInterval(()=>{if(session&&currentOrg)loadDevices()},20000);setInterval(()=>{if(session&&currentOrg)pollPcAdminAlerts()},15000);")
new_bottom = r'''updateDbSyncDirection();updateDbSyncModeNote();$('from').value=new Date(Date.now()-29*864e5).toISOString().slice(0,10);$('to').value=new Date().toISOString().slice(0,10);
async function startDualDbAdmin(){setAdminAuthEnabled(false);try{const route=await resolveDualDbRoute(true);configureDbTarget(route.target,route);dualDbRouteReady=true;v12InitDbSwitch();setAdminAuthEnabled(true);sb.auth.onAuthStateChange(()=>setTimeout(boot,0));await boot();if(!dualDbRouteMonitorStarted){dualDbRouteMonitorStarted=true;setInterval(monitorDualDbRoute,10000)}const notice=localStorage.getItem(DB_ROUTE_NOTICE_KEY);if(notice){localStorage.removeItem(DB_ROUTE_NOTICE_KEY);if(session)msg(notice);else loginMsg(notice)} }catch(e){dualDbRouteReady=false;$('app').classList.add('hidden');$('login').classList.remove('hidden');const system=$('dbSystemStatusBadge'),hint=$('dbRouteStatusHint');if(system){system.textContent='ROUTE BELUM AMAN';system.style.color='var(--bad)';system.style.borderColor='var(--bad)'}if(hint)hint.textContent=routeFailureText(e);loginMsg(routeFailureText(e));setAdminAuthEnabled(false);if(!dualDbRouteMonitorStarted){dualDbRouteMonitorStarted=true;const retry=setInterval(async()=>{try{const route=await resolveDualDbRoute(true);clearInterval(retry);dualDbRouteMonitorStarted=false;configureDbTarget(route.target,route);dualDbRouteReady=true;setAdminAuthEnabled(true);v12InitDbSwitch();sb.auth.onAuthStateChange(()=>setTimeout(boot,0));await boot();if(!dualDbRouteMonitorStarted){dualDbRouteMonitorStarted=true;setInterval(monitorDualDbRoute,10000)}}catch(_){/* quiet retry every 15 s; no repeated alert/log */}},15000)}}}
startDualDbAdmin();setInterval(()=>{if(session&&currentOrg)loadDevices()},20000);'''
if html.count(old_bottom) == 1:
    html = html.replace(old_bottom, new_bottom, 1)
elif html.count(old_bottom_with_alert_poll) == 1:
    html = html.replace(old_bottom_with_alert_poll, new_bottom + "setInterval(()=>{if(session&&currentOrg)pollPcAdminAlerts()},15000);", 1)
else:
    raise SystemExit(f'Old startup block variants not found: base={html.count(old_bottom)}, alert={html.count(old_bottom_with_alert_poll)}')

if "function readDualDbRoute(" not in html or "function monitorDualDbRoute(" not in html or '<select id="dbTargetApp"' in html:
    raise SystemExit('Post-patch routing structure validation failed')
for required in ["automatic failover is disabled", "String(backup.switch_id||'')!==String(route.switch_id||'')", "r.auth_parity_ready===true", "r.data_parity_ready===true", "r.routing_gateway_ready===true", "r.can_switch_to_backup===true"]:
    if required not in html:
        raise SystemExit('Missing strict DB route consistency guard: '+required)

if "versionCode 40" not in gradle or "versionName '12.1.12'" not in gradle:
    raise SystemExit('Unexpected baseline version; expected v12.1.12 / code 40')
gradle = gradle.replace('versionCode 40', 'versionCode 41', 1).replace("versionName '12.1.12'", "versionName '12.1.13'", 1)
gradle_path.write_text(gradle, encoding='utf-8')
html_path.write_text(html, encoding='utf-8')
(ROOT / 'VERSION.txt').write_text('v12.1.13-admin-dual-db-auto-routing\n', encoding='utf-8')
print('Applied guarded DB1/DB2 route resolution; removed the manual DB switch; Admin APK v12.1.13 / versionCode 41')
