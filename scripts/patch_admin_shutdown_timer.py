from pathlib import Path
import os
import re

ROOT = Path(".").resolve()
html_path = ROOT / "android/app/src/main/assets/web/admin.html"
gradle_path = ROOT / "android/app/build.gradle"
version_path = ROOT / "VERSION.txt"

if not html_path.is_file() or not gradle_path.is_file():
    raise SystemExit("Admin Android source root not found; expected android/app/src/main/assets/web/admin.html and android/app/build.gradle.")

html = html_path.read_text(encoding="utf-8")
gradle = gradle_path.read_text(encoding="utf-8")

if "function schedulePcShutdown()" in html or "V12.1.28-SCHEDULED-SHUTDOWN-TIMER" in html:
    raise SystemExit("Shutdown timer patch already exists; refusing to apply it twice.")

timer_card = r"""
<div class="card" id="pcShutdownTimerCard" style="margin-top:12px;border:1px solid var(--a)">
 <div class="top"><div><h3 style="margin:0">⏱️ Timer Shutdown PC</h3><div class="muted">Pilih satu PC, atur durasi, lalu jadwalkan shutdown. PC akan memeriksa sesi rental lagi sebelum tindakan dijalankan.</div></div><span id="shutdownTimerBadge" class="pill">BELUM DIJADWALKAN</span></div>
 <div class="cards2" style="margin-top:10px">
  <div class="field"><label for="shutdownTargetDevice">Target PC</label><select id="shutdownTargetDevice" onchange="updateShutdownTimerStatus()" style="width:100%"><option value="">Memuat daftar PC…</option></select></div>
  <div class="field"><label>Durasi dari sekarang</label><div class="row" style="align-items:center;gap:8px"><input id="shutdownHours" type="number" min="0" max="24" step="1" value="2" aria-label="Jam timer shutdown" style="width:90px"><span>jam</span><input id="shutdownMinutes" type="number" min="0" max="59" step="1" value="15" aria-label="Menit timer shutdown" style="width:90px"><span>menit</span></div></div>
 </div>
 <div id="shutdownTimerStatus" class="msg" role="status" aria-live="polite" style="margin-top:10px">Belum ada timer shutdown.</div>
 <div id="shutdownTimerCountdown" class="stat" style="margin:8px 0;font-variant-numeric:tabular-nums">--:--:--</div>
 <div id="shutdownTimerPreview" class="muted" style="margin:8px 0">Pratinjau tidak mengirim perintah ke PC.</div>
 <div class="row"><button type="button" onclick="previewPcShutdown()">Pratinjau Pilihan</button><button type="button" class="primary" onclick="schedulePcShutdown()">Jadwalkan Shutdown</button><button type="button" class="danger" onclick="cancelPcShutdown()">Batalkan Timer</button></div>
 <div class="muted" style="margin-top:8px">Pengaman: target harus online, admin harus terotorisasi, dan timer otomatis dibatalkan jika sesi rental masih aktif/paused pada saat jadwal diterima atau ketika countdown selesai. Pratinjau saja tidak mengirim perintah.</div>
</div>
"""

section_anchor = '</section>\n\n<section id="pairing"'
if html.count(section_anchor) != 1:
    raise SystemExit("Device section insertion anchor mismatch; refusing to patch the wrong page.")
html = html.replace(section_anchor, timer_card + '\n</section>\n\n<section id="pairing"', 1)

nav_anchor = '<button data-tab="databaseTools"'
if html.count(nav_anchor) != 1:
    raise SystemExit("Admin navigation insertion anchor mismatch; refusing to patch.")
html = html.replace(nav_anchor, '<button id="shutdownTimerNav" onclick="openShutdownTimerMenu()">⏱️ Timer Shutdown PC</button>' + nav_anchor, 1)

helpers = r"""
const ADMIN_PC_SHUTDOWN_STATE_KEY = 'ani_games_admin_shutdown_timer_v1';
function readAdminShutdownStates() {
 try {
  const v = JSON.parse(localStorage.getItem(ADMIN_PC_SHUTDOWN_STATE_KEY) || '{}');
  return v && typeof v === 'object' && !Array.isArray(v) ? v : {};
 } catch (_) { return {}; }
}
function saveAdminShutdownStates(value) {
 try { localStorage.setItem(ADMIN_PC_SHUTDOWN_STATE_KEY, JSON.stringify(value || {})); }
 catch (e) { console.warn('Timer shutdown status could not be persisted locally.', e); }
}
function shutdownDurationMs() {
 const h = Number($('shutdownHours')?.value);
 const m = Number($('shutdownMinutes')?.value);
 if (!Number.isInteger(h) || h < 0 || h > 24) throw new Error('Jam harus antara 0 dan 24.');
 if (!Number.isInteger(m) || m < 0 || m > 59) throw new Error('Menit harus antara 0 dan 59.');
 const ms = (h * 60 + m) * 60000;
 if (ms < 60000) throw new Error('Durasi minimum timer adalah 1 menit.');
 if (ms > 24 * 60 * 60000) throw new Error('Durasi maksimum timer adalah 24 jam.');
 return ms;
}
function shutdownFormatRemaining(ms) {
 const total = Math.max(0, Math.ceil(ms / 1000));
 const h = Math.floor(total / 3600);
 const m = Math.floor((total % 3600) / 60);
 const s = total % 60;
 return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
}
function selectedShutdownTarget() {
 const id = $('shutdownTargetDevice')?.value || '';
 return (devicesCache || []).find(d => String(d.id) === String(id)) || null;
}
function refreshShutdownTargetOptions(rows) {
 const select = $('shutdownTargetDevice');
 if (!select) return;
 const previous = select.value;
 const list = Array.isArray(rows) ? rows : [];
 select.innerHTML = '<option value="">Pilih PC target</option>' + list.map(d => {
  const timer = d.metadata?.shutdownTimer || {};
  const expected = timer.expectedDisconnect === true &&
   ['admin_shutdown_requested','shutdown_requested'].includes(String(timer.state || ''));
  const label = d.uiStatus === 'online' ? 'ONLINE' : (expected ? 'MATI VIA ADMIN' : 'OFFLINE DI LUAR PERINTAH ADMIN');
  return '<option value="' + esc(d.id) + '">' + esc(d.device_name || d.client_id || 'PC') + ' • ' + label + '</option>';
 }).join('');
 const target = list.find(d => d.id === previous)
  || list.find(d => /galtys/i.test(String(d.device_name || '')))
  || list.find(d => d.id === selectedDeviceId)
  || list.find(d => d.uiStatus === 'online')
  || list[0];
 select.value = target?.id || '';
 updateShutdownTimerStatus();
}
function activeRentalShutdownBlocker(device) {
 const metadata = device?.metadata || {};
 const activeCode = String(metadata.activeCode || '').trim();
 const pausedCode = String(metadata.pausedCode || '').trim();
 if (activeCode) return 'Sesi rental ' + activeCode + ' masih aktif. Shutdown tidak dijadwalkan.';
 if (pausedCode) return 'Sesi rental ' + pausedCode + ' masih paused/terbuka. Shutdown tidak dijadwalkan.';
 return '';
}
function effectiveShutdownTimerState(device) {
 if (!device) return null;
 const local = readAdminShutdownStates()[String(device.id)];
 const remote = device.metadata?.shutdownTimer;
 if (remote && typeof remote === 'object' && remote.state) {
  const remoteAt = Date.parse(remote.updatedAt || '') || 0;
  const localAt = Date.parse(local?.updatedAt || '') || 0;
  if (!local || remoteAt > localAt || (remote.scheduleId === local.scheduleId && remoteAt >= localAt)) return remote;
 }
 return local || (remote && typeof remote === 'object' ? remote : null);
}
function updateShutdownTimerStatus() {
 const target = selectedShutdownTarget();
 const status = $('shutdownTimerStatus');
 const countdown = $('shutdownTimerCountdown');
 const badge = $('shutdownTimerBadge');
 if (!status || !countdown || !badge) return;
 if (!target) {
  status.textContent = 'Pilih target PC yang akan dijadwalkan.';
  countdown.textContent = '--:--:--';
  badge.textContent = 'PILIH PC';
  return;
 }
 const state = effectiveShutdownTimerState(target);
 const blocker = activeRentalShutdownBlocker(target);
 if (state?.state === 'scheduled' || state?.state === 'pending') {
  const deadline = Date.parse(state.deadlineAt || '');
  if (Number.isFinite(deadline)) {
   countdown.textContent = shutdownFormatRemaining(deadline - Date.now());
   if (state.state === 'pending') {
    badge.textContent = 'MENUNGGU PC';
    status.textContent = state.message || ('Permintaan timer untuk ' + target.device_name + ' sedang menunggu konfirmasi PC.');
   } else {
    badge.textContent = 'TIMER AKTIF';
    status.textContent = 'Target: ' + target.device_name + ' • shutdown terjadwal ' + new Date(deadline).toLocaleString('id-ID') + '.';
   }
   if (blocker) status.textContent += ' Peringatan status terakhir: ' + blocker;
   return;
  }
 }
 countdown.textContent = '--:--:--';
 if (state?.state === 'blocked_active_session') {
  badge.textContent = 'DIBLOKIR';
  status.textContent = state.message || 'Shutdown dibatalkan karena sesi rental masih aktif.';
 } else if (state?.state === 'canceled') {
  badge.textContent = 'DIBATALKAN';
  status.textContent = state.message || 'Timer shutdown telah dibatalkan pada PC.';
 } else if (state?.state === 'admin_shutdown_requested' && state.expectedDisconnect === true) {
  badge.textContent = target.uiStatus === 'online' ? 'SHUTDOWN ADMIN' : 'MATI VIA ADMIN';
  status.textContent = 'Shutdown langsung diminta dari Admin APK. Timer telah dihentikan lebih dahulu; koneksi terputus setelah perintah ini diklasifikasikan sebagai shutdown terencana.';
 } else if (state?.state === 'shutdown_requested' && state.expectedDisconnect === true) {
  badge.textContent = target.uiStatus === 'online' ? 'SHUTDOWN TERJADWAL' : 'MATI VIA TIMER ADMIN';
  status.textContent = state.message || 'Countdown shutdown terjadwal selesai; PC menerima perintah dari timer Admin.';
 } else if (state?.state === 'shutdown_requested') {
  badge.textContent = 'SELESAI';
  status.textContent = 'Countdown selesai. PC telah menerima permintaan shutdown; status akhir bergantung pada Windows.';
 } else if (state?.state === 'shutdown_failed') {
  badge.textContent = 'GAGAL';
  status.textContent = state.message || 'Windows menolak permintaan shutdown.';
 } else if (blocker) {
  badge.textContent = 'DIBLOKIR';
  status.textContent = target.device_name + ' • ' + blocker;
 } else if (target.uiStatus !== 'online') {
  badge.textContent = 'OFFLINE DI LUAR PERINTAH ADMIN';
  status.textContent = target.device_name + ' offline tanpa penanda shutdown terencana dari Admin APK. Penyebab putus koneksi belum terkonfirmasi; jangan dianggap sebagai shutdown yang diperintahkan Admin.';
 } else if (state?.state === 'previous_admin_shutdown') {
  badge.textContent = 'ONLINE • RIWAYAT ADMIN';
  status.textContent = target.device_name + ' sudah online kembali. Riwayat terakhir mencatat shutdown yang diminta Admin, tetapi penanda itu tidak berlaku untuk putus koneksi berikutnya.';
 } else {
  badge.textContent = 'SIAP';
  status.textContent = target.device_name + ' • online • belum ada timer aktif.';
 }
}
function previewPcShutdown() {
 try {
  const target = selectedShutdownTarget();
  if (!target) throw new Error('Pilih target PC terlebih dahulu.');
  const delay = shutdownDurationMs();
  const endAt = new Date(Date.now() + delay);
  const line = 'PRATINJAU SAJA — Target: ' + (target.device_name || target.client_id) +
   ' • durasi ' + shutdownFormatRemaining(delay) + ' • perkiraan waktu ' + endAt.toLocaleString('id-ID') +
   '. Belum ada perintah yang dikirim ke PC.';
  $('shutdownTimerPreview').textContent = line;
  updateShutdownTimerStatus();
 } catch (e) {
  $('shutdownTimerPreview').textContent = 'Pratinjau gagal: ' + (e?.message || e);
 }
}
async function schedulePcShutdown() {
 if (ctx?.role !== 'owner') return msg('Timer shutdown hanya dapat dijadwalkan oleh Master/Owner.', true);
 let commandId = null;
 try {
  const target = selectedShutdownTarget();
  if (!target) throw new Error('Pilih target PC terlebih dahulu.');
  if (target.uiStatus !== 'online') throw new Error('PC target sedang offline. Perintah tidak dikirim.');
  const blocker = activeRentalShutdownBlocker(target);
  if (blocker) throw new Error(blocker);
  const delayMs = shutdownDurationMs();
  const deadlineAt = new Date(Date.now() + delayMs).toISOString();
  let scheduleId;
  try { scheduleId = crypto.randomUUID(); }
  catch (_) { scheduleId = 'shutdown-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 12); }
  const ok = confirm('Konfirmasi Timer Shutdown PC\n\nTarget: ' + target.device_name + '\nDurasi: ' + shutdownFormatRemaining(delayMs) +
   '\nPerkiraan waktu: ' + new Date(deadlineAt).toLocaleString('id-ID') +
   '\n\nPC tidak dimatikan sekarang. Jika ada sesi rental aktif/paused saat timer diterima atau selesai, shutdown akan diblokir.\n\nJadwalkan timer ini?');
  if (!ok) return;
  const result = await rpc('admin_command', {
   p_org_id: currentOrg.id,
   p_device_id: target.id,
   p_command: 'schedule_shutdown',
   p_payload: {scheduled:true, scheduleId:scheduleId, deadlineAt:deadlineAt, delayMs:delayMs,
    targetDeviceId:target.id, targetDeviceName:target.device_name || target.client_id || 'PC', source:'admin-shutdown-timer'}
  });
  commandId = typeof result === 'string' ? result : (result?.command_id || result?.id || null);
  const stateMap = readAdminShutdownStates();
  stateMap[String(target.id)] = {state:'pending', scheduleId:scheduleId, deadlineAt:deadlineAt,
   targetName:target.device_name || target.client_id || 'PC', updatedAt:new Date().toISOString(), commandId:commandId};
  saveAdminShutdownStates(stateMap);
  updateShutdownTimerStatus();
  msg('Permintaan timer shutdown dikirim ke ' + target.device_name + '. Menunggu konfirmasi PC.');
  if (commandId && typeof waitDeviceCommand === 'function') {
   const ack = await waitDeviceCommand(commandId, 15000);
   if (ack?.status === 'failed' || ack?.status === 'expired' || ack?.result?.ok === false) {
    const current = readAdminShutdownStates();
    current[String(target.id)] = {state:'blocked_active_session', scheduleId:scheduleId, deadlineAt:deadlineAt,
     targetName:target.device_name || 'PC', updatedAt:new Date().toISOString(),
     message:String(ack?.result?.message || ack?.result?.error || 'PC menolak timer shutdown.')};
    saveAdminShutdownStates(current);
    updateShutdownTimerStatus();
    throw new Error(String(ack?.result?.message || ack?.result?.error || 'PC menolak timer shutdown.'));
   }
   if (ack?.status === 'completed') {
    const current = readAdminShutdownStates();
    current[String(target.id)] = {...current[String(target.id)], state:'scheduled', updatedAt:new Date().toISOString()};
    saveAdminShutdownStates(current);
   }
  }
  updateShutdownTimerStatus();
 } catch (e) {
  msg('Timer shutdown tidak berhasil dipastikan: ' + (e?.message || e), true);
 }
}
async function cancelPcShutdown() {
 if (ctx?.role !== 'owner') return msg('Pembatalan timer shutdown hanya dapat dilakukan oleh Master/Owner.', true);
 try {
  const target = selectedShutdownTarget();
  if (!target) throw new Error('Pilih PC target terlebih dahulu.');
  if (target.uiStatus !== 'online') throw new Error('PC target sedang offline. Pembatalan tidak dapat dikirim.');
  const old = effectiveShutdownTimerState(target) || readAdminShutdownStates()[String(target.id)];
  const ok = confirm('Batalkan timer shutdown pada ' + target.device_name + '?\n\nTidak ada perintah shutdown baru yang akan dijalankan.');
  if (!ok) return;
  const result = await rpc('admin_command', {
   p_org_id: currentOrg.id,
   p_device_id: target.id,
   p_command: 'cancel_shutdown_timer',
   p_payload: {cancelScheduled:true, scheduleId:old?.scheduleId || null, targetDeviceId:target.id,
    targetDeviceName:target.device_name || target.client_id || 'PC', source:'admin-shutdown-timer-cancel'}
  });
  const commandId = result?.command_id || result?.id || null;
  const stateMap = readAdminShutdownStates();
  stateMap[String(target.id)] = {state:'pending', scheduleId:old?.scheduleId || null, deadlineAt:old?.deadlineAt || null,
   targetName:target.device_name || 'PC', updatedAt:new Date().toISOString(), commandId:commandId, message:'Permintaan pembatalan menunggu PC.'};
  saveAdminShutdownStates(stateMap);
  updateShutdownTimerStatus();
  if (!commandId || typeof waitDeviceCommand !== 'function') {
   msg('Permintaan pembatalan sudah dikirim, tetapi ID perintah belum tersedia. Status belum dianggap selesai.', true);
   return;
  }
  const ack = await waitDeviceCommand(commandId, 15000);
  if (ack?.status === 'failed' || ack?.status === 'expired' || ack?.result?.ok === false) throw new Error(String(ack?.result?.message || ack?.result?.error || 'PC tidak mengonfirmasi pembatalan.'));
  if (ack?.status !== 'completed') {
   msg('Permintaan pembatalan masih menunggu konfirmasi PC. Timer belum ditandai selesai.', true);
   return;
  }
  const latest = readAdminShutdownStates();
  latest[String(target.id)] = {state:'canceled', scheduleId:old?.scheduleId || null, deadlineAt:old?.deadlineAt || null,
   targetName:target.device_name || 'PC', updatedAt:new Date().toISOString(), message:'Timer shutdown dibatalkan oleh Admin.'};
  saveAdminShutdownStates(latest);
  updateShutdownTimerStatus();
  msg('Timer shutdown berhasil dibatalkan oleh PC ' + target.device_name + '.');
 } catch (e) {
  msg('Pembatalan timer shutdown gagal: ' + (e?.message || e), true);
 }
}
if (!window.__aniShutdownTimerStatusInterval) {
 window.__aniShutdownTimerStatusInterval = window.setInterval(updateShutdownTimerStatus, 1000);
}
"""

load_anchor = "async function loadDevices(){"
if html.count(load_anchor) != 1:
    raise SystemExit("loadDevices anchor mismatch; refusing to patch.")
timer_nav_helper = r"""
function openShutdownTimerMenu() {
 try { if (typeof closeMobileNav === 'function') closeMobileNav(); } catch (_) {}
 tab('devices');
 document.querySelectorAll('.nav button').forEach(x => x.classList.remove('active'));
 const btn = $('shutdownTimerNav');
 if (btn) btn.classList.add('active');
 document.querySelectorAll('#mobileBottomNav button').forEach(x => x.classList.toggle('active', (x.dataset.tab === 'devices' || x.dataset.mobileTab === 'devices')));
 const card = $('pcShutdownTimerCard');
 if (card) card.scrollIntoView({behavior:'smooth', block:'center'});
}
"""
html = html.replace(load_anchor, timer_nav_helper + "\n" + helpers + "\n" + load_anchor, 1)

device_rows_anchor = "devicesCache=rows;"
if html.count(device_rows_anchor) != 1:
    raise SystemExit("devicesCache assignment anchor mismatch; refusing to patch.")
html = html.replace(device_rows_anchor, "devicesCache=rows;refreshShutdownTargetOptions(rows);", 1)

required = [
 "id=\"shutdownTargetDevice\"", "id=\"shutdownTimerNav\"", "function openShutdownTimerMenu()",
 "function previewPcShutdown()",
 "function schedulePcShutdown()",
 "function cancelPcShutdown()",
 "p_command: 'schedule_shutdown'", "p_command: 'cancel_shutdown_timer'",
 "p_payload: {scheduled:true",
 "p_payload: {cancelScheduled:true",
 "metadata.activeCode",
 "MATI VIA ADMIN",
 "OFFLINE DI LUAR PERINTAH ADMIN",
 "admin_shutdown_requested",
 "expectedDisconnect",
 "previous_admin_shutdown",
 "PRATINJAU SAJA"
]
for token in required:
    if token not in html:
        raise SystemExit("Shutdown timer regression check failed: missing " + token)

if "versionCode 40" not in gradle or "versionName '12.1.12'" not in gradle:
    raise SystemExit("Unexpected Android baseline; expected version 12.1.12 / code 40 before shutdown timer patch.")
gradle = gradle.replace("versionCode 40", "versionCode 41", 1).replace("versionName '12.1.12'", "versionName '12.1.28'", 1)

html_path.write_text(html, encoding="utf-8")
gradle_path.write_text(gradle, encoding="utf-8")
version_path.write_text("v12.1.28-admin-pc-shutdown-timer\n", encoding="utf-8")
print("Patched Admin PC selector, preview, confirmed schedule/cancel commands, countdown state, online/rental guards; version 12.1.28 / versionCode 41.")
