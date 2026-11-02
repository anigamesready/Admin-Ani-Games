from pathlib import Path
import re

HTML = Path("android/app/src/main/assets/web/admin.html")
GRADLE = Path("android/app/build.gradle")
VERSION = Path("VERSION.txt")

if not HTML.is_file() or not GRADLE.is_file():
    raise SystemExit("Admin Android source root is missing.")

html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")
marker = "V12.1.42-RENTAL-LEASE-EDIT-FIX"

if marker in html:
    if "versionCode 70" in gradle and "versionName '12.1.42'" in gradle:
        print("PASS: Admin V12.1.42 rental edit/UI patch already applied.")
        raise SystemExit(0)
    raise SystemExit("V12.1.42 marker/version mismatch.")

if "V12.1.41-DASHBOARD-30D-REPORT" not in html:
    raise SystemExit("Expected exact Admin V12.1.41 dashboard 30-day baseline.")
if "versionCode 69" not in gradle or "versionName '12.1.41'" not in gradle:
    raise SystemExit("Expected exact Admin V12.1.41 Gradle version metadata.")

# On Android WebView, non-.field selects (global DB and PC selectors) inherited
# the light native select surface. Set a consistent dark form palette globally.
css_anchor = "</style>"
dark_controls_css = """
/* V12.1.42: dark native controls across all Admin sections, including top-level selectors. */
:root{color-scheme:dark}
input,select,textarea{color-scheme:dark}
select{
  background-color:#061424!important;
  color:#eaf4ff!important;
  border:1px solid #294966!important;
  border-radius:10px;
  padding:10px 12px;
  accent-color:#42d6ff;
}
select option{background:#0c1b2d;color:#eaf4ff}
.db-switch select,#globalDeviceSelect{background-color:#061424!important;color:#eaf4ff!important;border-color:#294966!important}
input[type="date"]{color-scheme:dark}
input[type="date"]::-webkit-calendar-picker-indicator{filter:invert(1)}
"""
if html.count(css_anchor) != 1:
    raise SystemExit("Admin stylesheet closing anchor mismatch.")
html = html.replace(css_anchor, dark_controls_css + "\n" + css_anchor, 1)

# Explain lease semantics instead of implying that a device must be online before saving.
old_modal_note = '<div class="muted">Perubahan kode/status disimpan ke rental cloud. Pastikan PC online untuk sinkronisasi; jika PC tidak mengonfirmasi, periksa data PC sebelum digunakan.</div>'
new_modal_note = '<div class="muted">Perubahan langsung disimpan ke database bersama dan tidak menunggu PC online. Jika ada lease/reservasi lama, reservasi itu tetap dijaga sampai kedaluwarsa agar kode tidak dipakai ganda. PC pemegang lease mengambil data terbaru saat koneksi/lookup berikutnya.</div>'
if html.count(old_modal_note) != 1:
    raise SystemExit("Edit modal helper-text anchor mismatch.")
html = html.replace(old_modal_note, new_modal_note, 1)

# Map database errors to actionable messages while retaining unknown error detail.
error_anchor = "async function saveAdminRentalEdit(){"
friendly = """function rentalAdminFriendlyError(error){
 const raw=String(error?.message||error||'Kesalahan tidak diketahui');
 const code=raw.toUpperCase();
 if(code.includes('RENTAL_ACTIVE_TIMER_LOCKED'))return 'Rental sedang dipakai dalam sesi aktif/paused. Akhiri sesi dari PC yang sedang memakai rental sebelum mengubah kode, durasi, expiry, atau status.';
 if(code.includes('RENTAL_HAS_OFFLINE_LEASE'))return 'Database lama masih menahan lease reservasi. Data rental tidak dihapus; refresh lalu coba lagi setelah server memperbarui aturan lease.';
 if(code.includes('CODE_ALREADY_EXISTS'))return 'Kode rental sudah dipakai akun lain. Gunakan kode yang berbeda.';
 if(code.includes('RENTAL_CODE_INVALID')||code.includes('RENTAL_FIELDS_INVALID'))return 'Kode rental tidak valid. Periksa kembali kode yang dimasukkan.';
 if(code.includes('RENTAL_MINUTES_INVALID'))return 'Sisa menit berada di luar batas yang diizinkan.';
 if(code.includes('RENTAL_CATEGORY_INVALID'))return 'Kategori rental tidak dikenali. Pilih kategori yang tersedia.';
 if(code.includes('RENTAL_STATUS_INVALID'))return 'Status rental tidak valid.';
 if(code.includes('EXPIRY_MUST_BE_FUTURE'))return 'Tanggal expired harus berada di masa depan.';
 if(code.includes('SYNC_WRITE_QUIESCE_ACTIVE'))return 'Database sedang dikunci sementara untuk proses sinkronisasi. Coba lagi setelah proses selesai.';
 if(code.includes('ADMIN_ORG_ACCESS_DENIED'))return 'Akun ini tidak memiliki izin mengubah rental pada workspace tersebut.';
 return raw;
}
function rentalAdminLeaseNote(result){
 if(result?.lease_preserved!==true)return '';
 const until=result.lease_until?new Date(result.lease_until).toLocaleString('id-ID'):'waktu kedaluwarsa';
 return ' Reservasi PC sebelumnya tetap dijaga sampai '+until+' agar kode tidak digunakan ganda.';
}
"""
if html.count(error_anchor) != 1:
    raise SystemExit("Rental edit function insertion point mismatch.")
html = html.replace(error_anchor, friendly + error_anchor, 1)

old_success = "msg('Rental '+code+' langsung diperbarui di DB bersama. PC tidak perlu online.');"
new_success = "msg('Rental '+code+' berhasil diperbarui di database bersama.'+rentalAdminLeaseNote(r));"
if html.count(old_success) != 1:
    raise SystemExit("Edit success message anchor mismatch.")
html = html.replace(old_success, new_success, 1)

old_edit_catch = "catch(e){msg('Gagal edit '+st.code+': '+(e.message||'error'),true)}"
if html.count(old_edit_catch) != 1:
    raise SystemExit("Edit error handler anchor mismatch.")
html = html.replace(old_edit_catch, "catch(e){msg('Gagal edit '+st.code+': '+rentalAdminFriendlyError(e),true)}", 1)

old_disable_success = "msg('Rental '+code+' dinonaktifkan langsung di DB. Histori tetap tersimpan.');"
new_disable_success = "msg('Rental '+code+' berhasil dinonaktifkan. Histori tetap tersimpan.'+rentalAdminLeaseNote(r));"
if html.count(old_disable_success) != 1:
    raise SystemExit("Disable success message anchor mismatch.")
html = html.replace(old_disable_success, new_disable_success, 1)

old_disable_catch = "catch(e){msg('Gagal menonaktifkan '+code+': '+(e.message||'error'),true)}"
if html.count(old_disable_catch) != 1:
    raise SystemExit("Disable error handler anchor mismatch.")
html = html.replace(old_disable_catch, "catch(e){msg('Gagal menonaktifkan '+code+': '+rentalAdminFriendlyError(e),true)}", 1)

old_create_success = "msg('Rental '+code+' langsung tersimpan di DB bersama. Tidak perlu memilih PC atau menunggu PC online.');"
new_create_success = "msg('Rental '+code+' berhasil disimpan di database bersama untuk seluruh PC.');"
if html.count(old_create_success) != 1:
    raise SystemExit("Create success message anchor mismatch.")
html = html.replace(old_create_success, new_create_success, 1)

old_create_catch = "catch(e){msg('Gagal menambahkan rental: '+(e.message||'error tidak diketahui'),true)}"
if html.count(old_create_catch) != 1:
    raise SystemExit("Create error handler anchor mismatch.")
html = html.replace(old_create_catch, "catch(e){msg('Gagal menambahkan rental: '+rentalAdminFriendlyError(e),true)}", 1)

# Use a more precise heading/helper on the global rental form.
if html.count("<h3>Tambah Data Rental</h3>") != 1:
    raise SystemExit("Global rental form heading anchor mismatch.")
html = html.replace("<h3>Tambah Data Rental</h3>", "<h3>Tambah Data Rental Bersama</h3>", 1)

# Bump version and add an auditable marker.
gradle, c = re.subn(r"\bversionCode\s+69\b", "versionCode 70", gradle, count=1)
gradle, n = re.subn(r"versionName\s*'12\.1\.41'", "versionName '12.1.42'", gradle, count=1)
if c != 1 or n != 1:
    raise SystemExit("Could not safely update V12.1.41 Gradle version metadata.")

html = html.replace(
    "V12.1.41-DASHBOARD-30D-REPORT",
    "V12.1.41-DASHBOARD-30D-REPORT • " + marker,
    1,
)
VERSION.write_text(
    "AniGames Admin Android V12.1.42 — fixes global rental edit/disable UX after DB lease policy change; dark theme for all form selectors; keeps V12.1.40 no-shutdown and V12.1.41 dashboard 30-day reporting.\n",
    encoding="utf-8",
)

for required in (
    marker, "admin_update_rental_global", "admin_create_rental_global",
    "admin_disable_rental_global", "rentalAdminFriendlyError",
    "rentalAdminLeaseNote", "Reservasi PC sebelumnya tetap dijaga",
    "dashboardReportRows", "loadDashboardReport30d",
    "V12.1.40-ADMIN-NO-SHUTDOWN",
    "wakeRelayCard", "wake_on_lan_relay",
    "admin_rental_accounts_global", "offlineRestart=command==='restart_billing'",
    "dbSyncCall('start')", "requestSharedDbRouteSwitch",
):
    if required not in html:
        raise SystemExit("Rental/UI regression: missing " + required)

for forbidden in (
    "pcShutdownTimerCard", "shutdownTimerNav", "shutdownHours", "shutdownMinutes",
    "shutdownSeconds", "schedulePcShutdown", "cancelPcShutdown",
    "schedule_shutdown", "cancel_shutdown_timer",
):
    if forbidden in html:
        raise SystemExit("Removed shutdown timer has reappeared: " + forbidden)

if html.count("rentalAdminFriendlyError") < 4:
    raise SystemExit("Rental error translation is not wired to create/edit/disable.")
ids = re.findall(r'\bid=["\']([^"\']+)', html)
duplicates = sorted({value for value in ids if ids.count(value) > 1})
if duplicates:
    raise SystemExit("Duplicate HTML IDs after V12.1.42 patch: " + ", ".join(duplicates))

HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
print("PASS: global rental add/edit/disable remain independent of selected PC status.")
print("PASS: user-facing errors are translated; active/paused session lock is explained.")
print("PASS: all select controls use dark surfaces on Android WebView.")
print("PASS: no-shutdown menu remains absent; 30-day dashboard, WoL and dual-DB retained.")
print("PASS: Admin V12.1.42 / versionCode 70; HTML IDs unique.")
