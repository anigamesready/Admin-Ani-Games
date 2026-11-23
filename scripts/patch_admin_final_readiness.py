from pathlib import Path

ROOT=Path(".")
HTML=ROOT/"android/app/src/main/assets/web/admin.html"
GRADLE=ROOT/"android/app/build.gradle"
VERSION=ROOT/"VERSION.txt"
html=HTML.read_text(encoding="utf-8")
gradle=GRADLE.read_text(encoding="utf-8")

def once(old,new,label):
    global html
    n=html.count(old)
    if n==0 and new in html: return
    if n!=1: raise SystemExit(f"{label}: expected one anchor, found {n}")
    html=html.replace(old,new,1)

# ExcelJS should not hang/fail the report: use the existing XLSX library as a compatible fallback.
once("""async function ensureExcelJS(){
  if(window.ExcelJS)return true;
  return await new Promise(resolve=>{const s=document.createElement('script');s.src='https://cdn.jsdelivr.net/npm/exceljs@4.4.0/dist/exceljs.min.js';s.onload=()=>resolve(true);s.onerror=()=>resolve(false);document.head.appendChild(s)})
}""","""async function ensureExcelJS(){
  if(window.ExcelJS)return true;
  return await new Promise(resolve=>{
    let settled=false;const s=document.createElement('script');s.async=true;
    const finish=value=>{if(settled)return;settled=true;clearTimeout(timer);resolve(!!value)};
    const timer=setTimeout(()=>finish(false),6000);
    s.src='https://cdn.jsdelivr.net/npm/exceljs@4.4.0/dist/exceljs.min.js';
    s.onload=()=>finish(!!window.ExcelJS);s.onerror=()=>finish(false);document.head.appendChild(s);
  });
}""","ExcelJS bounded loader")

fallback = r'''function exportExcelFallbackXLSX(){
 const X=window.XLSX;if(!X||!X.utils||!X.utils.book_new||!X.writeFile)throw new Error('Mesin Excel tidak tersedia; library XLSX gagal dimuat.');
 const wb=X.utils.book_new(),period=String($('from')?.value||'-')+' s/d '+String($('to')?.value||'-'),summary=report?.summary||{};
 const active=Number(report?.total_active_seconds||0)/3600,event=Number(report?.total_event_seconds||0)/3600;
 const add=(name,rows)=>X.utils.book_append_sheet(wb,X.utils.aoa_to_sheet(rows),name);
 add('Dashboard',[
  ['ANI GAMES BILLING - LAPORAN PEMAKAIAN'],['Organisasi',currentOrg?.name||'Organisasi'],['Periode',period],
  ['Transaksi',Number(summary.transactions||summary.sessions||report?.rows?.length||0)],
  ['Sesi',Number(summary.sessions||report?.rows?.length||0)],['Sesi aktif',Number(summary.active_sessions||0)],
  ['Jam aktif bermain',Number(active.toFixed(2))],['Jam event tersimpan',Number(event.toFixed(2))],
  ['Pendapatan (IDR)',Number(summary.revenue||0)],['Dibuat',new Date().toLocaleString('id-ID')]
 ]);
 add('Detail Sesi',[['User ID','PC','Tanggal','Mulai','Selesai','Jam Aktif','Jam Event','Status'],
  ...reportRows().map(x=>[x.user_id,x.pc,x.date,x.start,x.end,Number(x.active.toFixed(2)),Number(x.event.toFixed(2)),x.status])]);
 add('Per PC',[['PC','Sesi','Jam Aktif','Jam Event'],...(report?.by_device||[]).map(x=>[
  x.pc_name||'-',Number(x.sessions||0),Number((Number(x.seconds_active||0)/3600).toFixed(2)),Number((Number(x.seconds_event||0)/3600).toFixed(2))])]);
 add('Per User',[['User ID','PC','Sesi','Jam Penggunaan','Jam Event'],...(report?.by_user||[]).map(x=>[
  x.user_id||'-',x.pc_names||'-',Number(x.sessions||0),Number((Number(x.seconds_active||0)/3600).toFixed(2)),Number((Number(x.seconds_event||0)/3600).toFixed(2))])]);
 add('Per Hari',[['Tanggal','Jumlah Sesi','Jam Aktif'],...reportDaily().map(x=>[x.date,Number(x.sessions||0),Number(x.hours.toFixed(2))])]);
 X.writeFile(wb,'laporan-'+String(currentOrg?.slug||'rental')+'-'+String($('from')?.value||'periode')+'.xlsx',{compression:true});
 msg('Excel berhasil diunduh (5 sheet laporan; mode kompatibel XLSX).');
}
async function ensureJsPDF(){
 if(window.jspdf?.jsPDF)return true;
 return await new Promise(resolve=>{
  let settled=false;const s=document.createElement('script');s.async=true;
  const finish=value=>{if(settled)return;settled=true;clearTimeout(timer);resolve(!!value)};
  const timer=setTimeout(()=>finish(false),6000);
  s.src='https://cdn.jsdelivr.net/npm/jspdf@2.5.2/dist/jspdf.umd.min.js';
  s.onload=()=>finish(!!window.jspdf?.jsPDF);s.onerror=()=>finish(false);document.head.appendChild(s);
 });
}
'''
once("function reportRows(){",fallback+"\nfunction reportRows(){","Excel fallback/PDF loader")
once("const ok=await ensureExcelJS();if(!ok||!window.ExcelJS)throw new Error('Mesin Excel belum berhasil dimuat.');const wb=new ExcelJS.Workbook();",
     "const ok=await ensureExcelJS();if(!ok||!window.ExcelJS){if(window.XLSX){exportExcelFallbackXLSX();return;}throw new Error('Mesin Excel belum berhasil dimuat.');}const wb=new ExcelJS.Workbook();","Excel fallback entry")
once("catch(e){console.error(e);msg('❌ Export Excel gagal: '+(e.message||e),true)}}",
     "catch(e){console.error(e);try{if(window.XLSX){exportExcelFallbackXLSX();return}}catch(f){console.error(f)}msg('❌ Export Excel gagal: '+(e.message||e),true)}}","Excel fallback catch")
once("function exportPDF(){if(!report)return msg('Laporan belum tersedia. Terapkan periode terlebih dahulu.',true);try{const {jsPDF}=window.jspdf;",
     "async function exportPDF(){if(!report)return msg('Laporan belum tersedia. Terapkan periode terlebih dahulu.',true);try{if(!window.jspdf?.jsPDF){const loaded=await ensureJsPDF();if(!loaded)throw new Error('Library PDF belum berhasil dimuat. Periksa koneksi internet lalu coba lagi.');}const {jsPDF}=window.jspdf;","PDF dependency guard")

helpers = r'''async function fetchIoTWithTimeout(url,options={},timeoutMs=12000){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeoutMs);
 try{return await fetch(url,{...options,cache:'no-store',signal:controller.signal})}
 catch(e){if(e?.name==='AbortError')throw new Error('BLYNK_REQUEST_TIMEOUT');throw e}
 finally{clearTimeout(timer)}
}
function blynkUserError(raw){
 const value=String(raw||'error'),key=value.toLowerCase();
 if(key.includes('token_not_configured'))return 'Token Blynk belum diatur pada Supabase Secret BLYNK_AUTH_TOKEN.';
 if(key.includes('owner_only'))return 'Kontrol Blynk hanya untuk akun Owner.';
 if(key.includes('device_mapping_required'))return 'Pemetaan PC ke Blynk belum ditentukan. Atur metadata blynkPowerTarget=true.';
 if(key.includes('device_mapping_conflict'))return 'Lebih dari satu PC ditandai sebagai target Blynk; sisakan satu target.';
 if(key.includes('device_mapping_mismatch'))return 'PC yang dipilih tidak cocok dengan pemetaan Blynk.';
 if(key.includes('device_not_accessible'))return 'PC tidak dapat diakses oleh akun Admin ini.';
 if(key.includes('blynk_device_offline'))return 'Hardware Blynk sedang offline; pulsa belum dikirim.';
 if(key.includes('blynk_status_unavailable')||key.includes('blynk_status_rejected'))return 'Status hardware gagal diverifikasi; cek token/koneksi Blynk.';
 if(key.includes('blynk_command_failed'))return 'Blynk menolak pulsa. Cek token, datastream/pin V0, dan log Edge Function.';
 if(key.includes('blynk_request_timeout')||key.includes('aborterror'))return 'Permintaan Blynk timeout. Cek status sebelum mencoba lagi.';
 if(key.includes('failed to fetch')||key.includes('fetch failed'))return 'Koneksi ke Supabase gagal; perintah belum dapat diverifikasi.';
 return value;
}
'''
once("async function refreshIoTStatus(){",helpers+"async function refreshIoTStatus(){","Blynk helper")

start=html.find("async function refreshIoTStatus(){")
end=html.find("function v12DbTargetChanged",start)
if start<0 or end<0: raise SystemExit("Blynk function anchors not found")
old=html[start:end]
if "async function sendIoTPower()" not in old or "SB_FUNCTION_URL" not in old: raise SystemExit("Unexpected Blynk code block")

blynk=r'''async function refreshIoTStatus(){
 const el=$('iotPowerStatus');if(!el||!session?.access_token)return;
 try{
  const r=await fetchIoTWithTimeout(SB_FUNCTION_URL+'/iot/status',{headers:{apikey:SB_KEY,authorization:'Bearer '+session.access_token}},12000);
  const d=await r.json().catch(()=>({}));if(!r.ok||!d.ok)throw new Error(d.error||('BLYNK_STATUS_HTTP_'+r.status));
  el.textContent=d.online?'IoT Blynk: ONLINE':'IoT Blynk: OFFLINE';el.style.color=d.online?'var(--ok)':'var(--danger)';
 }catch(e){el.textContent=blynkUserError(e?.message||'BLYNK_STATUS_UNAVAILABLE');el.style.color='var(--danger)'}
}
async function sendIoTPower(){
 if(ctx?.role!=='owner')return msg('Kontrol power IoT hanya untuk Master/Owner.',true);
 if(!selectedDeviceId)return msg('Pilih PC terlebih dahulu.',true);
 const target=devicesCache.find(d=>d.id===selectedDeviceId);if(!target)return msg('PC terpilih tidak ditemukan.',true);
 const promptText=target.uiStatus==='online'?'PC '+target.device_name+' masih ONLINE menurut heartbeat. Menekan tombol fisik dapat memicu sleep/shutdown. Tetap kirim satu pulsa?':'Kirim satu pulsa tekan ke modul IoT Blynk V0 untuk PC '+target.device_name+'?';
 if(!confirm(promptText))return;
 const button=$('iotPowerButton'),status=$('iotPowerStatus');if(button)button.disabled=true;
 if(status)status.textContent='Memeriksa Blynk dan mengirim satu pulsa…';
 let pulseAccepted=false;
 try{
  const r=await fetchIoTWithTimeout(SB_FUNCTION_URL+'/iot/power',{method:'POST',headers:{'content-type':'application/json',apikey:SB_KEY,authorization:'Bearer '+session.access_token},body:JSON.stringify({deviceId:selectedDeviceId})},15000);
  const d=await r.json().catch(()=>({}));
  if(!r.ok||!d.ok){const e=new Error(d.error||('BLYNK_POWER_HTTP_'+r.status));e.detail=d.detail||'';throw e}
  pulseAccepted=true;if(status)status.textContent='Pulsa diterima Blynk • menunggu heartbeat PC…';
  msg('Pulsa Blynk diterima. Menunggu heartbeat PC; belum menganggap PC berhasil hidup sampai terdeteksi.');
  const started=Date.now();let online=false;
  while(Date.now()-started<90000){
   await new Promise(resolve=>setTimeout(resolve,5000));
   try{await loadDevices()}catch(_){/* missed refresh does not prove pulse failed */}
   const current=devicesCache.find(x=>x.id===selectedDeviceId);if(current?.uiStatus==='online'){online=true;break}
  }
  if(status)status.textContent=online?'PC terdeteksi ONLINE melalui heartbeat.':'Pulsa diterima, tetapi heartbeat PC belum terdeteksi setelah 90 detik.';
  msg(online?'PC sudah terdeteksi ONLINE melalui heartbeat.':'Pulsa diterima, tetapi PC belum memberi heartbeat. Periksa daya/modul sebelum mengirim pulsa lagi.',!online);
 }catch(e){
  const reason=blynkUserError(e?.message||'BLYNK_POWER_FAILED'),detail=String(e?.detail||''),message=detail?reason+' Detail: '+detail:reason;
  if(status)status.textContent='IoT gagal: '+message;
  msg((pulseAccepted?'Pulsa mungkin sudah dikirim tetapi konfirmasi lanjutan gagal: ':'IoT gagal: ')+message,true);
 }finally{if(button)button.disabled=false}
}
'''
html=html[:start]+blynk+html[end:]

if "function exportExcelFallbackXLSX()" not in html or "function blynkUserError(" not in html or "async function ensureJsPDF()" not in html: raise SystemExit("Final readiness functions missing")
if "versionCode 43" not in gradle or "versionName '12.1.15'" not in gradle: raise SystemExit("Unexpected Android baseline; expected v12.1.15/code 43")
gradle=gradle.replace("versionCode 43","versionCode 44",1).replace("versionName '12.1.15'","versionName '12.1.16'",1)
HTML.write_text(html,encoding="utf-8")
GRADLE.write_text(gradle,encoding="utf-8")
VERSION.write_text("v12.1.16-dual-db-blynk-report-readiness\n",encoding="utf-8")
print("Admin readiness patch: Blynk timeouts/errors, Excel fallback, PDF retry; version 12.1.16/code 44")
