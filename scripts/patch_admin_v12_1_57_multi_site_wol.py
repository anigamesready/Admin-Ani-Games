#!/usr/bin/env python3
"""V12.1.57 SAFE TEST: explicit PC + Android relay routing for multi-site WoL."""
from pathlib import Path
import re, sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
PAGE = ROOT / "android/app/src/main/assets/web/admin.html"
GRADLE = ROOT / "android/app/build.gradle"
MANIFEST = ROOT / "android/app/src/main/AndroidManifest.xml"
VERSION = ROOT / "VERSION_ADMIN_ANDROID.txt"
MARKER = "V12.1.57-MULTI-SITE-WOL-ROUTING"

for p in (PAGE, GRADLE, MANIFEST):
    if not p.is_file():
        raise SystemExit("REQUIRED_ADMIN_FILE_MISSING:" + str(p))
html, gradle, manifest = (PAGE.read_text(encoding="utf-8"),
                          GRADLE.read_text(encoding="utf-8"),
                          MANIFEST.read_text(encoding="utf-8"))
if MARKER in html:
    if "versionCode 84" in gradle and "versionName '12.1.57'" in gradle and "com.anigames.billingadmin.v157dbtest" in gradle:
        print("PASS: V12.1.57 already applied")
        raise SystemExit(0)
    raise SystemExit("V12.1.57_MARKER_METADATA_MISMATCH")
if "V12.1.56-STOP-PAUSE-OWNER-ROLE-VISIBILITY" not in html:
    raise SystemExit("EXPECTED_V12_1_56_BASELINE_MISSING")
if ("versionCode 83" not in gradle or "versionName '12.1.56'" not in gradle
        or "applicationId 'com.anigames.billingadmin.v156dbtest'" not in gradle):
    raise SystemExit("EXPECTED_V12_1_56_SAFE_TEST_PACKAGE_MISSING")
for token in ("function isWakeRelayOwner()", "wol_relay_status",
              "wol_relay_probe_request", "wol_relay_probe_status",
              "wol_relay_enqueue", "wol_relay_command_status",
              "admin_create_rental_global", "admin_update_rental_global",
              "admin_delete_rental_global", "report_detailed_usage_page",
              "report_summary_compact", "admin_remote_play_dashboard", "startLocalAdmin();"):
    if token not in html:
        raise SystemExit("BASELINE_REGRESSION_GUARD_FAILED:" + token)

# Add the second selector beside the existing PC target selector.
picker = '''
 <div class="field" style="margin-top:10px">
  <label for="wakeRelayAndroidSelect">Android Relay / Router LAN</label>
  <select id="wakeRelayAndroidSelect" onchange="saveWakeRelayRelaySelection();updateWakeRelayStatus();probeWakeRelayNow()" style="width:100%">
   <option value="">Memuat daftar Android relay…</option>
  </select>
  <div class="muted">Pilih HP relay yang satu lokasi dan jaringan LAN dengan PC target. Perintah hanya masuk ke relay yang dipilih.</div>
 </div>
'''
target_field = re.compile(r'(?m)^(\s*)<div class="field"[^>]*>\s*<label for="wakeRelayTarget">')
if len(target_field.findall(html)) != 1:
    raise SystemExit("PC_TARGET_FIELD_ANCHOR_MISMATCH")
html = target_field.sub(lambda m: picker + "\n" + m.group(0), html, count=1)

# Extend the relay state already initialized before Admin startup.
state_anchor = "let aniAndroidWakeRelayActionMessage = '';"
if html.count(state_anchor) != 1:
    raise SystemExit("RELAY_STATE_ANCHOR_MISMATCH")
html = html.replace(state_anchor,
    state_anchor + "\nlet aniAndroidWakeRelays = [];\nlet aniAndroidSelectedRelayId = '';",
    1)

def replace_all_functions(src, signature, replacement, minimum=1):
    pattern = re.compile(r"(?ms)^" + re.escape(signature) + r".*?^\}")
    found = list(pattern.finditer(src))
    if len(found) < minimum:
        raise SystemExit("FUNCTION_ANCHOR_MISMATCH:" + signature + ":" + str(len(found)))
    for m in reversed(found):
        src = src[:m.start()] + replacement.rstrip() + src[m.end():]
    return src, len(found)

helpers = r"""function selectedAndroidRelay() {
 const id = String($('wakeRelayAndroidSelect')?.value || aniAndroidSelectedRelayId || '');
 return (aniAndroidWakeRelays || []).find(r => String(r.relay_id || r.id || '') === id) || null;
}
function saveWakeRelayRelaySelection() {
 const id = String($('wakeRelayAndroidSelect')?.value || '');
 aniAndroidSelectedRelayId = id;
 try { if (id) localStorage.setItem('ani_games_admin_wol_selected_relay_v1', id); } catch (_) {}
 const row = selectedAndroidRelay();
 aniAndroidWakeRelay = row ? {...row, active_probe_at:0, probe_failed_at:0} : null;
 aniAndroidWakeRelayActionMessage = '';
}
function relayHeartbeatFresh(row) {
 const seen = Date.parse(row?.last_seen_at || '');
 const age = seen > 0 ? Date.now() - seen : Number.POSITIVE_INFINITY;
 return String(row?.status || '').toLowerCase() === 'online' && age >= 0 && age <= 90000;
}
function relayOptionLabel(row) {
 const name = String(row?.relay_name || row?.model || 'Android Relay').trim();
 const model = String(row?.model || '').trim();
 const suffix = model && !name.toLowerCase().includes(model.toLowerCase()) ? ' (' + model + ')' : '';
 const battery = Number.isFinite(Number(row?.battery_percent)) && row.battery_percent !== null
  ? ' • ' + Number(row.battery_percent) + '%' : '';
 return name + suffix + ' • ' + (relayHeartbeatFresh(row) ? 'ONLINE' : 'OFFLINE') + battery;
}
function renderWakeRelayAndroidOptions(preferredId) {
 const select = $('wakeRelayAndroidSelect');
 if (!select) return;
 const rows = (aniAndroidWakeRelays || []).filter(r => r && (r.relay_id || r.id) && !r.revoked_at);
 let chosen = String(preferredId || aniAndroidSelectedRelayId || select.value || '');
 if (!chosen) {
  const first = rows.find(r => r.is_selected === true) || rows.find(relayHeartbeatFresh) || rows[0];
  chosen = String(first?.relay_id || first?.id || '');
 }
 select.innerHTML = '<option value="">Pilih Android relay</option>' + rows.map(r => {
  const id = String(r.relay_id || r.id);
  const disabled = relayHeartbeatFresh(r) ? '' : ' disabled';
  return '<option value="' + esc(id) + '"' + disabled + '>' + esc(relayOptionLabel(r)) + '</option>';
 }).join('');
 select.value = rows.some(r => String(r.relay_id || r.id) === chosen) ? chosen : '';
 aniAndroidSelectedRelayId = select.value || '';
 try { if (aniAndroidSelectedRelayId) localStorage.setItem('ani_games_admin_wol_selected_relay_v1', aniAndroidSelectedRelayId); } catch (_) {}
 const row = selectedAndroidRelay();
 aniAndroidWakeRelay = row ? {...row, active_probe_at:0, probe_failed_at:0} : null;
}
"""
load_anchor = "async function loadWakeRelayStatus(force = false) {"
if "function selectedAndroidRelay()" not in html:
    positions = [m.start() for m in re.finditer(r"(?m)^" + re.escape(load_anchor), html)]
    if not positions: raise SystemExit("LOAD_RELAY_STATUS_ANCHOR_MISSING")
    html = html[:positions[-1]] + helpers + "\n" + html[positions[-1]:]

load_fn = r"""async function loadWakeRelayStatus(force = false) {
 const info = $('wakeRelaySourceInfo');
 if (aniAndroidWakeRelayLoading) return aniAndroidWakeRelay;
 if (!force && Date.now() - aniAndroidWakeRelayCheckedAt < 15000) return aniAndroidWakeRelay;
 aniAndroidWakeRelayLoading = true;
 try {
  const raw = await rpc('wol_relay_status', {});
  const payload = raw?.data?.data ?? raw?.data ?? raw?.result ?? raw;
  if (!payload || payload.ok === false) throw new Error(payload?.message || payload?.error || 'Respons status relay tidak valid.');
  aniAndroidWakeRelays = Array.isArray(payload.relays) ? payload.relays.filter(r => r && !r.revoked_at) : [];
  let wanted = aniAndroidSelectedRelayId;
  try { wanted = wanted || localStorage.getItem('ani_games_admin_wol_selected_relay_v1') || ''; } catch (_) {}
  if (!wanted && payload.selected_relay_id) wanted = String(payload.selected_relay_id);
  renderWakeRelayAndroidOptions(wanted);
  aniAndroidWakeRelayCheckedAt = Date.now();
  const active = aniAndroidWakeRelays.filter(relayHeartbeatFresh).length;
  if (info) info.textContent = aniAndroidWakeRelays.length + ' relay terdaftar • ' + active
    + ' ONLINE • pilih router/HP satu jaringan LAN dengan PC target. Heartbeat aktif maksimal 90 detik.';
 } catch (e) {
  aniAndroidWakeRelays = [];
  aniAndroidWakeRelay = null;
  aniAndroidWakeRelayCheckedAt = Date.now();
  if (info) info.textContent = 'GAGAL MEMBACA DATA RELAY: ' + String(e?.message || e).slice(0,160);
 } finally {
  aniAndroidWakeRelayLoading = false;
 }
 updateWakeRelayStatus();
 return aniAndroidWakeRelay;
}"""
html, load_count = replace_all_functions(html, load_anchor, load_fn, 1)

probe_fn = r"""async function probeWakeRelayNow() {
 if (aniAndroidWakeRelayLoading) return null;
 const relay = selectedAndroidRelay();
 const relayId = String(relay?.relay_id || relay?.id || '');
 if (!relayId || !relayHeartbeatFresh(relay)) {
  aniAndroidWakeRelay = relay ? {...relay, active_probe_at:0, probe_failed_at:Date.now()} : null;
  aniAndroidWakeRelayActionMessage = relay ? 'RELAY OFFLINE: heartbeat HP kedaluwarsa. Tidak ada perintah yang dikirim.' : 'Pilih Android relay terlebih dahulu.';
  updateWakeRelayStatus();
  return null;
 }
 aniAndroidWakeRelayLoading = true;
 aniAndroidWakeRelayActionMessage = 'Mengetes koneksi langsung ke ' + relayOptionLabel(relay) + '…';
 updateWakeRelayStatus();
 const info = $('wakeRelaySourceInfo');
 try {
  const rawRequest = await rpc('wol_relay_probe_request_selected', {p_relay_id:relayId});
  const request = rawRequest?.data?.data ?? rawRequest?.data ?? rawRequest?.result ?? rawRequest;
  if (!request || request.ok === false || !request.probe_id || String(request.relay_id) !== relayId)
   throw new Error(request?.message || request?.error || 'Server tidak mengonfirmasi relay yang dipilih.');
  const deadline = Date.now() + 39000;
  while (Date.now() < deadline) {
   await new Promise(resolve => setTimeout(resolve, 1200));
   const rawState = await rpc('wol_relay_probe_status', {p_probe_id:request.probe_id});
   const state = rawState?.data?.data ?? rawState?.data ?? rawState?.result ?? rawState;
   if (state?.status === 'online') {
    aniAndroidWakeRelay = {...relay, status:'online', last_seen_at:state.responded_at || new Date().toISOString(),
      active_probe_at:Date.now(), probe_failed_at:0};
    aniAndroidWakeRelayActionMessage = 'RELAY TERKONFIRMASI: ' + relayOptionLabel(relay) + ' merespons tes langsung.';
    if (info) info.textContent = 'Relay terpilih merespons langsung • ' + relayOptionLabel(relay);
    updateWakeRelayStatus();
    return aniAndroidWakeRelay;
   }
   if (state?.status === 'expired' || state?.status === 'offline') break;
   if (state?.ok === false) throw new Error(state?.message || state?.error || 'Probe relay gagal.');
  }
  aniAndroidWakeRelay = {...relay, active_probe_at:0, probe_failed_at:Date.now()};
  aniAndroidWakeRelayActionMessage = 'RELAY TIDAK MERESPONS PROBE: ' + relayOptionLabel(relay) + '. Tidak ada perintah WoL yang dikirim.';
  updateWakeRelayStatus();
  return null;
 } catch (e) {
  aniAndroidWakeRelay = {...relay, active_probe_at:0, probe_failed_at:Date.now()};
  aniAndroidWakeRelayActionMessage = 'GAGAL TES RELAY: ' + String(e?.message || e).slice(0,150);
  updateWakeRelayStatus();
  return null;
 } finally {
  aniAndroidWakeRelayLoading = false;
 }
}"""
html, probe_count = replace_all_functions(html, "async function probeWakeRelayNow() {", probe_fn, 1)

status_fn = r"""function updateWakeRelayStatus(message) {
 if (message !== undefined) aniAndroidWakeRelayActionMessage = String(message || '');
 const badge = $('wakeRelayBadge'), status = $('wakeRelayStatus'), button = $('wakeRelaySend');
 if (!badge || !status || !button) return;
 const target = selectedWakeRelayTarget(), relay = selectedAndroidRelay();
 const probeAt = Number(aniAndroidWakeRelay?.active_probe_at || 0);
 const relayProbeFresh = !!relay && !!probeAt && Date.now() - probeAt >= 0 && Date.now() - probeAt <= 60000
   && String(aniAndroidWakeRelay?.relay_id || aniAndroidWakeRelay?.id || '') === String(relay.relay_id || relay.id);
 let label = 'BELUM SIAP', detail = 'Pilih PC target dan Android relay/router.', ready = false;
 if (!isWakeRelayOwner()) detail = 'Fitur WoL Android hanya tersedia untuk Master/Owner.';
 else if (!target) detail = 'Pilih PC target yang sudah ter-pairing.';
 else if (!relay) { label = 'RELAY BELUM DIPILIH'; detail = 'Pilih HP relay/router yang satu jaringan LAN dengan PC tujuan.'; }
 else if (!relayHeartbeatFresh(relay)) { label = 'RELAY OFFLINE'; detail = 'Relay pilihan tidak memiliki heartbeat segar. Hidupkan aplikasi relay atau pilih router yang online.'; }
 else if (!relayProbeFresh) {
  label = aniAndroidWakeRelay?.probe_failed_at ? 'RELAY TIDAK MERESPONS' : 'TES RELAY DIPERLUKAN';
  detail = aniAndroidWakeRelay?.probe_failed_at ? 'HP relay tidak menjawab probe terakhir. Tes ulang sebelum mengirim.' : 'Tes relay terpilih sebelum mengirim Magic Packet.';
 }
 else if (target.uiStatus === 'online') { label = 'PC SUDAH ONLINE'; detail = wakeRelayLabel(target) + ' sudah ONLINE; Magic Packet tidak dikirim.'; }
 else if (!normalizeWakeRelayMac(target.metadata?.wolLanMac)) { label = 'MAC BELUM TERSEDIA'; detail = 'MAC LAN belum dilaporkan oleh PC Billing.'; }
 else { label = 'SIAP MENGIRIM'; detail = 'Target OFFLINE • relay ' + relayOptionLabel(relay) + ' sudah merespons probe.'; ready = true; }
 if (aniAndroidWakeRelayActionMessage) detail = aniAndroidWakeRelayActionMessage;
 badge.textContent = label; status.textContent = detail; button.disabled = !ready || aniAndroidWakeRelayBusy;
}"""
html, status_count = replace_all_functions(html, "function updateWakeRelayStatus(message) {", status_fn, 2)

refresh_fn = r"""async function refreshWakeRelayDevices() {
 aniAndroidWakeRelayActionMessage = ''; aniAndroidWakeRelayCheckedAt = 0;
 try { await loadDevices(); } catch (_) {}
 await loadWakeRelayStatus(true);
 if (selectedAndroidRelay()) await probeWakeRelayNow();
 else updateWakeRelayStatus('Pilih Android relay/router terlebih dahulu.');
}"""
html, refresh_count = replace_all_functions(html, "async function refreshWakeRelayDevices() {", refresh_fn, 2)

request_fn = r"""async function requestWakePc2() {
 if (!isWakeRelayOwner()) return msg('Akses WoL hanya untuk Master/Owner.', true);
 aniAndroidWakeRelayActionMessage = '';
 const target = selectedWakeRelayTarget(), relay = selectedAndroidRelay();
 const relayId = String(relay?.relay_id || relay?.id || '');
 if (!target) return updateWakeRelayStatus('Pilih PC target terlebih dahulu.');
 if (!relayId) return updateWakeRelayStatus('Pilih Android relay/router terlebih dahulu.');
 if (target.uiStatus === 'online') return updateWakeRelayStatus('PC target sudah ONLINE; perintah tidak dikirim.');
 if (!normalizeWakeRelayMac(target.metadata?.wolLanMac)) return updateWakeRelayStatus('MAC LAN PC target belum tersedia dari PC Billing.');
 const probeAt = Number(aniAndroidWakeRelay?.active_probe_at || 0);
 if (!probeAt || Date.now() - probeAt > 60000 || String(aniAndroidWakeRelay?.relay_id || aniAndroidWakeRelay?.id || '') !== relayId) {
  const live = await probeWakeRelayNow();
  if (!live) return updateWakeRelayStatus('Relay pilihan tidak merespons probe. Perintah tidak dikirim.');
 }
 const activeRelay = selectedAndroidRelay();
 if (!activeRelay || !relayHeartbeatFresh(activeRelay)) return updateWakeRelayStatus('Relay pilihan OFFLINE. Perintah tidak dikirim.');
 if (!confirm('Kirim Wake-on-LAN ke PC yang dipilih?\n\nPC target: ' + wakeRelayLabel(target)
   + ' (OFFLINE)\nAndroid relay/router: ' + relayOptionLabel(activeRelay)
   + '\n\nServer hanya mengirim antrean ke relay ini. Pastikan HP relay dan PC target berada di LAN yang sama.')) return;
 aniAndroidWakeRelayBusy = true;
 const button = $('wakeRelaySend'); if (button) button.disabled = true;
 let finalMessage = 'Perintah WoL sedang diproses relay pilihan…';
 updateWakeRelayStatus(finalMessage);
 try {
  const rawQueued = await rpc('wol_relay_enqueue_selected', {p_target_device_id:target.id, p_relay_id:relayId});
  const queued = rawQueued?.data?.data ?? rawQueued?.data ?? rawQueued?.result ?? rawQueued;
  if (queued?.ok === false) throw new Error(queued?.message || queued?.error || 'Server menolak perintah WoL.');
  if (String(queued?.relay_id || '') !== relayId) throw new Error('SERVER_RELAY_SELECTION_MISMATCH');
  const commandId = queued?.command_id || queued?.id;
  if (!commandId) throw new Error('Server tidak mengembalikan ID perintah.');
  const targetId = String(target.id); let packetSent = false;
  for (let attempt = 0; attempt < 16; attempt++) {
   await new Promise(resolve => setTimeout(resolve, 5000));
   const rawState = await rpc('wol_relay_command_status', {p_command_id:commandId});
   const state = rawState?.data?.data ?? rawState?.data ?? rawState?.result ?? rawState;
   if (state?.status === 'failed' || state?.status === 'expired') {
    finalMessage = 'RELAY GAGAL: ' + String(state?.result?.message || state?.result?.error || state.status);
    updateWakeRelayStatus(finalMessage); return;
   }
   if (state?.status === 'packet_sent') {
    packetSent = true;
    finalMessage = 'MAGIC PACKET TERKIRIM melalui ' + String(queued.relay_name || activeRelay.relay_name || activeRelay.model) + '. Menunggu PC boot…';
   } else finalMessage = 'Perintah masuk antrean relay terpilih; menunggu HP mengambil perintah…';
   await loadDevices();
   const updated = (devicesCache || []).find(d => String(d.id) === targetId);
   if (updated?.uiStatus === 'online') {
    finalMessage = 'TERKONFIRMASI: ' + wakeRelayLabel(updated) + ' sudah ONLINE; heartbeat Billing terdeteksi.';
    updateWakeRelayStatus(finalMessage); msg('PC berhasil dinyalakan dan terdeteksi ONLINE.'); return;
   }
   updateWakeRelayStatus(finalMessage);
  }
  finalMessage = packetSent
   ? 'Magic Packet sudah dikirim melalui relay pilihan, tetapi PC belum mengirim heartbeat. Periksa BIOS WoL, ErP, kabel LAN, dan NIC.'
   : 'Relay pilihan belum mengambil perintah. Periksa service, izin background, dan Wi-Fi.';
  updateWakeRelayStatus(finalMessage);
 } catch (e) {
  finalMessage = 'GAGAL WOL: ' + String(e?.message || e).slice(0,180);
  updateWakeRelayStatus(finalMessage);
 } finally {
  aniAndroidWakeRelayBusy = false; updateWakeRelayStatus(finalMessage);
 }
}"""
html, request_count = replace_all_functions(html, "async function requestWakePc2() {", request_fn, 2)

# Route the two new RPCs through the separate DB1 Supabase relay sidecar, not local DB Android.
rpc_names = re.compile(r"const RELAY_RPC_NAMES=new Set\(\[([^\]]*)\]\);")
m = rpc_names.search(html)
if not m: raise SystemExit("RELAY_RPC_NAMES_ROUTING_SET_MISSING")
names = m.group(1)
for name in ("wol_relay_enqueue_selected", "wol_relay_probe_request_selected"):
    if "'" + name + "'" not in names: names = names.rstrip() + ",'" + name + "'"
html = rpc_names.sub("const RELAY_RPC_NAMES=new Set([" + names + "]);", html, count=1)

for token in ('id="wakeRelayAndroidSelect"', "function selectedAndroidRelay()",
              "function renderWakeRelayAndroidOptions(", "wol_relay_enqueue_selected",
              "wol_relay_probe_request_selected", "function isWakeRelayOwner()"):
    if token not in html: raise SystemExit("MULTI_SITE_WOL_ASSERTION_FAILED:" + token)

# Side-by-side test identity only; do not replace stable Admin.
gradle, c1 = re.subn(r"\bversionCode\s+83\b", "versionCode 84", gradle, count=1)
gradle, c2 = re.subn(r"versionName\s*'12\.1\.56'", "versionName '12.1.57'", gradle, count=1)
gradle, c3 = re.subn(r"applicationId\s+'com\.anigames\.billingadmin\.v156dbtest'",
                    "applicationId 'com.anigames.billingadmin.v157dbtest'", gradle, count=1)
manifest, c4 = re.subn(r'android:label="AniGames Admin DB Android V12\.1\.56 SAFE TEST"',
    'android:label="AniGames Admin DB Android V12.1.57 MULTI-SITE WoL SAFE TEST"', manifest, count=1)
if (c1,c2,c3,c4) != (1,1,1,1):
    raise SystemExit("V12.1.57_VERSION_OR_PACKAGE_ANCHOR_MISMATCH:" + str((c1,c2,c3,c4)))

html += "\n<!-- " + MARKER + " -->\n"
PAGE.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
MANIFEST.write_text(manifest, encoding="utf-8")
VERSION.write_text("AniGames Admin DB Android V12.1.57 SAFE TEST — Multi-Site WoL; choose PC target and explicit Android relay.\n", encoding="utf-8")
print("PASS: separate PC-target and Android-relay selectors are wired.")
print("PASS: selected relay receives a direct probe before an explicit per-relay enqueue.")
print("PASS: stale/offline relay is blocked; no cross-site automatic fallback or command fan-out.")
print(f"PASS: relay functions normalized (load={load_count}, probe={probe_count}, status={status_count}, refresh={refresh_count}, send={request_count}).")
print("PASS: stable Admin untouched; SAFE TEST package v157dbtest / versionCode 84.")
