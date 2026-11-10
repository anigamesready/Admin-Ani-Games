from pathlib import Path
import re

HTML = Path('android/app/src/main/assets/web/admin.html')
GRADLE = Path('android/app/build.gradle')
VERSION = Path('VERSION.txt')
if not HTML.is_file() or not GRADLE.is_file():
    raise SystemExit('Admin Android source root is missing.')

html = HTML.read_text(encoding='utf-8')
gradle = GRADLE.read_text(encoding='utf-8')
MARKER = 'V12.1.47-ANDROID-WOL-RELAY'
if MARKER in html:
    if 'versionCode 75' in gradle and "versionName '12.1.47'" in gradle:
        print('PASS: Admin Android WoL Relay patch already applied.')
        raise SystemExit(0)
    raise SystemExit('V12.1.47 marker/version mismatch.')

if 'versionCode 74' not in gradle or "versionName '12.1.46'" not in gradle:
    raise SystemExit('Expected exact Admin V12.1.46 source; refusing unknown baseline.')
if 'id="wakeRelayCard"' not in html or 'function requestWakePc2()' not in html:
    raise SystemExit('Existing Admin PC WoL section is missing; refusing unsafe patch.')
if "rpc('report_detailed_usage_page'" not in html or "rpc('report_summary_compact'" not in html:
    raise SystemExit('Monthly/yearly report regression guard failed before patch.')

def replace_div_block(source, opening):
    start = source.find(opening)
    if start < 0:
        raise SystemExit('Wake relay card opening anchor not found.')
    token_re = re.compile(r'<div\b[^>]*>|</div>', re.I)
    depth = 0
    for match in token_re.finditer(source, start):
        token = match.group(0).lower()
        if token.startswith('<div'):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return source[:start] + new_card + source[match.end():]
    raise SystemExit('Wake relay card div structure is unbalanced.')

new_card = r'''
<div class="card" id="wakeRelayCard" style="margin-top:12px;border:1px solid var(--a)">
 <div class="top">
  <div><h3 style="margin:0">⚡ Ani WoL Relay Android</h3><div class="muted">Gunakan Redmi 6 Pro sebagai gateway untuk menyalakan PC melalui jaringan lokal.</div></div>
  <span id="wakeRelayBadge" class="pill">RELAY OFFLINE</span>
 </div>
 <div id="wakeRelaySourceInfo" class="muted" style="margin-top:8px">Memeriksa status HP relay…</div>
 <div class="field" style="margin-top:10px">
  <label for="wakeRelayTarget">PC yang mau dinyalakan</label>
  <select id="wakeRelayTarget" onchange="saveWakeRelaySelection();updateWakeRelayStatus()" style="width:100%">
   <option value="">Memuat daftar PC…</option>
  </select>
 </div>
 <div id="wakeRelayStatus" class="msg" role="status" aria-live="polite" style="margin-top:10px">Pilih PC target.</div>
 <div class="row" style="margin-top:8px;flex-wrap:wrap">
  <button id="wakeRelayPair" type="button" onclick="createWakeRelayPairingCode()">Buat kode pairing HP</button>
  <button id="wakeRelaySend" type="button" class="primary" onclick="requestWakePc2()" disabled>⚡ Nyalakan PC</button>
  <button type="button" onclick="refreshWakeRelayDevices()">Refresh status</button>
 </div>
 <div id="wakeRelayPairingBox" class="card" style="display:none;margin-top:10px">
  <div class="muted">Masukkan kode ini ke aplikasi Ani WoL Relay di Redmi 6 Pro. Kode hanya berlaku 10 menit dan hanya bisa dipakai sekali.</div>
  <div id="wakeRelayPairingCode" style="font-size:24px;font-weight:700;letter-spacing:3px;margin:10px 0"></div>
  <div id="wakeRelayPairingExpiry" class="muted"></div>
 </div>
 <div class="muted" style="margin-top:8px">MAC LAN dibaca dari heartbeat PC Billing V12.3.8 atau lebih baru. PC baru dianggap ONLINE setelah heartbeat terdeteksi, bukan hanya karena Magic Packet terkirim.</div>
</div>
'''
html = replace_div_block(html, '<div class="card" id="wakeRelayCard"')

# Keep the navigation entry but give it a precise label.
html = html.replace('⚡ Nyalakan PC Kedua', '⚡ WoL Android Relay', 1)

# Override the legacy PC-to-PC relay helpers with the Android relay flow.
anchor = 'function openShutdownTimerMenu()'
if anchor not in html:
    raise SystemExit('Admin PC control function insertion anchor missing.')

new_helpers = r'''
// V12.1.47-ANDROID-WOL-RELAY — separate relay identity; never masquerades as a billing PC.
let aniAndroidWakeRelay = null;
let aniAndroidWakeRelayBusy = false;

function openWakeRelayMenu() {
 const nav = document.querySelector('[data-tab="devices"]');
 if (nav) nav.click();
 setTimeout(() => {
  const card = $('wakeRelayCard');
  if (card) card.scrollIntoView({behavior:'smooth', block:'start'});
  refreshWakeRelayDevices();
 }, 120);
}

function refreshWakeRelayOptions(rows) {
 const select = $('wakeRelayTarget');
 if (!select) return;
 const list = Array.isArray(rows) ? rows.filter(d => d && d.id && !d.metadata?.pairingDuplicateArchivedAt) : [];
 let saved = select.value || '';
 try { saved = saved || localStorage.getItem(WAKE_RELAY_TARGET_KEY) || ''; } catch (_) {}
 const preferred = list.find(d => String(d.id) === String(saved))
  || list.find(d => d.uiStatus !== 'online')
  || list[0] || null;
 select.innerHTML = '<option value="">Pilih PC target</option>' + list.map(d =>
  '<option value="' + esc(d.id) + '">' + esc(wakeRelayLabel(d)) + ' • ' + wakeRelayStatusWord(d) + '</option>'
 ).join('');
 select.value = preferred?.id || '';
 saveWakeRelaySelection();
 updateWakeRelayStatus();
 loadWakeRelayStatus();
}

function selectedWakeRelayTarget() {
 const id = $('wakeRelayTarget')?.value || '';
 return (devicesCache || []).find(d => String(d.id) === String(id)) || null;
}

function saveWakeRelaySelection() {
 try {
  if ($('wakeRelayTarget')?.value) localStorage.setItem(WAKE_RELAY_TARGET_KEY, $('wakeRelayTarget').value);
 } catch (_) {}
}

async function loadWakeRelayStatus() {
 const info = $('wakeRelaySourceInfo');
 try {
  const result = await rpc('wol_relay_status', {});
  const rows = Array.isArray(result?.relays) ? result.relays : [];
  aniAndroidWakeRelay = rows.find(r => r.status === 'online') || rows[0] || null;
  if (info) {
   if (!aniAndroidWakeRelay) info.textContent = 'Belum ada HP relay terdaftar. Buat kode pairing lalu masukkan ke aplikasi Redmi 6 Pro.';
   else {
    const r = aniAndroidWakeRelay;
    const temp = Number.isFinite(Number(r.battery_temp_c)) ? Number(r.battery_temp_c).toFixed(1) + '°C' : 'suhu belum tersedia';
    const battery = Number.isFinite(Number(r.battery_percent)) && Number(r.battery_percent) >= 0 ? Number(r.battery_percent) + '%' : 'baterai belum tersedia';
    info.textContent = 'HP: ' + String(r.relay_name || 'Android Relay') + ' • ' + String(r.status || 'offline').toUpperCase()
      + ' • baterai ' + battery + ' • suhu ' + temp + ' • ' + String(r.app_version || 'versi tidak diketahui');
   }
  }
 } catch (e) {
  aniAndroidWakeRelay = null;
  if (info) info.textContent = 'Status HP relay tidak dapat dibaca: ' + String(e?.message || e).slice(0,120);
 }
 updateWakeRelayStatus();
 return aniAndroidWakeRelay;
}

function updateWakeRelayStatus(message) {
 const badge = $('wakeRelayBadge');
 const status = $('wakeRelayStatus');
 const button = $('wakeRelaySend');
 if (!badge || !status || !button) return;
 const target = selectedWakeRelayTarget();
 const relayOnline = aniAndroidWakeRelay?.status === 'online';
 const owner = ctx?.role === 'owner';
 let label = 'BELUM SIAP';
 let detail = 'Pilih PC target.';
 let ready = false;
 if (!owner) detail = 'Fitur WoL Android hanya tersedia untuk Master/Owner.';
 else if (!aniAndroidWakeRelay) { label = 'RELAY BELUM TERDAFTAR'; detail = 'Buat kode pairing HP dan hubungkan aplikasi Ani WoL Relay.'; }
 else if (!relayOnline) { label = 'RELAY OFFLINE'; detail = 'HP relay belum mengirim heartbeat. Periksa daya, Wi-Fi, dan aplikasi relay.'; }
 else if (!target) detail = 'Pilih PC target yang sudah ter-pairing.';
 else if (target.uiStatus === 'online') { label = 'PC SUDAH ONLINE'; detail = wakeRelayLabel(target) + ' sudah ONLINE; Magic Packet tidak dikirim.'; }
 else if (!normalizeWakeRelayMac(target.metadata?.wolLanMac)) { label = 'MAC BELUM TERSEDIA'; detail = 'MAC LAN belum dilaporkan. Nyalakan PC sekali dengan Billing V12.3.8 atau lebih baru.'; }
 else { label = 'SIAP MENGIRIM'; detail = 'HP relay ONLINE • target OFFLINE • MAC LAN terdeteksi. Tekan Nyalakan PC.'; ready = true; }
 if (message) detail = message;
 badge.textContent = label;
 status.textContent = detail;
 button.disabled = !ready || aniAndroidWakeRelayBusy;
}

async function createWakeRelayPairingCode() {
 if (ctx?.role !== 'owner') return msg('Pairing WoL hanya tersedia untuk Master/Owner.', true);
 const button = $('wakeRelayPair');
 if (button) button.disabled = true;
 try {
  const result = await rpc('wol_relay_create_enrollment', {});
  if (result?.ok === false || !result?.code) throw new Error(result?.message || 'Server tidak mengembalikan kode pairing.');
  $('wakeRelayPairingCode').textContent = String(result.code);
  $('wakeRelayPairingExpiry').textContent = 'Berlaku sampai ' + new Date(result.expires_at).toLocaleString();
  $('wakeRelayPairingBox').style.display = 'block';
  msg('Kode pairing Ani WoL Relay berhasil dibuat.');
 } catch (e) {
  msg('Gagal membuat kode pairing: ' + String(e?.message || e).slice(0,160), true);
 } finally {
  if (button) button.disabled = false;
 }
}

async function refreshWakeRelayDevices() {
 try { await loadDevices(); } catch (_) {}
 await loadWakeRelayStatus();
 updateWakeRelayStatus();
}

async function requestWakePc2() {
 if (ctx?.role !== 'owner') return msg('Fitur menyalakan PC hanya tersedia untuk Master/Owner.', true);
 const target = selectedWakeRelayTarget();
 if (!target) return updateWakeRelayStatus('Pilih PC target terlebih dahulu.');
 if (target.uiStatus === 'online') return updateWakeRelayStatus('PC target sudah ONLINE; perintah tidak dikirim.');
 if (!normalizeWakeRelayMac(target.metadata?.wolLanMac)) return updateWakeRelayStatus('MAC LAN PC target belum tersedia. Nyalakan PC sekali dengan Billing V12.3.8 atau lebih baru.');
 await loadWakeRelayStatus();
 if (aniAndroidWakeRelay?.status !== 'online') return updateWakeRelayStatus('HP relay OFFLINE. Tidak ada perintah yang dikirim.');
 if (!confirm('Kirim perintah Wake-on-LAN ke ' + wakeRelayLabel(target) + '?\\n\\nHP Android relay: ONLINE\\nPC target: OFFLINE\\nMAC LAN divalidasi ulang oleh database.\\n\\nPC hanya dianggap menyala setelah heartbeat Billing terdeteksi.')) return;

 aniAndroidWakeRelayBusy = true;
 const button = $('wakeRelaySend');
 if (button) button.disabled = true;
 updateWakeRelayStatus('Memasukkan perintah ke antrean relay Android…');
 try {
  const queued = await rpc('wol_relay_enqueue', {p_target_device_id: target.id});
  if (queued?.ok === false) throw new Error(queued?.message || 'Server menolak perintah WoL.');
  const commandId = queued?.command_id || queued?.id;
  if (!commandId) throw new Error('Server tidak mengembalikan ID perintah.');
  const targetId = String(target.id);
  let packetSent = false;
  for (let attempt = 0; attempt < 18; attempt++) {
   await new Promise(resolve => setTimeout(resolve, 5000));
   const state = await rpc('wol_relay_command_status', {p_command_id: commandId});
   if (state?.status === 'failed' || state?.status === 'expired') {
    updateWakeRelayStatus('Relay gagal mengirim Magic Packet: ' + String(state?.result?.message || state?.result?.error || state.status));
    return;
   }
   if (state?.status === 'packet_sent') packetSent = true;
   await loadDevices();
   const updated = (devicesCache || []).find(d => String(d.id) === targetId);
   if (updated?.uiStatus === 'online') {
    updateWakeRelayStatus('TERKONFIRMASI: ' + wakeRelayLabel(updated) + ' sudah ONLINE dan heartbeat Billing terdeteksi.');
    msg('PC berhasil dinyalakan dan terdeteksi ONLINE.');
    return;
   }
   updateWakeRelayStatus(packetSent
    ? 'Magic Packet sudah dikirim oleh HP. Menunggu PC boot dan mengirim heartbeat…'
    : 'Perintah menunggu diproses HP relay. Memeriksa status kembali…');
  }
  updateWakeRelayStatus('Magic Packet belum terkonfirmasi sebagai PC ONLINE. Periksa kabel LAN, BIOS WoL, ErP, dan pengaturan NIC target.');
 } catch (e) {
  updateWakeRelayStatus('Gagal meminta HP relay menyalakan PC: ' + String(e?.message || e).slice(0,180));
 } finally {
  aniAndroidWakeRelayBusy = false;
  updateWakeRelayStatus();
 }
}

'''
html = html.replace(anchor, new_helpers + '\n' + anchor, 1)

# Version and package metadata.
gradle, code_count = re.subn(r'\bversionCode\s+74\b', 'versionCode 75', gradle, count=1)
gradle, name_count = re.subn(r"versionName\s*'12\.1\.46'", "versionName '12.1.47'", gradle, count=1)
if code_count != 1 or name_count != 1:
    raise SystemExit('Admin versionCode/versionName update anchor mismatch.')

html += '\n<!-- ' + MARKER + ' -->\n'
if 'id="wakeRelaySource"' in html or 'id="wakeRelayMac"' in html:
    raise SystemExit('Legacy PC relay or manual MAC selector remains in Admin UI.')
for required in (MARKER, 'wol_relay_create_enrollment', 'wol_relay_status', 'wol_relay_enqueue', 'wol_relay_command_status', 'ANI-WOL-RELAY'):
    if required not in html:
        raise SystemExit('Android relay integration assertion missing: ' + required)
if html.count('id="wakeRelayCard"') != 1 or html.count('id="wakeRelayTarget"') != 1:
    raise SystemExit('Wake relay UI IDs missing or duplicated.')
ids = re.findall(r'\bid=["\']([^"\']+)', html)
duplicates = sorted({x for x in ids if ids.count(x) > 1})
if duplicates:
    raise SystemExit('Duplicate HTML IDs after Android relay patch: ' + ', '.join(duplicates))

# Preserve existing reports, billing controls, pairing and global DB routing.
for required in ("rpc('report_detailed_usage_page'", "rpc('report_summary_compact'", "ensureActiveDbRouteForAuth", "V12.1.36-PC-WOL-RELAY"):
    if required not in html:
        raise SystemExit('Existing Admin feature regression: ' + required)

HTML.write_text(html, encoding='utf-8')
GRADLE.write_text(gradle, encoding='utf-8')
VERSION.write_text(
    'AniGames Admin Android V12.1.47 — Android WoL Relay Gateway integration. Existing rental, pairing, PC billing controls, reports, reseller and DB1/DB2 routing preserved.\n',
    encoding='utf-8'
)
print('PASS: Android relay pairing, status, target-only WoL and command confirmation integrated.')
print('PASS: manual MAC and PC1-as-relay selection removed from the active Admin UI.')
print('PASS: existing reports, rental, pairing, billing controls and DB routing preserved.')
print('PASS: unique HTML IDs; Admin V12.1.47 / versionCode 75.')
