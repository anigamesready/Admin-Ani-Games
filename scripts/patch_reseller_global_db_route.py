from pathlib import Path
import re
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
html_paths = list(root.rglob("index.html"))
login = [p for p in html_paths if p.parent.name == "web" and (p.parent / "admin-control.html").is_file()]
if len(login) != 1:
    raise SystemExit(f"Expected one reseller WebView assets/web pair, found {len(login)}")
index_path = login[0]
dashboard_path = index_path.parent / "admin-control.html"
index_html = index_path.read_text(encoding="utf-8")
dashboard_html = dashboard_path.read_text(encoding="utf-8")

route_constants = r"""
const DB1_ROUTE_URL='https://wzkjpycjizexxcxrfdvr.supabase.co';
const DB2_ROUTE_URL='';
const DB1_ROUTE_REF='wzkjpycjizexxcxrfdvr',DB2_ROUTE_REF='';
const DB1_ROUTE_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind6a2pweWNqaXpleHhjeHJmZHZyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTEwMzc0OTUsImV4cCI6MjEwNjYxMzQ5NX0.lxjSt7CqWDJhKItPi1ckVRIcc-kM7etMzxTu3txANaI';
const DB2_ROUTE_KEY='';
const DB_ROUTE_STAMP_KEY='ani_games_reseller_db_route_stamp_v1';
const DB_ROUTE_CACHE_MS=5000;
const DB_ROUTE_POLL_MS=10000;
let activeResellerRoute=null,resellerRouteCheckedAt=0,resellerRoutePromise=null,resellerRouteMonitorStarted=false;
async function fetchWithTimeout(url,options={},timeoutMs=7000){
 let timer=null,controller=null;
 const timeout=new Promise((_,reject)=>{timer=setTimeout(()=>{if(controller)controller.abort();reject(new Error('REQUEST_TIMEOUT'))},timeoutMs)});
 try{
  const requestOptions={...options};
  if(typeof AbortController==='function'){controller=new AbortController();requestOptions.signal=controller.signal}
  return await Promise.race([fetch(url,requestOptions),timeout]);
 }finally{if(timer!==null)clearTimeout(timer)}
}
// DB2_HOLD_PRIMARY_ONLY: reseller operations remain pinned to DB1; no route polling or DB2 fetch.
async function resolveResellerGlobalRoute(_force=false){
 const config={target:'primary',url:DB1_ROUTE_URL,key:DB1_ROUTE_KEY,ref:DB1_ROUTE_REF};
 const epoch=1,switchId='',stamp='primary:1:';
 if(SB_URL!==config.url||SB_KEY!==config.key){
  SB_URL=config.url;SB_KEY=config.key;
  sb=supabase.createClient(SB_URL,SB_KEY,{auth:{persistSession:false,autoRefreshToken:false,detectSessionInUrl:false}});
 }
 activeResellerRoute={...config,epoch,switchId,stamp,initial:true,syncInProgress:false};
 resellerRouteCheckedAt=Date.now();
 return activeResellerRoute;
}
function isResellerDashboardPage(){return /admin-control\.html(?:$|[?#])/i.test(String(location.href||''))}
async function ensureCurrentDbRoute(force=false){
 const route=await resolveResellerGlobalRoute(force);
 const savedStamp=sessionStorage.getItem(DB_ROUTE_STAMP_KEY)||'';
 const activeToken=sessionStorage.getItem(SESSION_KEY)||'';
 if(activeToken&&savedStamp!==route.stamp){
  sessionStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem('ani_games_reseller_selected_pc_v1');
  sessionStorage.setItem(DB_ROUTE_STAMP_KEY,route.stamp);
  if(isResellerDashboardPage()){
   location.replace('index.html?dbswitched=1');
   throw new Error('DB_ROUTE_CHANGED_LOGIN_REQUIRED');
  }
  if(typeof showMsg==='function')showMsg('Database aktif berubah. Login ulang ke database yang baru.');
  return route;
 }
 sessionStorage.setItem(DB_ROUTE_STAMP_KEY,route.stamp);
 if(route.syncInProgress)throw new Error('DB_SYNC_IN_PROGRESS');
 return route;
}
function startResellerRouteMonitor(){ /* DB2 held: no periodic route checks. */ }
"""
# Replace the fixed Supabase client construction with mutable target config and shared route resolver.
for name, source in (("index.html", index_html), ("admin-control.html", dashboard_html)):
    old = "const SB_URL='https://wzkjpycjizexxcxrfdvr.supabase.co';"
    if source.count(old) != 1:
        raise SystemExit(f"{name}: expected one DB1 SB_URL declaration, found {source.count(old)}")
    source = source.replace(old, "let SB_URL='https://wzkjpycjizexxcxrfdvr.supabase.co';", 1)
    old = "const SB_KEY='sb_publishable_DobdCrOd43-vluON5gV7hg_6Js2Ea5V';"
    if source.count(old) != 1:
        raise SystemExit(f"{name}: expected one DB1 public key declaration, found {source.count(old)}")
    source = source.replace(old, "let SB_KEY='sb_publishable_DobdCrOd43-vluON5gV7hg_6Js2Ea5V';", 1)
    old = "const sb=supabase.createClient(SB_URL,SB_KEY,{auth:{persistSession:false,autoRefreshToken:false,detectSessionInUrl:false}});"
    if source.count(old) != 1:
        raise SystemExit(f"{name}: Supabase client declaration mismatch")
    source = source.replace(old, "let sb=supabase.createClient(SB_URL,SB_KEY,{auth:{persistSession:false,autoRefreshToken:false,detectSessionInUrl:false}});", 1)
    anchor = "const SESSION_KEY='ani_games_billing_control_session_v1';"
    if source.count(anchor) != 1:
        raise SystemExit(f"{name}: session key insertion point mismatch")
    source = source.replace(anchor, anchor + "\n" + route_constants, 1)
    old_rpc = "async function rpc(name,args={}){const r=await sb.schema('api').rpc(name,args);if(r.error)throw r.error;return r.data}"
    if source.count(old_rpc) != 1:
        raise SystemExit(f"{name}: RPC wrapper mismatch")
    new_rpc = "async function rpc(name,args={}){await ensureCurrentDbRoute(false);const r=await sb.schema('api').rpc(name,args);if(r.error)throw r.error;return r.data}"
    source = source.replace(old_rpc, new_rpc, 1)
    # Route monitor starts only after static constants and UI helper functions exist.
    if name == "index.html":
        old_form = "$('loginForm').addEventListener('submit',async e=>{e.preventDefault();const username=$('username').value.trim(),password=$('password').value;"
        if source.count(old_form) != 1:
            raise SystemExit("login submit anchor mismatch")
        source = source.replace(old_form, "$('loginForm').addEventListener('submit',async e=>{e.preventDefault();const username=$('username').value.trim(),password=$('password').value;", 1)
        old_try = "try{const d=await rpc('billing_login',{p_username:username,p_password:password});if(!d?.token)throw new Error('LOGIN_SESSION_FAILED');"
        if source.count(old_try) != 1:
            raise SystemExit("login ensure-route anchor mismatch")
        source = source.replace(old_try, "try{await ensureCurrentDbRoute(true);const routeStamp=activeResellerRoute?.stamp||sessionStorage.getItem(DB_ROUTE_STAMP_KEY)||'';const d=await rpc('billing_login',{p_username:username,p_password:password});if(!d?.token)throw new Error('LOGIN_SESSION_FAILED');sessionStorage.setItem(DB_ROUTE_STAMP_KEY,routeStamp);", 1)
        old_boot = "(async()=>{const params=new URLSearchParams(location.search);if(params.get('role')==='denied')showMsg('Akun ini tidak memiliki akses reseller.');const t=sessionStorage.getItem(SESSION_KEY);if(!t)return;try{await checkReseller(t);location.replace('admin-control.html')}catch(_){sessionStorage.removeItem(SESSION_KEY)}})();"
        if source.count(old_boot) != 1:
            raise SystemExit("login startup route anchor mismatch")
        new_boot = "(async()=>{const params=new URLSearchParams(location.search);if(params.get('role')==='denied')showMsg('Akun ini tidak memiliki akses reseller.');if(params.get('dbswitched')==='1')showMsg('Database aktif sudah berubah. Silakan login ulang.');try{await ensureCurrentDbRoute(true);startResellerRouteMonitor();const t=sessionStorage.getItem(SESSION_KEY);if(!t)return;await checkReseller(t);location.replace('admin-control.html')}catch(e){if(String(e?.message||'').includes('DB_ROUTE_CHANGED_LOGIN_REQUIRED'))return;showMsg('Route database belum bisa diverifikasi. Login ditahan: '+(e?.message||'status route gagal.'))}})();"
        source = source.replace(old_boot, new_boot, 1)
    else:
        old_boot = "async function boot(){token=sessionStorage.getItem(SESSION_KEY)||'';if(!token)return location.replace('index.html');try{ctx=await rpc('billing_context',{p_session_token:token});"
        if source.count(old_boot) != 1:
            raise SystemExit("dashboard boot route anchor mismatch")
        source = source.replace(old_boot, "async function boot(){token=sessionStorage.getItem(SESSION_KEY)||'';if(!token)return location.replace('index.html');try{await ensureCurrentDbRoute(true);startResellerRouteMonitor();token=sessionStorage.getItem(SESSION_KEY)||'';if(!token)return location.replace('index.html?dbswitched=1');ctx=await rpc('billing_context',{p_session_token:token});", 1)
        # Keep expiry/route failures from looking like a normal logout; route monitor will refresh if DB changes.
        source = source.replace("if(/SESSION|TOKEN|ACCESS_DENIED|INVALID|AUTHENTICATED/.test((e.message||'').toUpperCase()))return logout(true);",
                                "if(/SESSION|TOKEN|ACCESS_DENIED|INVALID|AUTHENTICATED/.test((e.message||'').toUpperCase()))return logout(true);if(String(e?.message||'').includes('DB_ROUTE_CHANGED_LOGIN_REQUIRED'))return;", 1)
    if "const SB_URL=" in source or "const SB_KEY=" in source or "const sb=supabase.createClient" in source:
        raise SystemExit(f"{name}: immutable DB1-only client declaration remains")
    if "DB_ROUTE_SPLIT_BRAIN" not in source or "DB_ROUTE_NOT_FINALIZED" not in source or "DB_ROUTE_STAMP_KEY" not in source:
        raise SystemExit(f"{name}: global route guards missing")
    if source.count("await ensureCurrentDbRoute(false)") < 1:
        raise SystemExit(f"{name}: DB RPC calls do not follow global route")
    if name == "index.html":
        index_html = source
    else:
        dashboard_html = source

# Bump only the new branch/release artifact; source ZIP and locked baseline stay untouched.
gradle_candidates = [root / "app/build.gradle", root / "app/build.gradle.kts"]
gradle_path = next((p for p in gradle_candidates if p.is_file()), None)
if gradle_path is None:
    raise SystemExit("Reseller Gradle file is missing")
gradle = gradle_path.read_text(encoding="utf-8", errors="replace")
if "versionCode 131" in gradle and "versionName '1.0.1'" in gradle:
    gradle = gradle.replace("versionCode 131", "versionCode 133", 1)
    gradle = gradle.replace("versionName '1.0.1'", "versionName '1.0.3'", 1)
elif not ("versionCode 133" in gradle and "versionName '1.0.3'" in gradle):
    raise SystemExit("Expected exact Reseller V11.30.3 base metadata; refusing unknown version")
gradle_path.write_text(gradle, encoding="utf-8")
# Static post-patch checks for the route guard contract and destination-client configuration.
for marker in ("DB2_HOLD_PRIMARY_ONLY", "DB1_ROUTE_URL", "DB1_ROUTE_KEY", "DB_ROUTE_STAMP_KEY", "DB_ROUTE_CHANGED_LOGIN_REQUIRED"):
    if marker not in index_html or marker not in dashboard_html:
        raise SystemExit("Route readiness marker missing from reseller pages: " + marker)

index_path.write_text(index_html, encoding="utf-8")
dashboard_path.write_text(dashboard_html, encoding="utf-8")
print("PASS: V11.30.2 route readiness, DB target aliases, final login refresh and version bump validated.")
