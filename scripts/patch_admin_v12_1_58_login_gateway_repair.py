#!/usr/bin/env python3
"""V12.1.58 repair based exactly on the V12.1.53 DB Android source.

Fixes the missing setAdminAuthEnabled() frontend function, makes the relay
Supabase login non-blocking, adds precise login-stage feedback, and routes
all DB Android pages through the deployed stage-gateway Worker. Admin auth
RPC names, payloads, token format, database schema, device APIs and WoL
sidecar contracts are intentionally preserved.
"""
from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
WEB = ROOT / "android/app/src/main/assets/web"
GRADLE = ROOT / "android/app/build.gradle"
MANIFEST = ROOT / "android/app/src/main/AndroidManifest.xml"
VERSION = ROOT / "VERSION.txt"

GATEWAY = "https://ani-games-db-android-stage-gateway.anigamesready.workers.dev"
LEGACY_RELAY_HOST = "ani-games-db-android-stage-ws-relay.anigamesready.workers.dev"
OLD_LOOPBACKS = ("http://127.0.0.1:8787", "http://127.0.0.1:8788")
GATEWAY_MARKER = "ANI-ADMIN-V12.1.58-CANONICAL-STAGE-GATEWAY"
LOGIN_MARKER = "ANI-ADMIN-V12.1.58-LOGIN-ENTRY-FIX"
OWNER_MARKER = "ANI-ADMIN-V12.1.58-CANONICAL-OWNER-GUARD"
BASE_MARKER = "V12.1.53-REMOTE-PLAY-SHARED-DB-PORT-8787"
POLICY_MARKER = "V12.1.51-BILLING-STOP-PAUSE-POLICY"
BASE_PACKAGE_ID = "com.anigames.billingadmin.v153db"
TEST_PACKAGE_ID = "com.anigames.billingadmin.v158online"
PAGES = ("admin.html", "index.html", "admin-control.html")

for path in (WEB / "admin.html", WEB / "index.html", WEB / "admin-control.html", GRADLE, MANIFEST):
    if not path.is_file():
        raise SystemExit("REQUIRED_ADMIN_SOURCE_MISSING:" + str(path))

admin_path = WEB / "admin.html"
admin = admin_path.read_text(encoding="utf-8")
if BASE_MARKER not in admin:
    raise SystemExit("EXPECTED_V12_1_53_SOURCE_BASELINE_MISSING")
if POLICY_MARKER not in admin:
    raise SystemExit("V12_1_53_STOP_PAUSE_POLICY_FEATURE_MISSING")
if "admin_remote_play_dashboard" not in admin:
    raise SystemExit("V12_1_53_REMOTE_PLAY_FEATURE_MISSING")
if "function isWakeRelayOwner()" not in admin:
    raise SystemExit("V12_1_53_SHARED_OWNER_RESOLVER_MISSING")

# 1. Canonical public HTTP API front door. The ws-relay Worker is the
# internal WebSocket/DO hop; the stage-gateway Worker is the public entry.
for name in PAGES:
    path = WEB / name
    source = path.read_text(encoding="utf-8")
    if GATEWAY_MARKER not in source:
        key_line = re.search(r"(?m)^const LOCAL_API_KEY=.*;$", source)
        if not key_line:
            raise SystemExit("LOCAL_API_KEY_DECLARATION_NOT_FOUND:" + name)
        declaration = key_line.group(0)
        if source.count(declaration) != 1:
            raise SystemExit("LOCAL_API_KEY_DECLARATION_NOT_UNIQUE:" + name)
        source = source.replace(
            declaration,
            declaration + "\nconst ONLINE_GATEWAY_URL='" + GATEWAY + "';\nconst LEGACY_RELAY_HOST='" + LEGACY_RELAY_HOST + "';",
            1
        )

    api_base = r"""function localApiBase(){
 let saved='';
 try{saved=String(localStorage.getItem(LOCAL_API_KEY)||'').trim()}catch(_){}
 let target=saved||ONLINE_GATEWAY_URL,u=null;
 try{u=new URL(target)}catch(_){target=ONLINE_GATEWAY_URL;u=new URL(target)}
 const host=String(u.hostname||'').toLowerCase();
 const loopback=['127.0.0.1','localhost','::1'].includes(host);
 const stale=!saved||loopback||host===LEGACY_RELAY_HOST||u.protocol!=='https:';
 if(stale){
  target=ONLINE_GATEWAY_URL;u=new URL(target);
  try{localStorage.setItem(LOCAL_API_KEY,ONLINE_GATEWAY_URL)}catch(_){}
 }
 if(u.protocol!=='https:')throw new Error('Gateway DB Android wajib menggunakan HTTPS.');
 return u.href.replace(/\/+$/,'');
}"""
    base_pattern = re.compile(r"(?ms)^function localApiBase\(\)\s*\{.*?^\}")
    source, base_count = base_pattern.subn(lambda _: api_base, source, count=1)
    if base_count != 1:
        raise SystemExit("LOCAL_API_BASE_FUNCTION_ANCHOR_MISMATCH:" + name)

    # Replace every visible legacy mode label, but do not touch business logic.
    source = source.replace("DB Android Lokal", "DB Android Online")
    source = source.replace("Alamat API Lokal", "Alamat Gateway DB Android")
    source = source.replace("ALAMAT SERVER DATABASE", "ALAMAT GATEWAY DB ANDROID")
    source = source.replace("Login memakai database lokal Ani Games Ready. Alamat awal adalah server di perangkat ini.",
                            "Login memakai DB Android Ani Games Ready melalui gateway aman menuju Redmi.")
    for old in OLD_LOOPBACKS:
        source = source.replace(old, GATEWAY)
    source = source.replace("https://" + LEGACY_RELAY_HOST, GATEWAY)
    source += "\n<!-- " + GATEWAY_MARKER + " -->\n"
    if GATEWAY not in source or GATEWAY_MARKER not in source:
        raise SystemExit("CANONICAL_GATEWAY_DEFAULT_NOT_INSTALLED:" + name)
    for old in OLD_LOOPBACKS:
        if old in source:
            raise SystemExit("LOOPBACK_DEFAULT_REMAINS:" + name + ":" + old)
    legacy_url = "https://" + LEGACY_RELAY_HOST
    if legacy_url in source:
        pos = source.find(legacy_url)
        raise SystemExit("LEGACY_DIRECT_RELAY_URL_REMAINS:" + name + ":" + repr(source[max(0,pos-120):pos+len(legacy_url)+120]))
    if source.count(LEGACY_RELAY_HOST) != 1:
        raise SystemExit("LEGACY_RELAY_MIGRATION_GUARD_COUNT_INVALID:" + name)
    path.write_text(source, encoding="utf-8")

# 2. Define the JavaScript helper already called by V12.1.53 startup and
# health/login paths. It was referenced three times but never declared.
admin = admin_path.read_text(encoding="utf-8")
if admin.count("setAdminAuthEnabled(") < 3:
    raise SystemExit("EXPECTED_V12_1_53_ADMIN_AUTH_ENABLE_CALLS_MISSING")
if "function setAdminAuthEnabled(enabled)" not in admin:
    anchor = "async function localJson(path,body=null,method='POST',token=''){"
    if admin.count(anchor) != 1:
        raise SystemExit("LOCAL_JSON_INSERTION_ANCHOR_NOT_UNIQUE")
    helper = """function setAdminAuthEnabled(enabled){
 const root=$('login');if(!root)return;
 const allowed=enabled===true;
 root.querySelectorAll('input,button').forEach(control=>{
  if(control.matches('button.primary')&&control.dataset.loginSubmitting==='true')return;
  control.disabled=!allowed;
 });
}
"""
    admin = admin.replace(anchor, helper + anchor, 1)

# Keep response bodies safe: only a bounded server error string is surfaced;
# credentials, tokens and request bodies are never written to the page/log.
local_json = r"""async function localJson(path,body=null,method='POST',token=''){
 const headers={'content-type':'application/json','accept':'application/json'};if(token)headers.authorization='Bearer '+token;
 let response;
 try{response=await fetch(localApiBase()+path,{method,headers,cache:'no-store',...(body===null?{}:{body:JSON.stringify(body)})})}
 catch(e){throw new Error('GATEWAY_NETWORK_ERROR: '+String(e?.message||e||'fetch failed').slice(0,120))}
 const raw=await response.text().catch(()=>''),data=(()=>{try{return raw?JSON.parse(raw):{}}catch(_){return {message:raw.slice(0,160)}}})();
 if(!response.ok)throw new Error(String(data.error||data.message||'GATEWAY_HTTP_ERROR')+' [HTTP '+response.status+']');
 return data;
}"""
local_pattern = re.compile(r"(?ms)^async function localJson\(path,body=null,method='POST',token=''\)\s*\{.*?^\}")
admin, n = local_pattern.subn(lambda _: local_json, admin, count=1)
if n != 1:
    raise SystemExit("LOCAL_JSON_FUNCTION_ANCHOR_MISMATCH")

ensure_fn = r"""async function ensureActiveDbRouteForAuth(){
 setAdminAuthEnabled(false);
 try{
  const base=localApiBase();
  const data=await localJson('/health',null,'GET');
  if(data?.api!=='online'||data?.database!=='online')throw new Error('STAGE_API_OR_DATABASE_NOT_ONLINE');
  if($('localApiInput'))$('localApiInput').value=base;
  setAdminAuthEnabled(true);
  return true;
 }catch(e){
  setAdminAuthEnabled(true);
  loginMsg('Gateway Redmi belum siap: '+String(e?.message||e||'unknown error').slice(0,180));
  return false;
 }
}"""
ensure_pattern = re.compile(r"(?ms)^async function ensureActiveDbRouteForAuth\(\)\s*\{.*?^\}")
admin, n = ensure_pattern.subn(lambda _: ensure_fn, admin, count=1)
if n != 1:
    raise SystemExit("ENSURE_ACTIVE_DB_ROUTE_FUNCTION_ANCHOR_MISMATCH")

store_fn = """async function storeAdminRefreshToken(value){
 if(!value){secureRemove('admin_refresh_token');return true;}
 return secureSet('admin_refresh_token',value)===true;
}"""
store_pattern = re.compile(r"(?m)^async function storeAdminRefreshToken\(value\)\s*\{[^\r\n]*\}")
admin, n = store_pattern.subn(lambda _: store_fn, admin, count=1)
if n != 1:
    raise SystemExit("ADMIN_REFRESH_STORAGE_FUNCTION_ANCHOR_MISMATCH")

refresh_fn = r"""async function refreshLocalAdminSession(refreshToken){
 const data=await localJson('/auth/v1/token?grant_type=refresh_token',{refresh_token:refreshToken});
 if(!data?.access_token||!data?.refresh_token)throw new Error('ADMIN_REFRESH_SESSION_INVALID');
 if(!(await storeAdminRefreshToken(data.refresh_token)))throw new Error('ADMIN_REFRESH_STORAGE_FAILED');
 return data;
}"""
refresh_start = admin.find("async function refreshLocalAdminSession(refreshToken){")
refresh_end = admin.find("async function relayAccessToken(){", refresh_start)
if refresh_start < 0 or refresh_end <= refresh_start or admin.count("async function refreshLocalAdminSession(refreshToken){") != 1:
    raise SystemExit("ADMIN_REFRESH_SESSION_FUNCTION_BOUNDARY_MISMATCH")
admin = admin[:refresh_start] + refresh_fn + "\n" + admin[refresh_end:]

login_fn = r"""async function login(){
 const btn=$('login')?.querySelector('button.primary');
 if(btn){btn.dataset.loginSubmitting='true';btn.disabled=true}
 session=null;
 try{
  loginMsg('1/3 • Memeriksa koneksi gateway online Redmi...');
  if(!(await ensureActiveDbRouteForAuth()))return false;
  const username=String($('email')?.value||'').trim();
  const password=String($('password')?.value||'');
  if(!username||!password)throw new Error('USERNAME_OR_PASSWORD_REQUIRED');
  loginMsg('2/3 • Mengirim login Admin ke database...');
  session=await localJson('/auth/v1/token?grant_type=password',{email:username,password});
  if(!session?.access_token||!session?.refresh_token)throw new Error('ADMIN_LOGIN_RESPONSE_INVALID');
  if(!(await storeAdminRefreshToken(session.refresh_token)))throw new Error('ADMIN_REFRESH_STORAGE_FAILED');

  // Blynk/WoL uses a separate Supabase auth session. It must never block
  // the primary DB Android Admin login or the admin_context request.
  try{
   Promise.resolve(sb.auth.signInWithPassword({email:session.user?.email||username,password}))
    .then(result=>{if(result?.error)console.warn('Blynk/WoL relay authentication unavailable:',String(result.error.message||result.error).slice(0,120))})
    .catch(e=>console.warn('Blynk/WoL relay authentication unavailable:',String(e?.message||e).slice(0,120)));
  }catch(e){console.warn('Blynk/WoL relay authentication unavailable:',String(e?.message||e).slice(0,120))}

  loginMsg('3/3 • Login diterima. Memeriksa hak akses Admin...');
  const ready=await boot();
  return ready===true;
 }catch(e){
  session=null;
  loginMsg('Login Admin gagal: '+String(e?.message||e||'unknown error').slice(0,200));
  return false;
 }finally{
  if(btn){delete btn.dataset.loginSubmitting;btn.disabled=false}
  setAdminAuthEnabled(true);
 }
}"""
login_start = admin.find("async function login(){")
login_end = admin.find("async function signup(){", login_start)
login_count = admin.count("async function login(){")
signup_count = admin.count("async function signup(){")
if login_start < 0 or login_end <= login_start or login_count != 1 or signup_count != 1:
    raise SystemExit(
        "ADMIN_LOGIN_FUNCTION_BOUNDARY_MISMATCH:"
        + str({"login_count":login_count,"signup_count":signup_count,
               "login_start":login_start,"signup_end":login_end,
               "near_login":admin[max(0,login_start-80):login_start+160] if login_start>=0 else ""})
    )
admin = admin[:login_start] + login_fn + "\n" + admin[login_end:]

boot_fn = r"""async function boot(){
 let stage='memulihkan sesi Admin';
 try{
  if(!session){
   const refresh=secureGet('admin_refresh_token');
   if(refresh){
    try{session=await refreshLocalAdminSession(refresh)}
    catch(e){await storeAdminRefreshToken('');session=null;console.warn('Admin refresh session unavailable:',String(e?.message||e).slice(0,120))}
   }
  }
  if(!session?.access_token){
   $('login').classList.remove('hidden');$('app').classList.add('hidden');
   loginMsg('Sesi Admin belum tersedia. Masukkan username/email dan password.');
   return false;
  }
  stage='memeriksa gateway dan database';
  if(!(await ensureActiveDbRouteForAuth()))throw new Error('STAGE_GATEWAY_NOT_READY');
  stage='memvalidasi akun dan hak akses Admin';
  const context=await rpc('admin_context');
  if(!context||typeof context!=='object'||!context.role||!Array.isArray(context.orgs)){
   throw new Error('ADMIN_CONTEXT_RESPONSE_INVALID');
  }
  ctx=context;orgs=ctx.orgs||[];
  stage='menyiapkan dashboard Admin';
  if(ctx.role==='owner'){refreshIoTStatus();ensureNativeNotificationPermission()}
  $('role').textContent=ctx.role||'admin';
  $('who').textContent=session.user?.email||session.user?.user_metadata?.username||'Admin';
  renderOrgs();applyPairingRoleUI();applyRemotePlayRoleUI();
  $('login').classList.add('hidden');$('app').classList.remove('hidden');
  if(orgs.length){
   currentOrg=orgs[0];$('orgSelect').value=currentOrg.id;
   stage='memuat data dashboard';
   await refresh();
  }else{
   currentOrg=null;
  }
  return true;
 }catch(e){
  $('app').classList.add('hidden');$('login').classList.remove('hidden');
  loginMsg('Login token diterima, tetapi dashboard gagal pada tahap '+stage+': '+String(e?.message||e||'unknown error').slice(0,180));
  return false;
 }
}"""
boot_pattern = re.compile(r"(?ms)^async function boot\(\)\s*\{.*?^\}")
admin, n = boot_pattern.subn(lambda _: boot_fn, admin, count=1)
if n != 1:
    raise SystemExit("ADMIN_BOOT_FUNCTION_ANCHOR_MISMATCH")

start_admin_fn = """async function startLocalAdmin(){
 setAdminAuthEnabled(true);
 try{sb.auth.onAuthStateChange(()=>setTimeout(()=>{if(session)refreshIoTStatus()},0))}catch(_){}
 return await boot();
}"""
start_pattern = re.compile(r"(?m)^async function startLocalAdmin\(\)\s*\{[^\r\n]*\}")
admin, n = start_pattern.subn(lambda _: start_admin_fn, admin, count=1)
if n != 1:
    raise SystemExit("START_LOCAL_ADMIN_FUNCTION_ANCHOR_MISMATCH")

# 3. Use the existing canonical Owner resolver for policy/Pairing/Remote Play.
def replace_exact_function(source, name, replacement):
    pattern = re.compile(r"(?m)^function " + re.escape(name) + r"\(\)\s*\{[^\r\n]*\}")
    source, count = pattern.subn(lambda _: replacement, source, count=1)
    if count != 1:
        raise SystemExit("OWNER_FUNCTION_ANCHOR_MISMATCH:" + name)
    return source

admin = replace_exact_function(
    admin, "billingStopPausePolicyIsOwner",
    "function billingStopPausePolicyIsOwner(){return typeof isWakeRelayOwner==='function'&&isWakeRelayOwner()===true}"
)
admin = replace_exact_function(
    admin, "isRemotePlayOwner",
    "function isRemotePlayOwner(){return typeof isWakeRelayOwner==='function'&&isWakeRelayOwner()===true}"
)
free_owner = r"""function freeTestPolicyIsOwner(){
 return typeof isWakeRelayOwner==='function'&&isWakeRelayOwner()===true;
}"""
free_pattern = re.compile(r"(?ms)^function freeTestPolicyIsOwner\(\)\s*\{.*?^\}")
admin, n = free_pattern.subn(lambda _: free_owner, admin, count=1)
if n != 1:
    raise SystemExit("FREE_TEST_OWNER_FUNCTION_ANCHOR_MISMATCH")

apply_start = admin.find("function applyPairingRoleUI(){")
apply_end = admin.find("function selectOrg(){", apply_start)
if apply_start < 0 or apply_end <= apply_start:
    raise SystemExit("PAIRING_ROLE_UI_FUNCTION_BOUNDARY_MISMATCH")
apply_fn = """function applyPairingRoleUI(){
 const owner=typeof isWakeRelayOwner==='function'&&isWakeRelayOwner()===true;
 const freeTestNav=$('freeTestPolicyNav');if(freeTestNav)freeTestNav.classList.toggle('hidden',!owner);
 const freeTestCard=$('freeTestPolicyCard');if(freeTestCard)freeTestCard.classList.toggle('hidden',!owner);
 const stopPauseNav=$('billingStopPausePolicyNav');if(stopPauseNav)stopPauseNav.classList.toggle('hidden',!owner);
 const stopPauseCard=$('billingStopPausePolicyCard');if(stopPauseCard)stopPauseCard.classList.toggle('hidden',!owner);
 const nav=$('pairingNav'),sec=$('pairing');
 if(nav)nav.classList.toggle('hidden',!owner);
 if(sec)sec.classList.toggle('hidden',!owner);
 if(owner&&$('enrollOrg'))$('enrollOrg').innerHTML=orgs.map(o=>'<option value="'+o.id+'">'+esc(o.name)+' • '+esc(o.kind)+'</option>').join('');
}
"""
admin = admin[:apply_start] + apply_fn + admin[apply_end:]
admin = admin.replace(
    "if(id==='pairing'&&ctx?.role!=='owner')return;",
    "if(id==='pairing'&&!isWakeRelayOwner())return;"
)
admin = admin.replace(
    "if(id==='remotePlay'&&!isRemotePlayOwner())return;",
    "if(id==='remotePlay'&&!isRemotePlayOwner())return;"
)

# Confirm auth contracts and ensure the Supabase relay request is not awaited.
if "function setAdminAuthEnabled(enabled)" not in admin:
    raise SystemExit("MISSING_SET_ADMIN_AUTH_ENABLED_DEFINITION")
if admin.count("setAdminAuthEnabled(") != 6:
    raise SystemExit("ADMIN_AUTH_ENABLE_CALL_COUNT_UNEXPECTED")
if "await sb.auth.signInWithPassword" in admin:
    raise SystemExit("RELAY_SUPABASE_LOGIN_STILL_BLOCKS_ADMIN_LOGIN")
if "localJson('/auth/v1/token?grant_type=password'" not in admin:
    raise SystemExit("V12_1_53_PRIMARY_ADMIN_AUTH_ROUTE_CHANGED")
if "rpc('admin_context')" not in admin:
    raise SystemExit("V12_1_53_ADMIN_CONTEXT_RPC_CHANGED")
if "admin_get_billing_stop_pause_policy" not in admin or "admin_set_billing_stop_pause_policy" not in admin:
    raise SystemExit("STOP_PAUSE_POLICY_RPC_MISSING")
if "admin_remote_play_dashboard" not in admin or "wol_relay_probe_request" not in admin:
    raise SystemExit("REMOTE_PLAY_OR_WOL_FEATURE_MISSING")
if "function isWakeRelayOwner()" not in admin:
    raise SystemExit("CANONICAL_OWNER_RESOLVER_REMOVED")
admin += "\n<!-- " + LOGIN_MARKER + " -->\n<!-- " + OWNER_MARKER + " -->\n"
admin_path.write_text(admin, encoding="utf-8")

# The online Admin login form always presents the canonical gateway address.
for name in PAGES:
    source=(WEB/name).read_text(encoding="utf-8")
    if GATEWAY not in source or GATEWAY_MARKER not in source:
        raise SystemExit("GATEWAY_MARKER_OR_URL_MISSING:" + name)
    if ("https://" + LEGACY_RELAY_HOST) in source:
        raise SystemExit("LEGACY_DIRECT_RELAY_URL_REMAINS:" + name)
    if source.count(LEGACY_RELAY_HOST) != 1:
        raise SystemExit("LEGACY_RELAY_MIGRATION_GUARD_COUNT_INVALID_FINAL:" + name)
    for old in OLD_LOOPBACKS:
        if old in source:
            raise SystemExit("LOOPBACK_DEFAULT_REMAINS_FINAL:" + name)
    (WEB/name).write_text(source,encoding="utf-8")

# 4. Safe test identity: the stable V12.1.53 package is never overwritten.
gradle=GRADLE.read_text(encoding="utf-8")
manifest=MANIFEST.read_text(encoding="utf-8")
if gradle.count("versionCode 81")!=1 or gradle.count("versionName '12.1.53'")!=1:
    raise SystemExit("V12_1_53_GRADLE_VERSION_ANCHOR_MISMATCH")
if gradle.count("applicationId '" + BASE_PACKAGE_ID + "'")!=1:
    raise SystemExit("V12_1_53_PACKAGE_ID_ANCHOR_MISMATCH")
gradle=gradle.replace("applicationId '" + BASE_PACKAGE_ID + "'","applicationId '" + TEST_PACKAGE_ID + "'",1)
gradle=gradle.replace("versionCode 81","versionCode 85",1)
gradle=gradle.replace("versionName '12.1.53'","versionName '12.1.58'",1)
label_old='android:label="AniGames Admin V12.1.53 DB Android"'
label_new='android:label="AniGames Admin Online V12.1.58 SAFE TEST"'
if manifest.count(label_old)!=1:
    raise SystemExit("V12_1_53_MANIFEST_LABEL_ANCHOR_MISMATCH")
manifest=manifest.replace(label_old,label_new,1)

GRADLE.write_text(gradle,encoding="utf-8")
MANIFEST.write_text(manifest,encoding="utf-8")
VERSION.write_text(
    "AniGames Admin Online V12.1.58 SAFE TEST — exact V12.1.53 base; canonical stage-gateway URL; fixed missing Admin auth helper; non-blocking Blynk/WoL sidecar login; staged auth diagnostics; separate package com.anigames.billingadmin.v158online.\n",
    encoding="utf-8"
)
print("PASS: exact V12.1.53 Admin DB Android source is the patch base.")
print("PASS: missing setAdminAuthEnabled() is defined; Admin login no longer stops on ReferenceError.")
print("PASS: canonical stage-gateway is the default on Admin, Billing login and Billing Control.")
print("PASS: the ws-relay host and loopback defaults are migrated to stage-gateway.")
print("PASS: primary /auth/v1/token and admin_context contracts are unchanged.")
print("PASS: Blynk/WoL Supabase auth runs in background and cannot block Admin login.")
print("PASS: Stop/Pause, Free Test, Pairing, Remote Play, and WoL handlers retain the canonical Owner resolver.")
print("PASS: V12.1.53 business APIs are preserved and APK uses an isolated SAFE TEST package.")
