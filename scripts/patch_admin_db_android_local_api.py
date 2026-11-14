#!/usr/bin/env python3
"""Patch the isolated Admin DB Android source to use the Redmi local API.
Supabase is retained only as an independent Blynk/WoL relay authentication client.
"""
from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
html_path = next(ROOT.rglob("admin.html"), None)
main_path = next(ROOT.rglob("MainActivity.java"), None)
manifest_path = next(ROOT.rglob("AndroidManifest.xml"), None)
if not html_path or not main_path or not manifest_path:
    raise SystemExit("DB_ANDROID_ADMIN_SOURCE_FILES_NOT_FOUND")

html = html_path.read_text(encoding="utf-8")
login_pattern = re.compile(
    r'<div class="muted">Admin Dashboard • Supabase Auth</div>.*?<div id="loginMsg" class="msg hidden"></div>',
    re.S,
)
login_replacement = """<div class="muted">Admin Dashboard • DB Android Lokal</div>
<div class="msg" style="margin-top:12px">Login memakai database lokal Ani Games Ready. Alamat awal adalah server di perangkat ini.</div>
<div class="field"><label>Alamat API Lokal</label><input id="localApiInput" type="url" value="http://127.0.0.1:8787" autocomplete="url"></div>
<div class="row"><button type="button" onclick="saveLocalApiUrl()">Simpan Alamat Server</button></div>
<div class="field"><label>Username / Email Admin</label><input id="email" type="text" autocomplete="username" autocapitalize="none"></div>
<div class="field"><label>Password Admin</label><input id="password" type="password" autocomplete="current-password"></div>
<div class="row"><button class="primary" onclick="login()">Masuk</button></div>
<div id="loginMsg" class="msg hidden"></div>"""
html, n = login_pattern.subn(login_replacement, html, count=1)
if n != 1:
    raise SystemExit("ADMIN_LOGIN_CARD_PATCH_FAILED")

html = html.replace("Supabase Direct • multi-tenant • audit • reporting",
                    "DB Android Lokal • multi-tenant • audit • reporting")
style = """
/* DB Android branch: legacy Supabase DB1/DB2 route UI is intentionally unavailable. */
.db-switch,#databaseTools,.nav [data-tab="databaseTools"],button[onclick*="databaseTools"],#recovery{display:none!important}
"""
if "</style>" not in html:
    raise SystemExit("ADMIN_STYLE_END_NOT_FOUND")
html = html.replace("</style>", style + "\n</style>", 1)

start = html.find("const DB_CONFIG_KEY=")
end = html.find("const GLOBAL_DEVICE_KEY=", start)
if start < 0 or end < 0:
    raise SystemExit("ADMIN_DUAL_DB_CONFIG_BLOCK_NOT_FOUND")
config = r"""
const LOCAL_API_KEY='ani_games_ready_db_android_api_url_v1';
const DB1_URL='https://wzkjpycjizexxcxrfdvr.supabase.co';
const DB1_KEY='sb_publishable_DobdCrOd43-vluON5gV7hg_6Js2Ea5V';
const DB2_URL='',DB2_KEY='',DB1_ROUTE_KEY='',DB2_ROUTE_KEY='';
const DB_ROUTE_NOTICE_KEY='ani_games_db_android_notice_v1';
function localApiBase(){
 const raw=String(localStorage.getItem(LOCAL_API_KEY)||'http://127.0.0.1:8787').trim();
 const u=new URL(raw);
 if(!['http:','https:'].includes(u.protocol))throw new Error('Alamat API harus memakai HTTP/HTTPS.');
 const loopback=['127.0.0.1','localhost','::1'].includes(u.hostname);
 if(!loopback&&u.protocol!=='https:')throw new Error('Alamat server di luar perangkat wajib HTTPS.');
 return u.href.replace(/\/+$/,'');
}
function saveLocalApiUrl(){
 try{
  const value=String($('localApiInput')?.value||'').trim(),u=new URL(value);
  const loopback=['127.0.0.1','localhost','::1'].includes(u.hostname);
  if(!['http:','https:'].includes(u.protocol)||(!loopback&&u.protocol!=='https:'))throw new Error('Server non-lokal harus memakai HTTPS.');
  localStorage.setItem(LOCAL_API_KEY,u.href.replace(/\/+$/,''));
  if($('localApiInput'))$('localApiInput').value=localApiBase();
  loginMsg('Alamat server lokal disimpan. Memeriksa koneksi…');
  ensureActiveDbRouteForAuth();
 }catch(e){loginMsg('Alamat server tidak valid: '+(e.message||'periksa URL.'))}
}
let DB_TARGET='local',SB_URL=DB1_URL,SB_KEY=DB1_KEY,SB_FUNCTION_URL=DB1_URL+'/functions/v1/ani-games-api';
let DB_ROUTE_EPOCH=0,DB_ROUTE_SWITCH_ID=null,dualDbRouteReady=true,dualDbRouteLocked=false;
const relaySecureStorage={
 async getItem(key){try{return window.AniAdminNative?.getSecureValue('relay_'+key)||null}catch(_){return null}},
 async setItem(key,value){if(!window.AniAdminNative?.setSecureValue('relay_'+key,String(value)))throw new Error('ANDROID_KEYSTORE_UNAVAILABLE')},
 async removeItem(key){try{window.AniAdminNative?.removeSecureValue('relay_'+key)}catch(_){}}
};
// Supabase is retained only for the independent Blynk/WoL relay sidecar.
let sb=supabase.createClient(DB1_URL,DB1_KEY,{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:false,storage:relaySecureStorage,storageKey:'ani_admin_relay_auth_v1'}});
"""
html = html[:start] + config + html[end:]

start = html.find("async function ensureActiveDbRouteForAuth(){")
end = html.find("async function fetchIoTWithTimeout", start)
if start < 0 or end < 0:
    raise SystemExit("ADMIN_AUTH_RPC_BLOCK_NOT_FOUND")
auth = r"""
let session=null,ctx=null,orgs=[],currentOrg=null,devicesCache=[],selectedDeviceId=null,selectedDevice=null;
const RELAY_RPC_NAMES=new Set(['wol_relay_status','wol_relay_probe_request','wol_relay_probe_status','wol_relay_create_enrollment','wol_relay_enqueue','wol_relay_command_status']);
function secureGet(key){try{const v=window.AniAdminNative?.getSecureValue(key);return v||sessionStorage.getItem(key)||''}catch(_){return sessionStorage.getItem(key)||''}}
function secureSet(key,value){try{if(window.AniAdminNative?.setSecureValue(key,String(value)))return true}catch(_){}try{sessionStorage.setItem(key,String(value));return true}catch(_){return false}}
function secureRemove(key){try{window.AniAdminNative?.removeSecureValue(key)}catch(_){}try{sessionStorage.removeItem(key)}catch(_){}}
async function localJson(path,body=null,method='POST',token=''){
 const headers={'content-type':'application/json'};if(token)headers.authorization='Bearer '+token;
 const response=await fetch(localApiBase()+path,{method,headers,cache:'no-store',...(body===null?{}:{body:JSON.stringify(body)})});
 const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error||data.message||('HTTP_'+response.status));return data;
}
async function ensureActiveDbRouteForAuth(){
 try{const data=await localJson('/health',null,'GET');if(data.api!=='online'||data.database!=='online')throw new Error('LOCAL_DATABASE_NOT_READY');setAdminAuthEnabled(true);if($('localApiInput'))$('localApiInput').value=localApiBase();return true}
 catch(e){setAdminAuthEnabled(true);loginMsg('Server database lokal belum siap: '+String(e?.message||e).slice(0,160));return false}
}
async function storeAdminRefreshToken(value){if(value)secureSet('admin_refresh_token',value);else secureRemove('admin_refresh_token')}
async function refreshLocalAdminSession(refreshToken){const data=await localJson('/auth/v1/token?grant_type=refresh_token',{refresh_token:refreshToken});if(!data.access_token||!data.refresh_token)throw new Error('ADMIN_REFRESH_SESSION_INVALID');await storeAdminRefreshToken(data.refresh_token);return data}
async function relayAccessToken(){try{const r=await sb.auth.getSession();return r?.data?.session?.access_token||''}catch(_){return ''}}
async function login(){
 if(!(await ensureActiveDbRouteForAuth()))return;
 const btn=document.querySelector('#login button.primary');if(btn)btn.disabled=true;
 try{
  session=await localJson('/auth/v1/token?grant_type=password',{email:$('email').value.trim(),password:$('password').value});
  if(!session.access_token)throw new Error('ADMIN_LOGIN_FAILED');
  await storeAdminRefreshToken(session.refresh_token);
  try{await sb.auth.signInWithPassword({email:session.user?.email||$('email').value.trim(),password:$('password').value})}
  catch(e){console.warn('Separate relay authentication unavailable:',String(e?.message||e).slice(0,100))}
  await boot();
 }catch(e){session=null;loginMsg(String(e?.message||e||'Login lokal gagal.'))}
 finally{if(btn)btn.disabled=false}
}
async function signup(){loginMsg('Pembuatan akun Admin dilakukan melalui halaman Setup lokal server.')}
async function logout(){try{if(session?.access_token)await localJson('/auth/v1/logout',{},'POST',session.access_token)}catch(_){}try{await sb.auth.signOut()}catch(_){}await storeAdminRefreshToken('');session=null;ctx=null;location.reload()}
async function resetPassword(){loginMsg('Reset password lokal dilakukan oleh Owner melalui pengaturan akun/server. Email reset Supabase tidak digunakan untuk database rental lokal.')}
async function rpc(name,args={}){
 if(RELAY_RPC_NAMES.has(name)){const r=await sb.schema('api').rpc(name,args);if(r.error)throw r.error;return r.data}
 const token=session?.access_token||args?.p_session_token||'',payload={...args};delete payload.p_session_token;
 const headers={'content-type':'application/json'};if(token)headers.authorization='Bearer '+token;
 const response=await fetch(localApiBase()+'/rest/v1/rpc/'+encodeURIComponent(name),{method:'POST',headers,cache:'no-store',body:JSON.stringify(payload)});
 const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error||data.message||('LOCAL_API_HTTP_'+response.status));return data;
}
async function boot(){
 try{
  if(!session){const refresh=secureGet('admin_refresh_token');if(refresh){try{session=await refreshLocalAdminSession(refresh)}catch(_){await storeAdminRefreshToken('');session=null}}}
  if(!session?.access_token){$('login').classList.remove('hidden');$('app').classList.add('hidden');return}
  if(!(await ensureActiveDbRouteForAuth()))throw new Error('LOCAL_DATABASE_NOT_READY');
  $('login').classList.add('hidden');$('app').classList.remove('hidden');$('who').textContent=session.user?.email||session.user?.user_metadata?.username||'Admin';
  ctx=await rpc('admin_context');orgs=ctx.orgs||[];
  if(ctx.role==='owner'){refreshIoTStatus();ensureNativeNotificationPermission()}
  $('role').textContent=ctx.role||'admin';renderOrgs();applyPairingRoleUI();
  if(orgs.length){currentOrg=orgs[0];$('orgSelect').value=currentOrg.id;await refresh()}
 }catch(e){$('app').classList.add('hidden');$('login').classList.remove('hidden');loginMsg('Gagal memuat dashboard lokal: '+String(e?.message||e).slice(0,180))}
}
async function startLocalAdmin(){setAdminAuthEnabled(true);try{sb.auth.onAuthStateChange(()=>setTimeout(()=>{if(session)refreshIoTStatus()},0))}catch(_){}await boot()}
function requestGlobalDbSwitch(){msg('Perpindahan DB1/DB2 tidak tersedia pada cabang DB Android.',true)}
function v12DbTargetChanged(){}
function v12InitDbSwitch(){}
async function v12SaveDbTarget(){msg('DB Android memakai satu server lokal; menu perpindahan DB dinonaktifkan.',true)}
"""
html = html[:start] + auth + html[end:]

# Replace direct table reads with the token-bound local Admin RPCs.
direct_devices = "const r=await sb.from('devices').select('id,org_id,client_id,device_name,status,app_version,last_seen_at,last_heartbeat_at,power_state,metadata').eq('org_id',currentOrg.id).order('device_name');if(r.error){setHealth('dbHealthDot','dbHealthText','bad','Gagal membaca data: '+r.error.message);return msg(r.error.message,true)}const now=Date.now();const rows=(r.data||[]).map(d=>"
if direct_devices not in html:
    raise SystemExit("ADMIN_DIRECT_DEVICES_QUERY_NOT_FOUND")
html = html.replace(direct_devices, "const data=await rpc('admin_devices',{p_org_id:currentOrg.id});const now=Date.now();const rows=(data||[]).map(d=>", 1)

old_wait = "async function waitDeviceCommand(commandId,timeoutMs=12000){const started=Date.now();while(Date.now()-started<timeoutMs){const q=await sb.from('device_commands').select('status,result,delivered_at,completed_at').eq('id',commandId).maybeSingle();if(q.error)throw q.error;const row=q.data;if(row&&['completed','failed','expired'].includes(row.status))return row;await new Promise(r=>setTimeout(r,1500));}return null}"
new_wait = "async function waitDeviceCommand(commandId,timeoutMs=12000){const started=Date.now();while(Date.now()-started<timeoutMs){const row=await rpc('admin_command_status',{p_org_id:currentOrg.id,p_command_id:commandId});if(row&&['completed','failed','expired'].includes(row.status))return row;await new Promise(r=>setTimeout(r,1500));}return null}"
if old_wait not in html:
    raise SystemExit("ADMIN_DIRECT_COMMAND_QUERY_NOT_FOUND")
html = html.replace(old_wait, new_wait, 1)

# Relay calls use the relay JWT, never the local opaque Admin session token.
html = html.replace("const el=$('iotPowerStatus');if(!el||!session?.access_token)return;\n try{\n  const r=await fetchIoTWithTimeout(SB_FUNCTION_URL+'/iot/status',{headers:{apikey:SB_KEY,authorization:'Bearer '+session.access_token}},12000);",
"""const el=$('iotPowerStatus');if(!el)return;
 try{
  const relayToken=await relayAccessToken();if(!relayToken)throw new Error('RELAY_AUTH_REQUIRED');
  const r=await fetchIoTWithTimeout(SB_FUNCTION_URL+'/iot/status',{headers:{apikey:SB_KEY,authorization:'Bearer '+relayToken}},12000);""")
html = html.replace("const r=await fetchIoTWithTimeout(SB_FUNCTION_URL+'/iot/power',{method:'POST',headers:{'content-type':'application/json',apikey:SB_KEY,authorization:'Bearer '+session.access_token},body:JSON.stringify({deviceId:selectedDeviceId})},15000);",
"""const relayToken=await relayAccessToken();if(!relayToken)throw new Error('RELAY_AUTH_REQUIRED');
  const r=await fetchIoTWithTimeout(SB_FUNCTION_URL+'/iot/power',{method:'POST',headers:{'content-type':'application/json',apikey:SB_KEY,authorization:'Bearer '+relayToken},body:JSON.stringify({deviceId:selectedDeviceId})},15000);""")

# Remove every active DB1/DB2 sync/cutover function from this isolated branch.
sync_start = html.find("function updateDbSyncDirection(){")
sync_end = html.find("function v12SyncMobileActiveTab", sync_start)
if sync_start < 0 or sync_end < 0:
    raise SystemExit("ADMIN_DB_SYNC_BLOCK_NOT_FOUND")
html = html[:sync_start] + html[sync_end:]

old_tab = re.compile(r"const v12BaseTab=tab;tab=function\\(id\\)\\{.*?\\};", re.S)
tab_replacement = "const v12BaseTab=tab;tab=function(id){if(id==='databaseTools'){msg('Database & Sync DB1/DB2 tidak tersedia pada cabang DB Android.',true);return;}v12BaseTab(id);closeMobileNav();v12SyncMobileActiveTab(id);if(id==='windowsChat'){loadDevices().then(refreshChatTargets)}};"
html, n = old_tab.subn(tab_replacement, html, count=1)
if n != 1:
    raise SystemExit("ADMIN_TAB_WRAPPER_PATCH_FAILED")
html = html.replace("updateDbSyncDirection();updateDbSyncModeNote();setAdminDefaultMonthRange();$('reportDetailDate').value=jakartaDateString();",
                    "setAdminDefaultMonthRange();$('reportDetailDate').value=jakartaDateString();")

boot_start = html.find("// V12.1.25-ROUTE-BOOT-SEPARATION")
boot_end = html.find("startDualDbAdmin();setInterval", boot_start)
if boot_start < 0 or boot_end < 0:
    raise SystemExit("ADMIN_DUAL_DB_BOOT_BLOCK_NOT_FOUND")
html = html[:boot_start] + html[boot_end:]
html = html.replace("startDualDbAdmin();setInterval", "startLocalAdmin();setInterval", 1)
html = html.replace("Koneksi Supabase gagal", "Koneksi server lokal gagal")
html = html.replace("cek koneksi/proyek Supabase", "cek koneksi server lokal")
html_path.write_text(html, encoding="utf-8")

# Add Android Keystore-backed AES/GCM storage to the existing native bridge.
main = main_path.read_text(encoding="utf-8")
imports = [
    "import android.content.SharedPreferences;",
    "import android.util.Base64;",
    "import android.security.keystore.KeyGenParameterSpec;",
    "import android.security.keystore.KeyProperties;",
    "import java.security.KeyStore;",
    "import java.nio.charset.StandardCharsets;",
    "import javax.crypto.Cipher;",
    "import javax.crypto.KeyGenerator;",
    "import javax.crypto.SecretKey;",
    "import javax.crypto.spec.GCMParameterSpec;",
]
for imp in imports:
    if imp not in main:
        main = main.replace("import java.io.OutputStream;", "import java.io.OutputStream;\n" + imp, 1)
bridge_anchor = "    private class AdminNotificationBridge {\n"
secure_methods = r"""
        private static final String SECURE_PREFS = "ani_admin_secure_store_v1";
        private static final String SECURE_KEY_ALIAS = "AniAdminDbAndroidKeyV1";
        private String safeSecureName(String name) {
            if (name == null || !name.matches("[A-Za-z0-9._-]{1,96}")) return null;
            return name;
        }
        private SecretKey getOrCreateSecureKey() throws Exception {
            KeyStore keyStore = KeyStore.getInstance("AndroidKeyStore");
            keyStore.load(null);
            if (keyStore.containsAlias(SECURE_KEY_ALIAS)) return (SecretKey) keyStore.getKey(SECURE_KEY_ALIAS, null);
            KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
            generator.init(new KeyGenParameterSpec.Builder(SECURE_KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true).build());
            return generator.generateKey();
        }
        @JavascriptInterface public String getSecureValue(String name) {
            String safe = safeSecureName(name);
            if (safe == null) return "";
            try {
                SharedPreferences prefs = getSharedPreferences(SECURE_PREFS, MODE_PRIVATE);
                String packed = prefs.getString(safe, "");
                if (packed == null || packed.isEmpty()) return "";
                String[] parts = packed.split(":", 2);
                if (parts.length != 2) return "";
                byte[] iv = Base64.decode(parts[0], Base64.NO_WRAP);
                byte[] encrypted = Base64.decode(parts[1], Base64.NO_WRAP);
                Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
                cipher.init(Cipher.DECRYPT_MODE, getOrCreateSecureKey(), new GCMParameterSpec(128, iv));
                return new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8);
            } catch (Exception ignored) {
                try { getSharedPreferences(SECURE_PREFS, MODE_PRIVATE).edit().remove(safe).apply(); } catch (Exception ignoredAgain) {}
                return "";
            }
        }
        @JavascriptInterface public boolean setSecureValue(String name, String value) {
            String safe = safeSecureName(name);
            if (safe == null || value == null || value.length() > 32768) return false;
            try {
                Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
                cipher.init(Cipher.ENCRYPT_MODE, getOrCreateSecureKey());
                byte[] encrypted = cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
                String packed = Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP) + ":" +
                    Base64.encodeToString(encrypted, Base64.NO_WRAP);
                getSharedPreferences(SECURE_PREFS, MODE_PRIVATE).edit().putString(safe, packed).apply();
                return true;
            } catch (Exception ignored) { return false; }
        }
        @JavascriptInterface public void removeSecureValue(String name) {
            String safe = safeSecureName(name);
            if (safe == null) return;
            try { getSharedPreferences(SECURE_PREFS, MODE_PRIVATE).edit().remove(safe).apply(); } catch (Exception ignored) {}
        }
"""
if bridge_anchor not in main:
    raise SystemExit("ADMIN_NATIVE_BRIDGE_ANCHOR_NOT_FOUND")
if "getSecureValue(String name)" not in main:
    main = main.replace(bridge_anchor, bridge_anchor + secure_methods, 1)
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

if "sb.from('devices')" in html or "sb.from('device_commands')" in html:
    raise SystemExit("ADMIN_DIRECT_POSTGREST_READ_REMAINS")
if "startDualDbAdmin();" in html or "resolveDualDbRoute(" in html:
    raise SystemExit("ADMIN_DUAL_DB_BOOT_REFERENCE_REMAINS")
print("PASS: Admin local API adapter, Android Keystore bridge, relay isolation and DB1/DB2 UI removal")
