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
 const role = String(ctx?.role || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
 return ['owner', 'master', 'super_admin', 'superadmin'].includes(role);
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
if "Pairing WoL hanya tersedia untuk Master/Owner." in html:
    raise SystemExit("Stale V12.1.47 pairing denial message remains.")

gradle, n1 = re.subn(r"\bversionCode\s+76\b", "versionCode 77", gradle, count=1)
gradle, n2 = re.subn(r"versionName\s*'12\.1\.48'", "versionName '12.1.49'", gradle, count=1)
if n1 != 1 or n2 != 1:
    raise SystemExit("Admin version update anchor mismatch.")

html += "\n<!-- " + MARKER + " -->\n"
for token in (MARKER, "function isWakeRelayOwner()", "if (!isWakeRelayOwner())",
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
