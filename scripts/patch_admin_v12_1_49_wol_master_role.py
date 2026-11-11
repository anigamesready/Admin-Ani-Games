from pathlib import Path
import re

HTML = Path("android/app/src/main/assets/web/admin.html")
GRADLE = Path("android/app/build.gradle")
VERSION = Path("VERSION.txt")
MARKER = "V12.1.49-ANDROID-WOL-PAIRING-ROLE-FIX"

if not HTML.is_file() or not GRADLE.is_file():
    raise SystemExit("Admin Android source root is missing.")
html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")

if MARKER in html:
    if "versionCode 77" in gradle and "versionName '12.1.49'" in gradle:
        print("PASS: V12.1.49 role fix already applied.")
        raise SystemExit(0)
    raise SystemExit("V12.1.49 marker/version mismatch.")

if "V12.1.48-ANDROID-WOL-RELAY-RELIABILITY" not in html:
    raise SystemExit("Expected exact V12.1.48 baseline.")
for token in ("createWakeRelayPairingCode", "wol_relay_create_enrollment",
              "report_detailed_usage_page", "report_summary_compact",
              "ensureActiveDbRouteForAuth", "admin_create_rental_global",
              "admin_update_rental_global", "admin_delete_rental_global"):
    if token not in html:
        raise SystemExit("Regression guard failed before role patch: " + token)

# Normalize the canonical role once. Do not grant the permission to generic admin/reseller roles.
owner_fn = r"""function isWakeRelayOwner() {
 const role = String(ctx?.role || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
 return ['owner', 'master', 'master_owner', 'owner_master', 'master_admin', 'admin_master', 'super_admin', 'superadmin'].includes(role);
}"""
html, n = re.subn(
    r"function isWakeRelayOwner\(\)\s*\{.*?\n\}",
    lambda _: owner_fn,
    html, count=1, flags=re.S
)
if n != 1:
    raise SystemExit("Could not safely locate canonical WoL role resolver.")

# Fix the pairing handler explicitly. Previous patch used a fragile function-boundary
# replacement; target the actual stale guard/message instead of relying on brace parsing.
old_guard = "if (ctx?.role !== 'owner') return msg('Pairing WoL hanya tersedia untuk Master/Owner.', true);"
if old_guard in html:
    html = html.replace(old_guard,
        "if (!isWakeRelayOwner()) return msg('Akses pairing WoL hanya untuk Master/Owner.', true);", 1)
else:
    # Accept an already-normalized guard, but reject an unknown handler shape.
    if "async function createWakeRelayPairingCode()" not in html:
        raise SystemExit("Pairing handler is missing.")
    start = html.find("async function createWakeRelayPairingCode()")
    end = html.find("\n}", start)
    if end < 0:
        raise SystemExit("Pairing handler boundary not found.")
    chunk = html[start:end+2]
    if "if (!isWakeRelayOwner())" not in chunk:
        raise SystemExit("Pairing handler has an unrecognized authorization guard.")
    html = html[:start] + chunk + html[end+2:]


# V12.1.48 accidentally left an unconditional legacy denial after the new role guard.
# Rebuild the entire pairing function rather than replacing only the guard fragment.
pairing_fn = r"""async function createWakeRelayPairingCode() {
 if (!isWakeRelayOwner()) return msg('Akses pairing WoL hanya untuk Master/Owner.', true);
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
}"""
def replace_all_functions(source, signature, replacement, label):
    pattern = re.compile(r"(?ms)^" + re.escape(signature) + r".*?^\}")
    matches = list(pattern.finditer(source))
    if not matches:
        raise SystemExit("Could not safely locate " + label)
    for match in reversed(matches):
        source = source[:match.start()] + replacement.rstrip() + source[match.end():]
    return source, len(matches)

html, pairing_count = replace_all_functions(
    html, "async function createWakeRelayPairingCode() {",
    pairing_fn, "createWakeRelayPairingCode")
if pairing_count != 1:
    raise SystemExit("Expected exactly one pairing handler; found " + str(pairing_count))

# The 47/48 patch chain left two requestWakePc2 declarations; the later one won
# at runtime and still checked ctx.role === owner directly. Normalize BOTH copies.
request_fn = r"""async function requestWakePc2() {
 if (!isWakeRelayOwner()) return msg('Akses hanya untuk Master/Owner.', true);
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
html, request_count = replace_all_functions(
    html, "async function requestWakePc2() {", request_fn, "requestWakePc2")
if request_count < 2:
    raise SystemExit("Expected both legacy and active WoL handlers; found " + str(request_count))

# Remove any remaining legacy role guard in the earlier navigation function as well.
menu_fn = r"""function openWakeRelayMenu() {
 if (!isWakeRelayOwner()) return msg('Akses WoL hanya untuk Master/Owner.', true);
 tab('devices');
 setTimeout(() => {
  const card = $('wakeRelayCard');
  if (card) card.scrollIntoView({behavior:'smooth', block:'start'});
  refreshWakeRelayDevices();
 }, 120);
}"""
html, menu_count = replace_all_functions(
    html, "function openWakeRelayMenu() {", menu_fn, "openWakeRelayMenu")
if menu_count < 1:
    raise SystemExit("WoL menu handler missing")


# Also ensure every WoL action uses the same explicit role resolver.
start = html.find("async function requestWakePc2()")
end = html.find("\n}", start)
if start < 0 or end < 0:
    raise SystemExit("WoL request handler is missing.")
request = html[start:end+2]
if "if (!isWakeRelayOwner())" not in request:
    raise SystemExit("WoL send handler is not protected by the canonical role resolver.")

if old_guard in html:
    raise SystemExit("Stale owner-only pairing guard remains.")
pair_start = html.find("async function createWakeRelayPairingCode()")
pair_end = html.find("\n}", pair_start)
pair_fn = html[pair_start:pair_end + 2] if pair_start >= 0 and pair_end >= 0 else ""
if not pair_fn or pair_fn.count("return msg('Akses pairing WoL hanya untuk Master/Owner.', true);") != 1:
    raise SystemExit("Pairing handler does not contain exactly one guarded denial.")
if "return msg('Pairing WoL hanya tersedia untuk Master/Owner.', true);" in pair_fn:
    raise SystemExit("Unconditional legacy pairing return remains.")
if len(re.findall(r"(?m)^async function requestWakePc2\(\) \{", html)) < 2:
    raise SystemExit("Expected both WoL request handler declarations to be normalized.")
for match in re.finditer(r"(?ms)^async function requestWakePc2\(\) \{.*?^\}", html):
    if "if (!isWakeRelayOwner())" not in match.group(0):
        raise SystemExit("A legacy WoL request handler still bypasses the shared role resolver.")
if "return msg('Pairing WoL hanya tersedia untuk Master/Owner.', true);" in html:
    raise SystemExit("Unconditional legacy pairing denial remains.")

gradle, n1 = re.subn(r"\bversionCode\s+76\b", "versionCode 77", gradle, count=1)
gradle, n2 = re.subn(r"versionName\s*'12\.1\.48'", "versionName '12.1.49'", gradle, count=1)
if n1 != 1 or n2 != 1:
    raise SystemExit("Admin version update anchor mismatch.")

html += "\n<!-- " + MARKER + " -->\n"
for token in (MARKER, "function isWakeRelayOwner()", "if (!isWakeRelayOwner())",
              "Akses pairing WoL hanya untuk Master/Owner.",
              "wol_relay_create_enrollment", "wol_relay_enqueue",
              "report_detailed_usage_page", "report_summary_compact",
              "ensureActiveDbRouteForAuth"):
    if token not in html:
        raise SystemExit("V12.1.49 assertion failed: " + token)

HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
VERSION.write_text("AniGames Admin Android V12.1.49 — fix Master/Owner authorization for Android WoL pairing and send actions.\n", encoding="utf-8")
print("PASS: Master/Owner role normalization applied to pairing and WoL actions.")
print("PASS: generic admin/reseller roles remain excluded.")
print("PASS: stale V12.1.47 pairing denial guard removed.")
print("PASS: rental, billing, reports and DB routing regression guards preserved.")
print("PASS: Admin V12.1.49 / versionCode 77.")
