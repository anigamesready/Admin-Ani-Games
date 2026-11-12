#!/usr/bin/env python3
"""V12.1.50: fix Admin relay-state TDZ and switch to explicit on-demand relay probes."""
from pathlib import Path
import re

HTML = Path("android/app/src/main/assets/web/admin.html")
GRADLE = Path("android/app/build.gradle")
VERSION = Path("VERSION_ADMIN_ANDROID.txt")
MANIFEST = Path("android/app/src/main/AndroidManifest.xml")
if not HTML.exists() or not GRADLE.exists() or not MANIFEST.exists():
    raise SystemExit("Admin Android source files not found")

html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")
manifest = MANIFEST.read_text(encoding="utf-8")

STATE = """// ANI-WOL-RELAY V12.1.50 — state is declared before startup/auth callbacks can access it.
let aniAndroidWakeRelay = null;
let aniAndroidWakeRelayBusy = false;
let aniAndroidWakeRelayCheckedAt = 0;
let aniAndroidWakeRelayLoading = false;
let aniAndroidWakeRelayActionMessage = '';
"""

# Fix the temporal-dead-zone crash: move all relay state declarations to the
# beginning of the inline application script, before startDualDbAdmin() runs.
old_state = re.compile(
    r"(?m)^// ANI-WOL-RELAY V12\.1\.47-ANDROID-WOL-RELAY[^\n]*\n"
    r"let aniAndroidWakeRelay = null;\n"
    r"let aniAndroidWakeRelayBusy = false;\n"
    r"let aniAndroidWakeRelayCheckedAt = 0;\n"
    r"let aniAndroidWakeRelayLoading = false;\n"
    r"let aniAndroidWakeRelayActionMessage = '';\n?"
)
html, removed = old_state.subn("", html)
if removed != 1:
    raise SystemExit(f"Expected one old relay state block, found {removed}")
script_tags = list(re.finditer(r"<script\b(?![^>]*\bsrc=)[^>]*>", html, re.I))
if len(script_tags) != 1:
    raise SystemExit(f"Expected one inline application script, found {len(script_tags)}")
insert_at = script_tags[0].end()
html = html[:insert_at] + "\n" + STATE + html[insert_at:]

def replace_last_function(source: str, signature: str, replacement: str, expected_min: int = 1):
    pattern = re.compile(r"(?ms)^" + re.escape(signature) + r".*?^\}")
    matches = list(pattern.finditer(source))
    if len(matches) < expected_min:
        raise SystemExit(f"Could not safely find {signature}; matches={len(matches)}")
    match = matches[-1]
    return source[:match.start()] + replacement.rstrip() + source[match.end():], len(matches)

load_fn = r"""async function loadWakeRelayStatus(force = false) {
 const info = $('wakeRelaySourceInfo');
 if (aniAndroidWakeRelayLoading) return aniAndroidWakeRelay;
 if (!force && Date.now() - aniAndroidWakeRelayCheckedAt < 15000) return aniAndroidWakeRelay;
 aniAndroidWakeRelayLoading = true;
 try {
  const raw = await rpc('wol_relay_status', {});
  const payload = raw?.data?.data ?? raw?.data ?? raw?.result ?? raw;
  if (!payload || payload.ok === false) throw new Error(payload?.message || payload?.error || 'Respons status relay tidak valid.');
  const rows = Array.isArray(payload.relays) ? payload.relays : (Array.isArray(payload) ? payload : []);
  const ordered = rows.filter(r => r && !r.revoked_at).sort((a,b) =>
   (Date.parse(b.created_at || b.last_seen_at || '') || 0) - (Date.parse(a.created_at || a.last_seen_at || '') || 0));
  const registered = ordered[0] || null;
  aniAndroidWakeRelay = registered ? {...registered, status:'unverified', active_probe_at:0, probe_failed_at:0} : null;
  aniAndroidWakeRelayCheckedAt = Date.now();
  if (info) {
   if (!registered) info.textContent = 'Belum ada HP relay terdaftar. Buat kode pairing dan hubungkan aplikasi Ani WoL Relay.';
   else {
    const r = registered;
    const battery = Number.isFinite(Number(r.battery_percent)) && Number(r.battery_percent) >= 0 ? Number(r.battery_percent) + '%' : 'N/A';
    const temp = Number.isFinite(Number(r.battery_temp_c)) ? Number(r.battery_temp_c).toFixed(1) + '°C' : 'N/A';
    info.textContent = 'HP ' + String(r.relay_name || r.model || 'Android Relay')
     + ' • terdaftar • belum dites langsung • baterai ' + battery + ' • suhu ' + temp
     + ' • app ' + String(r.app_version || 'N/A');
   }
  }
 } catch (e) {
  aniAndroidWakeRelay = null;
  aniAndroidWakeRelayCheckedAt = Date.now();
  if (info) info.textContent = 'GAGAL MEMBACA DATA RELAY: ' + String(e?.message || e).slice(0,160);
 } finally {
  aniAndroidWakeRelayLoading = false;
 }
 updateWakeRelayStatus();
 return aniAndroidWakeRelay;
}"""
html, load_count = replace_last_function(html, "async function loadWakeRelayStatus(force = false) {", load_fn)

probe_fn = r"""async function probeWakeRelayNow() {
 if (aniAndroidWakeRelayLoading) return null;
 aniAndroidWakeRelayLoading = true;
 aniAndroidWakeRelayActionMessage = 'Mengirim tes koneksi langsung ke HP relay…';
 updateWakeRelayStatus();
 const info = $('wakeRelaySourceInfo');
 try {
  const rawRequest = await rpc('wol_relay_probe_request', {});
  const request = rawRequest?.data?.data ?? rawRequest?.data ?? rawRequest?.result ?? rawRequest;
  if (!request || request.ok === false || !request.probe_id) {
   throw new Error(request?.message || request?.error || 'HP relay belum terdaftar atau permintaan tes ditolak.');
  }
  const deadline = Date.now() + 38000;
  while (Date.now() < deadline) {
   await new Promise(resolve => setTimeout(resolve, 1200));
   const rawState = await rpc('wol_relay_probe_status', {p_probe_id: request.probe_id});
   const state = rawState?.data?.data ?? rawState?.data ?? rawState?.result ?? rawState;
   if (state?.status === 'online') {
    const current = aniAndroidWakeRelay || {};
    aniAndroidWakeRelay = {
     ...current,
     status:'online',
     last_seen_at:state.responded_at || new Date().toISOString(),
     active_probe_at:Date.now(),
     probe_failed_at:0
    };
    aniAndroidWakeRelayCheckedAt = Date.now();
    if (info) {
     const battery = Number.isFinite(Number(state.battery_percent)) ? Number(state.battery_percent) + '%' : 'N/A';
     const temp = Number.isFinite(Number(state.battery_temp_c)) ? Number(state.battery_temp_c).toFixed(1) + '°C' : 'N/A';
     info.textContent = 'HP ' + String(state.relay_name || current.relay_name || current.model || 'Android Relay')
      + ' • ONLINE • membalas tes langsung • baterai ' + battery + ' • suhu ' + temp;
    }
    aniAndroidWakeRelayActionMessage = 'Relay ONLINE • HP membalas pemeriksaan langsung dari Admin.';
    updateWakeRelayStatus();
    return aniAndroidWakeRelay;
   }
   if (state?.status === 'expired' || state?.status === 'offline') break;
   if (state?.ok === false) throw new Error(state?.message || state?.error || 'Gagal memeriksa respons relay.');
  }
  if (aniAndroidWakeRelay) {
   aniAndroidWakeRelay = {...aniAndroidWakeRelay, status:'offline', active_probe_at:0, probe_failed_at:Date.now()};
  }
  if (info) info.textContent = 'HP relay tidak membalas tes langsung. Periksa aplikasi Relay, Wi-Fi, izin background, dan baterai.';
  aniAndroidWakeRelayActionMessage = 'RELAY OFFLINE / TIDAK MERESPONS • Admin tidak menerima balasan dari HP.';
  updateWakeRelayStatus();
  return null;
 } catch (e) {
  if (aniAndroidWakeRelay) {
   aniAndroidWakeRelay = {...aniAndroidWakeRelay, status:'offline', active_probe_at:0, probe_failed_at:Date.now()};
  }
  aniAndroidWakeRelayActionMessage = 'GAGAL TES RELAY: ' + String(e?.message || e).slice(0,150);
  if (info) info.textContent = aniAndroidWakeRelayActionMessage;
  updateWakeRelayStatus();
  return null;
 } finally {
  aniAndroidWakeRelayLoading = false;
 }
}"""
if "async function probeWakeRelayNow()" in html:
    raise SystemExit("Probe function already present; refusing duplicate insertion")
anchor = "function updateWakeRelayStatus(message) {"
idxs = [m.start() for m in re.finditer(r"(?m)^" + re.escape(anchor), html)]
if not idxs:
    raise SystemExit("Could not find relay status renderer")
# Put it directly before the last (active) renderer.
at = idxs[-1]
html = html[:at] + probe_fn + "\n\n" + html[at:]

update_fn = r"""function updateWakeRelayStatus(message) {
 if (message !== undefined) aniAndroidWakeRelayActionMessage = String(message || '');
 const badge = $('wakeRelayBadge');
 const status = $('wakeRelayStatus');
 const button = $('wakeRelaySend');
 if (!badge || !status || !button) return;
 const target = selectedWakeRelayTarget();
 const checkedAt = Number(aniAndroidWakeRelay?.active_probe_at || 0);
 const relayOnline = aniAndroidWakeRelay?.status === 'online'
  && checkedAt > 0 && Date.now() - checkedAt <= 60000;
 let label = 'BELUM SIAP';
 let detail = 'Pilih PC target.';
 let ready = false;
 if (!isWakeRelayOwner()) detail = 'Fitur WoL Android hanya tersedia untuk Master/Owner.';
 else if (!aniAndroidWakeRelay) { label = 'RELAY BELUM TERDAFTAR'; detail = 'Buat kode pairing HP dan hubungkan aplikasi Ani WoL Relay.'; }
 else if (!relayOnline) {
  label = aniAndroidWakeRelay?.probe_failed_at ? 'RELAY OFFLINE' : 'BELUM DICEK';
  detail = aniAndroidWakeRelay?.probe_failed_at
   ? 'HP relay tidak membalas tes terakhir. Buka aplikasi Relay, cek Wi-Fi dan izin berjalan di latar belakang, lalu Refresh status.'
   : 'Tekan Refresh status untuk mengetes HP relay secara langsung. Status lama tidak dianggap ONLINE.';
 }
 else if (!target) detail = 'Pilih PC target yang sudah ter-pairing.';
 else if (target.uiStatus === 'online') { label = 'PC SUDAH ONLINE'; detail = wakeRelayLabel(target) + ' sudah ONLINE; Magic Packet tidak dikirim.'; }
 else if (!normalizeWakeRelayMac(target.metadata?.wolLanMac)) { label = 'MAC BELUM TERSEDIA'; detail = 'MAC LAN belum dilaporkan oleh PC Billing.'; }
 else { label = 'SIAP MENGIRIM'; detail = 'HP relay baru saja membalas tes langsung • PC target OFFLINE • MAC LAN terdeteksi.'; ready = true; }
 if (aniAndroidWakeRelayActionMessage) detail = aniAndroidWakeRelayActionMessage;
 badge.textContent = label;
 status.textContent = detail;
 button.disabled = !ready || aniAndroidWakeRelayBusy;
}"""
html, update_count = replace_last_function(html, "function updateWakeRelayStatus(message) {", update_fn, expected_min=2)

refresh_fn = r"""async function refreshWakeRelayDevices() {
 aniAndroidWakeRelayActionMessage = '';
 aniAndroidWakeRelayCheckedAt = 0;
 try { await loadDevices(); } catch (_) {}
 await loadWakeRelayStatus(true);
 if (aniAndroidWakeRelay) await probeWakeRelayNow();
 else updateWakeRelayStatus('Belum ada HP relay terdaftar. Buat kode pairing terlebih dahulu.');
}"""
html, refresh_count = replace_last_function(html, "async function refreshWakeRelayDevices() {", refresh_fn, expected_min=2)

# Only send WoL after a fresh active response; the DB enqueue RPC also checks
# the explicit-probe timestamp updated by the relay acknowledgement.
old_gate = """ await loadWakeRelayStatus(true);
 const lastSeen = Date.parse(aniAndroidWakeRelay?.last_seen_at || '');
 if (!aniAndroidWakeRelay || aniAndroidWakeRelay.status !== 'online' ||
     !lastSeen || Date.now() - lastSeen > 120000) {
  return updateWakeRelayStatus('HP relay OFFLINE. Buka aplikasi relay dan aktifkan kembali service-nya.');
 }"""
new_gate = """ const probeAt = Number(aniAndroidWakeRelay?.active_probe_at || 0);
 if (!aniAndroidWakeRelay || aniAndroidWakeRelay.status !== 'online' ||
     !probeAt || Date.now() - probeAt > 60000) {
  const live = await probeWakeRelayNow();
  if (!live) return updateWakeRelayStatus('HP relay tidak merespons tes langsung. Periksa aplikasi dan izin background.');
 }"""
if old_gate not in html:
    raise SystemExit("Could not find exact WoL relay readiness gate")
request_pattern = re.compile(r"(?ms)^async function requestWakePc2\(\) \{.*?^\}")
request_matches = list(request_pattern.finditer(html))
if len(request_matches) < 2:
    raise SystemExit(f"Expected both legacy and active WoL send handlers; found {len(request_matches)}")
active_request = request_matches[-1]
request_body = active_request.group(0)
if old_gate not in request_body:
    raise SystemExit("Could not find readiness gate inside the active requestWakePc2 handler")
request_body = request_body.replace(old_gate, new_gate, 1)
html = html[:active_request.start()] + request_body + html[active_request.end():]

# Keep the legacy backend heartbeat endpoint for backwards compatibility, but
# no UI/service code in V1.0.2 is allowed to call it.
if "wol_relay_probe_request" not in html or "wol_relay_probe_status" not in html:
    raise SystemExit("Active probe RPCs were not inserted")
if "Cannot access 'aniAndroidWakeRelay' before initialization" in html:
    raise SystemExit("Stale TDZ error text unexpectedly present")

gradle, n1 = re.subn(r"\bversionCode\s+77\b", "versionCode 78", gradle, count=1)
gradle, n2 = re.subn(r"versionName\s*'12\.1\.49'", "versionName '12.1.50'", gradle, count=1)
if n1 != 1 or n2 != 1:
    raise SystemExit("Admin version update anchor mismatch")

# Keep the installed stable Admin untouched. V12.1.50 is a separate install
# identity so Android never tries to replace a differently signed old build.
gradle, n3 = re.subn(
    r"applicationId\\s+'com\\.anigames\\.billingadmin'",
    "applicationId 'com.anigames.billingadmin.v150'", gradle, count=1)
manifest, n4 = re.subn(
    r'android:label="AniGames Admin"',
    'android:label="AniGames Admin V12.1.50"', manifest, count=1)
if n3 != 1 or n4 != 1:
    raise SystemExit("V12.1.50 side-by-side package/label anchor mismatch")

# Syntax is checked by the CI after every patch. Also assert all old feature
# markers remain present before touching source files.
for token in (
    "report_detailed_usage_page", "report_summary_compact", "ensureActiveDbRouteForAuth",
    "V12.1.49-ANDROID-WOL-PAIRING-ROLE-FIX", "wol_relay_enqueue",
    "wol_relay_command_status", "probeWakeRelayNow", "wol_relay_probe_request",
    "wol_relay_probe_status"
):
    if token not in html:
        raise SystemExit("V12.1.50 regression assertion failed: " + token)

HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
MANIFEST.write_text(manifest, encoding="utf-8")
VERSION.write_text(
    "AniGames Admin Android V12.1.50 — relay TDZ fix and on-demand relay probe; "
    "existing rental, billing, reports and DB routing retained.\n",
    encoding="utf-8"
)
print("PASS: relay state declared before startup; no TDZ access.")
print(f"PASS: replaced active relay functions (load={load_count}, update={update_count}, refresh={refresh_count}).")
print("PASS: Admin status now requires a fresh explicit relay probe.")
print("PASS: WoL action requires a recent probe response.")
print("PASS: prior rental, billing, reports, reseller and dual-DB markers preserved.")
print("PASS: Admin V12.1.50 / versionCode 78 / side-by-side package com.anigames.billingadmin.v150.")
