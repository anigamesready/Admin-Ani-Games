#!/usr/bin/env python3
"""Patch Reseller UI so rental-account CRUD uses one org-wide list, independent of PC presence."""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
web_candidates = [
    p for p in root.rglob("index.html")
    if p.parent.name == "web" and (p.parent / "admin-control.html").is_file()
]
if len(web_candidates) != 1:
    raise SystemExit(f"Expected one Reseller WebView index/admin-control pair, found {len(web_candidates)}")

dashboard_path = web_candidates[0].parent / "admin-control.html"
html = dashboard_path.read_text(encoding="utf-8")

required_once = [
    "function refreshAll(manual=false)",
    "async function loadRentals(force=false){",
    "function renderRentals(){",
    "function updateFormGuard(){",
    "$('rentalForm').addEventListener('submit',async e=>{",
    "function openEdit(id){",
    "$('editForm').addEventListener('submit',async e=>{",
]
for marker in required_once:
    count = html.count(marker)
    if count != 1:
        raise SystemExit(f"Expected one occurrence of {marker!r}, found {count}")

def replace_between(source: str, start: str, end: str, replacement: str, label: str) -> str:
    if source.count(start) != 1 or source.count(end) != 1:
        raise SystemExit(f"{label}: start/end marker is missing or ambiguous")
    a = source.index(start)
    b = source.index(end, a + len(start))
    if b <= a:
        raise SystemExit(f"{label}: invalid marker order")
    return source[:a] + replacement + source[b:]

# The selected PC remains useful for monitoring and sessions, but no longer scopes the rental list.
old_refresh_gate = "if(selectedId&&devices.some(d=>d.id===selectedId)){await loadRentals(manual||activeView==='members'||Date.now()-lastRentalsAt>45000)}else{rentals=[];lastRentalsAt=Date.now()}"
if html.count(old_refresh_gate) != 1:
    raise SystemExit("Refresh rental gate did not match the inspected baseline")
html = html.replace(
    old_refresh_gate,
    "await loadRentals(manual||activeView==='members'||Date.now()-lastRentalsAt>45000);",
    1
)

html = replace_between(
    html,
    "async function loadRentals(force=false){",
    "function renderRentals(){",
    """async function loadRentals(force=false){
 if(!force&&Date.now()-lastRentalsAt<25000)return;
 try{
  const rows=await rpc('billing_reseller_rental_accounts_global',{p_session_token:token,p_org_id:org.id});
  rentals=Array.isArray(rows)?rows:[];
  lastRentalsAt=Date.now();
  renderRentals();renderStats();renderSelectedPc();
 }catch(e){showMessage('Data rental bersama gagal dimuat: '+(e.message||'error'),'bad')}
}
""",
    "global rental loader"
)

html = replace_between(
    html,
    "function renderRentals(){",
    "function updateFormGuard(){",
    """function renderRentals(){
 const wrap=$('memberRows');if(!wrap)return;
 const q=($('memberSearch')?.value||'').trim().toLowerCase(),filter=$('memberFilter')?.value||'all';
 const activeCodes=new Set(sessions.filter(s=>['active','paused'].includes(s.status)).map(s=>String(s.code||'').toUpperCase()));
 const rows=rentals.filter(r=>{
  const status=String(r.status||'').toLowerCase();
  const search=String(r.code||'').toLowerCase().includes(q)||String(r.client_label||'').toLowerCase().includes(q);
  return search&&(filter==='all'||status===filter)
 });
 if(!rows.length){wrap.innerHTML='<div class="empty">Belum ada member pada daftar rental bersama, atau tidak ada data yang cocok.</div>';return}
 wrap.innerHTML=`<table><thead><tr><th>Kode</th><th>Nama Member</th><th>Kategori</th><th>Sisa Waktu</th><th>Expired</th><th>Status</th><th>Aksi</th></tr></thead><tbody>${rows.map(r=>{
  const st=String(r.status||'active').toLowerCase(),cls=st==='active'?'active':st==='expired'?'expired':'done',busy=activeCodes.has(String(r.code||'').toUpperCase());
  return `<tr><td><b>${esc(r.code)}</b></td><td>${esc(r.client_label||'—')}</td><td>${esc(r.category||'reguler')}</td><td>${esc(secsText(r.remaining_seconds))}</td><td>${esc(fmtDate(r.expiry_at))}</td><td><span class="status ${cls}">${esc(st.toUpperCase())}</span></td><td><button class="btn small secondary" ${busy?'disabled title="Sesi member sedang aktif"':''} onclick="openEdit('${esc(r.id)}')">Edit</button></td></tr>`
 }).join('')}</tbody></table>`
}
""",
    "global rental list renderer"
)

html = replace_between(
    html,
    "function updateFormGuard(){",
    "function resetRentalForm(){",
    """function updateFormGuard(){
 const valid=!!$('rentalCode').value.trim();
 $('saveRentalBtn').disabled=!valid;
 $('formPcBadge').textContent='DATA GLOBAL · Tidak terikat status PC';
 $('saveRentalBtn').title='Disimpan ke daftar rental bersama; PC tidak harus online';
}
""",
    "global rental form guard"
)

# The PC status panel must not overwrite the global-form badge.
for old in [
    "$('formPcBadge').textContent='Belum ada PC';",
    "$('formPcBadge').textContent=(d.device_name||d.client_id||'PC')+' · '+(online?'Online':'Offline')"
]:
    count = html.count(old)
    if count != 1:
        raise SystemExit(f"Expected one PC-specific form badge assignment, found {count}: {old}")
    html = html.replace(old, "", 1)

html = replace_between(
    html,
    "$('rentalForm').addEventListener('submit',async e=>{",
    "function openEdit(id){",
    """$('rentalForm').addEventListener('submit',async e=>{
 e.preventDefault();
 const code=$('rentalCode').value.trim().toUpperCase(),minutes=Number($('rentalMinutes').value);
 if(!code)return showMessage('Kode rental wajib diisi.','bad');
 if(!Number.isFinite(minutes)||minutes<1)return showMessage('Durasi minimal 1 menit.','bad');
 $('saveRentalBtn').disabled=true;$('saveRentalBtn').textContent='Menyimpan…';
 try{
  const expiry=localDateToISO($('rentalExpiry').value);
  if(expiry&&new Date(expiry).getTime()<=Date.now())throw new Error('Tanggal expired harus di masa depan.');
  await rpc('billing_reseller_create_rental_global',{
   p_session_token:token,p_org_id:org.id,p_code:code,
   p_category:$('rentalCategory').value,p_minutes:Math.round(minutes),
   p_client_label:$('rentalClient').value.trim()||null,p_expiry_at:expiry
  });
  resetRentalForm();
  await loadRentals(true);
  showMessage(`Rental ${code} berhasil ditambahkan ke daftar bersama. Tidak perlu memilih PC atau menunggu PC online.`,'good');
  showView('members');
 }catch(err){showMessage('Gagal menambahkan rental: '+(err.message||'error tidak diketahui'),'bad')}
 finally{$('saveRentalBtn').textContent='Simpan Rental';updateFormGuard()}
});
""",
    "global rental create handler"
)

html = replace_between(
    html,
    "$('editForm').addEventListener('submit',async e=>{",
    "function loadAudio(){",
    """$('editForm').addEventListener('submit',async e=>{
 e.preventDefault();if(!editRentalState)return;
 const st=editRentalState,minutes=Number($('editMinutes').value);
 if(!Number.isFinite(minutes)||minutes<0)return showMessage('Sisa menit tidak valid.','bad');
 $('editSaveBtn').disabled=true;$('editSaveBtn').textContent='Menyimpan…';
 try{
  const expiry=localDateToISO($('editExpiry').value);
  if(expiry&&new Date(expiry).getTime()<=Date.now())throw new Error('Tanggal expired harus di masa depan.');
  await rpc('billing_reseller_edit_rental_global',{
   p_session_token:token,p_org_id:org.id,p_rental_id:st.id,
   p_category:$('editCategory').value,p_minutes:Math.round(minutes),
   p_client_label:$('editClient').value.trim()||null,p_expiry_at:expiry
  });
  closeEdit();
  await loadRentals(true);
  showMessage(`Perubahan rental ${st.code} tersimpan di database bersama. Tidak perlu menunggu PC online.`,'good');
 }catch(err){showMessage('Gagal mengedit rental: '+(err.message||'error tidak diketahui'),'bad')}
 finally{$('editSaveBtn').disabled=false;$('editSaveBtn').textContent='Simpan Perubahan'}
});
""",
    "global rental edit handler"
)

# Keep the PC picker for monitoring, but make the member/rental copy explicit about global scope.
text_replacements = {
    "Menampilkan data dari PC yang dipilih.": "Satu daftar rental bersama untuk seluruh organisasi; tidak bergantung pada PC yang dipilih.",
    "Pilih PC dulu.": "Data member rental bersama akan tampil di sini.",
    "Masukkan data member untuk PC yang dipilih.": "Data rental disimpan bersama tanpa harus memilih PC.",
    '<span id="formPcBadge" class="pill">Belum ada PC</span>': '<span id="formPcBadge" class="pill">DATA GLOBAL</span>',
    "Rental baru akan disimpan ke Supabase dan dikirim ke antrean sinkronisasi PC. Hasil akhir akan menunjukkan apakah PC sudah mengonfirmasi penerimaan data.": "Data disimpan langsung ke database rental bersama. PC tidak harus online; pembaruan ke PC yang pernah memakai akun hanya masuk antrean dan tidak ditunggu.",
    "Pilih PC di atas untuk melihat status dan rental.": "Pilih PC hanya untuk melihat status perangkat dan sesi aktif; daftar member rental dikelola terpisah."
}
for old, new in text_replacements.items():
    count = html.count(old)
    expected_count = 2 if old == "Pilih PC di atas untuk melihat status dan rental." else 1
    if count != expected_count:
        raise SystemExit(f"Expected {expected_count} UI copy occurrence(s), found {count}: {old}")
    html = html.replace(old, new)

for marker in (
    "billing_reseller_rental_accounts_global",
    "billing_reseller_create_rental_global",
    "billing_reseller_edit_rental_global",
    "DATA GLOBAL · Tidak terikat status PC"
):
    if marker not in html:
        raise SystemExit("Missing global rental feature marker: " + marker)

# Guard against the old PC-gated CRUD paths surviving in the active form handlers.
create_start = html.index("$('rentalForm').addEventListener('submit',async e=>{")
create_end = html.index("function openEdit(id){", create_start)
create_handler = html[create_start:create_end]
edit_start = html.index("$('editForm').addEventListener('submit',async e=>{")
edit_end = html.index("function loadAudio(){", edit_start)
edit_handler = html[edit_start:edit_end]
for forbidden in ("billing_create_rental'", "waitCommand(", "isOnline(d)", "currentDevice()"):
    if forbidden in create_handler:
        raise SystemExit("Old PC-dependent create logic remains: " + forbidden)
for forbidden in ("billing_edit_rental'", "waitCommand(", "currentDevice()"):
    if forbidden in edit_handler:
        raise SystemExit("Old PC-dependent edit logic remains: " + forbidden)

# Preserve the existing locked baseline and bump only this isolated Reseller branch.
gradle_candidates = [root / "app/build.gradle", root / "app/build.gradle.kts"]
gradle_path = next((p for p in gradle_candidates if p.is_file()), None)
if gradle_path is None:
    raise SystemExit("Reseller Gradle file is missing")
gradle = gradle_path.read_text(encoding="utf-8", errors="replace")
gradle, code_count = re.subn(r"\bversionCode\s+133\b", "versionCode 134", gradle, count=1)
gradle, name_count = re.subn(
    r"(\bversionName\s*=?\s*['\"])1\.0\.3(['\"])",
    r"\g<1>1.0.4\2",
    gradle,
    count=1
)
if code_count != 1 or name_count != 1:
    raise SystemExit("Expected exact Reseller V11.30.3 version metadata; refusing unknown Gradle version")
gradle_path.write_text(gradle, encoding="utf-8")
dashboard_path.write_text(html, encoding="utf-8")

# Export the final inline JS for the workflow's Node syntax check.
scripts = re.findall(r"<script\b(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.I | re.S)
if len(scripts) != 1:
    raise SystemExit(f"Expected one inline Reseller dashboard script, found {len(scripts)}")
Path("/tmp/reseller-global-rental-dashboard.js").write_text(scripts[0], encoding="utf-8")

print("PASS: shared org-wide rental list, add/edit without PC online dependency, active-session edit guard, and APK version 1.0.4 patched.")
# Android WebView login compatibility is patched by the preceding DB route patch.
# Keep workflow rebuilds deterministic after quote-style-independent Gradle version validation.
# Trigger build with corrected Gradle audit regex.
# Rebuild against corrected workflow regex.
