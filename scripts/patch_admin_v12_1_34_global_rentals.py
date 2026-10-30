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
gradle = gradle.replace("versionCode 61", "versionCode 63", 1)
gradle = gradle.replace("versionName '12.1.33'", "versionName '12.1.35'", 1)
if "V12.1.33-OFFLINE-RESTART-QUEUE" not in html:
    raise SystemExit("Admin V12.1.33 marker missing; baseline patch not applied")
html = html.replace("V12.1.33-OFFLINE-RESTART-QUEUE", "V12.1.35-GLOBAL-RENTAL-DB-FIRST-NO-PC-RENTAL", 1)

# V12.1.35: move global rental management into the Rental tab and remove PC coupling.
# The device selector remains available only for remote PC controls.
card_start = html.find('<div class="card" style="margin-top:12px"><h3>Tambah Data Rental ke PC</h3>')
card_end_marker = '\n\n<div class="card" id="freeTestPolicyCard"'
card_end = html.find(card_end_marker, card_start)
if card_start < 0 or card_end < 0:
    raise SystemExit("Global rental form block anchors not found; refusing to move the card")
rental_card = html[card_start:card_end].strip()
html = html[:card_start] + html[card_end:]

replacements = [
    ("<h3>Tambah Data Rental ke PC</h3>", "<h3>Tambah Data Rental</h3>"),
    (
      '<div class="muted"><b>PC wajib dipilih di baris PC Remote Aktif di bagian paling atas.</b> Data dibuat di cloud dan dikirim hanya ke PC tersebut melalui command queue.</div>',
      '<div class="muted">Data rental disimpan langsung ke database bersama untuk seluruh PC dalam workspace ini. PC tidak perlu dipilih atau sedang online.</div>'
    ),
    ('<div class="field"><label>PC</label><select id="rentalDevice"></select></div>', ''),
    ('Buat &amp; Kirim ke PC', 'Simpan Rental ke Database'),
    ('Buat & Kirim ke PC', 'Simpan Rental ke Database')
]
for old, new in replacements:
    if rental_card.count(old) != 1:
        raise SystemExit("Rental form UI anchor mismatch: " + old[:90])
    rental_card = rental_card.replace(old, new, 1)
if "rentalDevice" in rental_card or "Pilih PC" in rental_card or "Kirim ke PC" in rental_card:
    raise SystemExit("Rental form still contains a PC prerequisite")
accounts_open = '<section id="accounts" class="section">'
accounts_start = html.find(accounts_open)
if accounts_start < 0:
    raise SystemExit("Rental tab anchor not found")
accounts_insert = accounts_start + len(accounts_open)
html = html[:accounts_insert] + rental_card + html[accounts_insert:]
accounts_end = html.find("</section>", accounts_insert)
if accounts_end < 0 or not (accounts_insert < html.find("Tambah Data Rental") < accounts_end):
    raise SystemExit("Rental form was not inserted inside the Rental tab")

# Make the global account view load on its own, never through loadDevices().
html = html.replace("loadAccountsForSelectedDevice", "loadGlobalRentalAccounts")
html = html.replace("createRentalOnDevice", "createGlobalRental")
old_accounts_tab = "if(id==='accounts'){if(!selectedDeviceId)loadDevices();else loadGlobalRentalAccounts()}"
if html.count(old_accounts_tab) != 1:
    raise SystemExit("Rental tab still uses PC selection to decide whether to load accounts")
html = html.replace(old_accounts_tab, "if(id==='accounts')loadGlobalRentalAccounts()", 1)

old_org_select = "function selectOrg(){currentOrg=orgs.find(o=>o.id===$('orgSelect').value)||null;selectedDeviceId=null;selectedDevice=null;localStorage.removeItem(GLOBAL_DEVICE_KEY);refresh()}"
new_org_select = "function selectOrg(){currentOrg=orgs.find(o=>o.id===$('orgSelect').value)||null;selectedDeviceId=null;selectedDevice=null;localStorage.removeItem(GLOBAL_DEVICE_KEY);refresh();if($('accounts').classList.contains('active'))loadGlobalRentalAccounts()}"
if html.count(old_org_select) != 1:
    raise SystemExit("Workspace switch anchor mismatch")
html = html.replace(old_org_select, new_org_select, 1)

# Remove obsolete PC-specific rental dropdown population from device discovery.
rental_device_start = html.find("$('rentalDevice').innerHTML=rows.map(", html.find("async function loadDevices(){"))
rental_device_end_marker = "$('rentalDevice').value=selectedDeviceId||'';"
rental_device_end = html.find(rental_device_end_marker, rental_device_start)
if rental_device_start < 0 or rental_device_end < 0:
    raise SystemExit("Obsolete rental PC selector population not found")
html = html[:rental_device_start] + html[rental_device_end + len(rental_device_end_marker):]
if "rentalDevice" in html:
    raise SystemExit("PC-specific rental selector reference remains after patch")

# Global rentals must not be shown as if they belong to one selected PC.
old_pc_rental_table = '<h4>Rental di PC terpilih</h4><div class="table-wrap"><table class="table"><thead><tr><th>Kode</th><th>Kategori</th><th>Sisa</th><th>Status</th><th>Client</th></tr></thead><tbody id="selectedRentalRows"></tbody></table></div>'
if html.count(old_pc_rental_table) != 1:
    raise SystemExit("PC rental subtable anchor mismatch")
html = html.replace(
    old_pc_rental_table,
    '<div class="muted">Data rental dikelola terpusat di menu Rental. Pemilihan PC di sini hanya untuk status dan kendali jarak jauh.</div>',
    1
)
render_start = html.find("async function renderSelectedDevice(){")
render_end = html.find("async function disconnectDevice", render_start)
if render_start < 0 or render_end < 0:
    raise SystemExit("Selected-PC renderer anchors not found")
new_render = """async function renderSelectedDevice(){
 if(!selectedDevice){
  $('selectedDeviceMeta').textContent='Belum ada PC terpilih.';
  $('selectedStatus').textContent='-';
  $('selectedCode').textContent='-';
  $('selectedRemaining').textContent='-';
  $('selectedHeartbeat').textContent='-';
  return;
 }
 const m=selectedDevice.metadata||{};
 const active=selectedDevice.uiStatus==='online';
 $('selectedDeviceMeta').innerHTML='<b>'+esc(selectedDevice.device_name)+'</b> • '+esc(selectedDevice.client_id)+' • App '+esc(selectedDevice.app_version||'-')+'<br>Last seen: '+(selectedDevice.last_seen_at?new Date(selectedDevice.last_seen_at).toLocaleString('id-ID'):'-');
 const state=active?(m.activeCode?'RENTAL AKTIF':m.pausedCode?'RENTAL PAUSED':'STANDBY / BILLING SIAP'):'TERPUTUS';
 $('selectedStatus').textContent=state;
 $('selectedCode').textContent=m.activeCode||m.pausedCode||'-';
 $('selectedRemaining').textContent=(m.activeCode||m.pausedCode)?Math.floor((Number(m.activeRemainingSeconds||m.pausedRemainingSeconds)||0)/60)+' m':'-';
 $('selectedHeartbeat').textContent=selectedDevice.last_heartbeat_at?new Date(selectedDevice.last_heartbeat_at).toLocaleTimeString('id-ID'):'-';
}
"""
html = html[:render_start] + new_render + html[render_end:]

# Clarify that the global PC selector is for remote operations only.
old_global_pc_help = '<div class="muted">Pilih PC terlebih dahulu. Semua rental, sesi, dan kontrol Windows di halaman ini mengikuti PC yang dipilih.</div>'
new_global_pc_help = '<div class="muted">Pilihan PC hanya untuk status dan kendali jarak jauh. Data rental tersimpan bersama dan dapat dipakai dari PC mana saja.</div>'
if html.count(old_global_pc_help) != 1:
    raise SystemExit("Global PC selector helper-text anchor mismatch")
html = html.replace(old_global_pc_help, new_global_pc_help, 1)
if html.count("<h2 style=\"margin:0\">Akun Rental</h2>") != 1:
    raise SystemExit("Rental tab title anchor mismatch")
html = html.replace("<h2 style=\"margin:0\">Akun Rental</h2>", "<h2 style=\"margin:0\">Data Rental Bersama</h2>", 1)

# No create/edit/list path is allowed to wait for a selected or online PC.
create_start = html.find("async function createGlobalRental(){")
create_end = html.find("async function loadReport(){", create_start)
create_fn = html[create_start:create_end]
if create_start < 0 or create_end < 0 or "admin_create_rental_global" not in create_fn:
    raise SystemExit("Global create function missing after UI move")
for forbidden in ("selectedDeviceId", "rentalDevice", "uiStatus", "waitDeviceCommand", "admin_command"):
    if forbidden in create_fn:
        raise SystemExit("Global create still depends on PC state: " + forbidden)
if "admin_update_rental_global" not in html or "admin_disable_rental_global" not in html:
    raise SystemExit("Global edit/disable RPC handlers are missing")
if "function tab(id){if(id==='pairing'&&ctx?.role!=='owner')return;document.querySelectorAll('.section').forEach(x=>x.classList.remove('active'));$(id).classList.add('active');document.querySelectorAll('.nav button').forEach(x=>x.classList.toggle('active',x.dataset.tab===id));if(id==='pairing')applyPairingRoleUI();if(id==='devices')loadDevices();if(id==='accounts')loadGlobalRentalAccounts();if(id==='reports')loadReport();if(id==='billingUsers'){loadBillingUsers().then(()=>bindBillingUserActions())}}" not in html:
    raise SystemExit("Rental tab global loading assertion failed")

html_path.write_text(html, encoding="utf-8")
gradle_path.write_text(gradle, encoding="utf-8")
version_path.write_text("v12.1.35-global-rental-db-first-no-pc-form\n", encoding="utf-8")
print("PASS: Admin rental UI is in the Rental tab; global list/create/edit/disable use DB RPCs without selected-PC/online prerequisites.")
