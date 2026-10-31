from pathlib import Path
import re

HTML = Path('android/app/src/main/assets/web/admin.html')
GRADLE = Path('android/app/build.gradle')
VERSION = Path('VERSION.txt')

if not HTML.is_file() or not GRADLE.is_file():
    raise SystemExit('Admin Android source root is missing.')
html = HTML.read_text(encoding='utf-8')
gradle = GRADLE.read_text(encoding='utf-8')
MARKER = 'V12.1.36-PC-WOL-RELAY'

if MARKER in html:
    if "versionCode 64" in gradle and "versionName '12.1.36'" in gradle:
        print('PASS: Admin V12.1.36 PC Wake-on-LAN relay patch already applied')
        raise SystemExit(0)
    raise SystemExit('V12.1.36 marker/version mismatch')

if "versionCode 63" not in gradle or "versionName '12.1.35'" not in gradle:
    raise SystemExit('Expected exact Admin V12.1.35 Gradle base; refusing unknown source.')
if 'V12.1.35-GLOBAL-RENTAL-DB-FIRST-NO-PC-RENTAL' not in html:
    raise SystemExit('Expected V12.1.35 global rental marker missing.')
if "function openShutdownTimerMenu()" not in html:
    raise SystemExit('Existing PC controls navigation anchor not found.')

nav_anchor = '<button data-tab="databaseTools"'
if html.count(nav_anchor) != 1:
    raise SystemExit('Admin navigation anchor mismatch.')
html = html.replace(
    nav_anchor,
    '<button id="wakeRelayNav" type="button" onclick="openWakeRelayMenu()">⚡ Nyalakan PC Kedua</button>' + nav_anchor,
    1,
)

section_anchor = '</section>\n\n<section id="pairing"'
if html.count(section_anchor) != 1:
    raise SystemExit('PC devices-section insertion anchor mismatch.')
card = r'''
<div class="card" id="wakeRelayCard" style="margin-top:12px;border:1px solid var(--a)">
 <div class="top"><div><h3 style="margin:0">⚡ Nyalakan PC Kedua • Wake-on-LAN</h3><div class="muted">PC1 menjadi relay sementara untuk mengirim Magic Packet ke PC2 yang sedang shutdown.</div></div><span id="wakeRelayBadge" class="pill">BELUM SIAP</span></div>
 <div class="cards2" style="margin-top:10px">
  <div class="field"><label for="wakeRelaySource">PC1 Relay (harus ONLINE)</label><select id="wakeRelaySource" onchange="saveWakeRelaySelection();updateWakeRelayStatus()" style="width:100%"><option value="">Memuat daftar PC…</option></select></div>
  <div class="field"><label for="wakeRelayTarget">PC2 Target</label><select id="wakeRelayTarget" onchange="saveWakeRelaySelection();loadWakeRelayMac();updateWakeRelayStatus()" style="width:100%"><option value="">Memuat daftar PC…</option></select></div>
 </div>
 <div class="field" style="margin-top:10px"><label for="wakeRelayMac">MAC Address LAN PC2</label><input id="wakeRelayMac" type="text" inputmode="text" autocomplete="off" autocapitalize="characters" spellcheck="false" maxlength="17" placeholder="Contoh: AA:BB:CC:DD:EE:FF" oninput="updateWakeRelayStatus()" onchange="saveWakeRelayMac()" style="width:100%"><div class="muted">Gunakan MAC kartu jaringan LAN PC2 yang terhubung ke router yang sama. MAC belum tersimpan otomatis dari data pairing.</div></div>
 <div id="wakeRelayStatus" class="msg" role="status" aria-live="polite" style="margin-top:10px">Pilih PC1 relay dan PC2 target.</div>
 <div class="row" style="margin-top:8px"><button id="wakeRelaySend" type="button" class="primary" onclick="requestWakePc2()" disabled>⚡ Kirim Perintah Nyalakan PC2</button><button type="button" onclick="refreshWakeRelayDevices()">Perbarui Status PC</button></div>
 <div class="muted" style="margin-top:8px">Pengaman: perintah hanya dikirim ketika PC1 online, PC2 sedang offline, dan MAC Address valid. Status MENYALA baru dikonfirmasi setelah PC2 mengirim heartbeat. PC2 harus mendukung Wake-on-LAN dari Shutdown, memakai LAN, serta BIOS/Windows sudah dikonfigurasi.</div>
</div>
'''
html = html.replace(section_anchor, card + '\n</section>\n\n<section id="pairing"', 1)

helpers_anchor = 'function openShutdownTimerMenu()'
if html.count(helpers_anchor) != 1:
    raise SystemExit('Wake relay helper insertion anchor mismatch.')
helpers = r'''// V12.1.36-PC-WOL-RELAY — separate addon; uses the existing paired-device command queue.
const WAKE_RELAY_SOURCE_KEY = 'ani_games_admin_wol_relay_source_v1';
const WAKE_RELAY_TARGET_KEY = 'ani_games_admin_wol_relay_target_v1';
const WAKE_RELAY_MAC_PREFIX = 'ani_games_admin_wol_mac_v1:';
let wakeRelayBusy = false;
let wakeRelayLastMessage = '';
function wakeRelayLabel(device) {
 return String(device?.device_name || device?.client_id || 'PC').slice(0, 100);
}
function wakeRelayStatusWord(device) {
 return device?.uiStatus === 'online' ? 'ONLINE' : 'OFFLINE';
}
function wakeRelayMacKey(deviceId) {
 return WAKE_RELAY_MAC_PREFIX + String(deviceId || '');
}
function normalizeWakeRelayMac(value) {
 const compact = String(value || '').trim().replace(/[:-]/g, '').toUpperCase();
 return /^[0-9A-F]{12}$/.test(compact) ? compact.match(/.{2}/g).join(':') : '';
}
function selectedWakeRelaySource() {
 const id = $('wakeRelaySource')?.value || '';
 return (devicesCache || []).find(d => String(d.id) === String(id)) || null;
}
function selectedWakeRelayTarget() {
 const id = $('wakeRelayTarget')?.value || '';
 return (devicesCache || []).find(d => String(d.id) === String(id)) || null;
}
function saveWakeRelaySelection() {
 try {
  if ($('wakeRelaySource')?.value) localStorage.setItem(WAKE_RELAY_SOURCE_KEY, $('wakeRelaySource').value);
  if ($('wakeRelayTarget')?.value) localStorage.setItem(WAKE_RELAY_TARGET_KEY, $('wakeRelayTarget').value);
 } catch (_) {}
}
function loadWakeRelayMac() {
 const target = selectedWakeRelayTarget();
 const input = $('wakeRelayMac');
 if (!input) return;
 try { input.value = target ? (localStorage.getItem(wakeRelayMacKey(target.id)) || '') : ''; }
 catch (_) { input.value = ''; }
}
function saveWakeRelayMac() {
 const target = selectedWakeRelayTarget();
 if (!target) return;
 const value = normalizeWakeRelayMac($('wakeRelayMac')?.value || '');
 if (value) {
  try { localStorage.setItem(wakeRelayMacKey(target.id), value); } catch (_) {}
  $('wakeRelayMac').value = value;
 } else {
  try { localStorage.removeItem(wakeRelayMacKey(target.id)); } catch (_) {}
 }
 updateWakeRelayStatus();
}
function refreshWakeRelayOptions(rows) {
 wakeRelayLastMessage = '';
 const sourceSelect = $('wakeRelaySource');
 const targetSelect = $('wakeRelayTarget');
 if (!sourceSelect || !targetSelect) return;
 const list = Array.isArray(rows) ? rows.filter(d => d && d.id) : [];
 let sourceId = sourceSelect.value;
 let targetId = targetSelect.value;
 try {
  sourceId = sourceId || localStorage.getItem(WAKE_RELAY_SOURCE_KEY) || '';
  targetId = targetId || localStorage.getItem(WAKE_RELAY_TARGET_KEY) || '';
 } catch (_) {}
 const byName = (pattern) => list.find(d => pattern.test(wakeRelayLabel(d)));
 const source = list.find(d => String(d.id) === String(sourceId)) || byName(/rtx\s*3060/i) || list.find(d => d.uiStatus === 'online');
 const target = list.find(d => String(d.id) === String(targetId)) || byName(/rtx\s*5060/i) || list.find(d => d.id !== source?.id);
 const optionHTML = (d) => '<option value="' + esc(d.id) + '">' + esc(wakeRelayLabel(d)) + ' • ' + wakeRelayStatusWord(d) + '</option>';
 sourceSelect.innerHTML = '<option value="">Pilih PC1 relay</option>' + list.map(optionHTML).join('');
 targetSelect.innerHTML = '<option value="">Pilih PC2 target</option>' + list.map(optionHTML).join('');
 sourceSelect.value = source?.id || '';
 targetSelect.value = target?.id || '';
 saveWakeRelaySelection();
 loadWakeRelayMac();
 updateWakeRelayStatus();
}
function updateWakeRelayStatus(message) {
 const badge = $('wakeRelayBadge');
 const status = $('wakeRelayStatus');
 const button = $('wakeRelaySend');
 if (!badge || !status || !button) return;
 const source = selectedWakeRelaySource();
 const target = selectedWakeRelayTarget();
 const mac = normalizeWakeRelayMac($('wakeRelayMac')?.value || '');
 const owner = ctx?.role === 'owner';
 let ready = false;
 let label = 'BELUM SIAP';
 let detail = 'Pilih PC1 relay dan PC2 target.';
 if (!owner) detail = 'Fitur menyalakan PC hanya tersedia untuk akun Master/Owner.';
 else if (!source || !target) detail = 'Pastikan kedua PC sudah ter-pairing dalam workspace yang sama.';
 else if (String(source.id) === String(target.id)) detail = 'PC1 relay dan PC2 target tidak boleh perangkat yang sama.';
 else if (source.uiStatus !== 'online') { label = 'PC1 OFFLINE'; detail = 'PC1 (' + wakeRelayLabel(source) + ') sedang OFFLINE. Nyalakan PC1 terlebih dahulu; perintah tidak bisa diteruskan saat PC1 mati.'; }
 else if (target.uiStatus === 'online') { label = 'PC2 SUDAH ONLINE'; detail = 'PC2 (' + wakeRelayLabel(target) + ') sudah ONLINE. Tidak perlu mengirim Magic Packet.'; }
 else if (!mac) { label = 'MAC DIPERLUKAN'; detail = 'PC1 ONLINE dan PC2 OFFLINE. Masukkan MAC Address LAN PC2 untuk melanjutkan.'; }
 else { ready = true; label = 'SIAP MENGIRIM'; detail = 'PC1 ONLINE • PC2 OFFLINE • MAC valid. Perintah akan kedaluwarsa otomatis bila tidak segera diambil PC1.'; }
 if (message) wakeRelayLastMessage = message;
 if (wakeRelayLastMessage) detail = wakeRelayLastMessage;
 badge.textContent = label;
 status.textContent = detail;
 button.disabled = !ready || wakeRelayBusy;
}
async function refreshWakeRelayDevices() {
 try {
  await loadDevices();
  refreshWakeRelayOptions(devicesCache || []);
 } catch (e) {
  updateWakeRelayStatus('Gagal memperbarui daftar perangkat: ' + String(e?.message || e).slice(0, 160));
 }
}
function openWakeRelayMenu() {
 if (ctx?.role !== 'owner') return msg('Fitur menyalakan PC hanya tersedia untuk Master/Owner.', true);
 tab('devices');
 setTimeout(() => $('wakeRelayCard')?.scrollIntoView({ behavior:'smooth', block:'start' }), 150);
}
async function requestWakePc2() {
 if (ctx?.role !== 'owner') return msg('Fitur menyalakan PC hanya tersedia untuk Master/Owner.', true);
 const source = selectedWakeRelaySource();
 const target = selectedWakeRelayTarget();
 const mac = normalizeWakeRelayMac($('wakeRelayMac')?.value || '');
 if (!currentOrg?.id) return msg('Workspace aktif belum dipilih.', true);
 if (!source || !target) return msg('Pilih PC1 relay dan PC2 target.', true);
 if (String(source.id) === String(target.id)) return msg('PC1 dan PC2 tidak boleh sama.', true);
 if (source.uiStatus !== 'online') return updateWakeRelayStatus('PC1 relay sedang OFFLINE. Tidak ada perintah yang dikirim.');
 if (target.uiStatus === 'online') return updateWakeRelayStatus('PC2 sudah ONLINE; perintah tidak dikirim.');
 if (!mac) return updateWakeRelayStatus('MAC Address PC2 belum valid. Tidak ada perintah yang dikirim.');
 if (!confirm('Kirim perintah menyalakan PC2?\n\nPC1 relay: ' + wakeRelayLabel(source) + ' (ONLINE)\nPC2 target: ' + wakeRelayLabel(target) + ' (OFFLINE)\nMAC LAN: ' + mac + '\n\nPC1 akan mengirim Magic Packet melalui jaringan lokal. PC2 hanya dianggap menyala setelah heartbeat terdeteksi.')) return;
 const requestAt = Date.now();
 const expiresAt = new Date(requestAt + 90000).toISOString();
 wakeRelayBusy = true;
 wakeRelayLastMessage = '';
 $('wakeRelaySend').disabled = true;
 updateWakeRelayStatus('Mengirim perintah ke PC1 relay…');
 try {
  const result = await rpc('admin_command', {
   p_org_id: currentOrg.id,
   p_device_id: source.id,
   p_command: 'wake',
   p_payload: {
    mode:'wake_on_lan_relay',
    relayDeviceId:String(source.id),
    targetDeviceId:String(target.id),
    targetDeviceName:wakeRelayLabel(target),
    targetMac:mac,
    expiresAt,
    source:'admin-apk-wol-relay-v12.1.36'
   }
  });
  if (result?.ok !== true) throw new Error(result?.message || 'Server tidak mengonfirmasi antrean perintah.');
  updateWakeRelayStatus('Perintah masuk antrean PC1. Menunggu PC1 mengirim Magic Packet dan PC2 melakukan boot…');
  const targetId = String(target.id);
  for (let attempt = 0; attempt < 12 && Date.now() < Date.parse(expiresAt) + 60000; attempt++) {
   await new Promise(resolve => setTimeout(resolve, 5000));
   await loadDevices();
   const updatedTarget = (devicesCache || []).find(d => String(d.id) === targetId);
   const updatedSource = (devicesCache || []).find(d => String(d.id) === String(source.id));
   if (updatedTarget?.uiStatus === 'online') {
    updateWakeRelayStatus('TERKONFIRMASI: PC2 (' + wakeRelayLabel(updatedTarget) + ') sudah ONLINE dan heartbeat terdeteksi.');
    msg('PC2 berhasil terdeteksi ONLINE.');
    return;
   }
   if (updatedSource?.uiStatus !== 'online') {
    updateWakeRelayStatus('PC1 relay terputus sebelum PC2 terkonfirmasi. PC2 belum terdeteksi ONLINE; periksa status dan coba lagi ketika PC1 menyala.');
    return;
   }
   updateWakeRelayStatus('Perintah sudah diterima PC1 atau masih diproses. PC2 belum mengirim heartbeat; memeriksa lagi…');
  }
  updateWakeRelayStatus('Magic Packet mungkin sudah dikirim, tetapi heartbeat PC2 belum terdeteksi. Periksa MAC LAN, kabel LAN, ErP/Wake-on-LAN BIOS, dan pengaturan NIC PC2. Status menyala belum terkonfirmasi.');
 } catch (e) {
  updateWakeRelayStatus('Gagal meminta PC1 menyalakan PC2: ' + String(e?.message || e).slice(0, 180));
 } finally {
  wakeRelayBusy = false;
  updateWakeRelayStatus(wakeRelayLastMessage);
 }
}

'''
html = html.replace(helpers_anchor, helpers + helpers_anchor, 1)

load_anchor = 'selectedDevice=rows.find(x=>x.id===selectedDeviceId)||null;refreshShutdownTargetOptions(rows);renderGlobalDeviceSelector(rows);'
if html.count(load_anchor) != 1:
    raise SystemExit('Expected V12.1.30 resolved-device initialization anchor exactly once.')
html = html.replace(load_anchor, load_anchor + 'refreshWakeRelayOptions(rows);', 1)

html = html.replace('V12.1.35-GLOBAL-RENTAL-DB-FIRST-NO-PC-RENTAL', 'V12.1.36-GLOBAL-RENTAL-DB-FIRST-NO-PC-RENTAL-WOL-RELAY', 1)
gradle = gradle.replace('versionCode 63', 'versionCode 64', 1)
gradle = gradle.replace("versionName '12.1.35'", "versionName '12.1.36'", 1)
if 'versionCode 64' not in gradle or "versionName '12.1.36'" not in gradle:
    raise SystemExit('Admin version update failed.')

for token in (
    MARKER, 'wakeRelayCard', 'wakeRelayNav', 'refreshWakeRelayOptions(rows)',
    "p_command: 'wake'", 'wake_on_lan_relay', 'relayDeviceId', 'targetDeviceId',
    'targetMac', 'expiresAt', 'PC1 OFFLINE', 'MAC DIPERLUKAN',
    'TERKONFIRMASI', 'loadDevices()', 'admin_command',
):
    if token not in html:
        raise SystemExit('Wake relay regression assertion missing: ' + token)
if html.count('id="wakeRelayCard"') != 1 or html.count('id="wakeRelayMac"') != 1:
    raise SystemExit('Wake relay UI IDs are missing or duplicated.')
ids = re.findall(r'\bid=["\']([^"\']+)', html)
duplicates = sorted({x for x in ids if ids.count(x) > 1})
if duplicates:
    raise SystemExit('Duplicate HTML IDs after WOL insertion: ' + ', '.join(duplicates))
if 'if(id===\'accounts\')loadGlobalRentalAccounts();' not in html:
    raise SystemExit('Global rental tab loader was unexpectedly altered.')

HTML.write_text(html, encoding='utf-8')
GRADLE.write_text(gradle, encoding='utf-8')
VERSION.write_text('AniGames Admin Android V12.1.36 — PC2 Wake-on-LAN relay via paired PC1; uses existing device command queue; rental, pairing and DB routing unchanged.\n', encoding='utf-8')
print('PASS: Admin V12.1.36 adds PC1 relay -> PC2 Wake-on-LAN controls, relay-online gating, MAC validation, 90-second command expiry, and heartbeat confirmation.')
print('PASS: UI IDs unique; global rental tab and existing DB/pairing controls preserved.')
