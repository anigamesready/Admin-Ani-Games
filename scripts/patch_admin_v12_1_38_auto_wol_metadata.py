from pathlib import Path
import re

HTML = Path('android/app/src/main/assets/web/admin.html')
GRADLE = Path('android/app/build.gradle')
VERSION = Path('VERSION.txt')
if not HTML.is_file() or not GRADLE.is_file():
    raise SystemExit('Admin Android source root is missing.')
html = HTML.read_text(encoding='utf-8')
gradle = GRADLE.read_text(encoding='utf-8')
OLD_MARKER = 'V12.1.37-DAILY-REPORT-KEYSET-EXPORT'
MARKER = 'V12.1.38-AUTO-WOL-METADATA'

if MARKER in html:
    if "versionCode 66" in gradle and "versionName '12.1.38'" in gradle:
        print('PASS: Admin V12.1.38 automatic WoL metadata patch already applied')
        raise SystemExit(0)
    raise SystemExit('V12.1.38 marker/version mismatch.')
if OLD_MARKER not in html or "versionCode 65" not in gradle or "versionName '12.1.37'" not in gradle:
    raise SystemExit('Expected exact Admin V12.1.37 base; refusing unknown source.')
if 'wake_on_lan_relay' not in html or "p_command: 'wake'" not in html:
    raise SystemExit('Existing PC1 Wake-on-LAN relay command path is missing.')

mac_prefix = "const WAKE_RELAY_MAC_PREFIX = 'ani_games_admin_wol_mac_v1:';\n"
if html.count(mac_prefix) != 1:
    raise SystemExit('Manual MAC localStorage constant anchor mismatch.')
html = html.replace(mac_prefix, '', 1)

old_ui = '<div class="field" style="margin-top:10px"><label for="wakeRelayMac">MAC Address LAN PC2</label><input id="wakeRelayMac" type="text" inputmode="text" autocomplete="off" autocapitalize="characters" spellcheck="false" maxlength="17" placeholder="Contoh: AA:BB:CC:DD:EE:FF" oninput="updateWakeRelayStatus()" onchange="saveWakeRelayMac()" style="width:100%"><div class="muted">Gunakan MAC kartu jaringan LAN PC2 yang terhubung ke router yang sama. MAC belum tersimpan otomatis dari data pairing.</div></div>'
new_ui = '<div id="wakeRelayMacStatus" class="muted" style="margin-top:10px;padding:10px;border:1px solid var(--line);border-radius:10px">MAC LAN PC2: menunggu data otomatis dari heartbeat perangkat.</div>'
if html.count(old_ui) != 1:
    raise SystemExit(f'Manual MAC input UI anchor mismatch: found {html.count(old_ui)}')
html = html.replace(old_ui, new_ui, 1)

start = html.find('function wakeRelayMacKey(deviceId) {')
end = html.find('function refreshWakeRelayOptions(rows) {', start)
if start < 0 or end < 0:
    raise SystemExit('Manual MAC helper block boundaries not found.')
new_helpers = r'''function normalizeWakeRelayMac(value) {
 const compact = String(value || '').trim().replace(/[:-]/g, '').toUpperCase();
 return /^[0-9A-F]{12}$/.test(compact) && compact !== '000000000000' && compact !== 'FFFFFFFFFFFF'
  ? compact.match(/.{2}/g).join(':') : '';
}
function wakeRelayMacFor(device) {
 return normalizeWakeRelayMac(device?.metadata?.wolLanMac || '');
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
 const status = $('wakeRelayMacStatus');
 if (!status) return;
 const mac = wakeRelayMacFor(target);
 status.textContent = mac
  ? 'MAC LAN PC2 terdeteksi otomatis: ' + mac + (target?.metadata?.wolLanAdapter ? ' • ' + String(target.metadata.wolLanAdapter).slice(0, 70) : '')
  : 'MAC LAN PC2 belum tersedia. Nyalakan PC2 dengan Billing V12.3.8 sekali dan tunggu heartbeat agar alamat LAN tersimpan otomatis.';
}
'''
html = html[:start] + new_helpers + html[end:]

start = html.find('function updateWakeRelayStatus(message) {')
end = html.find('async function refreshWakeRelayDevices() {', start)
if start < 0 or end < 0:
    raise SystemExit('Wake relay status function boundaries not found.')
new_status = r'''function updateWakeRelayStatus(message) {
 const badge = $('wakeRelayBadge');
 const status = $('wakeRelayStatus');
 const button = $('wakeRelaySend');
 if (!badge || !status || !button) return;
 const source = selectedWakeRelaySource();
 const target = selectedWakeRelayTarget();
 const mac = wakeRelayMacFor(target);
 const owner = ctx?.role === 'owner';
 let ready = false;
 let label = 'BELUM SIAP';
 let detail = 'Pilih PC1 relay dan PC2 target.';
 if (!owner) detail = 'Fitur menyalakan PC hanya tersedia untuk akun Master/Owner.';
 else if (!source || !target) detail = 'Pastikan kedua PC sudah ter-pairing dalam workspace yang sama.';
 else if (String(source.id) === String(target.id)) detail = 'PC1 relay dan PC2 target tidak boleh perangkat yang sama.';
 else if (source.uiStatus !== 'online') { label = 'PC1 OFFLINE'; detail = 'PC1 (' + wakeRelayLabel(source) + ') sedang OFFLINE. Nyalakan PC1 terlebih dahulu; perintah tidak bisa diteruskan saat PC1 mati.'; }
 else if (target.uiStatus === 'online') { label = 'PC2 SUDAH ONLINE'; detail = 'PC2 (' + wakeRelayLabel(target) + ') sudah ONLINE. Tidak perlu mengirim Magic Packet.'; }
 else if (!mac) { label = 'MAC BELUM TERDAFTAR'; detail = 'MAC LAN PC2 belum dikirim oleh heartbeat. Nyalakan PC2 sekali dengan Billing V12.3.8, lalu muat ulang daftar perangkat.'; }
 else { ready = true; label = 'SIAP MENGIRIM'; detail = 'PC1 ONLINE • PC2 OFFLINE • MAC LAN terdeteksi otomatis. Tekan Nyalakan untuk mengirim Magic Packet.'; }
 if (message) wakeRelayLastMessage = message;
 if (wakeRelayLastMessage) detail = wakeRelayLastMessage;
 badge.textContent = label;
 status.textContent = detail;
 button.disabled = !ready || wakeRelayBusy;
 loadWakeRelayMac();
}
'''
html = html[:start] + new_status + html[end:]

start = html.find('async function requestWakePc2() {')
end = html.find('function openShutdownTimerMenu() {', start)
if start < 0 or end < 0:
    raise SystemExit('Wake relay request function boundaries not found.')
new_request = r'''async function requestWakePc2() {
 if (ctx?.role !== 'owner') return msg('Fitur menyalakan PC hanya tersedia untuk akun Master/Owner.', true);
 const source = selectedWakeRelaySource();
 const target = selectedWakeRelayTarget();
 const mac = wakeRelayMacFor(target);
 if (!currentOrg?.id) return msg('Workspace aktif belum dipilih.', true);
 if (!source || !target) return msg('Pilih PC1 relay dan PC2 target.', true);
 if (String(source.id) === String(target.id)) return msg('PC1 dan PC2 tidak boleh sama.', true);
 if (source.uiStatus !== 'online') return updateWakeRelayStatus('PC1 relay sedang OFFLINE. Tidak ada perintah yang dikirim.');
 if (target.uiStatus === 'online') return updateWakeRelayStatus('PC2 sudah ONLINE; perintah tidak dikirim.');
 if (!mac) return updateWakeRelayStatus('MAC LAN PC2 belum terdaftar otomatis. Pastikan PC2 pernah menyala dengan Billing V12.3.8.');
 if (!confirm('Kirim perintah menyalakan PC2?\n\nPC1 relay: ' + wakeRelayLabel(source) + ' (ONLINE)\nPC2 target: ' + wakeRelayLabel(target) + ' (OFFLINE)\nMAC LAN: ' + mac + ' (terdeteksi otomatis)\n\nBackend memvalidasi MAC dari data pairing PC2. PC1 mengirim Magic Packet melalui jaringan lokal. PC2 hanya dianggap menyala setelah heartbeat terdeteksi.')) return;
 const expiresAt = new Date(Date.now() + 90000).toISOString();
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
    expiresAt,
    source:'admin-apk-wol-auto-metadata-v12.1.38'
   }
  });
  if (result?.ok === false) throw new Error(result?.message || 'Server menolak antrean perintah.');
  const commandId = typeof result === 'string' ? result : (result?.command_id || result?.id || null);
  if (!commandId) throw new Error('Server tidak mengembalikan ID antrean. Perintah tidak dianggap terkirim; periksa respons server.');
  updateWakeRelayStatus('Perintah masuk antrean PC1. Menunggu PC1 mengirim Magic Packet dan PC2 melakukan boot…');
  const targetId = String(target.id);
  let packetConfirmed = false;
  for (let attempt = 0; attempt < 12 && Date.now() < Date.parse(expiresAt) + 60000; attempt++) {
   await new Promise(resolve => setTimeout(resolve, 5000));
   const commandState = await waitDeviceCommand(commandId, 2500);
   if (commandState?.status === 'failed' || commandState?.status === 'expired') {
    const reason = commandState?.result?.message || commandState?.result?.error || commandState?.status;
    updateWakeRelayStatus('PC1 gagal memproses perintah Wake-on-LAN: ' + String(reason).slice(0, 150));
    return;
   }
   if (commandState?.status === 'completed') packetConfirmed = true;
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
   updateWakeRelayStatus(packetConfirmed
    ? 'PC1 mengonfirmasi Magic Packet terkirim. Menunggu PC2 boot dan mengirim heartbeat…'
    : 'Perintah masih menunggu PC1. PC2 belum mengirim heartbeat; memeriksa lagi…');
  }
  updateWakeRelayStatus('Magic Packet mungkin sudah dikirim, tetapi heartbeat PC2 belum terdeteksi. Periksa koneksi LAN, WoL BIOS, dan pengaturan NIC PC2. Status menyala belum terkonfirmasi.');
 } catch (e) {
  updateWakeRelayStatus('Gagal meminta PC1 menyalakan PC2: ' + String(e?.message || e).slice(0, 180));
 } finally {
  wakeRelayBusy = false;
  updateWakeRelayStatus(wakeRelayLastMessage);
 }
}

'''
html = html[:start] + new_request + html[end:]

anchor = '// V12.1.36-PC-WOL-RELAY — separate addon; uses the existing paired-device command queue.'
if html.count(anchor) != 1:
    raise SystemExit('Admin WoL helper marker anchor mismatch.')
html = html.replace(anchor, anchor + '\n// ' + MARKER, 1)
gradle, code_count = re.subn(r'\bversionCode\s+65\b', 'versionCode 66', gradle, count=1)
gradle, name_count = re.subn(r"versionName\s*'12\.1\.37'", "versionName '12.1.38'", gradle, count=1)
if code_count != 1 or name_count != 1:
    raise SystemExit('Admin versionCode/versionName update anchor mismatch.')

for forbidden in ('id="wakeRelayMac"', 'function saveWakeRelayMac()', 'WAKE_RELAY_MAC_PREFIX', 'localStorage.getItem(wakeRelayMacKey', 'targetMac:mac'):
    if forbidden in html:
        raise SystemExit('Manual MAC implementation still present: ' + forbidden)
for required in (MARKER, 'wakeRelayMacStatus', 'metadata?.wolLanMac', 'function wakeRelayMacFor(device)', "p_command: 'wake'", 'targetDeviceId', 'wake_on_lan_relay', 'PC1 OFFLINE', 'TERKONFIRMASI', 'V12.3.8'):
    if required not in html:
        raise SystemExit('Automatic MAC WoL assertion missing: ' + required)
if html.count('id="wakeRelayMacStatus"') != 1 or html.count('id="wakeRelayCard"') != 1:
    raise SystemExit('Wake relay UI IDs missing or duplicated.')
ids = re.findall(r'\bid=["\']([^"\']+)', html)
duplicates = sorted({x for x in ids if ids.count(x) > 1})
if duplicates:
    raise SystemExit('Duplicate HTML IDs after automatic WoL patch: ' + ', '.join(duplicates))
if 'if(id===\'accounts\')loadGlobalRentalAccounts();' not in html:
    raise SystemExit('Global rental tab loader regression detected.')
if OLD_MARKER not in html or 'rpc(\'report_detailed_usage_page\'' not in html:
    raise SystemExit('Daily report V12.1.37 features were not preserved.')

HTML.write_text(html, encoding='utf-8')
GRADLE.write_text(gradle, encoding='utf-8')
VERSION.write_text(
    'AniGames Admin Android V12.1.38 — one-tap Wake-on-LAN target selection; MAC LAN is read automatically from paired device heartbeat metadata and resolved again server-side. Existing login, pairing, billing controls, reports, rental and DB routing preserved.\n',
    encoding='utf-8'
)
print('PASS: Admin V12.1.38 removes manual MAC entry and reads wolLanMac from selected target metadata.')
print('PASS: wake command sends relay/target IDs only; backend must resolve target MAC securely.')
print('PASS: existing command polling, expiry, heartbeat confirmation, reports, global rentals and DB routing retained.')
print('PASS: no duplicate HTML IDs; Android version bumped to 12.1.38 / code 66.')
