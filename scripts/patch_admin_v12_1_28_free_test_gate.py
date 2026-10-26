from pathlib import Path
import re

HTML = Path("android/app/src/main/assets/web/admin.html")
GRADLE = Path("android/app/build.gradle")
VERSION = Path("VERSION.txt")
html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")

MARKER = "V12.1.28-FREE-TEST-GATE"
if MARKER in html:
    if "versionCode 56" not in gradle or "versionName '12.1.28'" not in gradle:
        raise SystemExit("V12.1.28 feature marker/version mismatch")
    print("PASS: V12.1.28 free-test gate already applied")
    raise SystemExit(0)

if "V12.1.27-LOGIN-CLICK-ROUTE-RESOLVE" not in html:
    raise SystemExit("Expected exact Admin V12.1.27 base; refusing to patch another baseline")
if "versionCode 55" not in gradle or "versionName '12.1.27'" not in gradle:
    raise SystemExit("Expected Admin V12.1.27 Gradle version markers")
if "function schedulePcShutdown()" not in html or "function cancelPcShutdown()" not in html:
    raise SystemExit("Selected-PC shutdown timer patch must be applied before this feature patch")
if "id=\"pcShutdownTimerCard\"" not in html:
    raise SystemExit("Shutdown timer card anchor is missing")

# Feature-policy card is inserted into the same device-management section as the shutdown timer.
policy_card = r"""
<div class="card" id="freeTestPolicyCard" style="margin-top:12px;border:1px solid var(--a)">
 <div class="top"><div><h3 style="margin:0">🛂 Izin FREE TEST 10 MENIT</h3><div class="muted">Master/Owner menentukan apakah tombol test 10 menit pada PC boleh dipakai.</div></div><span id="freeTestPolicyState" class="pill">BELUM DIPERIKSA</span></div>
 <div class="msg" style="margin-top:10px">Jika izin OFF, PC wajib menolak test baru dan menampilkan: <b>“Silahkan hubungi admin untuk melakukan tes 082298316902”</b>. Mematikan izin tidak memutus sesi test yang sudah berjalan.</div>
 <label class="row" style="display:flex;align-items:center;gap:10px;margin-top:12px"><input id="freeTestPolicySwitch" type="checkbox" disabled><span>Izinkan test gratis 10 menit</span></label>
 <div class="row" style="margin-top:10px"><button type="button" onclick="loadFreeTestPolicy()">Muat Status</button><button id="freeTestPolicySave" type="button" class="primary" onclick="saveFreeTestPolicy()" disabled>Simpan Pengaturan</button></div>
 <div id="freeTestPolicyMessage" class="msg" role="status" aria-live="polite" style="margin-top:10px">Muat status dari database untuk mengubah izin. Setting default adalah OFF sampai Owner mengaktifkan.</div>
</div>
"""
timer_anchor = '<div class="card" id="pcShutdownTimerCard"'
if html.count(timer_anchor) != 1:
    raise SystemExit("Expected exactly one shutdown timer card for free-test panel insertion")
html = html.replace(timer_anchor, policy_card + "\n" + timer_anchor, 1)

helpers = r"""
// V12.1.28-FREE-TEST-GATE — UI only; server RPCs remain the authorization authority.
function freeTestPolicyIsOwner() {
 const role = String(ctx?.role || '').trim().toLowerCase();
 return role === 'owner' || role === 'super_admin';
}
function freeTestPolicyMessage(text, error) {
 const el = $('freeTestPolicyMessage');
 if (!el) return;
 el.textContent = String(text || '');
 el.style.borderLeftColor = error ? '#ff4d6d' : 'var(--a)';
}
function renderFreeTestPolicy(result) {
 const enabled = result?.enabled === true;
 const sw = $('freeTestPolicySwitch');
 const state = $('freeTestPolicyState');
 const save = $('freeTestPolicySave');
 if (sw) { sw.checked = enabled; sw.disabled = !freeTestPolicyIsOwner(); }
 if (state) {
  state.textContent = enabled ? 'TEST DIIZINKAN' : 'TEST DINONAKTIFKAN';
  state.style.color = enabled ? 'var(--ok)' : '#ff4d6d';
  state.style.borderColor = enabled ? 'var(--ok)' : '#ff4d6d';
 }
 if (save) save.disabled = !freeTestPolicyIsOwner();
 freeTestPolicyMessage(
  enabled
   ? 'Database mengizinkan test 10 menit. Izin ini dapat dicabut kapan saja untuk permintaan test baru.'
   : 'Database menonaktifkan test 10 menit. PC harus menolak test baru dan menampilkan nomor admin 082298316902.',
  false
 );
}
async function loadFreeTestPolicy() {
 const sw = $('freeTestPolicySwitch'), save = $('freeTestPolicySave');
 const state = $('freeTestPolicyState');
 try {
  if (state) state.textContent = 'MEMUAT...';
  if (sw) sw.disabled = true;
  if (save) save.disabled = true;
  const result = await rpc('admin_get_free_test_policy', {});
  if (!result || typeof result.enabled !== 'boolean') throw new Error('Respons pengaturan test tidak valid.');
  renderFreeTestPolicy(result);
  if (!freeTestPolicyIsOwner()) {
   if (sw) sw.disabled = true;
   if (save) save.disabled = true;
   freeTestPolicyMessage('Hanya Master/Owner yang boleh mengubah izin test. Status dibaca dari database.', false);
  }
  return result;
 } catch (e) {
  if (state) state.textContent = 'GAGAL MEMUAT';
  if (sw) sw.disabled = true;
  if (save) save.disabled = true;
  freeTestPolicyMessage('Status izin tidak bisa diverifikasi. Jangan menganggap test aktif. Detail: ' + String(e?.message || e).slice(0, 180), true);
  return null;
 }
}
async function saveFreeTestPolicy() {
 if (!freeTestPolicyIsOwner()) {
  freeTestPolicyMessage('Hanya Master/Owner yang boleh mengubah izin test.', true);
  return;
 }
 const sw = $('freeTestPolicySwitch');
 const save = $('freeTestPolicySave');
 if (!sw || !save) return;
 const enabled = sw.checked === true;
 const action = enabled ? 'MENGAKTIFKAN' : 'MEMATIKAN';
 const message = enabled
  ? 'Silahkan hubungi admin untuk melakukan tes 082298316902 jika perlu bantuan.'
  : 'PC akan memblokir permintaan test baru dan menampilkan nomor admin 082298316902.';
 if (!confirm(action + ' izin FREE TEST 10 MENIT?' + '\n\n' + message + '\n\nPerubahan hanya mengatur test baru; sesi yang sedang berjalan tidak diputus.')) {
  await loadFreeTestPolicy();
  return;
 }
 save.disabled = true;
 try {
  const result = await rpc('admin_set_free_test_policy', {p_enabled: enabled});
  if (!result || result.enabled !== enabled) throw new Error('Database tidak mengonfirmasi perubahan izin.');
  renderFreeTestPolicy(result);
  freeTestPolicyMessage(
   enabled
    ? 'TERSIMPAN: PC boleh memulai test 10 menit setelah memverifikasi izin server.'
    : 'TERSIMPAN: test 10 menit OFF. PC harus menolak test baru dan menampilkan nomor admin 082298316902.',
   false
  );
  if (typeof msg === 'function') msg(enabled ? 'Izin FREE TEST 10 MENIT diaktifkan.' : 'Izin FREE TEST 10 MENIT dinonaktifkan.');
 } catch (e) {
  // Fail closed in the UI if the server could not confirm the save.
  if (sw) sw.disabled = true;
  freeTestPolicyMessage('SIMPAN GAGAL / STATUS TIDAK DIKETAHUI. Muat ulang dari database sebelum mengubah lagi. Detail: ' + String(e?.message || e).slice(0, 180), true);
 } finally {
  save.disabled = !freeTestPolicyIsOwner();
 }
}
"""
inline_scripts = list(re.finditer(r'<script\b(?![^>]*\bsrc\s*=)[^>]*>(.*?)</script\s*>', html, re.IGNORECASE | re.DOTALL))
matches = [m for m in inline_scripts if "ensureActiveDbRouteForAuth" in m.group(1)]
if len(matches) != 1:
    raise SystemExit(f"Expected exactly one V12.1.27 inline Admin app script, found {len(matches)}")
m = matches[0]
html = html[:m.start(1)] + helpers + "\n" + html[m.start(1):]
for token in [
 MARKER,
 "async function loadFreeTestPolicy()",
 "admin_get_free_test_policy",
 "admin_set_free_test_policy",
 "082298316902",
 "function schedulePcShutdown()",
 "function cancelPcShutdown()",
]:
 if token not in html:
  raise SystemExit("V12.1.28 feature assertion missing: " + token)

gradle = gradle.replace("versionCode 55", "versionCode 56", 1)
gradle = gradle.replace("versionName '12.1.27'", "versionName '12.1.28'", 1)
if "versionCode 56" not in gradle or "versionName '12.1.28'" not in gradle:
 raise SystemExit("V12.1.28 version update failed")
HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
VERSION.write_text("AniGames Admin Android V12.1.28 — based on V12.1.27; owner-only FREE TEST 10-minute policy + targeted PC shutdown timer with explicit cancel command\n", encoding="utf-8")
print("PASS: Admin V12.1.28 free-test policy UI + target-PC shutdown schedule/cancel markers are present; server must enforce authorization.")
