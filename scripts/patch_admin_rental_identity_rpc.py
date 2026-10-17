from pathlib import Path

html_path = Path("android/app/src/main/assets/web/admin.html")
gradle_path = Path("android/app/build.gradle")
version_path = Path("VERSION.txt")

html = html_path.read_text(encoding="utf-8")

old = (
    "const up=await sb.from('rental_accounts').update({code, status})"
    ".eq('id',st.id).eq('org_id',currentOrg.id).eq('device_id',selectedDeviceId)"
    ".select('id');"
    "if(up.error)throw new Error('Data durasi tersimpan, tetapi kode/status gagal diperbarui: '+up.error.message);"
    "if(!up.data?.length)throw new Error('Kode/status tidak berubah: rental tidak ditemukan atau akses ditolak.')"
)
new = (
    "const up=await rpc('admin_update_rental_identity',{"
    "p_org_id:currentOrg.id,"
    "p_device_id:selectedDeviceId,"
    "p_rental_id:st.id,"
    "p_code:code,"
    "p_status:status"
    "});"
    "if(up?.ok!==true)throw new Error('Kode/status tidak berubah: rental tidak ditemukan atau akses ditolak.')"
)

count = html.count(old)
if count != 1:
    raise SystemExit(
        f"Rental identity direct-update anchor expected once, found {count}; refusing to patch"
    )

html = html.replace(old, new, 1)

if "sb.from('rental_accounts').update({code, status})" in html:
    raise SystemExit("Direct rental code/status update remains; refusing to build")
if html.count("rpc('admin_update_rental_identity'") != 1:
    raise SystemExit("Expected exactly one admin_update_rental_identity RPC call")

gradle = gradle_path.read_text(encoding="utf-8")
if "versionCode 36" not in gradle or "versionName '12.1.8'" not in gradle:
    raise SystemExit("Unexpected Android baseline version; expected v12.1.8 / code 36")
gradle = gradle.replace("versionCode 36", "versionCode 37", 1)
gradle = gradle.replace("versionName '12.1.8'", "versionName '12.1.9'", 1)

html_path.write_text(html, encoding="utf-8")
gradle_path.write_text(gradle, encoding="utf-8")
version_path.write_text("v12.1.9-db1-rental-identity-rpc-hardening\n", encoding="utf-8")

print("Patched rental code/status editing to use audited RPC; bumped Android version to 12.1.9 / versionCode 37")
