from pathlib import Path
import re
import sys

ROOT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd()
PAGE=ROOT/"android/app/src/main/assets/web/admin.html"
GRADLE=ROOT/"android/app/build.gradle"
MANIFEST=ROOT/"android/app/src/main/AndroidManifest.xml"
VERSION=ROOT/"VERSION.txt"
MARKER="V12.1.52-REMOTE-PLAY-ADMIN-CONTROLS"

for path in (PAGE,GRADLE,MANIFEST):
    if not path.is_file():
        raise SystemExit("Required Admin project file missing: "+str(path))

page=PAGE.read_text(encoding="utf-8")
gradle=GRADLE.read_text(encoding="utf-8")
manifest=MANIFEST.read_text(encoding="utf-8")
if MARKER in page:
    print("PASS: Admin V12.1.52 Remote Play controls already applied")
    raise SystemExit(0)

nav_anchor='<button data-tab="devices" onclick="tab(\'devices\')">🖥 PC Aktif</button>'
if page.count(nav_anchor)!=1:
    raise SystemExit("Admin navigation anchor mismatch")
page=page.replace(
    nav_anchor,
    nav_anchor+'<button id="remotePlayAdminNav" data-tab="remotePlay" onclick="tab(\'remotePlay\')">🎮 Remote Play</button>',
    1
)

section_anchor='<section id="accounts" class="section">'
if page.count(section_anchor)!=1:
    raise SystemExit("Admin Rental section anchor mismatch")
section=r"""
<section id="remotePlay" class="section">
 <div class="card" style="margin-top:12px">
  <div class="top"><div><h3 style="margin:0">🎮 Ani Remote Play</h3><div class="muted">Kontrol izin PC Host dan akun rental dari DB Android. Hanya Master/Owner yang dapat membuka menu ini.</div></div><button class="primary" type="button" onclick="loadRemotePlayAdmin()">Refresh Status</button></div>
  <div class="msg" id="remotePlayAdminStatus" role="status" aria-live="polite" style="margin-top:10px">Status belum dimuat. Tekan Refresh Status untuk membaca server.</div>
  <div class="cards2" style="margin-top:12px">
   <div class="card"><div class="label">PC Host</div><div class="stat" id="remotePlayHostCount">—</div><div class="muted">Izin aktif / total PC pada workspace</div></div>
   <div class="card"><div class="label">Akun Rental</div><div class="stat" id="remotePlayRentalCount">—</div><div class="muted">Izin Remote Play aktif / total rental</div></div>
   <div class="card"><div class="label">Sesi Berjalan</div><div class="stat" id="remotePlaySessionCount">—</div><div class="muted">Sesi starting / active yang belum diselesaikan</div></div>
  </div>
 </div>
 <div class="card" style="margin-top:12px">
  <div class="top"><div><h3 style="margin:0">🖥 Izin PC Host</h3><div class="muted">PC wajib diizinkan sebelum Host Agent dapat didaftarkan dan menerima sesi Remote Play.</div></div></div>
  <div class="table-wrap"><table><thead><tr><th>PC</th><th>Status Host</th><th>Izin</th><th>Aksi</th></tr></thead><tbody id="remotePlayHostRows"><tr><td colspan="4" class="empty">Tekan Refresh Status.</td></tr></tbody></table></div>
 </div>
 <div class="card" style="margin-top:12px">
  <div class="top"><div><h3 style="margin:0">👤 Izin Akun Rental</h3><div class="muted">Aktivasi Remote Play berbeda dari login rental PC biasa. Kode aktivasi ditampilkan satu kali setelah diterbitkan.</div></div></div>
  <div class="table-wrap"><table><thead><tr><th>Rental</th><th>Sisa Waktu</th><th>Status Remote Play</th><th>Aksi</th></tr></thead><tbody id="remotePlayRentalRows"><tr><td colspan="4" class="empty">Tekan Refresh Status.</td></tr></tbody></table></div>
 </div>
 <div class="card" style="margin-top:12px">
  <div class="top"><div><h3 style="margin:0">🕹 Sesi Remote Play</h3><div class="muted">Riwayat terbaru, batas maksimal 3 jam per sesi. Cooldown diterapkan oleh DB.</div></div></div>
  <div class="table-wrap"><table><thead><tr><th>Rental</th><th>PC</th><th>Status</th><th>Mulai</th><th>Batas Waktu</th><th>Selesai</th></tr></thead><tbody id="remotePlaySessionRows"><tr><td colspan="6" class="empty">Tekan Refresh Status.</td></tr></tbody></table></div>
 </div>
 <div class="card hidden" id="remotePlayOneTimeCard" style="margin-top:12px;border:1px solid var(--a)">
  <div class="top"><div><h3 style="margin:0" id="remotePlayOneTimeTitle">Kode Satu Kali</h3><div class="muted">Kode hanya muncul pada layar ini setelah diterbitkan. Salin dan berikan ke penerima yang benar. Kode tidak disimpan oleh UI.</div></div><button type="button" onclick="dismissRemotePlayOneTimeCode()">Tutup</button></div>
  <input id="remotePlayOneTimeCode" type="text" readonly autocomplete="off" style="font-family:monospace;font-size:18px;font-weight:700;letter-spacing:1px;margin-top:10px">
  <div class="muted" id="remotePlayOneTimeExpiry" style="margin-top:6px"></div>
  <div class="row" style="margin-top:10px"><button type="button" class="primary" onclick="copyRemotePlayOneTimeCode()">Salin Kode</button><button type="button" onclick="dismissRemotePlayOneTimeCode()">Sudah Disalin</button></div>
 </div>
</section>
"""
page=page.replace(section_anchor,section+section_anchor,1)

tab_anchor="function tab(id){if(id==='pairing'&&ctx?.role!=='owner')return;"
if page.count(tab_anchor)!=1:
    raise SystemExit("Admin tab permission anchor mismatch")
page=page.replace(tab_anchor,"function tab(id){if(id==='pairing'&&ctx?.role!=='owner')return;if(id==='remotePlay'&&!isRemotePlayOwner())return;",1)
tab_loader="if(id==='billingUsers'){loadBillingUsers().then(()=>bindBillingUserActions())}}"
if page.count(tab_loader)!=1:
    raise SystemExit("Admin tab loader anchor mismatch")
page=page.replace(tab_loader,"if(id==='billingUsers'){loadBillingUsers().then(()=>bindBillingUserActions())}if(id==='remotePlay')loadRemotePlayAdmin()}",1)

boot_anchor="renderOrgs();applyPairingRoleUI();"
if page.count(boot_anchor)!=1:
    raise SystemExit("Admin boot role UI anchor mismatch")
page=page.replace(boot_anchor,"renderOrgs();applyPairingRoleUI();applyRemotePlayRoleUI();",1)

script_anchor="const LOCAL_API_KEY='ani_games_ready_db_android_api_url_v1';"
if page.count(script_anchor)!=1:
    raise SystemExit("Admin local API insertion anchor mismatch")
functions=r"""
// V12.1.52-REMOTE-PLAY-ADMIN-CONTROLS — DB Android owner-only Remote Play operations.
function isRemotePlayOwner(){return String(ctx?.role||'').trim().toLowerCase()==='owner';}
function applyRemotePlayRoleUI(){const nav=$('remotePlayAdminNav');if(nav)nav.classList.toggle('hidden',!isRemotePlayOwner());}
function remotePlayDate(value){if(!value)return '-';const d=new Date(value);return Number.isNaN(d.getTime())?'-':d.toLocaleString('id-ID');}
function remotePlayText(value){return esc(value===null||value===undefined||value===''?'-':value);}
function remotePlayMessage(text,error){const el=$('remotePlayAdminStatus');if(!el)return;el.textContent=String(text||'');el.style.borderLeftColor=error?'#ff4d6d':'var(--a)';}
function remotePlayUuid(value){const id=String(value||'');return /^[0-9a-f-]{36}$/i.test(id)?id:'';}
function renderRemotePlayAdmin(data){
 const hosts=Array.isArray(data?.host_devices)?data.host_devices:[];
 const rentals=Array.isArray(data?.rental_accounts)?data.rental_accounts:[];
 const sessions=Array.isArray(data?.sessions)?data.sessions:[];
 const hostEnabled=hosts.filter(x=>x.permission_enabled===true).length;
 const rentalEnabled=rentals.filter(x=>x.permission_enabled===true).length;
 const active=sessions.filter(x=>x.status==='starting'||x.status==='active').length;
 $('remotePlayHostCount').textContent=hostEnabled+' / '+hosts.length;
 $('remotePlayRentalCount').textContent=rentalEnabled+' / '+rentals.length;
 $('remotePlaySessionCount').textContent=String(active);
 $('remotePlayHostRows').innerHTML=hosts.map(h=>{
  const id=remotePlayUuid(h.device_id);if(!id)return '';
  const permitted=h.permission_enabled===true;
  const ready=h.agent_enrolled===true&&h.sunshine_ready===true&&h.media_path_ready===true;
  const online=h.host_last_seen_at&&Date.now()-new Date(h.host_last_seen_at).getTime()<60000;
  const state=ready?'SUNSHINE SIAP':(h.agent_enrolled?'HOST BELUM SIAP':(h.device_online?'PC ONLINE':'PC OFFLINE'));
  const details=[h.agent_enrolled?'Agent '+(h.agent_version||'terdaftar'):'Belum enroll',h.host_last_seen_at?'Heartbeat '+remotePlayDate(h.host_last_seen_at):'Belum ada heartbeat',h.media_address?'Route '+h.media_address:'Route belum disetel'].join(' • ');
  const permitButton='<button class="mini '+(permitted?'danger':'primary')+'" onclick="setRemotePlayHostPermission(\''+id+'\','+(!permitted)+')">'+(permitted?'Cabut Izin':'Izinkan PC')+'</button>';
  const enrollButton=permitted?'<button class="mini" onclick="issueRemotePlayHostEnrollment(\''+id+'\')">'+(h.agent_enrolled?'Buat Ulang Kode Agent':'Buat Kode Agent')+'</button>':'';
  return '<tr><td><b>'+remotePlayText(h.device_name)+'</b><div class="muted">'+remotePlayText(h.client_id)+'</div></td><td><span class="pill '+(ready?'online':(online?'warn':'offline'))+'">'+state+'</span><div class="muted">'+details+'</div></td><td><span class="pill '+(permitted?'online':'offline')+'">'+(permitted?'DIIZINKAN':'DIBLOKIR')+'</span></td><td><div class="row">'+permitButton+enrollButton+'</div></td></tr>';
 }).join('')||'<tr><td colspan="4" class="empty">Belum ada PC pada workspace ini.</td></tr>';
 $('remotePlayRentalRows').innerHTML=rentals.map(r=>{
  const id=remotePlayUuid(r.rental_account_id);if(!id)return '';
  const permitted=r.permission_enabled===true;
  const activated=r.activation_issued===true;
  const remaining=Math.max(0,Number(r.remaining_seconds)||0);
  const hours=Math.floor(remaining/3600),minutes=Math.floor((remaining%3600)/60);
  const access=permitted?'DIIZINKAN':'DIBLOKIR';
  const toggle='<button class="mini '+(permitted?'danger':'primary')+'" onclick="setRemotePlayRentalPermission(\''+id+'\','+(!permitted)+')">'+(permitted?'Cabut Izin':'Izinkan Rental')+'</button>';
  const issue=permitted?'<button class="mini" onclick="issueRemotePlayActivation(\''+id+'\',\''+remotePlayText(r.rental_code).replace(/'/g,'&#39;')+'\')">'+(activated?'Terbitkan Ulang Kode':'Terbitkan Kode')+'</button>':'';
  const session=r.active_session?'<div class="muted">Sesi '+remotePlayText(r.active_session.status)+' • sampai '+remotePlayDate(r.active_session.deadline_at)+'</div>':'';
  return '<tr><td><b>'+remotePlayText(r.rental_code)+'</b><div class="muted">'+remotePlayText(r.client_label)+' • '+remotePlayText(r.category)+'</div><div class="muted">'+remotePlayText(r.status)+' • Exp: '+remotePlayDate(r.expiry_at)+'</div></td><td>'+hours+'j '+minutes+'m</td><td><span class="pill '+(permitted?'online':'offline')+'">'+access+'</span><div class="muted">'+(activated?'Kode pernah diterbitkan':'Kode belum diterbitkan')+' • '+(r.client_logged_in?'Client login':'Belum login')+'</div>'+session+'</td><td><div class="row">'+toggle+issue+'</div></td></tr>';
 }).join('')||'<tr><td colspan="4" class="empty">Belum ada akun rental pada workspace ini.</td></tr>';
 $('remotePlaySessionRows').innerHTML=sessions.map(s=>'<tr><td><b>'+remotePlayText(s.rental_code)+'</b></td><td>'+remotePlayText(s.device_name)+'</td><td><span class="pill '+(s.status==='active'?'online':(s.status==='starting'?'warn':'offline'))+'">'+remotePlayText(s.status)+'</span><div class="muted">'+remotePlayText(s.end_reason)+'</div></td><td>'+remotePlayDate(s.started_at)+'</td><td>'+remotePlayDate(s.deadline_at)+'</td><td>'+remotePlayDate(s.ended_at)+'</td></tr>').join('')||'<tr><td colspan="6" class="empty">Belum ada sesi Remote Play.</td></tr>';
}
async function loadRemotePlayAdmin(){
 if(!isRemotePlayOwner()){remotePlayMessage('Menu ini hanya tersedia untuk Master/Owner.',true);return null;}
 remotePlayMessage('Membaca izin PC, rental, dan sesi dari DB Android…',false);
 for(const id of ['remotePlayHostRows','remotePlayRentalRows','remotePlaySessionRows']){const el=$(id);if(el)el.innerHTML='<tr><td colspan="'+(id==='remotePlaySessionRows'?6: id==='remotePlayHostRows'?4:4)+'" class="empty">Memuat dari server…</td></tr>';}
 try{
  const data=await rpc('admin_remote_play_dashboard',{p_limit:200});
  if(!data||data.ok!==true||!Array.isArray(data.host_devices)||!Array.isArray(data.rental_accounts)||!Array.isArray(data.sessions))throw new Error('Respons dashboard Remote Play tidak lengkap.');
  renderRemotePlayAdmin(data);
  remotePlayMessage('Status berhasil diperbarui dari DB Android • '+remotePlayDate(data.server_time),false);
  return data;
 }catch(e){
  $('remotePlayHostRows').innerHTML='<tr><td colspan="4" class="empty">Status tidak dapat diverifikasi. Jangan menganggap izin aktif.</td></tr>';
  $('remotePlayRentalRows').innerHTML='<tr><td colspan="4" class="empty">Status tidak dapat diverifikasi. Jangan menganggap izin aktif.</td></tr>';
  $('remotePlaySessionRows').innerHTML='<tr><td colspan="6" class="empty">Riwayat tidak dapat dimuat.</td></tr>';
  remotePlayMessage('Gagal membaca status Remote Play: '+String(e?.message||e).slice(0,180),true);
  return null;
 }
}
async function setRemotePlayHostPermission(deviceId,enabled){
 if(!isRemotePlayOwner())return remotePlayMessage('Hanya Master/Owner yang dapat mengubah izin Host.',true);
 const id=remotePlayUuid(deviceId);if(!id)return;
 if(!enabled&&!confirm('Cabut izin Remote Play PC ini? Sesi yang sedang berjalan pada PC ini akan dihentikan oleh server.'))return;
 if(enabled&&!confirm('Izinkan PC ini menjadi Host Remote Play? Host Agent tetap harus dipasang dan didaftarkan pada PC tersebut.'))return;
 try{
  const result=await rpc('admin_remote_play_set_host_permission',{p_device_id:id,p_enabled:enabled});
  if(result?.ok!==true||result.enabled!==enabled)throw new Error('Server tidak mengonfirmasi perubahan izin Host.');
  await loadRemotePlayAdmin();
  msg(enabled?'Izin Host Remote Play dibuka.':'Izin Host Remote Play dicabut.');
 }catch(e){remotePlayMessage('Perubahan izin Host gagal: '+String(e?.message||e).slice(0,180),true);}
}
async function setRemotePlayRentalPermission(rentalId,enabled){
 if(!isRemotePlayOwner())return remotePlayMessage('Hanya Master/Owner yang dapat mengubah izin rental.',true);
 const id=remotePlayUuid(rentalId);if(!id)return;
 if(!enabled&&!confirm('Cabut izin Remote Play rental ini? Sesi aktif akan dihentikan dan sesi login Remote Play akan dicabut.'))return;
 if(enabled&&!confirm('Izinkan akun rental ini menggunakan Remote Play? Kode aktivasi baru hanya bisa diterbitkan setelah izin aktif.'))return;
 try{
  const result=await rpc('admin_remote_play_set_rental_permission',{p_rental_account_id:id,p_enabled:enabled});
  if(result?.ok!==true||result.enabled!==enabled)throw new Error('Server tidak mengonfirmasi perubahan izin rental.');
  await loadRemotePlayAdmin();
  msg(enabled?'Izin Remote Play rental dibuka.':'Izin Remote Play rental dicabut.');
 }catch(e){remotePlayMessage('Perubahan izin rental gagal: '+String(e?.message||e).slice(0,180),true);}
}
async function issueRemotePlayActivation(rentalId,rentalCode){
 if(!isRemotePlayOwner())return remotePlayMessage('Hanya Master/Owner yang dapat menerbitkan kode.',true);
 const id=remotePlayUuid(rentalId);if(!id)return;
 if(!confirm('Terbitkan kode aktivasi Remote Play untuk rental '+rentalCode+'?\n\nKode lama akan dinonaktifkan, login Remote Play sebelumnya dicabut, dan sesi Remote Play aktif akan dihentikan.'))return;
 try{
  const result=await rpc('admin_remote_play_issue_client_credential',{p_rental_account_id:id});
  const code=String(result?.activation_code||'');
  if(result?.ok!==true||! /^[0-9a-f]{16}$/i.test(code))throw new Error('Server tidak mengembalikan kode aktivasi yang valid.');
  showRemotePlayOneTimeCode('KODE AKTIVASI RENTAL',code,'Berikan ke penyewa untuk login. Kode ini hanya ditampilkan sekali.');
  await loadRemotePlayAdmin();
 }catch(e){remotePlayMessage('Gagal menerbitkan aktivasi: '+String(e?.message||e).slice(0,180),true);}
}
async function issueRemotePlayHostEnrollment(deviceId){
 if(!isRemotePlayOwner())return remotePlayMessage('Hanya Master/Owner yang dapat menerbitkan enrollment.',true);
 const id=remotePlayUuid(deviceId);if(!id)return;
 if(!confirm('Buat kode enrollment Host Agent selama 15 menit? Kode dapat dipakai sekali. Menggunakan kode ini pada Host Agent lain akan mengganti token Host sebelumnya.'))return;
 try{
  const result=await rpc('admin_remote_play_issue_host_enrollment',{p_device_id:id,p_valid_minutes:15});
  const code=String(result?.enrollment_code||'');
  if(result?.ok!==true||! /^[0-9a-f]{64}$/i.test(code))throw new Error('Server tidak mengembalikan kode enrollment yang valid.');
  showRemotePlayOneTimeCode('KODE ENROLLMENT HOST AGENT',code,'Berlaku sampai '+remotePlayDate(result.expires_at)+'. Tempel di installer Host Agent pada PC yang dipilih.');
  await loadRemotePlayAdmin();
 }catch(e){remotePlayMessage('Gagal menerbitkan enrollment: '+String(e?.message||e).slice(0,180),true);}
}
function showRemotePlayOneTimeCode(title,code,expiry){
 const card=$('remotePlayOneTimeCard'),name=$('remotePlayOneTimeTitle'),input=$('remotePlayOneTimeCode'),note=$('remotePlayOneTimeExpiry');
 if(!card||!input||!name||!note)return;
 name.textContent=String(title||'Kode satu kali');input.value=String(code||'');note.textContent=String(expiry||'');
 card.classList.remove('hidden');card.scrollIntoView({behavior:'smooth',block:'center'});input.focus();input.select();
}
function copyRemotePlayOneTimeCode(){
 const input=$('remotePlayOneTimeCode');if(!input||!input.value)return;
 input.focus();input.select();let copied=false;try{copied=document.execCommand('copy')}catch(_){}
 remotePlayMessage(copied?'Kode disalin. Simpan di tempat aman; kode hanya ditampilkan satu kali.':'Kode belum tersalin otomatis. Pilih teks pada kolom kode lalu gunakan Salin.',!copied);
}
function dismissRemotePlayOneTimeCode(){
 const card=$('remotePlayOneTimeCard'),input=$('remotePlayOneTimeCode'),note=$('remotePlayOneTimeExpiry');
 if(input)input.value='';if(note)note.textContent='';if(card)card.classList.add('hidden');
}

"""
page=page.replace(script_anchor,functions+"\n"+script_anchor,1)

if gradle.count("versionCode 79")!=1 or gradle.count("versionName '12.1.51'")!=1:
    raise SystemExit("Admin Gradle V12.1.51 version anchor mismatch")
gradle=gradle.replace("versionCode 79","versionCode 80",1).replace("versionName '12.1.51'","versionName '12.1.52'",1)
if gradle.count("applicationId 'com.anigames.billingadmin.v151'")!=1:
    raise SystemExit("Admin Gradle isolated application id anchor mismatch")
gradle=gradle.replace("applicationId 'com.anigames.billingadmin.v151'","applicationId 'com.anigames.billingadmin.v152'",1)
manifest,n=re.subn(r'android:label="[^"]+"','android:label="AniGames Admin V12.1.52"',manifest,count=1)
if n!=1:
    raise SystemExit("Admin manifest label anchor mismatch")

for token in (MARKER,"remotePlayAdminNav","admin_remote_play_dashboard","admin_remote_play_set_host_permission",
              "admin_remote_play_set_rental_permission","admin_remote_play_issue_client_credential",
              "admin_remote_play_issue_host_enrollment"):
    if token not in page:
        raise SystemExit("Missing Remote Play Admin wiring: "+token)
if page.count('id="remotePlayAdminNav"')!=1 or page.count('id="remotePlayOneTimeCode"')!=1:
    raise SystemExit("Duplicate Remote Play Admin control IDs")
if "if(id==='remotePlay'&&!isRemotePlayOwner())return;" not in page:
    raise SystemExit("Remote Play Admin UI owner guard missing")
if "applyRemotePlayRoleUI();" not in page:
    raise SystemExit("Remote Play Admin nav visibility hook missing")

PAGE.write_text(page,encoding="utf-8")
GRADLE.write_text(gradle,encoding="utf-8")
MANIFEST.write_text(manifest,encoding="utf-8")
VERSION.write_text("AniGames Admin Android V12.1.52 — Owner-only Ani Remote Play permissions and one-time activation/enrollment codes, based on V12.1.51 DB Android.\n",encoding="utf-8")
print("PASS: Admin V12.1.52 owner-only Remote Play controls, one-time code flow, and isolated package metadata.")
