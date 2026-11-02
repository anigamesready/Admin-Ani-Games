from pathlib import Path
import re,sys
R=Path(sys.argv[1]) if len(sys.argv)>1 else Path('.')
pages=[p for p in R.rglob('admin-control.html') if p.parent.name=='web']
if len(pages)!=1: raise SystemExit('Expected one Reseller WebView dashboard')
D=pages[0]; G=R/'app/build.gradle'
if not G.is_file(): raise SystemExit('Reseller app/build.gradle missing')
h=D.read_text(encoding='utf-8'); g=G.read_text(encoding='utf-8')
if 'V1.0.5-GLOBAL-RENTAL-HARD-DELETE' in h:
 print('PASS: Reseller V1.0.5 patch already applied'); raise SystemExit(0)
def once(s,o,n,label):
 c=s.count(o)
 if c!=1: raise SystemExit(f'{label} anchor mismatch: expected 1, found {c}')
 return s.replace(o,n,1)
h=once(h,'<option value="disabled">Nonaktif</option>','','Remove obsolete disabled status filter')
h=once(h,
 "const st=String(r.status||'active').toLowerCase(),cls=st==='active'?'active':st==='expired'?'expired':'done',busy=activeCodes.has(String(r.code||'').toUpperCase());",
 "const st=String(r.status||'active').toLowerCase(),cls=st==='active'?'active':st==='expired'?'expired':'done',busy=activeCodes.has(String(r.code||'').toUpperCase())||sessions.some(s=>['active','paused'].includes(s.status)&&(s.rental_account_id===r.id||String(s.code||'').toUpperCase()===String(r.code||'').toUpperCase()));",
 'Reseller active/paused guard')
b=chr(96)
old_row='return '+b+"""<tr><td><b>${esc(r.code)}</b></td><td>${esc(r.client_label||'—')}</td><td>${esc(r.category||'reguler')}</td><td>${esc(secsText(r.remaining_seconds))}</td><td>${esc(fmtDate(r.expiry_at))}</td><td><span class="status ${cls}">${esc(st.toUpperCase())}</span></td><td><button class="btn small secondary" ${busy?'disabled title="Sesi member sedang aktif"':''} onclick="openEdit('${esc(r.id)}')">Edit</button></td></tr>"""+b
new_row='return '+b+"""<tr><td><b>${esc(r.code)}</b></td><td>${esc(r.client_label||'—')}</td><td>${esc(r.category||'reguler')}</td><td>${esc(secsText(r.remaining_seconds))}</td><td>${esc(fmtDate(r.expiry_at))}</td><td><span class="status ${cls}">${esc(st.toUpperCase())}</span></td><td><button class="btn small secondary" ${busy?'disabled title="Sesi member sedang aktif"':''} onclick="openEdit('${esc(r.id)}')">Edit</button> <button class="btn small danger" ${busy?'disabled title="Selesaikan sesi aktif/paused sebelum menghapus"':''} onclick="deleteRental('${esc(r.id)}')">Hapus</button></td></tr>"""+b
h=once(h,old_row,new_row,'Reseller add delete action')
anchor='function openEdit(id){const r=rentals.find(x=>x.id===id);'
handler="""async function deleteRental(id){
 const r=rentals.find(x=>x.id===id);if(!r)return showMessage('Data rental tidak ditemukan. Muat ulang daftar.','bad');
 const busy=sessions.some(s=>['active','paused'].includes(s.status)&&(s.rental_account_id===id||String(s.code||'').toUpperCase()===String(r.code||'').toUpperCase()));
 if(busy)return showMessage('Rental masih memiliki sesi aktif/paused. Selesaikan timer terlebih dahulu sebelum dihapus.','bad');
 if(!confirm('HAPUS PERMANEN rental '+r.code+'? Histori transaksi, sesi dan laporan tetap disimpan. PC tidak harus online; penghapusan akun utama langsung dilakukan di database bersama.'))return;
 try{
  const result=await rpc('billing_reseller_delete_rental_global',{p_session_token:token,p_org_id:org.id,p_rental_id:id});
  if(result?.ok!==true)throw new Error('Database tidak mengonfirmasi penghapusan rental.');
  let pcNote='';
  if(result.command_id){
   const state=await waitCommand(result.command_id,6000);
   if(state?.status==='completed')pcNote=' PC juga sudah mengonfirmasi sinkronisasi penghapusan.';
   else if(state?.status==='failed'||state?.status==='expired')pcNote=' Akun sudah dihapus dari database; sinkronisasi PC gagal: '+String(state.result?.message||state.result?.error||state.status).slice(0,120)+'.';
   else pcNote=' Akun sudah dihapus dari database; sinkronisasi PC masih menunggu koneksi/konfirmasi.';
  }
  await loadRentals(true);
  showMessage('Rental '+r.code+' berhasil dihapus. Histori transaksi, sesi dan laporan tetap tersimpan.'+pcNote,'good');
 }catch(err){const code=String(err.message||'');if(code.includes('RENTAL_ACTIVE_TIMER_LOCKED'))showMessage('Rental masih memiliki sesi aktif/paused. Selesaikan sesi terlebih dahulu sebelum dihapus.','bad');else if(code.includes('RENTAL_ACTIVE_OFFLINE_LEASE'))showMessage('Rental masih memiliki reservasi offline yang berlaku. Coba lagi setelah reservasi berakhir.','bad');else showMessage('Gagal menghapus rental: '+(code||'error tidak diketahui'),'bad')}
}
"""
h=once(h,anchor,handler+anchor,'Reseller delete handler')
if not re.search(r'\bversionCode\s+134\b',g) or not re.search(r"""versionName\s*=?\s*['"]1\.0\.4['"]""",g):
 raise SystemExit('Unexpected Reseller baseline; expected versionCode 134 / versionName 1.0.4')
g,c=re.subn(r'\bversionCode\s+134\b','versionCode 135',g,count=1)
g,n=re.subn(r"""(\bversionName\s*=?\s*['"])1\.0\.4(['"])""",r'\g<1>1.0.5\2',g,count=1)
if c!=1 or n!=1: raise SystemExit('Reseller version metadata update failed')
h+='\n<!-- V1.0.5-GLOBAL-RENTAL-HARD-DELETE -->\n'
for m in ('billing_reseller_delete_rental_global',"deleteRental('${esc(r.id)}')",'Histori transaksi, sesi dan laporan tetap disimpan','V1.0.5-GLOBAL-RENTAL-HARD-DELETE'):
 if m not in h: raise SystemExit('Missing Reseller V1.0.5 marker: '+m)
for m in ('<option value="disabled">Nonaktif</option>','billing_reseller_disable_rental_global'):
 if m in h: raise SystemExit('Obsolete Reseller disable action remains: '+m)
for m in ('billing_reseller_edit_rental_global','billing_reseller_create_rental_global'):
 if m not in h: raise SystemExit('Existing Reseller add/edit missing: '+m)
scripts=re.findall(r'<script\b(?![^>]*\bsrc=)[^>]*>(.*?)</script>',h,re.I|re.S)
if len(scripts)!=1: raise SystemExit(f'Expected one inline Reseller dashboard script, found {len(scripts)}')
Path('/tmp/reseller-delete-dashboard.js').write_text(scripts[0],encoding='utf-8')
D.write_text(h,encoding='utf-8'); G.write_text(g,encoding='utf-8')
print('PASS: Reseller V1.0.5 hard delete; active-session guard; add/edit retained; version metadata updated.')
