from pathlib import Path
import re

HTML = Path("android/app/src/main/assets/web/admin.html")
GRADLE = Path("android/app/build.gradle")
VERSION = Path("VERSION.txt")

if not HTML.is_file() or not GRADLE.is_file():
    raise SystemExit("Admin Android source root is missing.")

html = HTML.read_text(encoding="utf-8")
gradle = GRADLE.read_text(encoding="utf-8")
marker = "V12.1.41-DASHBOARD-30D-REPORT"

if marker in html:
    if "versionCode 69" in gradle and "versionName '12.1.41'" in gradle:
        print("PASS: Admin V12.1.41 dashboard report patch already applied.")
        raise SystemExit(0)
    raise SystemExit("V12.1.41 marker/version mismatch.")

if "V12.1.40-ADMIN-NO-SHUTDOWN" not in html:
    raise SystemExit("Expected Admin V12.1.40 no-shutdown baseline.")
if "versionCode 68" not in gradle or "versionName '12.1.40'" not in gradle:
    raise SystemExit("Expected exact Admin V12.1.40 Gradle version metadata.")

# Add a real 30-day daily table directly below the existing dashboard charts.
anchor = '<div class="card activity-card" style="margin-top:12px"><div class="top"><div><b>Aktivitas Admin Terbaru</b>'
if html.count(anchor) != 1:
    raise SystemExit("Dashboard activity-card anchor mismatch.")
dashboard_table = '''<div class="card" id="dashboardReport30dCard" style="margin-top:12px">
 <div class="top"><div><b>Riwayat pemakaian 30 hari</b><div class="muted">Rekap sesi dimulai dan durasi aktif dari data rental tersimpan.</div></div><span id="dashboardReportPeriod" class="pill">Memuat periode…</span></div>
 <div class="table-wrap"><table class="table"><thead><tr><th>Tanggal</th><th>Sesi dimulai</th><th>Jam aktif</th></tr></thead><tbody id="dashboardReportRows"><tr><td colspan="3" class="empty">Memuat laporan 30 hari…</td></tr></tbody></table></div>
 <div id="dashboardReportMeta" class="muted" style="margin-top:8px">Mengambil data laporan dari database…</div>
</div>'''
html = html.replace(anchor, dashboard_table + anchor, 1)

# Dashboard boot/refresh previously loaded only PC devices; add the report fetch.
refresh_old = "await Promise.all([loadDevices()]);"
if html.count(refresh_old) != 1:
    raise SystemExit("Dashboard refresh function anchor mismatch.")
html = html.replace(refresh_old, "await Promise.all([loadDevices(),loadDashboardReport30d()]);", 1)

dashboard_js = r'''
let dashboardReportRequestSeq = 0;
function dashboardReportActiveSeconds(row, rangeFromMs, rangeToMs, nowMs) {
 if (String(row?.status || '').toLowerCase() === 'paused') return 0;
 const started = Date.parse(row?.started_at || '');
 if (!Number.isFinite(started)) return 0;
 const endedRaw = row?.ended_at ? Date.parse(row.ended_at)
  : row?.deadline_at ? Date.parse(row.deadline_at) : nowMs;
 const ended = Math.min(Number.isFinite(endedRaw) ? endedRaw : nowMs, nowMs, rangeToMs);
 const clippedStart = Math.max(started, rangeFromMs);
 const clippedEnd = Math.min(ended, rangeToMs);
 const overlap = Math.max(0, clippedEnd - clippedStart) / 1000;
 const reported = Number(row?.seconds_played);
 return Number.isFinite(reported) ? Math.min(overlap, Math.max(0, reported)) : overlap;
}
function drawDashboardReport30d(daily, users) {
 const trend = $('trendChart'), mix = $('categoryChart');
 if (!window.Chart || !trend || !mix) return;
 destroy('dashboard30Trend');
 destroy('dashboard30Mix');
 const labels = daily.map(x => x.date.slice(8,10) + '/' + x.date.slice(5,7));
 const trendValues = daily.map(x => Number(x.active_seconds || 0) / 3600);
 charts.dashboard30Trend = new Chart(trend, {
  type: 'line',
  data: { labels, datasets: [{ label: 'Jam aktif', data: trendValues, tension: .25, fill: true }] },
  options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true } }, scales: { y: { beginAtZero: true } } }
 });
 const topUsers = users.filter(x => Number(x.active_seconds || 0) > 0).slice(0,8);
 charts.dashboard30Mix = new Chart(mix, {
  type: 'doughnut',
  data: {
   labels: topUsers.length ? topUsers.map(x => x.user_id) : ['Belum ada data'],
   datasets: [{ label: 'Jam aktif', data: topUsers.length ? topUsers.map(x => Number(x.active_seconds || 0) / 3600) : [0] }]
  },
  options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true, position: 'bottom' } } }
 });
}
async function loadDashboardReport30d() {
 const orgId = currentOrg?.id;
 if (!orgId) return;
 const requestId = ++dashboardReportRequestSeq;
 const nowMs = Date.now();
 const today = jakartaDateString(new Date(nowMs));
 const firstMidnightMs = new Date(today + 'T00:00:00+07:00').getTime() - 29 * 864e5;
 const fromDay = jakartaDateString(new Date(firstMidnightMs));
 const toExclusiveMs = firstMidnightMs + 30 * 864e5;
 const fromIso = new Date(firstMidnightMs).toISOString();
 const toIso = new Date(toExclusiveMs).toISOString();
 const body = $('dashboardReportRows');
 const period = $('dashboardReportPeriod');
 const meta = $('dashboardReportMeta');
 if (period) period.textContent = fromDay + ' — ' + today;
 if (body) body.innerHTML = '<tr><td colspan="3" class="empty">Memuat laporan 30 hari…</td></tr>';
 if (meta) meta.textContent = 'Mengambil data sesi rental tersimpan…';
 destroy('dashboard30Trend');
 destroy('dashboard30Mix');
 try {
  // The existing report RPC uses cursor paging (max 500 rows/page). Fetch only
  // this 30-day window and cap total pages so a busy workspace cannot exhaust mobile memory.
  let cursor = null, rows = [], pages = 0;
  do {
   const page = await requestReportPage(fromIso, toIso, cursor, 500);
   if (!Array.isArray(page?.rows)) throw new Error('Format data laporan 30 hari tidak valid.');
   rows.push(...page.rows);
   if (page?.has_more !== true) break;
   if (!page?.next_cursor) throw new Error('Cursor laporan 30 hari tidak lengkap.');
   cursor = page.next_cursor;
   pages += 1;
   if (pages >= 20) throw new Error('Data 30 hari melebihi batas aman 10.000 sesi. Buka menu Laporan untuk melihat data bertahap.');
  } while (true);

  if (requestId !== dashboardReportRequestSeq || currentOrg?.id !== orgId) return;

  const daily = Array.from({length:30}, (_,i) => {
   const ms = firstMidnightMs + i * 864e5;
   const date = jakartaDateString(new Date(ms));
   return { date, sessions: 0, active_seconds: 0 };
  });
  const dailyMap = new Map(daily.map(x => [x.date, x]));
  const userMap = new Map();
  const rangeEndMs = Math.min(toExclusiveMs, nowMs + 1);
  let totalSessionsStarted = 0;

  for (const row of rows) {
   const playDate = String(row?.play_date || '').slice(0,10);
   const userId = String(row?.code || row?.user_id || 'Tanpa nama');
   const sessionSeconds = dashboardReportActiveSeconds(row, firstMidnightMs, rangeEndMs, nowMs);
   const startMs = Date.parse(row?.started_at || '');
   if (playDate >= fromDay && playDate <= today && dailyMap.has(playDate)) {
    dailyMap.get(playDate).sessions += 1;
    totalSessionsStarted += 1;
   }
   const user = userMap.get(userId) || { user_id: userId, sessions: 0, active_seconds: 0 };
   user.sessions += 1;
   user.active_seconds += sessionSeconds;
   userMap.set(userId, user);

   if (!Number.isFinite(startMs) || sessionSeconds <= 0) continue;
   const endCandidate = row?.ended_at ? Date.parse(row.ended_at)
    : row?.deadline_at ? Date.parse(row.deadline_at) : nowMs;
   const endMs = Math.min(Number.isFinite(endCandidate) ? endCandidate : nowMs, nowMs, rangeEndMs);
   const rawOverlap = Math.max(0, Math.min(endMs,rangeEndMs) - Math.max(startMs,firstMidnightMs)) / 1000;
   if (rawOverlap <= 0) continue;
   const scale = Math.min(1, sessionSeconds / rawOverlap);
   for (const item of daily) {
    const dayStart = new Date(item.date + 'T00:00:00+07:00').getTime();
    const dayEnd = dayStart + 864e5;
    const seconds = Math.max(0, Math.min(endMs,dayEnd,rangeEndMs) - Math.max(startMs,dayStart,firstMidnightMs)) / 1000;
    item.active_seconds += seconds * scale;
   }
  }

  const users = Array.from(userMap.values()).sort((a,b) => b.active_seconds - a.active_seconds);
  const dailyTotalSeconds = daily.reduce((sum,x) => sum + x.active_seconds, 0);
  const fmtHours = value => Number(value || 0).toLocaleString('id-ID',{minimumFractionDigits:2,maximumFractionDigits:2});
  if (body) body.innerHTML = daily.slice().reverse().map(x =>
   '<tr><td>' + esc(x.date) + '</td><td>' + Number(x.sessions).toLocaleString('id-ID') +
   '</td><td><b>' + fmtHours(x.active_seconds / 3600) + ' jam</b></td></tr>'
  ).join('');
  if ($('kSessions')) $('kSessions').textContent = totalSessionsStarted.toLocaleString('id-ID');
  if (meta) meta.textContent = totalSessionsStarted.toLocaleString('id-ID') + ' sesi dimulai • ' +
   fmtHours(dailyTotalSeconds / 3600) + ' jam aktif • ' + rows.length.toLocaleString('id-ID') +
   ' sesi terbaca melalui halaman bertahap';
  drawDashboardReport30d(daily, users);
 } catch(e) {
  if (requestId !== dashboardReportRequestSeq || currentOrg?.id !== orgId) return;
  if (body) body.innerHTML = '<tr><td colspan="3" class="empty">Laporan gagal dimuat.</td></tr>';
  if (meta) meta.textContent = String(e?.message || 'Gagal memuat laporan dashboard.');
 }
}
'''
load_anchor = "async function loadReport(){"
if html.count(load_anchor) != 1:
    raise SystemExit("Report loader insertion point mismatch.")
html = html.replace(load_anchor, dashboard_js + "\n" + load_anchor, 1)

# Add the release marker before checking the final required feature set.
base_marker = "V12.1.40-ADMIN-NO-SHUTDOWN"
if html.count(base_marker) != 1:
    raise SystemExit("Expected exactly one V12.1.40 no-shutdown marker.")
html = html.replace(base_marker, base_marker + " • " + marker, 1)

# Verify the report table and 30-day loader are wired to the existing authorized paginated RPC.
for required in (
    marker,
    'id="dashboardReport30dCard"',
    'id="dashboardReportPeriod"',
    'id="dashboardReportRows"',
    'id="dashboardReportMeta"',
    'async function loadDashboardReport30d()',
    "requestReportPage(fromIso, toIso, cursor, 500)",
    "report_detailed_usage_page",
    "drawDashboardReport30d(daily, users)",
    "loadDevices(),loadDashboardReport30d()",
    "dashboardReportActiveSeconds",
    "V12.1.40-ADMIN-NO-SHUTDOWN",
    "pcShutdownTimerCard", # checked as absent below, not a required positive marker
):
    if required == "pcShutdownTimerCard":
        continue
    if required not in html:
        raise SystemExit("Dashboard report integration is missing: " + required)

for forbidden in (
    "pcShutdownTimerCard", "shutdownTimerNav", "shutdownHours", "shutdownMinutes",
    "shutdownSeconds", "schedulePcShutdown", "cancelPcShutdown",
    "schedule_shutdown", "cancel_shutdown_timer", "refreshShutdownTargetOptions",
):
    if forbidden in html:
        raise SystemExit("Shutdown timer regression: " + forbidden)

for required in (
    "wakeRelayCard", "wakeRelayVersionSupported", "wake_on_lan_relay",
    "admin_rental_accounts_global", "admin_create_rental_global",
    "admin_update_rental_global", "admin_disable_rental_global",
    "V12.1.37-DAILY-REPORT-KEYSET-EXPORT", "report_summary_compact",
    "admin_get_free_test_policy", "admin_set_free_test_policy",
    "ensureActiveDbRouteForAuth", "dbSyncCall('start')",
    "requestSharedDbRouteSwitch", "offlineRestart=command==='restart_billing'",
    "Perintah Restart Billing masuk antrean",
):
    if required not in html:
        raise SystemExit("Existing feature regression: " + required)

gradle, code_count = re.subn(r"\bversionCode\s+68\b", "versionCode 69", gradle, count=1)
gradle, name_count = re.subn(r"versionName\s*'12\.1\.40'", "versionName '12.1.41'", gradle, count=1)
if code_count != 1 or name_count != 1:
    raise SystemExit("Could not safely update V12.1.40 version metadata.")

VERSION.write_text(
    "AniGames Admin Android V12.1.41 — adds 30-day dashboard report charts and daily table from authorized, cursor-paged rental sessions. Preserves no-shutdown timer removal, login, pairing, FREE TEST, PC/WoL, reseller, global rentals and dual-DB routing.\n",
    encoding="utf-8",
)

ids = re.findall(r'\bid=["\']([^"\']+)', html)
duplicates = sorted({value for value in ids if ids.count(value) > 1})
if duplicates:
    raise SystemExit("Duplicate HTML IDs after dashboard patch: " + ", ".join(duplicates))

HTML.write_text(html, encoding="utf-8")
GRADLE.write_text(gradle, encoding="utf-8")
print("PASS: Dashboard now loads 30 days of real rental-session data on login/refresh.")
print("PASS: 30 daily rows include sessions started and elapsed active time; no synthetic report rows.")
print("PASS: chart data uses bounded keyset paging (500 rows/page; 10,000-session safety cap).")
print("PASS: Timer Shutdown PC remains absent; WoL, Restart Billing queue, reports and dual-DB preserved.")
print("PASS: Admin V12.1.41 / versionCode 69; all HTML IDs remain unique.")
