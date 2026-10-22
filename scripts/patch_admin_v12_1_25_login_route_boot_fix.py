from pathlib import Path
import re

HTML = Path("android/app/src/main/assets/web/admin.html")
GRADLE = Path("android/app/build.gradle")
html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")
marker = "V12.1.25-ROUTE-BOOT-SEPARATION"

if marker in html:
    if "versionCode 53" not in gradle or "versionName '12.1.25'" not in gradle:
        raise SystemExit("V12.1.25 marker/version mismatch")
    print("PASS: V12.1.25 route/boot separation already applied")
    raise SystemExit(0)

if "V12.1.24-CROSS-PROJECT-OWNER-PROOF" not in html:
    raise SystemExit("Expected V12.1.24 bundled source; refusing to patch unknown baseline")
if "versionCode 52" not in gradle or "versionName '12.1.24'" not in gradle:
    raise SystemExit("Expected v12.1.24 Gradle version markers")

start_marker = "async function startDualDbAdmin(){"
end_marker = "\nstartDualDbAdmin();"
if html.count(start_marker) != 1:
    raise SystemExit(f"Expected one startDualDbAdmin, found {html.count(start_marker)}")
start = html.index(start_marker)
end = html.find(end_marker, start)
if end < 0:
    raise SystemExit("startDualDbAdmin invocation anchor not found")
# Preserve the existing polling intervals after startDualDbAdmin(); verbatim.
new_startup = r"""// V12.1.25-ROUTE-BOOT-SEPARATION
async function startDualDbAdmin(){
 setAdminAuthEnabled(false);
 let route;
 // Only a route-resolution error may lock login. Session/bootstrap failures must not
 // overwrite a verified active DB route with the generic route-not-verified message.
 try{
  route=await resolveDualDbRoute(true);
 }catch(e){
  dualDbRouteReady=false;
  $('app').classList.add('hidden');
  $('login').classList.remove('hidden');
  const system=$('dbSystemStatusBadge'),hint=$('dbRouteStatusHint');
  if(system){system.textContent='ROUTE BELUM TERVERIFIKASI';system.style.color='var(--bad)';system.style.borderColor='var(--bad)';}
  if(hint)hint.textContent=routeFailureText(e)+' • detail: '+String(e?.message||e).slice(0,120);
  loginMsg(routeFailureText(e));
  setAdminAuthEnabled(false);
  if(!dualDbRouteMonitorStarted){
   dualDbRouteMonitorStarted=true;
   const retry=setInterval(async()=>{
    try{
     await resolveDualDbRoute(true);
     clearInterval(retry);
     dualDbRouteMonitorStarted=false;
     await startDualDbAdmin();
    }catch(_){/* bounded quiet retry; do not flood logs or alerts */}
   },15000);
  }
  return;
 }

 configureDbTarget(route.target,route);
 dualDbRouteReady=true;
 v12InitDbSwitch();
 setAdminAuthEnabled(true);

 try{
  sb.auth.onAuthStateChange(()=>setTimeout(()=>{
   Promise.resolve(boot()).catch(e=>reportAdminBootFailure(e));
  },0));
 }catch(e){reportAdminBootFailure(e);}

 if(!dualDbRouteMonitorStarted){
  dualDbRouteMonitorStarted=true;
  setInterval(monitorDualDbRoute,10000);
 }

 try{
  await boot();
 }catch(e){
  reportAdminBootFailure(e);
 }

 const notice=localStorage.getItem(DB_ROUTE_NOTICE_KEY);
 if(notice){
  localStorage.removeItem(DB_ROUTE_NOTICE_KEY);
  if(session)msg(notice);
  else loginMsg(notice);
 }
}
function reportAdminBootFailure(e){
 const detail=String(e?.message||e||'startup failed').slice(0,140);
 // Do not reset dualDbRouteReady here: route was independently checked and configured.
 setAdminAuthEnabled(true);
 if(!session){
  $('app').classList.add('hidden');
  $('login').classList.remove('hidden');
  const hint=$('dbRouteStatusHint');
  if(hint)hint.textContent='Rute '+(DB_TARGET==='backup'?'DB2':'DB1')+' sudah terverifikasi. Pemulihan sesi gagal; coba Masuk lagi. Detail: '+detail;
  loginMsg('Database aktif sudah terverifikasi. Silakan coba Masuk lagi.');
 }else{
  msg('Rute database terverifikasi, tetapi pemuatan dashboard gagal: '+detail,true);
 }
}"""
html = html[:start] + new_startup + html[end:]

if "V12.1.25-ROUTE-BOOT-SEPARATION" not in html or "reportAdminBootFailure" not in html:
    raise SystemExit("V12.1.25 route/boot guard did not insert")
if "Rute database terverifikasi" not in html:
    raise SystemExit("Missing separate bootstrap-failure path")
gradle = gradle.replace("versionCode 52", "versionCode 53", 1).replace("versionName '12.1.24'", "versionName '12.1.25'", 1)
HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
Path("VERSION.txt").write_text(
    "AniGames Admin Android V12.1.25 — separate global DB route verification from session/dashboard bootstrap; login remains available after a route was verified\n",
    encoding="utf-8",
)
print("PASS: Admin V12.1.25 only blocks login when route resolution itself fails; boot failure no longer resets route readiness.")
