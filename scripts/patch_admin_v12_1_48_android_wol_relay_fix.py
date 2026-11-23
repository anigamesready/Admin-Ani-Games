from pathlib import Path
import re

HTML = Path("android/app/src/main/assets/web/admin.html")
GRADLE = Path("android/app/build.gradle")
VERSION = Path("VERSION.txt")
MARKER = "V12.1.48-ANDROID-WOL-RELAY-RELIABILITY"

if not HTML.is_file() or not GRADLE.is_file():
    raise SystemExit("Admin Android source root is missing.")
html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")

if MARKER in html:
    if "versionCode 76" in gradle and "versionName '12.1.48'" in gradle:
        print("PASS: Admin V12.1.48 relay reliability patch already applied.")
        raise SystemExit(0)
    raise SystemExit("V12.1.48 marker/version mismatch.")

if "V12.1.47-ANDROID-WOL-RELAY" not in html:
    raise SystemExit("Expected exact Admin V12.1.47 Android relay source.")
if "versionCode 75" not in gradle or "versionName '12.1.47'" not in gradle:
    raise SystemExit("Expected exact Admin V12.1.47 package baseline.")
for required in ("wol_relay_status", "wol_relay_enqueue", "wol_relay_command_status",
                 "report_detailed_usage_page", "report_summary_compact",
                 "ensureActiveDbRouteForAuth", "V12.1.36-PC-WOL-RELAY"):
    if required not in html:
        raise SystemExit("Regression guard failed before patch: " + required)

def replace_fn(source, pattern, replacement, label):
    updated, count = re.subn(pattern, lambda _: replacement, source, count=1, flags=re.S)
    if count != 1:
        raise SystemExit("Could not safely locate " + label)
    return updated

if "let aniAndroidWakeRelayActionMessage" not in html:
    html = html.replace(
        "let aniAndroidWakeRelayCheckedAt = 0;",
        "let aniAndroidWakeRelayCheckedAt = 0;\nlet aniAndroidWakeRelayLoading = false;\nlet aniAndroidWakeRelayActionMessage = '';",
        1
    )

load_fn = r"""async function loadWakeRelayStatus(force = false) {
 const info = $('wakeRelaySourceInfo');
 if (aniAndroidWakeRelayLoading) return aniAndroidWakeRelay;
 if (!force && Date.now() - aniAndroidWakeRelayCheckedAt < 15000) return aniAndroidWakeRelay;
 aniAndroidWakeRelayLoading = true;
 try {
  const raw = await rpc('wol_relay_status', {});
  const payload = raw?.data ?? raw?.result ?? raw;
  if (!payload || payload.ok === false) throw new Error(payload?.message || payload?.error || 'Respons status relay tidak valid.');
  const rows = Array.isArray(payload.relays) ? payload.relays : (Array.isArray(payload) ? payload : []);
  const now = Date.now();
  const ordered = rows.filter(r => r && !r.revoked_at).sort((a,b) =>
   (Date.parse(b.last_seen_at || '') || 0) - (Date.parse(a.last_seen_at || '') || 0));
  aniAndroidWakeRelay = ordered.find(r => {
   const seen = Date.parse(r.last_seen_at || '');
   const age = seen > 0 ? now - seen : Number.POSITIVE_INFINITY;
   return r.status === 'online' && age >= 0 && age <= 120000;
  }) || ordered[0] || null;
  aniAndroidWakeRelayCheckedAt = now;
  if (info) {
   if (!aniAndroidWakeRelay) {
    info.textContent = 'Belum ada HP relay terdaftar. Buat kode pairing dan hubungkan aplikasi Ani WoL Relay.';
   } else {
    const r = aniAndroidWakeRelay;
    const seen = Date.parse(r.last_seen_at || '');
    const age = seen > 0 ? Math.max(0, Math.floor((now-seen)/1000)) : null;
    const fresh = age !== null && age <= 120;
    const state = r.status === 'online' && fresh ? 'ONLINE' : 'OFFLINE';
    const ageText = age === null ? 'heartbeat tidak diketahui' : (age < 60 ? age + ' dtk lalu' : Math.floor(age/60) + ' mnt lalu');
    const battery = Number.isFinite(Number(r.battery_percent)) && Number(r.battery_percent) >= 0 ? Number(r.battery_percent) + '%' : 'N/A';
    const temp = Number.isFinite(Number(r.battery_temp_c)) ? Number(r.battery_temp_c).toFixed(1) + '°C' : 'N/A';
    info.textContent = 'HP ' + String(r.relay_name || r.model || 'Android Relay') + ' • ' + state
      + ' • heartbeat ' + ageText + ' • baterai ' + battery + ' • suhu ' + temp
      + ' • app ' + String(r.app_version || 'N/A')
      + (r.last_error ? ' • server error: ' + String(r.last_error).slice(0,100) : '');
   }
  }
 } catch (e) {
  aniAndroidWakeRelay = null;
  aniAndroidWakeRelayCheckedAt = Date.now();
  if (info) info.textContent = 'GAGAL MEMBACA STATUS RELAY: ' + String(e?.message || e).slice(0,160);
 } finally {
  aniAndroidWakeRelayLoading = false;
 }
 updateWakeRelayStatus();
 return aniAndroidWakeRelay;
}"""
html = replace_fn(html,
    r"async function loadWakeRelayStatus\(force = false\) \{.*?\n\}",
    load_fn, "loadWakeRelayStatus")

status_fn = r"""function isWakeRelayOwner() {
 const role = String(ctx?.role || '').toLowerCase();
 return role === 'owner' || role === 'super_admin' || role === 'superadmin';
}

function updateWakeRelayStatus(message) {
 if (message !== undefined) aniAndroidWakeRelayActionMessage = String(message || '');
 const badge = $('wakeRelayBadge');
 const status = $('wakeRelayStatus');
 const button = $('wakeRelaySend');
 if (!badge || !status || !button) return;
 const target = selectedWakeRelayTarget();
 const seen = Date.parse(aniAndroidWakeRelay?.last_seen_at || '');
 const age = seen > 0 ? Date.now() - seen : Number.POSITIVE_INFINITY;
 const relayOnline = aniAndroidWakeRelay?.status === 'online' && age >= 0 && age <= 120000;
 let label = 'BELUM SIAP';
 let detail = 'Pilih PC target.';
 let ready = false;
 if (!isWakeRelayOwner()) detail = 'Fitur WoL Android hanya tersedia untuk Master/Owner.';
 else if (!aniAndroidWakeRelay) { label = 'STATUS BELUM TERSEDIA'; detail = 'Periksa koneksi Admin atau pairing HP relay.'; }
 else if (!relayOnline) { label = 'RELAY OFFLINE'; detail = 'Heartbeat HP relay kedaluwarsa. Buka aplikasi relay, aktifkan Jalankan Relay, dan izinkan background / unrestricted battery.'; }
 else if (!target) detail = 'Pilih PC target yang sudah ter-pairing.';
 else if (target.uiStatus === 'online') { label = 'PC SUDAH ONLINE'; detail = wakeRelayLabel(target) + ' sudah ONLINE; Magic Packet tidak dikirim.'; }
 else if (!normalizeWakeRelayMac(target.metadata?.wolLanMac)) { label = 'MAC BELUM TERSEDIA'; detail = 'MAC LAN belum dilaporkan oleh PC Billing.'; }
 else { label = 'SIAP MENGIRIM'; detail = 'HP relay ONLINE • PC target OFFLINE • MAC LAN terdeteksi.'; ready = true; }
 if (aniAndroidWakeRelayActionMessage) detail = aniAndroidWakeRelayActionMessage;
 badge.textContent = label;
 status.textContent = detail;
 button.disabled = !ready || aniAndroidWakeRelayBusy;
}"""
html = replace_fn(html,
    r"function updateWakeRelayStatus\(message\) \{.*?\n\}",
    status_fn, "updateWakeRelayStatus")

def patch_one_owner_check(source, fn_name, old):
    start = source.find(fn_name)
    if start < 0: raise SystemExit("Missing " + fn_name)
    end = source.find("\n}", start)
    if end < 0: raise SystemExit("Malformed " + fn_name)
    chunk = source[start:end+2]
    if old in chunk:
        chunk = chunk.replace(old, "if (!isWakeRelayOwner()) return msg('Akses hanya untuk Master/Owner.', true);", 1)
        source = source[:start] + chunk + source[end+2:]
    return source

html = patch_one_owner_check(html, "async function createWakeRelayPairingCode()", "if (ctx?.role !== 'owner')")
html = replace_fn(html,
    r"async function refreshWakeRelayDevices\(\) \{.*?\n\}",
    r"""async function refreshWakeRelayDevices() {
 aniAndroidWakeRelayActionMessage = '';
 aniAndroidWakeRelayCheckedAt = 0;
 try { await loadDevices(); } catch (_) {}
 await loadWakeRelayStatus(true);
 updateWakeRelayStatus();
}""", "refreshWakeRelayDevices")

request_fn = r"""async function requestWakePc2() {
 if (!isWakeRelayOwner()) return msg('Fitur menyalakan PC hanya tersedia untuk Master/Owner.', true);
 aniAndroidWakeRelayActionMessage = '';
 const target = selectedWakeRelayTarget();
 if (!target) return updateWakeRelayStatus('Pilih PC target terlebih dahulu.');
 if (target.uiStatus === 'online') return updateWakeRelayStatus('PC target sudah ONLINE; perintah tidak dikirim.');
 if (!normalizeWakeRelayMac(target.metadata?.wolLanMac)) return updateWakeRelayStatus('MAC LAN PC target belum tersedia dari PC Billing.');
 await loadWakeRelayStatus(true);
 const lastSeen = Date.parse(aniAndroidWakeRelay?.last_seen_at || '');
 if (!aniAndroidWakeRelay || aniAndroidWakeRelay.status !== 'online' ||
     !lastSeen || Date.now() - lastSeen > 120000) {
  return updateWakeRelayStatus('HP relay OFFLINE. Buka aplikasi relay dan aktifkan kembali service-nya.');
 }
 if (!confirm('Kirim Wake-on-LAN ke ' + wakeRelayLabel(target) + '?\n\nRelay Android: ONLINE\nPC target: OFFLINE\nMAC LAN diambil dari database PC Billing.')) return;

 aniAndroidWakeRelayBusy = true;
 const button = $('wakeRelaySend');
 if (button) button.disabled = true;
 let finalMessage = 'Perintah WoL sedang diproses HP relay…';
 updateWakeRelayStatus(finalMessage);
 try {
  const rawQueued = await rpc('wol_relay_enqueue', {p_target_device_id: target.id});
  const queued = rawQueued?.data ?? rawQueued?.result ?? rawQueued;
  if (queued?.ok === false) throw new Error(queued?.message || queued?.error || 'Server menolak perintah WoL.');
  const commandId = queued?.command_id || queued?.id;
  if (!commandId) throw new Error('Server tidak mengembalikan ID perintah.');
  const targetId = String(target.id);
  let packetSent = false;
  for (let attempt = 0; attempt < 16; attempt++) {
   await new Promise(resolve => setTimeout(resolve, 5000));
   const rawState = await rpc('wol_relay_command_status', {p_command_id: commandId});
   const state = rawState?.data ?? rawState?.result ?? rawState;
   if (state?.status === 'failed' || state?.status === 'expired') {
    finalMessage = 'RELAY GAGAL: ' + String(state?.result?.message || state?.result?.error || state.status);
    updateWakeRelayStatus(finalMessage);
    return;
   }
   if (state?.status === 'packet_sent') {
    packetSent = true;
    finalMessage = 'MAGIC PACKET TERKIRIM. Menunggu PC boot dan heartbeat Billing…';
   } else {
    finalMessage = 'Perintah diterima server; menunggu HP relay mengambil perintah…';
   }
   await loadDevices();
   const updated = (devicesCache || []).find(d => String(d.id) === targetId);
   if (updated?.uiStatus === 'online') {
    finalMessage = 'TERKONFIRMASI: ' + wakeRelayLabel(updated) + ' sudah ONLINE; heartbeat Billing terdeteksi.';
    updateWakeRelayStatus(finalMessage);
    msg('PC berhasil dinyalakan dan terdeteksi ONLINE.');
    return;
   }
   updateWakeRelayStatus(finalMessage);
  }
  finalMessage = packetSent
   ? 'Magic Packet sudah dikirim HP, tetapi PC belum mengirim heartbeat. Periksa BIOS WoL, ErP, kabel LAN, dan NIC.'
   : 'HP belum mengambil perintah. Periksa status service relay, izin background, dan Wi-Fi.';
  updateWakeRelayStatus(finalMessage);
 } catch (e) {
  finalMessage = 'GAGAL WOL: ' + String(e?.message || e).slice(0,180);
  updateWakeRelayStatus(finalMessage);
 } finally {
  aniAndroidWakeRelayBusy = false;
  updateWakeRelayStatus(finalMessage);
 }
}"""
html = replace_fn(html,
    r"async function requestWakePc2\(\) \{.*?\n\}",
    request_fn, "requestWakePc2")

auto = r"""
// V12.1.48 relay status refresh, only while the WoL card is visible.
if (!window.__aniWakeRelayRefreshTimer) {
 window.__aniWakeRelayRefreshTimer = setInterval(() => {
  const card = $('wakeRelayCard');
  if (document.visibilityState !== 'visible' || !card || card.getClientRects().length === 0) return;
  loadWakeRelayStatus(true).catch(() => {});
 }, 20000);
}
"""
if "V12.1.48 relay status refresh" not in html:
    pos = html.rfind("</script>")
    if pos < 0: raise SystemExit("Admin inline script closing tag missing.")
    html = html[:pos] + auto + "\n" + html[pos:]

for token in ("isWakeRelayOwner", "loadWakeRelayStatus", "wol_relay_enqueue",
              "wol_relay_command_status", "V12.1.48 relay status refresh",
              "TERKONFIRMASI", "GAGAL WOL"):
    if token not in html: raise SystemExit("Missing relay reliability patch marker: " + token)
for token in ("rpc('report_detailed_usage_page'", "rpc('report_summary_compact'",
              "ensureActiveDbRouteForAuth", "admin_create_rental_global",
              "admin_update_rental_global", "admin_delete_rental_global",
              "V12.1.45-BILLING-LOGOUT-LOGIN-TOGGLE",
              "V12.1.46-MONTHLY-YEARLY-PC-REPORT-EXPORT"):
    if token not in html: raise SystemExit("Regression guard failed: " + token)
if 'id="wakeRelayCard"' not in html or 'id="wakeRelayTarget"' not in html:
    raise SystemExit("WoL relay UI is missing.")
html += "\n<!-- " + MARKER + " -->\n"

gradle, n1 = re.subn(r"\bversionCode\s+75\b", "versionCode 76", gradle, count=1)
gradle, n2 = re.subn(r"versionName\s*'12\.1\.47'", "versionName '12.1.48'", gradle, count=1)
if n1 != 1 or n2 != 1: raise SystemExit("Admin version update anchor mismatch.")
HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
VERSION.write_text("AniGames Admin Android V12.1.48 — Android WoL relay reliability, heartbeat freshness and command feedback.\n", encoding="utf-8")
print("PASS: relay heartbeat freshness, API diagnostics, and auto-refresh.")
print("PASS: SUPER_ADMIN owner validation and PC online/MAC guards.")
print("PASS: WoL command result is preserved; success requires PC Billing heartbeat.")
print("PASS: existing rental, billing, reports, reseller and DB routing remain.")
print("PASS: Admin V12.1.48 / versionCode 76.")
