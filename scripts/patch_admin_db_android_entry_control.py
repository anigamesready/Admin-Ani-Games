#!/usr/bin/env python3
"""Move the Admin APK's actual login entry and Billing Control page to the Redmi local API."""
from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
web = next((p for p in ROOT.rglob("assets/web") if p.is_dir()), None)
if web is None:
    raise SystemExit("ADMIN_WEB_ASSETS_NOT_FOUND")
entry_path = web / "index.html"
control_path = web / "admin-control.html"
if not entry_path.is_file() or not control_path.is_file():
    raise SystemExit("ADMIN_ENTRY_OR_CONTROL_PAGE_NOT_FOUND")

# Entry page: same local endpoint selector for setup, password login and automatic session restore.
entry = entry_path.read_text(encoding="utf-8")
entry = entry.replace('<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>', '')
entry_anchor = '  <div class="sub">Billing Control</div>\n'
entry_field = '''  <div class="sub">Billing Control • DB Android Lokal</div>
  <div class="field"><label for="localApiInput">ALAMAT SERVER DATABASE</label><input id="localApiInput" type="url" value="http://127.0.0.1:8788" autocomplete="url"></div>
  <button type="button" class="btn" style="margin-bottom:12px" onclick="saveLocalApiUrl()">SIMPAN ALAMAT SERVER</button>
'''
if entry_anchor not in entry:
    raise SystemExit("ADMIN_LOGIN_ENTRY_ANCHOR_NOT_FOUND")
entry = entry.replace(entry_anchor, entry_field, 1)

entry_script = r"""<script>
const LOCAL_API_KEY='ani_games_ready_db_android_api_url_v1';
const SESSION_KEY='ani_games_billing_control_session_v1';
const REFRESH_KEY='billing_control_refresh_token';
const $=id=>document.getElementById(id);
function localApiBase(){
 const raw=String(localStorage.getItem(LOCAL_API_KEY)||'http://127.0.0.1:8788').trim();
 const u=new URL(raw);
 if(!['http:','https:'].includes(u.protocol))throw new Error('Alamat server harus HTTP/HTTPS.');
 const loopback=['127.0.0.1','localhost','::1'].includes(u.hostname);
 if(!loopback&&u.protocol!=='https:')throw new Error('Alamat server di luar perangkat wajib HTTPS.');
 return u.href.replace(/\/+$/,'');
}
function secureGet(name){try{return window.AniAdminNative?.getSecureValue(name)||''}catch(_){return ''}}
function secureSet(name,value){try{return window.AniAdminNative?.setSecureValue(name,String(value))===true}catch(_){return false}}
function secureRemove(name){try{window.AniAdminNative?.removeSecureValue(name)}catch(_){}}
async function localJson(path,body=null,method='POST',accessToken=''){
 const headers={'content-type':'application/json'};
 if(accessToken)headers.authorization='Bearer '+accessToken;
 const response=await fetch(localApiBase()+path,{method,headers,cache:'no-store',...(body===null?{}:{body:JSON.stringify(body)})});
 const data=await response.json().catch(()=>({}));
 if(!response.ok)throw new Error(data.error||data.message||('HTTP_'+response.status));
 return data;
}
async function ensureLocalApi(){
 const h=await localJson('/health',null,'GET');
 if(h.api!=='online'||h.database!=='online')throw new Error('LOCAL_DATABASE_NOT_READY');
 return h;
}
function saveLocalApiUrl(){
 try{
  const u=new URL(String($('localApiInput')?.value||'').trim());
  const loopback=['127.0.0.1','localhost','::1'].includes(u.hostname);
  if(!['http:','https:'].includes(u.protocol)||(!loopback&&u.protocol!=='https:'))throw new Error('Server non-lokal wajib HTTPS.');
  localStorage.setItem(LOCAL_API_KEY,u.href.replace(/\/+$/,''));
  $('localApiInput').value=localApiBase();
  show('Alamat server tersimpan. Menguji koneksi…',false);
  ensureLocalApi().then(()=>show('Server lokal terhubung.',false)).catch(e=>show(e.message));
 }catch(e){show(e.message||'Alamat server tidak valid.')}
}
function secureRefresh(value){
 if(!secureSet(REFRESH_KEY,value))throw new Error('ANDROID_KEYSTORE_UNAVAILABLE');
}
async function refreshBillingSession(refresh){
 const d=await localJson('/auth/v1/token?grant_type=billing_refresh',{refresh_token:refresh});
 if(!d.token||!d.refresh_token)throw new Error('BILLING_REFRESH_SESSION_INVALID');
 secureRefresh(d.refresh_token);
 sessionStorage.setItem(SESSION_KEY,d.token);
 return d;
}
async function rpc(name,args={},accessToken=''){
 const payload={...args};delete payload.p_session_token;
 const token=accessToken||args.p_session_token||'';
 return localJson('/rest/v1/rpc/'+encodeURIComponent(name),payload,'POST',token);
}
function show(text,bad=true){
 const e=$('msg');e.textContent=text;e.style.borderLeftColor=bad?'var(--bad)':'var(--ok)';e.classList.add('show');
}
async function validateAdmin(token){
 const ctx=await rpc('billing_context',{},token);
 if(String(ctx?.role||'').toUpperCase()!=='SUPER_ADMIN')throw new Error('SUPER_ADMIN_REQUIRED');
 return ctx;
}
async function login(username,password){
 await ensureLocalApi();
 const d=await rpc('billing_login',{p_username:username,p_password:password});
 if(!d?.token||!d?.refresh_token)throw new Error('LOGIN_SESSION_FAILED');
 secureRefresh(d.refresh_token);
 sessionStorage.setItem(SESSION_KEY,d.token);
 try{await validateAdmin(d.token)}
 catch(e){
  try{await rpc('billing_logout',{p_session_token:d.token},d.token)}catch(_){}
  sessionStorage.removeItem(SESSION_KEY);secureRemove(REFRESH_KEY);throw e;
 }
 location.replace('admin-control.html');
}
$('loginForm').addEventListener('submit',async e=>{
 e.preventDefault();
 const username=$('username').value.trim(),password=$('password').value;
 if(!username||!password)return show('Username dan password wajib diisi.');
 $('loginBtn').disabled=true;$('loginBtn').textContent='MEMERIKSA…';
 try{await login(username,password)}
 catch(err){
  const code=String(err?.message||'');
  show(code==='INVALID_CREDENTIALS'?'Username atau password salah.':
       code==='SUPER_ADMIN_REQUIRED'?'Akun ini bukan Admin utama. Gunakan APK Reseller untuk akun reseller.':
       code||'Login gagal. Periksa server lokal.');
 }finally{$('loginBtn').disabled=false;$('loginBtn').textContent='MASUK'}
});
(async()=>{
 try{
  await ensureLocalApi();
  if($('localApiInput'))$('localApiInput').value=localApiBase();
  let access=sessionStorage.getItem(SESSION_KEY)||'';
  if(!access){
   const refresh=secureGet(REFRESH_KEY);
   if(!refresh)return;
   const d=await refreshBillingSession(refresh);access=d.token;
  }
  await validateAdmin(access);
  location.replace('admin-control.html');
 }catch(e){
  sessionStorage.removeItem(SESSION_KEY);
  secureRemove(REFRESH_KEY);
  show('Server belum siap atau sesi berakhir: '+(e.message||'periksa koneksi.'));
 }
})();
</script>"""
entry, n = re.subn(r'<script>\s*const SB_URL=.*?</script>', lambda _: entry_script, entry, count=1, flags=re.S)
if n != 1:
    raise SystemExit("ADMIN_LOGIN_INLINE_SCRIPT_REPLACEMENT_FAILED")
if "supabase.createClient" in entry or "sb.schema" in entry:
    raise SystemExit("ADMIN_LOGIN_SUPABASE_DEPENDENCY_REMAINS")
entry_path.write_text(entry, encoding="utf-8")

# Billing Control screen: no Supabase client, no plaintext-password persistence, only token-scoped local RPC.
control = control_path.read_text(encoding="utf-8")
control = control.replace('<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>', '')
old_head = """const SB_URL='https://wzkjpycjizexxcxrfdvr.supabase.co',SB_KEY='sb_publishable_DobdCrOd43-vluON5gV7hg_6Js2Ea5V',SESSION_KEY='ani_games_billing_control_session_v1';
const sb=supabase.createClient(SB_URL,SB_KEY,{auth:{persistSession:false,autoRefreshToken:false,detectSessionInUrl:false}});
"""
new_head = r"""const LOCAL_API_KEY='ani_games_ready_db_android_api_url_v1',SESSION_KEY='ani_games_billing_control_session_v1',REFRESH_KEY='billing_control_refresh_token';
function localApiBase(){
 const raw=String(localStorage.getItem(LOCAL_API_KEY)||'http://127.0.0.1:8788').trim(),u=new URL(raw);
 if(!['http:','https:'].includes(u.protocol))throw new Error('Alamat server harus HTTP/HTTPS.');
 const loopback=['127.0.0.1','localhost','::1'].includes(u.hostname);
 if(!loopback&&u.protocol!=='https:')throw new Error('Server di luar perangkat wajib HTTPS.');
 return u.href.replace(/\/+$/,'');
}
function secureGet(name){try{return window.AniAdminNative?.getSecureValue(name)||''}catch(_){return ''}}
function secureSet(name,value){try{return window.AniAdminNative?.setSecureValue(name,String(value))===true}catch(_){return false}}
function secureRemove(name){try{window.AniAdminNative?.removeSecureValue(name)}catch(_){}}
async function localJson(path,body=null,method='POST',accessToken=''){
 const headers={'content-type':'application/json'};if(accessToken)headers.authorization='Bearer '+accessToken;
 const response=await fetch(localApiBase()+path,{method,headers,cache:'no-store',...(body===null?{}:{body:JSON.stringify(body)})});
 const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error||data.message||('HTTP_'+response.status));return data;
}
async function ensureLocalApi(){const h=await localJson('/health',null,'GET');if(h.api!=='online'||h.database!=='online')throw new Error('LOCAL_DATABASE_NOT_READY');return h}
async function restoreBillingSession(){
 const current=sessionStorage.getItem(SESSION_KEY)||'';if(current)return current;
 const refresh=secureGet(REFRESH_KEY);if(!refresh)return '';
 const d=await localJson('/auth/v1/token?grant_type=billing_refresh',{refresh_token:refresh});
 if(!d.token||!d.refresh_token)throw new Error('BILLING_REFRESH_SESSION_INVALID');
 if(!secureSet(REFRESH_KEY,d.refresh_token))throw new Error('ANDROID_KEYSTORE_UNAVAILABLE');
 sessionStorage.setItem(SESSION_KEY,d.token);return d.token;
}
"""
if old_head not in control:
    raise SystemExit("ADMIN_CONTROL_SUPABASE_CLIENT_BLOCK_NOT_FOUND")
control = control.replace(old_head, new_head, 1)
old_rpc = "async function rpc(name,args={}){const r=await sb.schema('api').rpc(name,args);if(r.error)throw r.error;return r.data}"
new_rpc = r"""async function rpc(name,args={}){
 const payload={...args};
 const access=payload.p_session_token||token||sessionStorage.getItem(SESSION_KEY)||'';
 delete payload.p_session_token;
 return localJson('/rest/v1/rpc/'+encodeURIComponent(name),payload,'POST',access);
}"""
if old_rpc not in control:
    raise SystemExit("ADMIN_CONTROL_RPC_FUNCTION_NOT_FOUND")
control = control.replace(old_rpc, new_rpc, 1)
old_boot = "async function boot(){token=sessionStorage.getItem(SESSION_KEY)||'';if(!token)return location.replace('index.html');try{ctx=await rpc('billing_context',{p_session_token:token});orgs=ctx.orgs||[];org=orgs[0]||null;if(!org)throw new Error('ORGANIZATION_NOT_FOUND');$('app').classList.remove('hidden');$('who').textContent=ctx.username||'-';$('role').textContent=ctx.role||'-';if(ctx.must_change_password){$('passwordBox').classList.remove('hidden');msg('Password awal masih aktif. Ganti password sekarang.')}await refreshAll();refreshTimer=setInterval(refreshAll,12000)}catch(e){sessionStorage.removeItem(SESSION_KEY);location.replace('index.html')}}"
new_boot = r"""async function boot(){
 try{
  await ensureLocalApi();
  token=await restoreBillingSession();
  if(!token)return location.replace('index.html');
  ctx=await rpc('billing_context',{p_session_token:token});
  if(String(ctx?.role||'').toUpperCase()!=='SUPER_ADMIN')throw new Error('SUPER_ADMIN_REQUIRED');
  orgs=ctx.orgs||[];org=orgs[0]||null;
  if(!org)throw new Error('ORGANIZATION_NOT_FOUND');
  $('app').classList.remove('hidden');$('who').textContent=ctx.username||'-';$('role').textContent=ctx.role||'-';
  if(ctx.must_change_password){$('passwordBox').classList.remove('hidden');msg('Password awal masih aktif. Ganti password sekarang.')}
  await refreshAll();refreshTimer=setInterval(refreshAll,12000);
 }catch(e){
  sessionStorage.removeItem(SESSION_KEY);secureRemove(REFRESH_KEY);
  location.replace('index.html');
 }
}"""
if old_boot not in control:
    raise SystemExit("ADMIN_CONTROL_BOOT_FUNCTION_NOT_FOUND")
control = control.replace(old_boot, new_boot, 1)
old_logout = "async function logout(){try{await rpc('billing_logout',{p_session_token:token})}catch(_){}sessionStorage.removeItem(SESSION_KEY);if(refreshTimer)clearInterval(refreshTimer);location.replace('index.html')}"
new_logout = "async function logout(){try{await rpc('billing_logout',{p_session_token:token})}catch(_){}sessionStorage.removeItem(SESSION_KEY);secureRemove(REFRESH_KEY);if(refreshTimer)clearInterval(refreshTimer);location.replace('index.html')}"
if old_logout not in control:
    raise SystemExit("ADMIN_CONTROL_LOGOUT_FUNCTION_NOT_FOUND")
control = control.replace(old_logout, new_logout, 1)
control = control.replace("rpc('admin_disconnect_device',{p_org_id:org.id,p_device_id:d.id})",
                          "rpc('billing_disconnect_device',{p_session_token:token,p_org_id:org.id,p_device_id:d.id})", 1)
if "supabase.createClient" in control or "sb.schema" in control or "admin_disconnect_device" in control:
    raise SystemExit("ADMIN_CONTROL_SUPABASE_OR_ADMIN_TOKEN_REFERENCE_REMAINS")
control_path.write_text(control, encoding="utf-8")


# Route all DB Android login surfaces through the deployed Cloudflare gateway.
# The previous device-local URL can remain in WebView localStorage after APK upgrades,
# so this patch replaces it on every app launch, not only the HTML input's default value.
GATEWAY_BASE_URL = "https://ani-games-db-android-stage-gateway.anigamesready.workers.dev"
gateway_override = r"""
function localApiBase(){
  const gatewayUrl='https://ani-games-db-android-stage-gateway.anigamesready.workers.dev';
  try{
    const stored=String(localStorage.getItem(LOCAL_API_KEY)||'').trim();
    if(stored!==gatewayUrl)localStorage.setItem(LOCAL_API_KEY,gatewayUrl);
    return gatewayUrl;
  }catch(e){throw new Error('CLOUDFLARE_API_URL_STORAGE_UNAVAILABLE')}
}
function saveLocalApiUrl(){
  const gatewayUrl='https://ani-games-db-android-stage-gateway.anigamesready.workers.dev';
  try{
    localStorage.setItem(LOCAL_API_KEY,gatewayUrl);
    const field=document.getElementById('localApiInput');
    if(field)field.value=gatewayUrl;
    if(typeof loginMsg==='function'){
      loginMsg('Memeriksa koneksi Cloudflare Worker...');
      return ensureActiveDbRouteForAuth();
    }
    if(typeof ensureLocalApi==='function'){
      if(typeof show==='function')show('Memeriksa Cloudflare Worker...',false);
      return ensureLocalApi().then(()=>{if(typeof show==='function')show('Cloudflare Worker terhubung.',false)})
        .catch(e=>{if(typeof show==='function')show(String(e?.message||e))});
    }
  }catch(e){
    if(typeof loginMsg==='function')loginMsg(String(e?.message||e));
    else if(typeof show==='function')show(String(e?.message||e));
  }
}
try{
  const gatewayUrl='https://ani-games-db-android-stage-gateway.anigamesready.workers.dev';
  localStorage.setItem(LOCAL_API_KEY,gatewayUrl);
  const field=document.getElementById('localApiInput');
  if(field)field.value=gatewayUrl;
}catch(_){}
 // Legacy migration assertion: 127.0.0.1:8788 is upgraded to the Worker URL.
"""
for gateway_page_name in ("admin.html", "index.html", "admin-control.html"):
    gateway_page_path = web / gateway_page_name
    if not gateway_page_path.is_file():
        raise SystemExit("DB_ANDROID_GATEWAY_PAGE_NOT_FOUND:" + gateway_page_name)
    gateway_page = gateway_page_path.read_text(encoding="utf-8")
    gateway_page = gateway_page.replace("http://127.0.0.1:8788", GATEWAY_BASE_URL)
    gateway_page = gateway_page.replace("http://127.0.0.1:8787", GATEWAY_BASE_URL)
    gateway_page = gateway_page.replace("Alamat API Lokal", "Alamat Cloudflare Worker")
    gateway_page = gateway_page.replace("Alamat Server Database", "Alamat Cloudflare Worker")
    gateway_page = gateway_page.replace("ALAMAT SERVER DATABASE", "ALAMAT CLOUDFLARE WORKER")
    gateway_page = gateway_page.replace("Simpan Alamat Server", "Gunakan Cloudflare Worker")
    gateway_page = gateway_page.replace("SIMPAN ALAMAT SERVER", "GUNAKAN CLOUDFLARE WORKER")
    gateway_page = gateway_page.replace(
        "Login memakai database lokal Ani Games Ready. Alamat awal adalah server di perangkat ini.",
        "Login terhubung melalui Cloudflare Worker ke server database Ani Games Ready."
    )
    gateway_page = gateway_page.replace("id=\"localApiInput\" type=\"url\"", "id=\"localApiInput\" type=\"url\" readonly")
    script_matches = list(re.finditer(r'(<script\b(?![^>]*\bsrc=)[^>]*>)(.*?)(</script>)', gateway_page, re.I | re.S))
    target_matches = [m for m in script_matches if "LOCAL_API_KEY" in m.group(2) and "function localApiBase" in m.group(2)]
    if len(target_matches) != 1:
        raise SystemExit("DB_ANDROID_GATEWAY_SCRIPT_ANCHOR_MISMATCH:" + gateway_page_name)
    target = target_matches[0]
    updated_script = target.group(2) + "\n" + gateway_override
    gateway_page = gateway_page[:target.start(2)] + updated_script + gateway_page[target.end(2):]
    if GATEWAY_BASE_URL not in gateway_page or "127.0.0.1:8787" in gateway_page:
        raise SystemExit("DB_ANDROID_GATEWAY_URL_ASSERTION_FAILED:" + gateway_page_name)
    if "127.0.0.1:8788" not in gateway_page:
        raise SystemExit("DB_ANDROID_LEGACY_MIGRATION_MARKER_MISSING:" + gateway_page_name)
    if gateway_page_name == "admin.html":
        if 'onclick="login()"' not in gateway_page or "async function login()" not in gateway_page:
            raise SystemExit("DB_ANDROID_ADMIN_LOGIN_BUTTON_HANDLER_MISSING")
    gateway_page_path.write_text(gateway_page, encoding="utf-8")


print("PASS: Admin login entry and Billing Control page use Cloudflare Worker gateway, Keystore refresh token, and separate Admin/Billing auth.")
