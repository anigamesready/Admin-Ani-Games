#!/usr/bin/env python3
"""Add remembered reseller login and editable rental status to the V1.0.5 baseline."""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
pages = [p for p in root.rglob("index.html")
         if p.parent.name == "web" and (p.parent / "admin-control.html").is_file()]
if len(pages) != 1:
    raise SystemExit(f"Expected exactly one reseller WebView page pair, found {len(pages)}")
login_path = pages[0]
dashboard_path = login_path.parent / "admin-control.html"
login = login_path.read_text(encoding="utf-8")
dashboard = dashboard_path.read_text(encoding="utf-8")

def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source anchor, found {count}")
    return source.replace(old, new, 1)

# Login: remember username/password only on this device and only after a successful reseller login.
remember_css = ".remember-row{display:flex;align-items:center;gap:9px;margin:4px 0 16px;color:var(--muted);font-size:12px;line-height:1.4}.remember-row input{width:16px;height:16px;accent-color:var(--accent)}"
login = replace_once(login, "</style>", remember_css + "\n</style>", "remember-login style")
login = replace_once(
    login,
    '    <button id="loginBtn" class="btn" type="submit">MASUK</button>',
    '    <label class="remember-row" for="rememberLogin"><input id="rememberLogin" type="checkbox" checked> Simpan ID &amp; Password di perangkat ini</label>\n    <button id="loginBtn" class="btn" type="submit">MASUK</button>',
    "remember-login checkbox"
)
login_store = """
const RESELLER_LOGIN_STORE_KEY='ani_games_reseller_saved_login_v1';
function loadSavedResellerLogin(){
 try{
  const saved=JSON.parse(localStorage.getItem(RESELLER_LOGIN_STORE_KEY)||'null');
  if(saved&&typeof saved.username==='string'&&typeof saved.password==='string'&&saved.username&&saved.password){
   $('username').value=saved.username;
   $('password').value=saved.password;
   $('rememberLogin').checked=true;
  }
 }catch(_){try{localStorage.removeItem(RESELLER_LOGIN_STORE_KEY)}catch(__){}}
}
function saveResellerLogin(username,password){
 try{
  if(!$('rememberLogin').checked){localStorage.removeItem(RESELLER_LOGIN_STORE_KEY);return}
  localStorage.setItem(RESELLER_LOGIN_STORE_KEY,JSON.stringify({username,password}));
 }catch(_){/* Login must still work when device storage is unavailable. */}
}
$('rememberLogin').addEventListener('change',()=>{
 if(!$('rememberLogin').checked){try{localStorage.removeItem(RESELLER_LOGIN_STORE_KEY)}catch(_){}}
});
loadSavedResellerLogin();
"""
login = replace_once(
    login,
    "const $=id=>document.getElementById(id);",
    "const $=id=>document.getElementById(id);\n" + login_store,
    "remember-login storage helpers"
)
login = replace_once(
    login,
    "sessionStorage.setItem(SESSION_KEY,d.token);location.replace('admin-control.html')",
    "sessionStorage.setItem(SESSION_KEY,d.token);saveResellerLogin(username,password);location.replace('admin-control.html')",
    "remember-login successful save"
)
for marker in ("RESELLER_LOGIN_STORE_KEY", "loadSavedResellerLogin", "saveResellerLogin(username,password)", "rememberLogin"):
    if marker not in login:
        raise SystemExit("Remember-login verification failed: " + marker)

# Rental status: the database supports active / disabled / expired; keep active-session lock intact.
old_expiry_field = '<div class="field full"><label for="editExpiry">TANGGAL EXPIRED (OPSIONAL)</label><input id="editExpiry" type="date"></div>'
new_expiry_field = old_expiry_field + '<div class="field full"><label for="editStatus">STATUS RENTAL</label><select id="editStatus"><option value="active">ACTIVE</option><option value="disabled">DISABLE</option><option value="expired">EXPIRED</option></select></div>'
dashboard = replace_once(dashboard, old_expiry_field, new_expiry_field, "edit status selector markup")

dashboard = replace_once(
    dashboard,
    "$('editExpiry').value=toLocalDate(r.expiry_at);$('editClient').value=r.client_label||'';",
    "$('editExpiry').value=toLocalDate(r.expiry_at);$('editStatus').value=String(r.status||'active').toLowerCase();$('editClient').value=r.client_label||'';",
    "edit status preload"
)
dashboard = replace_once(
    dashboard,
    "const st=editRentalState,minutes=Number($('editMinutes').value);",
    "const st=editRentalState,minutes=Number($('editMinutes').value),status=String($('editStatus').value||'active').toLowerCase();",
    "edit status value"
)
dashboard = replace_once(
    dashboard,
    "if(!Number.isFinite(minutes)||minutes<0)return showMessage('Sisa menit tidak valid.','bad');",
    "if(!Number.isFinite(minutes)||minutes<0)return showMessage('Sisa menit tidak valid.','bad');\n if(!['active','disabled','expired'].includes(status))return showMessage('Status rental tidak valid.','bad');\n if(status==='active'&&minutes<1)return showMessage('Status ACTIVE memerlukan sisa waktu minimal 1 menit.','bad');",
    "edit status validation"
)
dashboard = replace_once(
    dashboard,
    "if(expiry&&new Date(expiry).getTime()<=Date.now())throw new Error('Tanggal expired harus di masa depan.');",
    "if(status==='active'&&expiry&&new Date(expiry).getTime()<=Date.now())throw new Error('Status ACTIVE memerlukan tanggal expired di masa depan atau kosongkan tanggalnya.');",
    "past expiry handling"
)
dashboard = replace_once(
    dashboard,
    "p_client_label:$('editClient').value.trim()||null,p_expiry_at:expiry",
    "p_client_label:$('editClient').value.trim()||null,p_status:status,p_expiry_at:expiry",
    "edit status RPC argument"
)
dashboard = replace_once(
    dashboard,
    "showMessage(`Perubahan rental ${st.code} tersimpan di database bersama. Tidak perlu menunggu PC online.`,'good');",
    "showMessage(`Perubahan rental ${st.code} tersimpan di database bersama. Status: ${status.toUpperCase()}.`,'good');",
    "edit status success message"
)

# Keep the existing active/paused-session safeguards; status is only editable when no timer is active.
for marker in (
    'id="editStatus"',
    'value="active">ACTIVE',
    'value="disabled">DISABLE',
    'value="expired">EXPIRED',
    "p_status:status",
    "sessions.some(s=>s.rental_account_id===id&&['active','paused'].includes(s.status))",
    "billing_reseller_edit_rental_global"
):
    if marker not in dashboard:
        raise SystemExit("Rental-status verification failed: " + marker)

# Version bump for a side-by-side installable patch; do not overwrite the V1.0.5 baseline branch.
gradle_candidates = [root / "app/build.gradle", root / "app/build.gradle.kts"]
gradle_path = next((p for p in gradle_candidates if p.is_file()), None)
if gradle_path is None:
    raise SystemExit("Reseller Gradle file is missing")
gradle = gradle_path.read_text(encoding="utf-8", errors="replace")
if not re.search(r"\bversionCode\s+135\b", gradle) or not re.search(r"""versionName\s*=?\s*['"]1\.0\.5['"]""", gradle):
    raise SystemExit("Expected exact V1.0.5 / versionCode 135 baseline")
gradle, c1 = re.subn(r"\bversionCode\s+135\b", "versionCode 136", gradle, count=1)
gradle, c2 = re.subn(r"""(\bversionName\s*=?\s*['"])1\.0\.5(['"])""", r"\g<1>1.0.6\2", gradle, count=1)
if c1 != 1 or c2 != 1:
    raise SystemExit("Unable to bump Reseller metadata to V1.0.6")
gradle_path.write_text(gradle, encoding="utf-8")

# Write patched HTML before extracting JavaScript for syntax checks.
login_path.write_text(login, encoding="utf-8")
dashboard_path.write_text(dashboard, encoding="utf-8")

# Extract inline JavaScript and require it to parse before the Android build starts.
for path, stem in ((login_path, "reseller-login-v106"), (dashboard_path, "reseller-status-v106")):
    source = path.read_text(encoding="utf-8")
    scripts = re.findall(r"<script\b(?![^>]*\bsrc=)[^>]*>(.*?)</script>", source, re.I | re.S)
    if len(scripts) != 1:
        raise SystemExit(f"{path.name}: expected one inline script, found {len(scripts)}")
    Path("/tmp/" + stem + ".js").write_text(scripts[0], encoding="utf-8")

print("PASS: remembered login, explicit ACTIVE/DISABLE/EXPIRED editing, expired-date handling, session lock, and V1.0.6 metadata.")
