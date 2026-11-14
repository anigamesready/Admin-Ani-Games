#!/usr/bin/env python3
"""Isolated Reseller DB Android adapter: local API + rotating refresh token in Android Keystore."""
from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
index_path = next((p for p in ROOT.rglob("index.html") if p.as_posix().endswith("/android/app/src/main/assets/web/index.html")), None)
control_path = next((p for p in ROOT.rglob("admin-control.html") if p.as_posix().endswith("/android/app/src/main/assets/web/admin-control.html")), None)
main_path = next(ROOT.rglob("MainActivity.java"), None)
manifest_path = next(ROOT.rglob("AndroidManifest.xml"), None)
if not all([index_path, control_path, main_path, manifest_path]):
    raise SystemExit("DB_ANDROID_RESELLER_SOURCE_FILES_NOT_FOUND")

def local_api_block(include_login_ui=False):
    return r"""
const LOCAL_API_KEY='ani_games_ready_db_android_api_url_v1';
const SESSION_KEY='ani_games_billing_control_session_v1';
const $=id=>document.getElementById(id);
function localApiBase(){
 const raw=String(localStorage.getItem(LOCAL_API_KEY)||'http://127.0.0.1:8788').trim(),u=new URL(raw);
 if(!['http:','https:'].includes(u.protocol))throw new Error('Alamat API harus HTTP/HTTPS.');
 const loopback=['127.0.0.1','localhost','::1'].includes(u.hostname);
 if(!loopback&&u.protocol!=='https:')throw new Error('Server di luar perangkat wajib memakai HTTPS.');
 return u.href.replace(/\/+$/,'');
}
function saveLocalApiUrl(){
 try{
  const u=new URL(String($('localApiInput')?.value||'').trim()),loopback=['127.0.0.1','localhost','::1'].includes(u.hostname);
  if(!['http:','https:'].includes(u.protocol)||(!loopback&&u.protocol!=='https:'))throw new Error('Server non-lokal harus HTTPS.');
  localStorage.setItem(LOCAL_API_KEY,u.href.replace(/\/+$/,''));
  if($('localApiInput'))$('localApiInput').value=localApiBase();
  if(typeof showMsg==='function')showMsg('Alamat server lokal tersimpan.','good');
 }catch(e){if(typeof showMsg==='function')showMsg(e.message||'Alamat server tidak valid.','bad')}
}
function secureGet(key){try{const v=window.AniResellerNative?.getSecureValue(key);return v||sessionStorage.getItem(key)||''}catch(_){return sessionStorage.getItem(key)||''}}
function secureSet(key,value){try{if(window.AniResellerNative?.setSecureValue(key,String(value)))return true}catch(_){}try{sessionStorage.setItem(key,String(value));return true}catch(_){return false}}
function secureRemove(key){try{window.AniResellerNative?.removeSecureValue(key)}catch(_){}try{sessionStorage.removeItem(key)}catch(_){}}
async function localJson(path,body=null,method='POST',token=''){
 const headers={'content-type':'application/json'};if(token)headers.authorization='Bearer '+token;
 const response=await fetch(localApiBase()+path,{method,headers,cache:'no-store',...(body===null?{}:{body:JSON.stringify(body)})});
 const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error||data.message||('HTTP_'+response.status));return data;
}
async function refreshResellerSession(refreshToken){
 const data=await localJson('/auth/v1/token?grant_type=billing_refresh',{refresh_token:refreshToken});
 if(!data.token||!data.refresh_token)throw new Error('BILLING_REFRESH_SESSION_INVALID');
 secureSet('reseller_refresh_token',data.refresh_token);
 sessionStorage.setItem(SESSION_KEY,data.token);
 return data.token;
}
async function restoreResellerSession(){
 let current=sessionStorage.getItem(SESSION_KEY)||'';
 if(current)return current;
 const refresh=secureGet('reseller_refresh_token');
 if(!refresh)return '';
 try{return await refreshResellerSession(refresh)}catch(_){secureRemove('reseller_refresh_token');sessionStorage.removeItem(SESSION_KEY);return ''}
}
async function ensureCurrentDbRoute(){
 const health=await localJson('/health',null,'GET');
 if(health.api!=='online'||health.database!=='online')throw new Error('LOCAL_DATABASE_NOT_READY');
 return health;
}
function startResellerRouteMonitor(){}
async function rpc(name,args={}){
 const token=args?.p_session_token||sessionStorage.getItem(SESSION_KEY)||'';
 const payload={...args};delete payload.p_session_token;
 const headers={'content-type':'application/json'};if(token)headers.authorization='Bearer '+token;
 const response=await fetch(localApiBase()+'/rest/v1/rpc/'+encodeURIComponent(name),{
  method:'POST',headers,cache:'no-store',body:JSON.stringify(payload)
 });
 const data=await response.json().catch(()=>({}));
 if(!response.ok)throw new Error(data.error||data.message||('LOCAL_API_HTTP_'+response.status));
 return data;
}
"""
index = index_path.read_text(encoding="utf-8")
control = control_path.read_text(encoding="utf-8")

# Remove the Supabase SDK from Reseller. This app has no Blynk/WoL relay dependency.
index = index.replace('<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>', '')
control = control.replace('<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>', '')

# Login page: replace all DB1/DB2 route resolution with the local API adapter.
start = index.find("let SB_URL=")
end = index.find("const RESELLER_LOGIN_STORE_KEY=", start)
if start < 0 or end < 0:
    raise SystemExit("RESELLER_LOGIN_ROUTE_BLOCK_NOT_FOUND")
index = index[:start] + local_api_block(True) + "\n" + index[end:]

# Remember only the username in ordinary storage; the revocable refresh token is Android-Keystore encrypted.
store_start = index.find("const RESELLER_LOGIN_STORE_KEY=")
store_end = index.find("function showMsg", store_start)
if store_start < 0 or store_end < 0:
    raise SystemExit("RESELLER_SAVED_LOGIN_BLOCK_NOT_FOUND")
store_block = r"""
const RESELLER_LOGIN_STORE_KEY='ani_games_reseller_saved_username_v1';
function loadSavedResellerLogin(){
 try{
  const username=localStorage.getItem(RESELLER_LOGIN_STORE_KEY)||'';
  if(username)$('username').value=username;
  $('rememberLogin').checked=!!secureGet('reseller_refresh_token');
 }catch(_){}
}
function saveResellerLogin(username,refreshToken){
 if(!$('rememberLogin').checked){secureRemove('reseller_refresh_token');localStorage.removeItem(RESELLER_LOGIN_STORE_KEY);return}
 localStorage.setItem(RESELLER_LOGIN_STORE_KEY,String(username||''));
 if(refreshToken)secureSet('reseller_refresh_token',refreshToken);
}
$('rememberLogin').addEventListener('change',()=>{
 if(!$('rememberLogin').checked){secureRemove('reseller_refresh_token');try{localStorage.removeItem(RESELLER_LOGIN_STORE_KEY)}catch(_){}}
});
loadSavedResellerLogin();

"""
index = index[:store_start] + store_block + index[store_end:]

index = index.replace("Simpan ID &amp; Password di perangkat ini",
                      "Tetap masuk di perangkat ini (token aman)")
# Add local API URL control before the username field.
login_anchor = '  <form id="loginForm" autocomplete="on">\n'
api_field = """  <div class="field"><label for="localApiInput">ALAMAT SERVER API LOKAL</label><input id="localApiInput" type="url" value="http://127.0.0.1:8788" autocomplete="url"></div>
  <button type="button" class="btn secondary" style="margin-top:8px" onclick="saveLocalApiUrl()">SIMPAN ALAMAT SERVER</button>
"""
if login_anchor not in index:
    raise SystemExit("RESELLER_LOGIN_FORM_ANCHOR_NOT_FOUND")
index = index.replace(login_anchor, api_field + login_anchor, 1)

old_rpc = "async function rpc(name,args={}){await ensureCurrentDbRoute(false);const r=await sb.schema('api').rpc(name,args);if(r.error)throw r.error;return r.data}"
if old_rpc not in index:
    raise SystemExit("RESELLER_LOGIN_RPC_NOT_FOUND")
index = index.replace(old_rpc, "", 1)

# Replace login handler and startup auto-login with local access/refresh-token flow.
login_start = index.find("$('loginForm').addEventListener('submit',async e=>{")
startup_start = index.find("(async()=>{const params=", login_start)
startup_end = index.find("})();", startup_start)
if login_start < 0 or startup_start < 0 or startup_end < 0:
    raise SystemExit("RESELLER_LOGIN_HANDLER_BLOCK_NOT_FOUND")
login_and_startup = r"""
$('loginForm').addEventListener('submit',async e=>{
 e.preventDefault();
 const username=$('username').value.trim(),password=$('password').value;
 if(!username||!password)return showMsg('Username dan password wajib diisi.');
 $('loginBtn').disabled=true;$('loginBtn').textContent='MEMERIKSA AKUN…';
 try{
  await ensureCurrentDbRoute();
  const d=await rpc('billing_login',{p_username:username,p_password:password});
  if(!d?.token||!d?.refresh_token)throw new Error('LOGIN_SESSION_FAILED');
  sessionStorage.setItem(SESSION_KEY,d.token);
  try{await checkReseller(d.token)}catch(roleErr){try{await rpc('billing_logout',{p_session_token:d.token})}catch(_){}throw roleErr}
  saveResellerLogin(username,d.refresh_token);
  location.replace('admin-control.html');
 }catch(err){
  const m=err?.message==='INVALID_CREDENTIALS'?'Username atau password salah.':
   err?.message==='RESELLER_ROLE_REQUIRED'?'Akun ini bukan akun reseller. Gunakan akun reseller yang telah dibuat admin.':
   err?.message||'Login gagal. Periksa server lokal.';
  showMsg(m);
 }finally{$('loginBtn').disabled=false;$('loginBtn').textContent='MASUK'}
});
(async()=>{
 const params=new URLSearchParams(location.search);
 if(params.get('role')==='denied')showMsg('Akun ini tidak memiliki akses reseller.');
 try{
  await ensureCurrentDbRoute();
  let t=sessionStorage.getItem(SESSION_KEY)||'';
  if(!t)t=await restoreResellerSession();
  if(!t)return;
  await checkReseller(t);
  location.replace('admin-control.html');
 }catch(e){
  secureRemove('reseller_refresh_token');sessionStorage.removeItem(SESSION_KEY);
  showMsg('Server lokal belum siap atau sesi berakhir: '+(e?.message||'periksa server.'));
 }
})();
"""
index = index[:login_start] + login_and_startup + index[startup_end+4:]
index_path.write_text(index, encoding="utf-8")

# Admin control page: local API only; no DB1/DB2 route status or Supabase client.
start = control.find("let SB_URL=")
end = control.find("const $=id=>document.getElementById(id);", start)
if start < 0 or end < 0:
    raise SystemExit("RESELLER_CONTROL_ROUTE_BLOCK_NOT_FOUND")
control = control[:start] + local_api_block(False) + "\n" + control[end+len("const $=id=>document.getElementById(id);"):]

# Remove the later legacy Supabase rpc declaration.
old_control_rpc = "async function rpc(name,args={}){await ensureCurrentDbRoute(false);const r=await sb.schema('api').rpc(name,args);if(r.error)throw r.error;return r.data}"
if old_control_rpc not in control:
    raise SystemExit("RESELLER_CONTROL_RPC_NOT_FOUND")
control = control.replace(old_control_rpc, "", 1)

# Replace the existing boot/logout implementations with Keystore refresh-token restoration.
logout_old = "async function logout(silent=false){try{if(token)await rpc('billing_logout',{p_session_token:token})}catch(_){}sessionStorage.removeItem(SESSION_KEY);sessionStorage.removeItem(SELECTED_PC_KEY);if(refreshTimer)clearInterval(refreshTimer);location.replace('index.html'+(silent?'?role=denied':''))}"
logout_new = "async function logout(silent=false){try{if(token)await rpc('billing_logout',{p_session_token:token})}catch(_){}secureRemove('reseller_refresh_token');sessionStorage.removeItem(SESSION_KEY);sessionStorage.removeItem(SELECTED_PC_KEY);if(refreshTimer)clearInterval(refreshTimer);location.replace('index.html'+(silent?'?role=denied':''))}"
if logout_old not in control:
    raise SystemExit("RESELLER_CONTROL_LOGOUT_NOT_FOUND")
control = control.replace(logout_old, logout_new, 1)

boot_start = control.find("async function boot(){")
boot_end = control.find("boot();", boot_start)
if boot_start < 0 or boot_end < 0:
    raise SystemExit("RESELLER_CONTROL_BOOT_NOT_FOUND")
boot_new = r"""async function boot(){
 try{
  token=await restoreResellerSession();
  if(!token)return location.replace('index.html');
  await ensureCurrentDbRoute();
  ctx=await rpc('billing_context',{p_session_token:token});
  if(String(ctx?.role||'').toUpperCase()!=='RESELLER_ADMIN')return logout(true);
  org=Array.isArray(ctx.orgs)?ctx.orgs[0]:null;
  if(!org)org={id:ctx.org_id,name:ctx.org_name||ctx.username,kind:'reseller'};
  $('who').textContent=ctx.username||'Reseller';$('accountPill').textContent='RESELLER';
  $('soundToggle').checked=soundEnabled;selectedId=sessionStorage.getItem(SELECTED_PC_KEY)||'';
  await refreshAll(false);
  refreshTimer=setInterval(()=>{if(document.visibilityState==='visible')refreshAll(false)},20000);
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')refreshAll(false)});
  if(ctx.must_change_password){$('passwordBox').classList.remove('hidden');showMessage('Ganti password awal sebelum melanjutkan.','bad')}
 }catch(e){
  if(/SESSION|TOKEN|ACCESS_DENIED|INVALID|AUTHENTICATED/.test((e.message||'').toUpperCase()))return logout(true);
  showMessage('Aplikasi gagal memuat server lokal: '+(e.message||'error'),'bad');
 }
}
"""
control = control[:boot_start] + boot_new + control[boot_end:]
control_path.write_text(control, encoding="utf-8")

# Android Keystore bridge for refresh token storage.
main = main_path.read_text(encoding="utf-8")
imports = [
    "import android.content.SharedPreferences;",
    "import android.security.keystore.KeyGenParameterSpec;",
    "import android.security.keystore.KeyProperties;",
    "import android.webkit.JavascriptInterface;",
    "import android.util.Base64;",
    "import java.security.KeyStore;",
    "import java.nio.charset.StandardCharsets;",
    "import javax.crypto.Cipher;",
    "import javax.crypto.KeyGenerator;",
    "import javax.crypto.SecretKey;",
    "import javax.crypto.spec.GCMParameterSpec;",
]
for imp in imports:
    if imp not in main:
        main = main.replace("import android.webkit.WebViewClient;", "import android.webkit.WebViewClient;\n" + imp, 1)
if 'web.addJavascriptInterface(new ResellerNativeBridge(), "AniResellerNative");' not in main:
    main = main.replace("web = new WebView(this);\n", "web = new WebView(this);\n        web.addJavascriptInterface(new ResellerNativeBridge(), \"AniResellerNative\");\n", 1)
bridge = r"""
    private class ResellerNativeBridge {
        private static final String PREFS = "ani_reseller_secure_store_v1";
        private static final String KEY_ALIAS = "AniResellerDbAndroidKeyV1";
        private String safeName(String name) {
            if (name == null || !name.matches("[A-Za-z0-9._-]{1,96}")) return null;
            return name;
        }
        private SecretKey secureKey() throws Exception {
            KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
            ks.load(null);
            if (ks.containsAlias(KEY_ALIAS)) return (SecretKey) ks.getKey(KEY_ALIAS, null);
            KeyGenerator kg = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
            kg.init(new KeyGenParameterSpec.Builder(KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true).build());
            return kg.generateKey();
        }
        @JavascriptInterface public String getSecureValue(String name) {
            String safe = safeName(name); if (safe == null) return "";
            try {
                String packed = getSharedPreferences(PREFS, MODE_PRIVATE).getString(safe, "");
                if (packed == null || packed.isEmpty()) return "";
                String[] parts = packed.split(":", 2); if (parts.length != 2) return "";
                Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
                cipher.init(Cipher.DECRYPT_MODE, secureKey(), new GCMParameterSpec(128, Base64.decode(parts[0], Base64.NO_WRAP)));
                return new String(cipher.doFinal(Base64.decode(parts[1], Base64.NO_WRAP)), StandardCharsets.UTF_8);
            } catch (Exception ignored) { return ""; }
        }
        @JavascriptInterface public boolean setSecureValue(String name, String value) {
            String safe = safeName(name); if (safe == null || value == null || value.length() > 32768) return false;
            try {
                Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
                cipher.init(Cipher.ENCRYPT_MODE, secureKey());
                byte[] encrypted = cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
                String packed = Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP) + ":" + Base64.encodeToString(encrypted, Base64.NO_WRAP);
                getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(safe, packed).apply();
                return true;
            } catch (Exception ignored) { return false; }
        }
        @JavascriptInterface public void removeSecureValue(String name) {
            String safe = safeName(name); if (safe == null) return;
            try { getSharedPreferences(PREFS, MODE_PRIVATE).edit().remove(safe).apply(); } catch (Exception ignored) {}
        }
    }
"""
if "private class ResellerNativeBridge" not in main:
    insert_at = main.find("    @Override public void onBackPressed()")
    if insert_at < 0: raise SystemExit("RESELLER_MAIN_ACTIVITY_INSERT_POINT_NOT_FOUND")
    main = main[:insert_at] + bridge + "\n" + main[insert_at:]
main_path.write_text(main, encoding="utf-8")

manifest = manifest_path.read_text(encoding="utf-8")
manifest = manifest.replace('android:usesCleartextTraffic="false"',
                            'android:usesCleartextTraffic="false" android:networkSecurityConfig="@xml/network_security_config"')
manifest_path.write_text(manifest, encoding="utf-8")
xml_dir = manifest_path.parent / "res" / "xml"
xml_dir.mkdir(parents=True, exist_ok=True)
(xml_dir / "network_security_config.xml").write_text(
    """<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="false">127.0.0.1</domain>
        <domain includeSubdomains="false">localhost</domain>
    </domain-config>
</network-security-config>
""", encoding="utf-8")

for p in [index_path, control_path]:
    text = p.read_text(encoding="utf-8")
    if "createClient(" in text or "sb.schema('api')" in text or "DB2_ROUTE_URL" in text:
        raise SystemExit("RESELLER_SUPABASE_OR_DUAL_DB_REFERENCE_REMAINS:" + p.name)
    if "localStorage.setItem(RESELLER_LOGIN_STORE_KEY,JSON.stringify({username,password}))" in text:
        raise SystemExit("RESELLER_PLAINTEXT_PASSWORD_STORAGE_REMAINS")
print("PASS: Reseller local API, rotating Keystore refresh token, no plaintext password storage, no Supabase DB routing")
