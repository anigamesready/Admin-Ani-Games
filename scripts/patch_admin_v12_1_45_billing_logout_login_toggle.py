from pathlib import Path

ROOT=Path('.')
html_path=ROOT/'android/app/src/main/assets/web/admin.html'
gradle_path=ROOT/'android/app/build.gradle'
if not html_path.is_file() or not gradle_path.is_file(): raise SystemExit('Admin V12.1.44 project files missing.')
html=html_path.read_text(encoding='utf-8')
gradle=gradle_path.read_text(encoding='utf-8')
MARKER='V12.1.45-BILLING-LOGOUT-LOGIN-TOGGLE'
if MARKER in html:
    print('PASS: Admin V12.1.45 patch already applied'); raise SystemExit(0)
if "versionCode 72" not in gradle or "versionName '12.1.44'" not in gradle:
    raise SystemExit('Expected Admin V12.1.44 baseline; refusing patch.')
def once(src,old,new,label):
    n=src.count(old)
    if n!=1: raise SystemExit(f'{label} anchor mismatch: expected 1, found {n}')
    return src.replace(old,new,1)

# Local override bridges the command ACK and the next device heartbeat; DB metadata wins once it agrees.
helper=r"""// V12.1.45 — Billing Logout/Login state. PC background command channel remains alive.
const ADMIN_BILLING_UI_RELEASE='V12.1.45-BILLING-LOGOUT-LOGIN-TOGGLE';
const ADMIN_BILLING_UI_STATE_KEY='ani_games_admin_billing_ui_state_v1';
function readBillingUiOverrides(){try{const v=JSON.parse(localStorage.getItem(ADMIN_BILLING_UI_STATE_KEY)||'{}');return v&&typeof v==='object'?v:{}}catch(_){return {}}}
function setBillingUiOverride(deviceId,state){if(!deviceId)return;const map=readBillingUiOverrides();map[deviceId]={state,at:Date.now()};try{localStorage.setItem(ADMIN_BILLING_UI_STATE_KEY,JSON.stringify(map))}catch(_){}}
function resolveBillingUiState(device){const server=String(device?.metadata?.billingUiState||'open')==='closed'?'closed':'open';const map=readBillingUiOverrides(),entry=map[device?.id];if(!entry)return server;if(entry.state===server){delete map[device.id];try{localStorage.setItem(ADMIN_BILLING_UI_STATE_KEY,JSON.stringify(map))}catch(_){}return server;}if(Date.now()-Number(entry.at||0)>120000){delete map[device.id];try{localStorage.setItem(ADMIN_BILLING_UI_STATE_KEY,JSON.stringify(map))}catch(_){}return server;}return String(entry.state||server)}
function renderBillingToggleControls(){const d=devicesCache.find(x=>x.id===selectedDeviceId)||selectedDevice;const state=d?.billingUiState||'open';const b=$('billingUiToggleButton');if(b){b.textContent=state==='closed'?'Login Billing':state==='closing'?'Menutup Billing…':state==='starting'?'Membuka Billing…':'Logout Billing';b.disabled=!d||state==='closing'||state==='starting'||(state==='open'&&d.uiStatus!=='online');}const restart=$('restartBillingButton');if(restart)restart.style.display=state==='closed'?'none':'';const refresh=$('refreshBillingButton');if(refresh)refresh.style.display=state==='closed'?'none':'';for(const id of ['pauseBillingButton','resumeBillingButton','stopBillingButton']){const el=$(id);if(el)el.disabled=!d||state!=='open'||d.uiStatus!=='online';}}
async function selectedBillingToggle(){return toggleBillingUi(selectedDeviceId)}
async function toggleBillingUi(deviceId){const d=devicesCache.find(x=>x.id===deviceId);if(!d)return msg('Pilih PC terlebih dahulu.',true);const state=d.billingUiState||resolveBillingUiState(d);if(state==='closed'){const command=d.uiStatus==='online'?'refresh':'restart_billing';setBillingUiOverride(deviceId,'starting');renderBillingToggleControls();const result=await cmd(deviceId,command);setBillingUiOverride(deviceId,result==='completed'?'open':'closed');await loadDevices();return;}if(d.uiStatus!=='online')return msg('PC belum online. Logout tidak dikirim.',true);if(!confirm('Logout Billing akan menghentikan sesi aktif dan timer, lalu menutup tampilan Billing. PC dan koneksi kontrol Admin tetap hidup. Login kembali dapat dilakukan dari tombol ini. Lanjutkan?'))return;setBillingUiOverride(deviceId,'closing');renderBillingToggleControls();const result=await cmd(deviceId,'logout');setBillingUiOverride(deviceId,result==='completed'?'closed':'open');await loadDevices();}

"""
html=once(html,'async function loadDevices(){',helper+'async function loadDevices(){','Billing state helper')

old_rows="const rows=(r.data||[]).map(d=>{const seen=d.last_seen_at?new Date(d.last_seen_at).getTime():0;const online=seen&&now-seen<=45000;return {...d,uiStatus:online?'online':'offline'}});"
new_rows="const rows=(r.data||[]).map(d=>{const seen=d.last_seen_at?new Date(d.last_seen_at).getTime():0;const online=seen&&now-seen<=45000;return {...d,uiStatus:online?'online':'offline',billingUiState:resolveBillingUiState(d)}});"
html=once(html,old_rows,new_rows,'Load-device billing state')

old_toolbar="<button onclick=\"selectedCmd('refresh')\">Refresh</button><button onclick=\"selectedCmd('restart_billing')\">Restart Billing</button><button onclick=\"selectedCmd('pause')\">Pause</button><button onclick=\"selectedCmd('resume')\">Resume</button><button onclick=\"selectedCmd('logout')\">Logout Billing</button><button class=\"danger\" onclick=\"selectedCmd('stop')\">Stop</button>"
new_toolbar="<button id=\"refreshBillingButton\" onclick=\"selectedCmd('refresh')\">Refresh</button><button id=\"restartBillingButton\" onclick=\"selectedCmd('restart_billing')\">Restart Billing</button><button id=\"pauseBillingButton\" onclick=\"selectedCmd('pause')\">Pause</button><button id=\"resumeBillingButton\" onclick=\"selectedCmd('resume')\">Resume</button><button id=\"billingUiToggleButton\" onclick=\"selectedBillingToggle()\">Logout Billing</button><button id=\"stopBillingButton\" class=\"danger\" onclick=\"selectedCmd('stop')\">Stop</button>"
html=once(html,old_toolbar,new_toolbar,'Selected Billing toolbar')

old_row="<button onclick=\"cmd('\${d.id}','logout')\">Logout</button>"
new_row="<button onclick=\"toggleBillingUi('\${d.id}')\">\${d.billingUiState==='closed'?'Login Billing':d.billingUiState==='closing'?'Menutup…':d.billingUiState==='starting'?'Membuka…':'Logout Billing'}</button>"
html=once(html,old_row,new_row,'Device row Billing toggle')

old_state="const state=active?(m.activeCode?'RENTAL AKTIF':m.pausedCode?'RENTAL PAUSED':'STANDBY / BILLING SIAP'):'TERPUTUS';"
new_state="const state=active?(selectedDevice.billingUiState==='closed'?'BILLING LOGOUT':selectedDevice.billingUiState==='closing'?'BILLING MENUTUP':selectedDevice.billingUiState==='starting'?'BILLING MEMBUKA':m.activeCode?'RENTAL AKTIF':m.pausedCode?'RENTAL PAUSED':'STANDBY / BILLING SIAP'):'TERPUTUS';"
html=once(html,old_state,new_state,'Selected device status')

old_table="d.uiStatus==='online'?(d.metadata?.activeCode?'RENTAL AKTIF':d.metadata?.pausedCode?'RENTAL PAUSED':'STANDBY / BILLING SIAP'):'TERPUTUS'"
new_table="d.uiStatus==='online'?(d.billingUiState==='closed'?'BILLING LOGOUT':d.billingUiState==='closing'?'BILLING MENUTUP':d.billingUiState==='starting'?'BILLING MEMBUKA':d.metadata?.activeCode?'RENTAL AKTIF':d.metadata?.pausedCode?'RENTAL PAUSED':'STANDBY / BILLING SIAP'):'TERPUTUS'"
html=once(html,old_table,new_table,'Device table status')
html=once(html,'await renderSelectedDevice();await loadGlobalRentalAccounts()','await renderSelectedDevice();renderBillingToggleControls();await loadGlobalRentalAccounts()','Render selected toggle')

start=html.find('async function cmd(device,command,seconds){')
if start<0: raise SystemExit('Admin cmd() missing.')
end=html.find('\nasync function waitDeviceCommand(',start)
if end<0: raise SystemExit('Admin waitDeviceCommand() boundary missing.')
new_cmd="""async function cmd(device,command,seconds){try{const target=devicesCache.find(d=>d.id===device);if(!target)return msg('PC tidak ditemukan pada tenant aktif.',true),'failed';const offlineRestart=command==='restart_billing'&&target.uiStatus!=='online';if(target.uiStatus!=='online'&&!offlineRestart)return msg('PC terpilih sedang OFFLINE. Kontrol tidak dikirim.',true),'failed';if(target.billingUiState==='closed'&&['pause','resume','stop'].includes(command))return msg('Billing sedang Logout. Tekan Login Billing terlebih dahulu.',true),'failed';const pcName=target.device_name||target.client_id||'PC terpilih';const windowsActions={shutdown:'Matikan Windows',restart_pc:'Restart Windows',logoff:'Logoff Windows'};if(windowsActions[command]&&!confirm(windowsActions[command]+' pada '+pcName+'? Perintah hanya dikirim ke PC ini.'))return 'cancelled';const payload={source:'dashboard-admin',...(offlineRestart?{queuedWhileOffline:true}: {})};if(seconds)payload.seconds=seconds;if(['pause','resume','stop'].includes(command)){const ss=await rpc('admin_selected_sessions',{p_org_id:currentOrg.id,p_device_id:device});const s=(ss||[])[0];if(!s)return msg('Tidak ada sesi aktif/paused pada PC ini.',true),'failed';payload.session_id=s.id;}const sent=await rpc('admin_command',{p_org_id:currentOrg.id,p_device_id:device,p_command:command,p_payload:payload});if(sent?.ok===false)throw new Error(sent.message||'Server menolak perintah.');const commandId=sent?.command_id||sent?.id;if(!commandId)throw new Error('Server tidak memberikan ID perintah; status belum dapat diverifikasi.');if(offlineRestart){msg('Login Billing masuk antrean. Agen PC akan mengambil perintah saat PC kembali aktif.');await loadDevices();return 'queued';}const timeout=(command==='refresh'||command==='restart_billing'||command==='logout')?45000:15000;const state=await waitDeviceCommand(commandId,timeout);if(state?.status==='completed'){if(command==='logout')setBillingUiOverride(device,'closed');if(command==='refresh'||command==='restart_billing')setBillingUiOverride(device,'open');msg(command==='logout'?'PC '+pcName+' menghentikan sesi dan menutup Billing.':'PC '+pcName+' mengonfirmasi perintah '+command+'.');}else if(state?.status==='failed'||state?.status==='expired')throw new Error(state.result?.message||state.result?.error||('PC gagal menjalankan '+command+'.'));else{msg('Perintah '+command+' sudah masuk antrean untuk '+pcName+', tetapi PC belum mengonfirmasi selesai.');await loadDevices();return 'pending';}await loadDevices();return 'completed'}catch(e){msg(e.message,true);return 'failed'}}"""
html=html[:start]+new_cmd+html[end:]

gradle=once(gradle,'versionCode 72','versionCode 73','Admin versionCode')
gradle=once(gradle,"versionName '12.1.44'","versionName '12.1.45'",'Admin versionName')
for token in (MARKER,'Login Billing','Logout Billing','billingUiState','toggleBillingUi',"cmd(deviceId,command)","command==='logout'","command==='refresh'","waitDeviceCommand(commandId,timeout)","shutdown:'Matikan Windows'","restart_pc:'Restart Windows'","logoff:'Logoff Windows'","rpc('admin_command'","rpc('admin_selected_sessions'","V12.1.43-MONTHLY-REPORT-ACTIVE-EDIT",'async function loadDashboardReport30d()','admin_delete_rental_global'):
    if token not in html: raise SystemExit('Admin regression marker missing: '+token)
if "versionCode 73" not in gradle or "versionName '12.1.45'" not in gradle: raise SystemExit('Admin V12.1.45 Gradle identity mismatch.')
html_path.write_text(html,encoding='utf-8')
gradle_path.write_text(gradle,encoding='utf-8')
print('PASS: Admin V12.1.45 Logout/Login toggle, command ACK, offline watchdog login, state labels and version bump.')
