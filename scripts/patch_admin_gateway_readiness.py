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
if "async function refreshGatewayReadiness()" not in html:
    anchor = "async function verifyDb2OwnerLogin(){"
    if html.count(anchor) != 1:
        raise SystemExit("Owner login-verification anchor missing or duplicated")
    helper = r"""
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

# Make the coordinated switch perform a fresh readiness probe and reload both route rows afterwards.
switch_anchor = "a=d1.route;b=d2.route;\n   if(a.active_target!==current||b.active_target!==current"
switch_replacement = """a=d1.route;b=d2.route;
   await refreshGatewayReadiness();
   [d1,d2]=await Promise.all([
    globalRouteStatus(DB1_URL,DB1_ROUTE_KEY,'wzkjpycjizexxcxrfdvr'),
    globalRouteStatus(DB2_URL,DB2_ROUTE_KEY,'xcdbipgsvohesxhxydep')
   ]);
   a=d1.route;b=d2.route;
   if(a.active_target!==current||b.active_target!==current"""
if html.count(switch_anchor) != 1:
    raise SystemExit(f"Expected one post-sync global route gate; found {html.count(switch_anchor)}")
html = html.replace(switch_anchor, switch_replacement, 1)

# Put the exact gate failure into the status string so a blocked switch has a concrete reason.
html = html.replace(
 "const verifiedGateway=readyGatewayAfterAuth;",
 "const verifiedGateway=readyGatewayAfterAuth;if(!verifiedGateway&&gatewayReadinessDetail)ready.gatewayReason=gatewayReadinessDetail;",
 1
)
html = html.replace(
 "Data/schema/auth parity lolos, tetapi gateway bersama belum terverifikasi. Database tujuan TIDAK boleh diaktifkan.",
 "Data/schema/auth parity lolos, tetapi gateway bersama belum terverifikasi. Database tujuan TIDAK boleh diaktifkan. '+(ready.gatewayReason||'')+'",
 1
) if "Data/schema/auth parity lolos, tetapi gateway bersama belum terverifikasi. Database tujuan TIDAK boleh diaktifkan." in html else html

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
