from pathlib import Path
import re

html_path = Path('android/app/src/main/assets/web/admin.html')
html = html_path.read_text(encoding='utf-8')

old_section = '<div class="muted" style="margin-top:10px">Kode hanya untuk proses pairing awal. Setelah berhasil, PC menyimpan device token dan memakai heartbeat cloud.</div></div></section>'
new_section = '''<div class="muted" style="margin-top:10px">Kode hanya untuk proses pairing awal. Setelah berhasil, PC menyimpan device token dan memakai heartbeat cloud.</div></div>
<div class="card" style="margin-top:12px;border:1px solid var(--a)"><div class="top"><div><h3 style="margin:0">♻️ Pemulihan Data PC Lama</h3><div class="muted">Untuk PC yang instal ulang atau kehilangan token. Pilih perangkat lama agar akun rental dan riwayat tetap terhubung.</div></div><span class="pill">Owner only</span></div>
<div class="field"><label>PC lama yang akan dipulihkan</label><select id="recoverDeviceSelect" style="width:100%"><option value="">Memuat daftar PC…</option></select></div>
<div class="msg" style="border-left-color:#f6c85f">Kode ini khusus untuk PC yang dipilih. Jika identitas PC yang mengirim kode tidak cocok dengan PC lama atau alias yang terdaftar, server harus menolak pairing dan tidak boleh membuat perangkat baru.</div>
<div class="row"><button class="primary" onclick="createRecoveryEnrollment()">Buat Kode Pemulihan</button><button onclick="clearRecoveryEnrollment()">Bersihkan</button></div>
<div id="recoverEnrollmentResult" class="msg hidden" role="status"></div>
<div id="recoverCodeBox" class="hidden" style="margin-top:12px"><div class="field"><label>Kode Pemulihan — siap copy</label><div class="row" style="align-items:stretch"><input id="recoverCode" readonly style="font-size:24px;letter-spacing:4px;font-weight:900;color:var(--a);text-align:center;flex:1;min-width:180px"><button class="ok" onclick="copyRecoveryCode()">📋 Copy Kode</button></div></div></div>
<div class="muted" style="margin-top:10px">Kode berlaku 30 menit dan hanya untuk sekali pemulihan. Kode pemulihan tidak menghapus atau memindahkan akun rental, sesi, maupun transaksi.</div></div>
<div class="card" id="adminAlertSettings" style="margin-top:12px;border:1px solid var(--a)">
 <div class="top"><div><h3 style="margin:0">🔔 Notifikasi Admin</h3><div class="muted">Pesan penting tampil di layar. Aktifkan suara sekali agar peringatan terdengar jelas.</div></div><span id="adminSoundState" class="pill">Suara belum diaktifkan</span></div>
 <div class="row"><button type="button" class="primary" onclick="enableAdminAlertSound()">🔊 Aktifkan & Tes Suara</button><button type="button" onclick="dismissAdminAlert()">Tutup Pesan</button></div>
 <div id="adminAlertFeed" class="msg" role="status" aria-live="polite" style="margin-top:10px;min-height:48px;font-weight:800">Notifikasi enrollment, pairing, dan status penting akan muncul di sini.</div>
</div></section>'''
if html.count(old_section) != 1:
    raise SystemExit('Pairing section anchor did not match exactly once; refusing to patch')
html = html.replace(old_section, new_section, 1)

load_anchor = 'devicesCache=rows;$(\'kPC\').textContent=rows.length;'
if html.count(load_anchor) != 1:
    raise SystemExit('loadDevices anchor did not match exactly once; refusing to patch')
html = html.replace(load_anchor, 'devicesCache=rows;renderRecoveryDeviceOptions();$(\'kPC\').textContent=rows.length;', 1)

marker = 'function adminNotify(message,kind){
 const feed=$('adminAlertFeed');if(!feed)return;
 const text=String(message||'Notifikasi admin').replace(/<[^>]*>/g,'').slice(0,500);
 const urgent=kind==='error'||/berakhir|rental.*(stop|end|habis)|enrollment gagal|pairing gagal|usage_exceeded|offline/i.test(text);
 feed.classList.remove('hidden');feed.style.borderLeftColor=urgent?'#ff4d6d':'var(--a)';
 feed.innerHTML='<strong>'+(urgent?'⚠️ PERINGATAN':'🔔 NOTIFIKASI')+'</strong><div style="margin-top:5px;white-space:pre-wrap">'+esc(text)+'</div><div class="muted" style="margin-top:5px">'+new Date().toLocaleTimeString('id-ID')+'</div>';
 if(urgent){const now=Date.now();if(text!==window.__lastAdminAlertText||now-(window.__lastAdminAlertAt||0)>2500)playAdminAlertSound();window.__lastAdminAlertText=text;window.__lastAdminAlertAt=now;}
}
let adminAlertAudioContext=null,adminAlertSoundReady=false;
function playAdminAlertSound(){
 if(!adminAlertSoundReady||!adminAlertAudioContext)return;
 try{
  const ctx=adminAlertAudioContext;
  if(ctx.state==='suspended')ctx.resume();
  const now=ctx.currentTime;
  [880,1174,880,1174,1568].forEach(function(freq,i){
   const start=now+i*0.19,osc=ctx.createOscillator(),gain=ctx.createGain();
   osc.type='sawtooth';osc.frequency.setValueAtTime(freq,start);
   gain.gain.setValueAtTime(0.0001,start);gain.gain.exponentialRampToValueAtTime(0.75,start+0.025);
   gain.gain.setValueAtTime(0.75,start+0.11);gain.gain.exponentialRampToValueAtTime(0.0001,start+0.17);
   osc.connect(gain);gain.connect(ctx.destination);osc.start(start);osc.stop(start+0.18);
  });
 }catch(e){console.warn('Admin alert sound unavailable',e)}
}
function enableAdminAlertSound(){
 try{
  const AC=window.AudioContext||window.webkitAudioContext;if(!AC)throw new Error('Browser tidak mendukung audio alert.');
  if(!adminAlertAudioContext)adminAlertAudioContext=new AC();
  adminAlertAudioContext.resume().then(function(){adminAlertSoundReady=true;$('adminSoundState').textContent='Suara aktif';$('adminSoundState').style.background='#14532d';playAdminAlertSound();});
 }catch(e){msg(e.message||'Gagal mengaktifkan suara notifikasi.',true)}
}
function dismissAdminAlert(){const feed=$('adminAlertFeed');if(feed){feed.innerHTML='Tidak ada pesan baru.';feed.style.borderLeftColor='var(--a)';}}
function installAdminNotificationBridge(){
 if(typeof msg==='function'&&!msg.__adminAlertWrapped){
  const original=msg;
  const wrapped=function(message,error){original.apply(this,arguments);adminNotify(message,error?'error':'info');};
  wrapped.__adminAlertWrapped=true;msg=wrapped;
 }
}

installAdminNotificationBridge();
async function createEnrollment(){'
if html.count(marker) != 1:
    raise SystemExit('createEnrollment function marker did not match exactly once; refusing to patch')
functions = '''function renderRecoveryDeviceOptions(){
 const select=$('recoverDeviceSelect');if(!select)return;
 const eligible=(devicesCache||[]).filter(function(d){return !d.metadata?.pairingDuplicateArchivedAt;});
 const prior=select.value;
 select.innerHTML=eligible.map(function(d){
   const aliases=Array.isArray(d.metadata?.clientIdAliases)?d.metadata.clientIdAliases:[];
   const aliasHint=aliases.length?' • alias: '+aliases.join(', '):'';
   const status=d.uiStatus==='online'?'ONLINE':'OFFLINE';
   return '<option value="'+esc(d.id)+'">'+esc(d.device_name||'PC')+' • '+esc(d.client_id||'-')+' • '+status+esc(aliasHint)+'</option>';
 }).join('')||'<option value="">Tidak ada PC lama yang dapat dipulihkan</option>';
 if(eligible.some(function(d){return d.id===prior;}))select.value=prior;
 else{const preferred=eligible.find(function(d){return d.client_id==='PC-38BFEEB2'||(Array.isArray(d.metadata?.clientIdAliases)&&d.metadata.clientIdAliases.includes('PC-6BB0901C'));});select.value=preferred?.id||eligible[0]?.id||'';}
}
async function createRecoveryEnrollment(){
 if(ctx?.role!=='owner')return msg('Pemulihan PC hanya dapat dibuat oleh Master/Owner.',true);
 try{
   const deviceId=$('recoverDeviceSelect').value;
   const target=(devicesCache||[]).find(function(d){return d.id===deviceId&&d.org_id===currentOrg?.id&&!d.metadata?.pairingDuplicateArchivedAt;});
   if(!target)throw new Error('Pilih PC lama yang valid dari organisasi aktif.');
   const aliases=Array.isArray(target.metadata?.clientIdAliases)?target.metadata.clientIdAliases:[];
   const confirmed=confirm('Buat kode pemulihan khusus untuk PC lama ini?\\n\\nNama: '+(target.device_name||'-')+'\\nClient ID: '+(target.client_id||'-')+'\\nUUID: '+target.id+'\\nAlias yang dikenal: '+(aliases.join(', ')||'(tidak ada)')+'\\n\\nJika PC yang akan pairing memiliki ID berbeda dan tidak ada di alias, server akan menolak kode ini.');
   if(!confirmed)return;
   const d=await rpc('create_device_recovery_enrollment',{p_device_id:target.id,p_minutes:30});
   if(!d?.code)throw new Error('Kode pemulihan tidak dikembalikan oleh server.');
   $('recoverEnrollmentResult').classList.remove('hidden');
   $('recoverEnrollmentResult').innerHTML='<div><b>Kode pemulihan berhasil dibuat.</b></div><div class="muted">Target: '+esc(target.device_name||'PC')+' ('+esc(target.client_id||'-')+')<br>Berlaku sampai: '+new Date(d.expires_at).toLocaleString('id-ID')+'<br>Server akan menolak PC yang tidak cocok; kode ini tidak boleh membuat PC baru.</div>';
   $('recoverCode').value=d.code;$('recoverCodeBox').classList.remove('hidden');msg('Kode pemulihan dibuat untuk PC yang dipilih pada database aktif.');adminNotify('Enrollment pemulihan berhasil dibuat pada database yang sedang dipilih. Pastikan DB2 sudah menerima migrasi SQL pemulihan jika DB2 digunakan.','success');
 }catch(e){const message=e?.message||'Gagal membuat kode pemulihan.';if(/create_device_recovery_enrollment|schema cache|Could not find the function/i.test(message))return msg('Fitur pemulihan belum aktif pada database yang sedang dipilih. Terapkan ADMIN-PC-RECOVERY-MIGRATION.sql pada proyek Supabase DB tersebut terlebih dahulu. Tidak ada data yang berubah.',true);adminNotify('Enrollment tidak tersedia pada database aktif: '+message,'error');msg(message,true);}
}
async function copyRecoveryCode(){const code=$('recoverCode').value;if(!code)return;try{await navigator.clipboard.writeText(code);msg('Kode pemulihan berhasil disalin.')}catch(e){$('recoverCode').select();document.execCommand('copy');msg('Kode pemulihan disalin.')}}
function clearRecoveryEnrollment(){$('recoverEnrollmentResult').classList.add('hidden');$('recoverEnrollmentResult').innerHTML='';$('recoverCode').value='';$('recoverCodeBox').classList.add('hidden')}
'''
html = html.replace(marker, functions + marker, 1)

gradle_path = Path('android/app/build.gradle')
gradle = gradle_path.read_text(encoding='utf-8')
if "versionCode 32" not in gradle or "versionName '12.1.0'" not in gradle:
    raise SystemExit('Unexpected baseline Android version; refusing to bump blindly')
gradle = gradle.replace('versionCode 32', 'versionCode 34', 1).replace("versionName '12.1.0'", "versionName '12.1.6'", 1)
gradle_path.write_text(gradle, encoding='utf-8')
Path('VERSION.txt').write_text('v12.1.6-admin-pc-enrollment-db2-alerts\n', encoding='utf-8')
html_path.write_text(html, encoding='utf-8')
print('Patched Admin PC enrollment + DB-aware recovery + alerts; Android version 12.1.6 / versionCode 34')
