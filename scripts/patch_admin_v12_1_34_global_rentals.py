from pathlib import Path

html_path = Path("android/app/src/main/assets/web/admin.html")
gradle_path = Path("android/app/build.gradle")
version_path = Path("VERSION.txt")

html = html_path.read_text(encoding="utf-8")

old_status_options = '<option value="active">active</option><option value="paused">paused</option><option value="expired">expired</option><option value="disabled">disabled</option><option value="inactive">inactive</option>'
new_status_options = '<option value="active">active</option><option value="expired">expired</option><option value="disabled">disabled</option>'
if html.count(old_status_options) != 1:
    raise SystemExit("Rental status option anchor mismatch; refusing unsupported statuses")
html = html.replace(old_status_options, new_status_options, 1)

# Global rental list: organization-scoped DB data, independent of device selection/status.
load_start = html.find("async function loadAccountsForSelectedDevice(){")
load_end = html.find("async function selectDevice(){", load_start)
if load_start < 0 or load_end < 0:
    raise SystemExit("Global rental list anchors not found; refusing to patch")
new_load = """async function loadAccountsForSelectedDevice(){
 if(!currentOrg)return;
 try{
  const rows=await rpc('admin_rental_accounts_global',{p_org_id:currentOrg.id});
  if(!Array.isArray(rows))throw new Error('Respons daftar rental DB tidak valid.');
  $('accountRows').innerHTML=rows.map(x=>'<tr><td><b>'+esc(x.code)+'</b></td><td>'+esc(x.category||'-')+'</td><td>'+Math.floor((Number(x.remaining_seconds)||0)/60)+' m</td><td>'+esc(x.status||'-')+'</td><td>'+esc(x.client_label||'-')+'</td><td>'+(x.expiry_at?new Date(x.expiry_at).toLocaleString('id-ID'):'Tanpa Batas')+'</td><td><button class="mini" data-rental-edit="'+encodeURIComponent(JSON.stringify(x))+'">Edit</button> <button class="mini danger" data-rental-disable="'+encodeURIComponent(x.id)+'" data-rental-code="'+encodeURIComponent(x.code)+'">Nonaktifkan</button></td></tr>').join('')||'<tr><td colspan="7" class="empty">Belum ada data rental untuk organisasi ini.</td></tr>';
 }catch(e){msg('Gagal memuat rental dari DB: '+(e.message||'error'),true)}
}
"""
html = html[:load_start] + new_load + html[load_end:]

# Create writes DB directly; no PC selection/online check, command queue, or PC ACK.
create_start = html.find("async function createRentalOnDevice(){")
create_end = html.find("async function loadReport(){", create_start)
if create_start < 0 or create_end < 0:
    raise SystemExit("Create rental anchors not found; refusing to patch")
new_create = """async function createRentalOnDevice(){
 try{
  if(!currentOrg)throw new Error('Organisasi belum dipilih.');
  const code=$('rentalCode').value.trim().toUpperCase();
  const minutes=Number($('rentalMinutes').value);
  if(!code)throw new Error('Kode rental wajib diisi.');
  if(code.length>120)throw new Error('Kode rental maksimal 120 karakter.');
  if(!Number.isFinite(minutes)||minutes<1||minutes>525600)throw new Error('Durasi harus 1 sampai 525600 menit.');
  const expiry=adminLocalToISO($('rentalExpiry').value);
  if(expiry&&new Date(expiry).getTime()<=Date.now())throw new Error('Tanggal expiry harus di masa depan.');
  const r=await rpc('admin_create_rental_global',{p_org_id:currentOrg.id,p_code:code,p_category:$('rentalCategory').value,p_minutes:Math.round(minutes),p_client_label:$('rentalClient').value.trim()||null,p_expiry_at:expiry});
  if(r?.ok!==true)throw new Error('Database tidak mengonfirmasi pembuatan rental.');
  $('rentalCode').value='';$('rentalClient').value='';$('rentalExpiry').value='';$('rentalMinutes').value='60';
  msg('Rental '+code+' langsung tersimpan di DB bersama. Tidak perlu memilih PC atau menunggu PC online.');
  await Promise.all([loadAccountsForSelectedDevice(),loadReport()]);
 }catch(e){msg('Gagal menambahkan rental: '+(e.message||'error tidak diketahui'),true)}
}
"""
html = html[:create_start] + new_create + html[create_end:]

# Edit is a single atomic server RPC, independent of selected/online PCs.
edit_start = html.find("async function saveAdminRentalEdit(){")
edit_end = html.find("document.addEventListener('click',ev=>{const b=ev.target.closest('button[data-rental-edit]');", edit_start)
if edit_start < 0 or edit_end < 0:
    raise SystemExit("Edit rental anchors not found; refusing to patch")
new_edit = """async function saveAdminRentalEdit(){
 if(!adminRentalEditState)return;
 const st=adminRentalEditState;
 try{
  if(!currentOrg)throw new Error('Organisasi belum dipilih.');
  const code=$('adminEditRentalCode').value.trim().toUpperCase();
  if(!code)throw new Error('Kode rental wajib diisi.');
  if(code.length>120)throw new Error('Kode rental maksimal 120 karakter.');
  const nextMinutes=Number($('adminEditRentalMinutes').value);
  if(!Number.isFinite(nextMinutes)||nextMinutes<0||nextMinutes>525600)throw new Error('Sisa menit harus 0 sampai 525600.');
  const expiry=adminLocalToISO($('adminEditRentalExpiry').value);
  if(expiry&&new Date(expiry).getTime()<=Date.now())throw new Error('Tanggal expiry harus di masa depan.');
  const category=$('adminEditRentalCategory').value;
  const status=$('adminEditRentalStatus').value;
  const client=$('adminEditRentalClient').value.trim()||null;
  const r=await rpc('admin_update_rental_global',{p_org_id:currentOrg.id,p_rental_id:st.id,p_code:code,p_category:category,p_minutes:Math.round(nextMinutes),p_client_label:client,p_expiry_at:expiry,p_status:status});
  if(r?.ok!==true)throw new Error('Database tidak mengonfirmasi perubahan rental.');
  closeAdminRentalEdit();
  msg('Rental '+code+' langsung diperbarui di DB bersama. PC tidak perlu online.');
  await Promise.all([loadAccountsForSelectedDevice(),loadReport()]);
 }catch(e){msg('Gagal edit '+st.code+': '+(e.message||'error'),true)}
}
"""
html = html[:edit_start] + new_edit + html[edit_end:]

old_click_listener = "document.addEventListener('click',ev=>{const b=ev.target.closest('button[data-rental-edit]');"
new_click_listener = "document.addEventListener('click',ev=>{const d=ev.target.closest('button[data-rental-disable]');if(d){void deleteRental(decodeURIComponent(d.dataset.rentalDisable||''),decodeURIComponent(d.dataset.rentalCode||''));return}const b=ev.target.closest('button[data-rental-edit]');"
if html.count(old_click_listener) != 1:
    raise SystemExit("Rental table delegated click listener anchor mismatch")
html = html.replace(old_click_listener, new_click_listener, 1)

# Delete UI becomes a soft-disable, preserving historical references.
del_start = html.find("async function deleteRental(id,code){")
del_end = html.find("\n", del_start)
if del_start < 0 or del_end < 0:
    raise SystemExit("Delete rental function anchor not found; refusing to patch")
new_delete = """async function deleteRental(id,code){
 if(!confirm('Nonaktifkan rental '+code+'? Histori transaksi akan tetap tersimpan.'))return;
 try{
  const r=await rpc('admin_disable_rental_global',{p_org_id:currentOrg.id,p_rental_id:id});
  if(r?.ok!==true)throw new Error('Database tidak mengonfirmasi nonaktifkan rental.');
  msg('Rental '+code+' dinonaktifkan langsung di DB. Histori tetap tersimpan.');
  await Promise.all([loadAccountsForSelectedDevice(),loadReport()]);
 }catch(e){msg('Gagal menonaktifkan '+code+': '+(e.message||'error'),true)}
}"""
html = html[:del_start] + new_delete + html[del_end:]

html = html.replace("Monitoring saldo waktu dan histori.", "Data bersama seluruh PC • tambah/edit langsung ke DB • tidak perlu memilih PC atau menunggu PC online.", 1)
for token in ("admin_rental_accounts_global", "admin_create_rental_global", "admin_update_rental_global", "admin_disable_rental_global"):
    if html.count(token) != 1:
        raise SystemExit("Expected exactly one " + token + " call")
create_section=html[html.find("async function createRentalOnDevice(){"):html.find("async function loadReport(){")]
if "selectedDeviceId" in create_section or "uiStatus!=='online'" in create_section or "waitDeviceCommand" in create_section:
    raise SystemExit("Rental creation still depends on device selection/online/ACK")

gradle = gradle_path.read_text(encoding="utf-8")
if "versionCode 61" not in gradle or "versionName '12.1.33'" not in gradle:
    raise SystemExit("Unexpected Admin base version; expected V12.1.33 / code 61")
gradle = gradle.replace("versionCode 61", "versionCode 62", 1)
gradle = gradle.replace("versionName '12.1.33'", "versionName '12.1.34'", 1)
if "V12.1.33-OFFLINE-RESTART-QUEUE" not in html:
    raise SystemExit("Admin V12.1.33 marker missing; baseline patch not applied")
html = html.replace("V12.1.33-OFFLINE-RESTART-QUEUE", "V12.1.34-GLOBAL-RENTAL-DB-FIRST", 1)
html_path.write_text(html, encoding="utf-8")
gradle_path.write_text(gradle, encoding="utf-8")
version_path.write_text("v12.1.34-global-rental-db-first\n", encoding="utf-8")
print("PASS: Admin rental list/create/edit/disable now uses global DB RPCs without selected-PC/online prerequisites.")
