from pathlib import Path
import re,sys
R=Path(sys.argv[1]) if len(sys.argv)>1 else Path('.')
W=R/'android/app/src/main/assets/web'; A=W/'admin.html'; C=W/'admin-control.html'; G=R/'android/app/build.gradle'
for p in (A,C,G):
 if not p.is_file(): raise SystemExit('Required Admin V12.1.43 source file missing: '+str(p))
a=A.read_text(encoding='utf-8'); c=C.read_text(encoding='utf-8'); g=G.read_text(encoding='utf-8')
def once(s,o,n,label):
 k=s.count(o)
 if k!=1: raise SystemExit(f'{label} anchor mismatch: expected 1, found {k}')
 return s.replace(o,n,1)
a=once(a,'data-rental-disable="\'+encodeURIComponent(x.id)+\'" data-rental-code="\'+encodeURIComponent(x.code)+\'">Nonaktifkan</button>','data-rental-delete="\'+encodeURIComponent(x.id)+\'" data-rental-code="\'+encodeURIComponent(x.code)+\'">Hapus</button>','Admin rental delete button')
a=once(a,"document.addEventListener('click',ev=>{const d=ev.target.closest('button[data-rental-disable]');if(d){void deleteRental(decodeURIComponent(d.dataset.rentalDisable||''),decodeURIComponent(d.dataset.rentalCode||''));return}const b=ev.target.closest('button[data-rental-edit]');","document.addEventListener('click',ev=>{const d=ev.target.closest('button[data-rental-delete]');if(d){void deleteRental(decodeURIComponent(d.dataset.rentalDelete||''),decodeURIComponent(d.dataset.rentalCode||''));return}const b=ev.target.closest('button[data-rental-edit]');",'Admin delete click')
old="""async function deleteRental(id,code){
 if(!confirm('Nonaktifkan rental '+code+'? Histori transaksi akan tetap tersimpan.'))return;
 try{
  const r=await rpc('admin_disable_rental_global',{p_org_id:currentOrg.id,p_rental_id:id});
  if(r?.ok!==true)throw new Error('Database tidak mengonfirmasi nonaktifkan rental.');
  msg('Rental '+code+' berhasil dinonaktifkan. Histori tetap tersimpan.'+rentalAdminLeaseNote(r));
  await loadGlobalRentalAccounts();
 }catch(e){msg('Gagal menonaktifkan '+code+': '+rentalAdminFriendlyError(e),true)}
}
"""
fresh="""async function deleteRental(id,code){
 if(!confirm('HAPUS PERMANEN rental '+code+' dari daftar bersama? Histori transaksi, sesi dan laporan tetap disimpan. Rental dengan timer aktif/paused atau reservasi offline yang masih berlaku tidak bisa dihapus.'))return;
 try{
  const r=await rpc('admin_delete_rental_global',{p_org_id:currentOrg.id,p_rental_id:id});
  if(r?.ok!==true)throw new Error('Database tidak mengonfirmasi penghapusan rental.');
  let pcNote='';
  if(r.command_id){
   const state=await waitDeviceCommand(r.command_id,6000);
   if(state?.status==='completed')pcNote=' PC juga sudah mengonfirmasi sinkronisasi penghapusan.';
   else if(state?.status==='failed'||state?.status==='expired')pcNote=' Data utama sudah dihapus; PC belum menerima perubahan: '+String(state.result?.message||state.result?.error||state.status).slice(0,120)+'.';
   else pcNote=' Data utama sudah dihapus; perintah sinkronisasi PC masih menunggu koneksi/konfirmasi.';
  }
  msg('Rental '+code+' berhasil dihapus dari daftar bersama. Histori transaksi, sesi dan laporan tetap tersimpan.'+pcNote);
  await loadGlobalRentalAccounts();
 }catch(e){msg('Gagal menghapus '+code+': '+rentalAdminFriendlyError(e),true)}
}
"""
a=once(a,old,fresh,'Admin hard delete RPC')
a=once(a,"if(code.includes('RENTAL_ACTIVE_TIMER_LOCKED'))return 'Rental sedang dipakai dalam sesi aktif/paused. Perubahan timer yang tidak aman ditolak.';","if(code.includes('RENTAL_ACTIVE_TIMER_LOCKED'))return 'Rental sedang dipakai dalam sesi aktif/paused. Selesaikan sesi terlebih dahulu sebelum menghapus atau mengubah timer.';\n if(code.includes('RENTAL_ACTIVE_OFFLINE_LEASE'))return 'Rental masih memiliki reservasi offline yang berlaku. Data tidak dihapus untuk mencegah kode dipakai ganda; coba lagi setelah reservasi berakhir.';",'Admin rental error mapping')
old_status="""<td class="${d.uiStatus===\'online\'?\'online\':\'offline\'}">● ${d.uiStatus===\'online\'?(d.metadata?.activeCode?\'RENTAL AKTIF\':d.metadata?.pausedCode?\'RENTAL PAUSED\':\'STANDBY / BILLING SIAP\'):\'TERPUTUS\'}</td>"""
new_status=old_status.replace('</td>', "${(d.metadata?.activeCode||d.metadata?.pausedCode)?"+chr(96)+'<div class="muted">ID Rental: ${esc(d.metadata.activeCode||d.metadata.pausedCode)}</div>'+chr(96)+":''}</td>")
a=once(a,old_status,new_status,'Active rental ID in PC table')
old_cmd="""async function cmd(device,command,seconds){try{const target=devicesCache.find(d=>d.id===device);if(!target)return msg('PC tidak ditemukan pada tenant aktif.',true);const offlineRestart=command==='restart_billing'&&target.uiStatus!=='online';if(target.uiStatus!=='online'&&!offlineRestart)return msg('PC terpilih sedang OFFLINE. Kontrol ini tidak dikirim.',true);const payload={source:'dashboard-admin',...(offlineRestart?{queuedWhileOffline:true}: {})};if(seconds)payload.seconds=seconds;if(['pause','resume','stop'].includes(command)){const ss=await rpc('admin_selected_sessions',{p_org_id:currentOrg.id,p_device_id:device});const s=(ss||[])[0];if(!s)return msg('Tidak ada sesi aktif/paused pada PC ini.',true);payload.session_id=s.id;}await rpc('admin_command',{p_org_id:currentOrg.id,p_device_id:device,p_command:command,p_payload:payload});msg(offlineRestart?'Perintah Restart Billing masuk antrean. Agen PC akan mengambilnya saat PC terhubung kembali; tunggu konfirmasi status.':'Perintah '+command+' dikirim hanya ke '+target.device_name+'.');await loadDevices()}catch(e){msg(e.message,true)}}
"""
new_cmd="""async function cmd(device,command,seconds){try{const target=devicesCache.find(d=>d.id===device);if(!target)return msg('PC tidak ditemukan pada tenant aktif.',true);const offlineRestart=command==='restart_billing'&&target.uiStatus!=='online';if(target.uiStatus!=='online'&&!offlineRestart)return msg('PC terpilih sedang OFFLINE. Kontrol ini tidak dikirim.',true);const pcName=target.device_name||target.client_id||'PC terpilih';const windowsActions={shutdown:'Matikan Windows',restart_pc:'Restart Windows',logoff:'Logoff Windows'};if(windowsActions[command]&&!confirm(windowsActions[command]+' pada '+pcName+'? Perintah hanya dikirim ke PC ini.'))return;const payload={source:'dashboard-admin',...(offlineRestart?{queuedWhileOffline:true}: {})};if(seconds)payload.seconds=seconds;if(['pause','resume','stop'].includes(command)){const ss=await rpc('admin_selected_sessions',{p_org_id:currentOrg.id,p_device_id:device});const s=(ss||[])[0];if(!s)return msg('Tidak ada sesi aktif/paused pada PC ini.',true);payload.session_id=s.id;}const sent=await rpc('admin_command',{p_org_id:currentOrg.id,p_device_id:device,p_command:command,p_payload:payload});if(sent?.ok===false)throw new Error(sent.message||'Server menolak perintah.');const commandId=sent?.command_id||sent?.id;if(!commandId)throw new Error('Server tidak memberikan ID perintah; status belum dapat diverifikasi.');if(offlineRestart){msg('Perintah Restart Billing masuk antrean. Agen PC akan mengambilnya saat PC terhubung kembali.');await loadDevices();return;}const state=await waitDeviceCommand(commandId,15000);if(state?.status==='completed')msg('PC '+pcName+' mengonfirmasi perintah '+command+'.');else if(state?.status==='failed'||state?.status==='expired')throw new Error(state.result?.message||state.result?.error||('PC gagal menjalankan '+command+'.'));else msg('Perintah '+command+' sudah masuk antrean untuk '+pcName+', tetapi belum ada konfirmasi selesai dari PC. Status tidak dianggap berhasil.');await loadDevices()}catch(e){msg(e.message,true)}}
"""
a=once(a,old_cmd,new_cmd,'Admin Windows acknowledgement')
old_send="""async function sendCommand(command,payload={}){const d=devices.find(x=>x.id===selectedId);if(!d)return msg('Pilih PC terlebih dahulu.',true);const offlineRestart=command==='restart_billing'&&!isOnline(d);if(!isOnline(d)&&!offlineRestart)return msg('PC OFFLINE — command tidak dikirim.',true);const question=offlineRestart?'PC '+(d.device_name||d.client_id)+' sedang OFFLINE. Antrekan Restart Billing agar watchdog mengambilnya saat PC terhubung kembali?':'Kirim '+command+' ke '+(d.device_name||d.client_id)+'?';if(!confirm(question))return;try{await rpc('billing_command',{p_session_token:token,p_org_id:org.id,p_device_id:d.id,p_command:command,p_payload:{...payload,source:'billing-control',...(offlineRestart?{queuedWhileOffline:true}:{})}});msg(offlineRestart?'Restart Billing masuk antrean. Status baru bisa dikonfirmasi saat PC kembali terhubung.':'Perintah '+command+' dikirim.');setTimeout(refreshAll,700)}catch(e){msg(e.message||'Perintah gagal.',true)}}
"""
new_send="""async function sendCommand(command,payload={}){const d=devices.find(x=>x.id===selectedId);if(!d)return msg('Pilih PC terlebih dahulu.',true);const offlineRestart=command==='restart_billing'&&!isOnline(d);if(!isOnline(d)&&!offlineRestart)return msg('PC OFFLINE — command tidak dikirim.',true);const pcName=d.device_name||d.client_id||'PC terpilih';const labels={shutdown:'Matikan Windows',restart_pc:'Restart Windows',logoff:'Logoff Windows'};const question=offlineRestart?'PC '+pcName+' sedang OFFLINE. Antrekan Restart Billing agar watchdog mengambilnya saat PC terhubung kembali?':(labels[command]||('Kirim '+command))+' ke '+pcName+'?';if(!confirm(question))return;try{const sent=await rpc('billing_command',{p_session_token:token,p_org_id:org.id,p_device_id:d.id,p_command:command,p_payload:{...payload,source:'billing-control',...(offlineRestart?{queuedWhileOffline:true}:{})}});if(sent?.ok===false)throw new Error(sent.message||'Server menolak perintah.');if(offlineRestart){msg('Restart Billing masuk antrean. Status baru bisa dikonfirmasi saat PC kembali terhubung.');setTimeout(refreshAll,700);return;}const commandId=sent?.command_id||sent?.id;if(!commandId)throw new Error('Server tidak memberikan ID perintah; status belum dapat diverifikasi.');const state=await waitCommand(commandId,15000);if(state?.status==='completed')msg('PC '+pcName+' mengonfirmasi perintah '+command+'.');else if(state?.status==='failed'||state?.status==='expired')throw new Error(state.result?.message||state.result?.error||('PC gagal menjalankan '+command+'.'));else msg('Perintah '+command+' sudah masuk antrean untuk '+pcName+', tetapi PC belum mengonfirmasi selesai.');await refreshAll()}catch(e){msg(e.message||'Perintah gagal.',true)}}
"""
c=once(c,old_send,new_send,'Admin legacy Windows acknowledgement')
if not re.search(r'\bversionCode\s+71\b',g) or not re.search(r"""versionName\s+['"]12\.1\.43['"]""",g): raise SystemExit('Unexpected Admin baseline; expected versionCode 71 / versionName 12.1.43')
g=re.sub(r'\bversionCode\s+71\b','versionCode 72',g,count=1)
g=re.sub(r"""(\bversionName\s+['"])12\.1\.43(['"])""",r'\g<1>12.1.44\2',g,count=1)
for m in ('admin_delete_rental_global','data-rental-delete','Hapus','ID Rental:','waitDeviceCommand(commandId,15000)','RENTAL_ACTIVE_OFFLINE_LEASE'):
 if m not in a: raise SystemExit('Missing Admin V12.1.44 marker: '+m)
for m in ('data-rental-disable','admin_disable_rental_global','>Nonaktifkan</button>'):
 if m in a: raise SystemExit('Old Admin nonaktif action remains: '+m)
for m in ('billing_command_status','waitCommand(commandId,15000)','Matikan Windows','Restart Windows','Logoff Windows'):
 if m not in c: raise SystemExit('Missing Admin Windows acknowledgement marker: '+m)
if 'schedule_shutdown' in a or 'cancel_shutdown_timer' in a: raise SystemExit('Admin shutdown countdown reintroduced')
for name,page in (('admin.html',a),('admin-control.html',c)):
 scripts=re.findall(r'<script\b(?![^>]*\bsrc=)[^>]*>(.*?)</script>',page,re.I|re.S)
 if len(scripts)!=1: raise SystemExit(f'Expected one inline script in {name}, found {len(scripts)}')
 Path('/tmp/'+name.replace('.html','-v12144-check.js')).write_text(scripts[0],encoding='utf-8')
A.write_text(a,encoding='utf-8'); C.write_text(c,encoding='utf-8'); G.write_text(g,encoding='utf-8')
print('PASS: Admin V12.1.44 rental delete, active rental ID, Windows confirmation/acknowledgement, version metadata.')
