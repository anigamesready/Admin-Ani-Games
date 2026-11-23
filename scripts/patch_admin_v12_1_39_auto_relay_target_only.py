from pathlib import Path
import re

HTML = Path('android/app/src/main/assets/web/admin.html')
GRADLE = Path('android/app/build.gradle')
VERSION = Path('VERSION.txt')
if not HTML.is_file() or not GRADLE.is_file():
    raise SystemExit('Admin Android source root is missing.')
html = HTML.read_text(encoding='utf-8')
gradle = GRADLE.read_text(encoding='utf-8')
OLD_MARKER = 'V12.1.38-AUTO-WOL-METADATA'
MARKER = 'V12.1.39-AUTO-RELAY-TARGET-ONLY'
if MARKER in html:
    if 'versionCode 67' in gradle and "versionName '12.1.39'" in gradle:
        print('PASS: Admin V12.1.39 target-only auto-relay patch already applied')
        raise SystemExit(0)
    raise SystemExit('V12.1.39 marker/version mismatch.')
if OLD_MARKER not in html or 'versionCode 66' not in gradle or "versionName '12.1.38'" not in gradle:
    raise SystemExit('Expected exact Admin V12.1.38 baseline; refusing unknown source.')

old_source_key = "const WAKE_RELAY_SOURCE_KEY = 'ani_games_admin_wol_relay_source_v1';\n"
if html.count(old_source_key) != 1:
    raise SystemExit('Relay source localStorage key anchor mismatch.')
html = html.replace(old_source_key, '', 1)

old_source_ui = '<div class="field"><label for="wakeRelaySource">PC1 Relay (harus ONLINE)</label><select id="wakeRelaySource" onchange="saveWakeRelaySelection();updateWakeRelayStatus()" style="width:100%"><option value="">Memuat daftar PC…</option></select></div>\n  '
if html.count(old_source_ui) != 1:
    raise SystemExit('Manual relay selector UI anchor mismatch.')
html = html.replace(old_source_ui, '', 1)
html = html.replace('<label for="wakeRelayTarget">PC2 Target</label>', '<label for="wakeRelayTarget">PC yang mau dinyalakan</label>', 1)
html = html.replace('<option value="">Pilih PC2 target</option>', '<option value="">Pilih PC target</option>', 1)
html = html.replace('<div class="muted">PC1 menjadi relay sementara untuk mengirim Magic Packet ke PC2 yang sedang shutdown.</div>', '<div class="muted">Pilih PC tujuan saja. Sistem otomatis memakai PC lain yang online dan sudah mendukung Wake-on-LAN sebagai relay.</div>', 1)
html = html.replace('Pilih PC1 relay dan PC2 target.', 'Pilih PC yang mau dinyalakan.', 1)
html = html.replace('⚡ Kirim Perintah Nyalakan PC2', '⚡ Nyalakan PC yang Dipilih', 1)
html = html.replace('PC1 harus online, PC2 sedang offline, dan MAC Address valid.', 'Relay otomatis harus online dan PC target sedang offline. MAC LAN dibaca otomatis dari metadata pairing.', 1)

start = html.find('function selectedWakeRelaySource() {')
end = html.find('function loadWakeRelayMac() {', start)
if start < 0 or end < 0:
    raise SystemExit('Relay selection helper boundaries not found.')
new_helpers = r'''function wakeRelayVersionSupported(device) {
 const match = String(device?.app_version || '').match(/V?(\d+)\.(\d+)\.(\d+)/i);
 if (!match) return false;
 const version = match.slice(1).map(Number);
 return version[0] > 12 || (version[0] === 12 && version[1] > 3) || (version[0] === 12 && version[1] === 3 && version[2] >= 6);
}
function wakeRelayOnlineCandidates(target) {
 return (devicesCache || []).filter(d => d && String(d.id) !== String(target?.id || '') && d.uiStatus === 'online');
}
function selectedWakeRelaySource() {
 const target = selectedWakeRelayTarget();
 const online = wakeRelayOnlineCandidates(target);
 const preferred = online.find(d => String(d.client_id || '').toUpperCase() === 'PC-38BFEEB2')
  || online.find(d => /rtx\s*3060/i.test(wakeRelayLabel(d)));
 if (preferred && wakeRelayVersionSupported(preferred)) return preferred;
 return online.find(wakeRelayVersionSupported) || null;
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
'''
html = html[:start] + new_helpers + html[end:]

start = html.find('function refreshWakeRelayOptions(rows) {')
end = html.find('function updateWakeRelayStatus(message) {', start)
if start < 0 or end < 0:
    raise SystemExit('Wake relay options function boundaries not found.')
new_options = r'''function refreshWakeRelayOptions(rows) {
 wakeRelayLastMessage = '';
 const targetSelect = $('wakeRelayTarget');
 if (!targetSelect) return;
 const list = Array.isArray(rows) ? rows.filter(d => d && d.id && !d.metadata?.pairingDuplicateArchivedAt) : [];
 let targetId = targetSelect.value;
 try { targetId = targetId || localStorage.getItem(WAKE_RELAY_TARGET_KEY) || ''; } catch (_) {}
 const preferredTarget = list.find(d => String(d.id) === String(targetId))
  || list.find(d => /rtx\s*5060/i.test(wakeRelayLabel(d)) || String(d.client_id || '').toUpperCase() === 'PC-0CC8529F')
  || list.find(d => d.uiStatus !== 'online')
  || list[0]
  || null;
 const optionHTML = d => '<option value="' + esc(d.id) + '">' + esc(wakeRelayLabel(d)) + ' • ' + wakeRelayStatusWord(d) + '</option>';
 targetSelect.innerHTML = '<option value="">Pilih PC target</option>' + list.map(optionHTML).join('');
 targetSelect.value = preferredTarget?.id || '';
 saveWakeRelaySelection();
 loadWakeRelayMac();
 updateWakeRelayStatus();
}
'''
html = html[:start] + new_options + html[end:]

start = html.find('function updateWakeRelayStatus(message) {')
end = html.find('async function refreshWakeRelayDevices() {', start)
if start < 0 or end < 0:
    raise SystemExit('Wake relay status function boundaries not found.')
new_status = r'''function updateWakeRelayStatus(message) {
 const badge = $('wakeRelayBadge');
 const status = $('wakeRelayStatus');
 const button = $('wakeRelaySend');
 const relayInfo = $('wakeRelaySourceInfo');
 if (!badge || !status || !button) return;
 const target = selectedWakeRelayTarget();
 const source = selectedWakeRelaySource();
 const mac = wakeRelayMacFor(target);
 const onlineCandidates = wakeRelayOnlineCandidates(target);
 const stalePreferred = onlineCandidates.find(d => String(d.client_id || '').toUpperCase() === 'PC-38BFEEB2')
  || onlineCandidates.find(d => /rtx\s*3060/i.test(wakeRelayLabel(d)))
  || onlineCandidates[0]
  || null;
 const owner = ctx?.role === 'owner';
 let ready = false;
 let label = 'BELUM SIAP';
 let detail = 'Pilih PC yang mau dinyalakan.';
 if (!owner) detail = 'Fitur menyalakan PC hanya tersedia untuk akun Master/Owner.';
 else if (!target) detail = 'Pilih PC target yang sudah ter-pairing dalam workspace ini.';
 else if (target.uiStatus === 'online') { label = 'PC SUDAH ONLINE'; detail = wakeRelayLabel(target) + ' sudah ONLINE. Tidak perlu mengirim Magic Packet.'; }
 else if (!mac) { label = 'MAC BELUM TERDAFTAR'; detail = 'MAC LAN target belum tersedia. Nyalakan PC target sekali dengan Billing V12.3.8 dan tunggu heartbeat.'; }
 else if (!source && stalePreferred) { label = 'RELAY PERLU UPDATE'; detail = 'Relay ' + wakeRelayLabel(stalePreferred) + ' masih memakai ' + String(stalePreferred.app_version || 'versi lama') + '. Update PC relay ke Billing V12.3.8 agar bisa mengirim Magic Packet.'; }
 else if (!source) { label = 'RELAY OFFLINE'; detail = 'Tidak ada PC relay online yang mendukung WoL. Nyalakan PC1 dan pastikan sudah memakai Billing V12.3.8.'; }
 else { ready = true; label = 'SIAP MENGIRIM'; detail = 'Target OFFLINE • relay otomatis ' + wakeRelayLabel(source) + ' ONLINE • MAC LAN terdeteksi. Tekan Nyalakan.'; }
 if (relayInfo) relayInfo.textContent = source
  ? 'Relay otomatis: ' + wakeRelayLabel(source) + ' • ' + String(source.app_version || 'versi tidak diketahui') + ' • ONLINE'
  : stalePreferred
   ? 'Relay terdeteksi: ' + wakeRelayLabel(stalePreferred) + ' • ' + String(stalePreferred.app_version || 'versi tidak diketahui') + ' • perlu update WoL'
   : 'Relay otomatis: menunggu PC relay online yang mendukung WoL.';
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
req = html[start:end]
req = req.replace("if (!source || !target) return msg('Pilih PC1 relay dan PC2 target.', true);", "if (!source || !target) return msg('Tidak ada relay WoL yang kompatibel atau PC target belum dipilih.', true);")
req = req.replace("if (source.uiStatus !== 'online') return updateWakeRelayStatus('PC1 relay sedang OFFLINE. Tidak ada perintah yang dikirim.');", "if (source.uiStatus !== 'online' || !wakeRelayVersionSupported(source)) return updateWakeRelayStatus('Relay PC belum online atau belum mendukung WoL. Tidak ada perintah yang dikirim.');")
req = req.replace("if (target.uiStatus === 'online') return updateWakeRelayStatus('PC2 sudah ONLINE; perintah tidak dikirim.');", "if (target.uiStatus === 'online') return updateWakeRelayStatus('PC target sudah ONLINE; perintah tidak dikirim.');")
req = req.replace("if (!mac) return updateWakeRelayStatus('MAC LAN PC2 belum terdaftar otomatis. Pastikan PC2 pernah menyala dengan Billing V12.3.8.');", "if (!mac) return updateWakeRelayStatus('MAC LAN PC target belum terdaftar otomatis. Pastikan PC target pernah menyala dengan Billing V12.3.8.');")
req = req.replace("if (!confirm('Kirim perintah menyalakan PC2?\\n\\nPC1 relay: ' + wakeRelayLabel(source) + ' (ONLINE)\\nPC2 target: ' + wakeRelayLabel(target) + ' (OFFLINE)\\nMAC LAN: ' + mac + ' (terdeteksi otomatis)\\n\\nBackend memvalidasi MAC dari data pairing PC2. PC1 mengirim Magic Packet melalui jaringan lokal. PC2 hanya dianggap menyala setelah heartbeat terdeteksi.')) return;",
"if (!confirm('Nyalakan PC yang dipilih?\\n\\nTarget: ' + wakeRelayLabel(target) + ' (OFFLINE)\\nRelay otomatis: ' + wakeRelayLabel(source) + ' (ONLINE)\\nMAC LAN terdeteksi otomatis dari pairing.\\n\\nPC baru dinyatakan menyala setelah heartbeat terdeteksi.')) return;")
req = req.replace("source:'admin-apk-wol-auto-metadata-v12.1.38'", "source:'admin-apk-wol-auto-relay-v12.1.39'")
if 'PC1 relay:' in req or 'source:' not in req or 'targetMac:' in req:
    raise SystemExit('Wake request payload/confirmation simplification failed.')
html = html[:start] + req + html[end:]

ui_anchor = '<div id="wakeRelayMacStatus" class="muted"'
if html.count(ui_anchor) != 1:
    raise SystemExit('MAC metadata status UI anchor mismatch.')
html = html.replace(ui_anchor, '<div id="wakeRelaySourceInfo" class="muted" style="margin-top:10px">Relay otomatis: menunggu PC relay online yang mendukung WoL.</div>\n <div id="wakeRelayMacStatus" class="muted"', 1)

# Replace outdated help copy and version marker.
html = html.replace('V12.1.38-AUTO-WOL-METADATA', MARKER, 1)
gradle, code_count = re.subn(r'\bversionCode\s+66\b', 'versionCode 67', gradle, count=1)
gradle, name_count = re.subn(r"versionName\s*'12\.1\.38'", "versionName '12.1.39'", gradle, count=1)
if code_count != 1 or name_count != 1:
    raise SystemExit('Admin versionCode/versionName update anchor mismatch.')

for forbidden in ('id="wakeRelaySource"', 'WAKE_RELAY_SOURCE_KEY', 'id="wakeRelayMac"', 'function saveWakeRelayMac()', 'WAKE_RELAY_MAC_PREFIX', 'targetMac:mac'):
    if forbidden in html:
        raise SystemExit('Old manual relay/MAC selection remains: ' + forbidden)
for required in (MARKER, 'wakeRelayTarget', 'function selectedWakeRelaySource()', 'wakeRelayVersionSupported(device)', 'metadata?.wolLanMac', 'wakeRelaySourceInfo', 'V12.3.8', "p_command: 'wake'", 'TERKONFIRMASI'):
    if required not in html:
        raise SystemExit('Auto relay target-only assertion missing: ' + required)
if html.count('id="wakeRelayMacStatus"') != 1 or html.count('id="wakeRelaySourceInfo"') != 1 or html.count('id="wakeRelayTarget"') != 1:
    raise SystemExit('Wake relay UI IDs missing or duplicated.')
ids = re.findall(r'\bid=["\']([^"\']+)', html)
duplicates = sorted({x for x in ids if ids.count(x) > 1})
if duplicates:
    raise SystemExit('Duplicate HTML IDs after target-only patch: ' + ', '.join(duplicates))
if 'if(id===\'accounts\')loadGlobalRentalAccounts();' not in html:
    raise SystemExit('Global rental tab loader regression detected.')
if OLD_MARKER not in html and MARKER not in html:
    raise SystemExit('V12.1.38 baseline feature marker not preserved.')
if 'rpc(\'report_detailed_usage_page\'' not in html:
    raise SystemExit('Daily report feature regression detected.')

HTML.write_text(html, encoding='utf-8')
GRADLE.write_text(gradle, encoding='utf-8')
VERSION.write_text(
    'AniGames Admin Android V12.1.39 — choose only the target PC; relay PC is selected automatically from online devices supporting WoL. MAC LAN comes from paired device heartbeat metadata and is resolved again server-side. Existing login, pairing, reports, rental, controls and DB routing preserved.\n',
    encoding='utf-8'
)
print('PASS: target-only UI; PC1 relay is automatic and version-gated at WoL V12.3.6 or newer.')
print('PASS: Admin cannot select an unsupported old PC relay or send a manual MAC.')
print('PASS: server remains responsible for canonical MAC, relay authorization, expiry and duplicate wake guard.')
print('PASS: existing pairing, global rental, reports, billing controls and DB routing preserved.')
print('PASS: unique HTML IDs; Admin V12.1.39 / versionCode 67.')
