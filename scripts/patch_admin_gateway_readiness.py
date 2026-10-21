from pathlib import Path
import re

HTML = Path("android/app/src/main/assets/web/admin.html")
GRADLE = Path("android/app/build.gradle")
html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")
marker = "V12.1.20-DB-ROUTE-AUTH-GATEWAY-READINESS"
if marker in html:
    print("PASS: V12.1.20 Auth/gateway readiness patch already applied.")
    raise SystemExit(0)

if "async function coreDbCall(action,payload={})" not in html:
    raise SystemExit("Expected Admin V12.1.19 core DB routing source")
if "async function requestSharedDbRouteSwitch(" not in html:
    route_switch_helper = r"""
async function requestSharedDbRouteSwitch(target,reason){
 if(!dualDbRouteReady)throw new Error('GLOBAL_ROUTE_NOT_VERIFIED');
 const token=await adminAccessToken();
 if(!token)throw new Error('OWNER_SESSION_REQUIRED');
 const peerApiKey=DB_TARGET==='backup'?DB1_KEY:DB2_KEY;
 const response=await fetch(SB_URL+'/functions/v1/db-route-readiness',{
  method:'POST',
  headers:{apikey:SB_KEY,'content-type':'application/json',authorization:'Bearer '+token},
  body:JSON.stringify({action:'switch-global',target,reason,peerApiKey,gatewayApiKey:DB1_ROUTE_KEY}),
  cache:'no-store'
 });
 const data=await response.json().catch(()=>({}));
 if(!response.ok||data?.ok!==true||data?.finalized!==true){
  throw new Error(String(data?.error||('GLOBAL_DB_SWITCH_HTTP_'+response.status)));
 }
 return data;
}
"""
    helper_anchor = "async function refreshGatewayReadiness(){"
    if html.count(helper_anchor) != 1:
        raise SystemExit("Shared route switch helper anchor missing")
    html = html.replace(helper_anchor, route_switch_helper + "\n" + helper_anchor, 1)

if "async function refreshGatewayReadiness()" not in html:
    anchor = "async function verifyDb2OwnerLogin(){"
    if html.count(anchor) != 1:
        raise SystemExit("Owner login-verification anchor missing or duplicated")
    helper = r"""
// V12.1.20-DB-ROUTE-AUTH-GATEWAY-READINESS
async function refreshGatewayReadiness(){
 if(!dualDbRouteReady)throw new Error('GLOBAL_ROUTE_NOT_VERIFIED');
 const token=await adminAccessToken();
 if(!token)throw new Error('OWNER_SESSION_REQUIRED');
 const peerApiKey=DB_TARGET==='backup'?DB1_KEY:DB2_KEY;
 const response=await fetch(SB_URL+'/functions/v1/db-route-readiness',{
  method:'POST',
  headers:{apikey:SB_KEY,'content-type':'application/json',authorization:'Bearer '+token},
  body:JSON.stringify({action:'mark-ready',peerApiKey,gatewayApiKey:DB1_ROUTE_KEY}),
  cache:'no-store'
 });
 const data=await response.json().catch(()=>({}));
 if(!response.ok||data?.ok!==true||data?.gatewayReady!==true){
  throw new Error(String(data?.error||('DB_ROUTE_GATEWAY_READINESS_HTTP_'+response.status)));
 }
 return data;
}
"""
    html = html.replace(anchor, helper + "\n" + anchor, 1)

# Re-enable the genuine per-account login test. It verifies the password on the other Supabase Auth
# instance; it does not copy passwords or Auth users.
hidden = '<span class="muted">Auth Admin dikelola backend/per project; tidak ikut Sync.</span>'
button = '<button type="button" id="dbSyncVerifyOwner" onclick="verifyDb2OwnerLogin()">Verifikasi login DB tujuan</button>'
if hidden in html:
    html = html.replace(hidden, button, 1)
elif button not in html:
    raise SystemExit("Could not restore owner login verification button")

# After data-hash and account-login verification, invoke the shared route/Gateway proof.
old_auth = "const ready=await dbSyncCall('mark-ready',{runId});readyGatewayAfterAuth=ready.gatewayReady===true;"
if html.count(old_auth) != 1:
    raise SystemExit(f"Expected exactly one Auth stage readiness call; found {html.count(old_auth)}")
new_auth = """const ready=await dbSyncCall('mark-ready',{runId});readyGatewayAfterAuth=ready.gatewayReady===true;
     let gatewayReadinessDetail='';
     try{const gatewayProof=await refreshGatewayReadiness();readyGatewayAfterAuth=gatewayProof.gatewayReady===true;if(readyGatewayAfterAuth)ready.gatewayReady=true;}
     catch(gatewayError){readyGatewayAfterAuth=false;ready.gatewayReady=false;gatewayReadinessDetail=String(gatewayError?.message||gatewayError);ready.gatewayReason=gatewayReadinessDetail;}"""
html = html.replace(old_auth, new_auth, 1)

old_switch = "const switched=await coreDbCall('switch-global',{target,reason:'Admin V12.1.17 simple scoped DB switch'});"
if html.count(old_switch) != 1:
    raise SystemExit(f"Expected one global switch backend call; found {html.count(old_switch)}")
html = html.replace(old_switch, "const switched=await requestSharedDbRouteSwitch(target,'Admin V12.1.20 Auth/Gateway guarded global switch');", 1)

# Make the coordinated switch perform a fresh readiness probe and refresh both route rows.
sync_anchor = "const sync=await coreDbCall('sync-core');"
if html.count(sync_anchor) != 1:
    raise SystemExit(f"Expected one final sync anchor; found {html.count(sync_anchor)}")
sync_pos = html.find(sync_anchor) + len(sync_anchor)
tail = html[sync_pos:]
switch_pattern = re.compile(r"a=d1\\.route;b=d2\\.route;\\s*if\\(a\\.active_target!==current\\|\\|b\\.active_target!==current")
switch_replacement = """a=d1.route;b=d2.route;
   await refreshGatewayReadiness();
   [d1,d2]=await Promise.all([
    globalRouteStatus(DB1_URL,DB1_ROUTE_KEY,'wzkjpycjizexxcxrfdvr'),
    globalRouteStatus(DB2_URL,DB2_ROUTE_KEY,'xcdbipgsvohesxhxydep')
   ]);
   a=d1.route;b=d2.route;
   if(a.active_target!==current||b.active_target!==current"""
tail, switch_count = switch_pattern.subn(switch_replacement, tail, count=1)
if switch_count != 1:
    raise SystemExit(f"Expected one post-sync global route gate; found {switch_count}")
html = html[:sync_pos] + tail

# Display the actual Gateway/readiness rejection reason in the login-test status.
old_status = "dbSyncStatus(ready.gatewayReady?'Database tujuan lolos hash/login/gateway. Penulisan ditahan agar perpindahan global dapat difinalisasi.':'Data/schema/auth parity lolos, tetapi gateway bersama belum terverifikasi. Database tujuan TIDAK boleh diaktifkan.',ready.gatewayReady!==true);"
new_status = "dbSyncStatus(ready.gatewayReady?'Database tujuan lolos hash/login/gateway. Penulisan ditahan agar perpindahan global dapat difinalisasi.':'Data/schema/auth parity lolos, tetapi gateway bersama belum terverifikasi. Database tujuan TIDAK boleh diaktifkan. '+(gatewayReadinessDetail?' ('+gatewayReadinessDetail+')':''),ready.gatewayReady!==true);"
if html.count(old_status) != 1:
    raise SystemExit(f"Expected one deferred-login status line; found {html.count(old_status)}")
html = html.replace(old_status, new_status, 1)

if "async function refreshGatewayReadiness()" not in html or "await refreshGatewayReadiness();" not in html:
    raise SystemExit("Gateway readiness calls were not inserted")
if "Verifikasi login DB tujuan" not in html or "DB_ROUTE_GATEWAY_READINESS_HTTP_" not in html:
    raise SystemExit("Auth/Gateway user path missing after patch")

old_v = "versionCode 47"
new_v = "versionCode 48"
old_name = "versionName '12.1.19'"
new_name = "versionName '12.1.20'"
if old_v not in gradle or old_name not in gradle:
    raise SystemExit("Expected V12.1.19 Gradle version markers")
gradle = gradle.replace(old_v, new_v, 1).replace(old_name, new_name, 1)

HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
Path("VERSION.txt").write_text("AniGames Admin Android V12.1.20 — global Auth/gateway readiness + guarded DB switch\n", encoding="utf-8")
print("PASS: Admin V12.1.20 re-enables cross-DB owner login-test, probes the shared gateway and refreshes both route rows before global switch.")
