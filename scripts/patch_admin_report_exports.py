from pathlib import Path
import re

ROOT = Path('.')
HTML = ROOT / 'android/app/src/main/assets/web/admin.html'
ACTIVITY = ROOT / 'android/app/src/main/java/com/anigames/billingadmin/MainActivity.java'
html = HTML.read_text(encoding='utf-8')
activity = ACTIVITY.read_text(encoding='utf-8')

# Fix charts ReferenceError: report rendering calls charts[id] but never declares charts.
chart_anchor = 'function destroy(id){if(charts[id])charts[id].destroy()}'
if 'var charts=window.charts||(window.charts={});' not in html:
    if html.count(chart_anchor) != 1:
        raise SystemExit('charts initialization anchor mismatch')
    html = html.replace(chart_anchor, 'var charts=window.charts||(window.charts={});\n' + chart_anchor, 1)

# Add a real Android Downloads writer to the existing AniAdminNative JavaScript bridge.
required = ['import android.os.Build;', 'import android.net.Uri;', 'import android.webkit.JavascriptInterface;',
            'private class AdminNotificationBridge {', 'addJavascriptInterface(new AdminNotificationBridge(), "AniAdminNative")']
for item in required:
    if item not in activity:
        raise SystemExit('Required Android notification bridge part is missing: ' + item)
new_imports = [
    'import android.content.ContentValues;', 'import android.os.Environment;',
    'import android.provider.MediaStore;', 'import android.util.Base64;',
    'import java.io.File;', 'import java.io.FileOutputStream;', 'import java.io.OutputStream;'
]
anchor_import = 'import android.webkit.JavascriptInterface;'
extra = '\n'.join(x for x in new_imports if x not in activity)
if extra:
    activity = activity.replace(anchor_import, anchor_import + '\n' + extra, 1)
if 'saveReportFile(String filename, String mimeType, String base64Payload)' not in activity:
    anchor = '    }\n\n    @Override public void onRequestPermissionsResult'
    if activity.count(anchor) != 1:
        raise SystemExit('AdminNotificationBridge closing anchor mismatch')
    method = r'''        @JavascriptInterface public String saveReportFile(String filename, String mimeType, String base64Payload) {
            Uri savedUri = null;
            try {
                String safeName = filename == null ? "laporan" : filename.trim();
                safeName = safeName.replaceAll("[^A-Za-z0-9._-]", "_");
                if (safeName.isEmpty() || safeName.equals(".") || safeName.equals("..")) safeName = "laporan";
                if (safeName.length() > 120) safeName = safeName.substring(0, 120);
                String safeMime = (mimeType == null || mimeType.trim().isEmpty()) ? "application/octet-stream" : mimeType.trim();
                if (base64Payload == null || base64Payload.isEmpty()) return "ERROR:Data file kosong.";
                if (base64Payload.length() > 24 * 1024 * 1024) return "ERROR:File laporan terlalu besar (maksimal 18 MB).";
                byte[] bytes = Base64.decode(base64Payload, Base64.DEFAULT);
                if (bytes.length == 0) return "ERROR:File laporan kosong.";
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    ContentValues values = new ContentValues();
                    values.put(MediaStore.MediaColumns.DISPLAY_NAME, safeName);
                    values.put(MediaStore.MediaColumns.MIME_TYPE, safeMime);
                    values.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/Ani Games Reports");
                    values.put(MediaStore.MediaColumns.IS_PENDING, 1);
                    savedUri = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
                    if (savedUri == null) return "ERROR:Android tidak dapat membuat file di folder Downloads.";
                    try (OutputStream output = getContentResolver().openOutputStream(savedUri, "w")) {
                        if (output == null) throw new java.io.IOException("Output stream tidak tersedia");
                        output.write(bytes);
                        output.flush();
                    }
                    ContentValues ready = new ContentValues();
                    ready.put(MediaStore.MediaColumns.IS_PENDING, 0);
                    getContentResolver().update(savedUri, ready, null, null);
                    return "OK:Downloads/Ani Games Reports/" + safeName;
                }
                File root = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
                if (root == null) return "ERROR:Folder penyimpanan aplikasi tidak tersedia.";
                File directory = new File(root, "Ani Games Reports");
                if (!directory.exists() && !directory.mkdirs()) return "ERROR:Gagal membuat folder laporan.";
                File outputFile = new File(directory, safeName);
                try (FileOutputStream output = new FileOutputStream(outputFile)) {
                    output.write(bytes);
                    output.flush();
                }
                return "OK:" + outputFile.getAbsolutePath();
            } catch (Exception e) {
                if (savedUri != null) { try { getContentResolver().delete(savedUri, null, null); } catch (Exception ignored) {} }
                String reason = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
                reason = reason.replaceAll("[\\r\\n]+", " ");
                if (reason.length() > 180) reason = reason.substring(0, 180);
                return "ERROR:Gagal menyimpan file laporan: " + reason;
            }
        }
'''
    activity = activity.replace(anchor, method + '    }\n\n    @Override public void onRequestPermissionsResult', 1)

helper = r'''function reportBlobToBase64(blob){
 return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onerror=()=>reject(new Error('File laporan tidak dapat dibaca untuk disimpan.'));reader.onload=()=>{const value=String(reader.result||''),comma=value.indexOf(',');if(comma<0)reject(new Error('Data file laporan tidak valid.'));else resolve(value.slice(comma+1));};reader.readAsDataURL(blob);});
}
async function saveReportFileDownload(blob,filename,mimeType){
 if(!blob||typeof blob.size!=='number'||blob.size<=0)throw new Error('File laporan kosong; tidak ada file yang disimpan.');
 const safeName=String(filename||'laporan').replace(/[^A-Za-z0-9._-]/g,'_').slice(0,120)||'laporan';
 const bridge=window.AniAdminNative;
 if(bridge&&typeof bridge.saveReportFile==='function'){
  const base64=await reportBlobToBase64(blob),result=String(bridge.saveReportFile(safeName,String(mimeType||'application/octet-stream'),base64)||'');
  if(!result.startsWith('OK:'))throw new Error(result.startsWith('ERROR:')?result.slice(6):'Android tidak mengonfirmasi penyimpanan file.');
  msg('✅ File berhasil disimpan. Lokasi: '+result.slice(3));return result.slice(3);
 }
 if(location.protocol==='file:')throw new Error('Fitur simpan file native tidak tersedia di APK ini. Build APK dengan bridge ekspor terbaru diperlukan.');
 const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=safeName;a.style.display='none';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
 msg('Unduhan dimulai. Periksa folder Downloads pada browser untuk file: '+safeName);return 'browser-download-started';
}
'''
helper_anchor = 'function exportExcelFallbackXLSX(){'
if 'async function saveReportFileDownload(' not in html:
    if html.count(helper_anchor) != 1:
        raise SystemExit('Excel fallback anchor mismatch')
    html = html.replace(helper_anchor, helper + 'async function exportExcelFallbackXLSX(){', 1)
else:
    html = html.replace(helper_anchor, 'async function exportExcelFallbackXLSX(){', 1)

fallback_pattern = re.compile(r"X\.writeFile\(wb,'laporan-'\+String\(currentOrg\?\.slug\|\|'rental'\)\+'-'\+String\(\$\('from'\)\?\.value\|\|'periode'\)\+'\.xlsx',\{compression:true\}\);\s*msg\('Excel berhasil diunduh \(5 sheet laporan; mode kompatibel XLSX\)\.'\);")
fallback_replacement = "const filename='laporan-'+String(currentOrg?.slug||'rental')+'-'+String($('from')?.value||'periode')+'.xlsx';\n const output=X.write(wb,{bookType:'xlsx',type:'array',compression:true});\n const blob=new Blob([output],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});\n await saveReportFileDownload(blob,filename,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');"
html, n = fallback_pattern.subn(fallback_replacement, html, count=1)
if n != 1:
    raise SystemExit('Excel XLSX fallback writer anchor mismatch')

# Await both XLSX fallback paths; do not let the caller report success before saving finishes.
html, calls = re.subn(r'(?<!function )exportExcelFallbackXLSX\(\);', 'await exportExcelFallbackXLSX();', html)
if calls != 2:
    raise SystemExit('Expected two Excel fallback call sites, found ' + str(calls))

excel_pattern = re.compile(r"const buf=await wb\.xlsx\.writeBuffer\(\);const blob=new Blob\(\[buf\],\{type:'application/vnd\.openxmlformats-officedocument\.spreadsheetml\.sheet'\}\);.*?msg\('✅ Excel berhasil dibuat dengan dashboard, grafik, tabel lengkap, dan rekap per user\.'\)")
excel_replacement = "const buf=await wb.xlsx.writeBuffer();const blob=new Blob([buf],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});const filename='laporan-'+String(currentOrg?.slug||'rental')+'-'+String($('from')?.value||'periode')+'.xlsx';await saveReportFileDownload(blob,filename,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')"
html, n = excel_pattern.subn(excel_replacement, html, count=1)
if n != 1:
    raise SystemExit('ExcelJS download block mismatch')

pdf_pattern = re.compile(r"doc\.save\([^;]+\);msg\('✅ PDF berhasil dibuat dengan dashboard, grafik, rekap per user/PC, dan detail sesi lengkap\.'\)")
pdf_replacement = "const filename='laporan-'+String(currentOrg?.slug||'rental')+'-'+String($('from')?.value||'periode')+'.pdf';await saveReportFileDownload(doc.output('blob'),filename,'application/pdf')"
html, n = pdf_pattern.subn(pdf_replacement, html, count=1)
if n != 1:
    raise SystemExit('PDF download block mismatch')

checks = [
    ('HTML charts initialization', 'var charts=window.charts||(window.charts={});' in html),
    ('HTML native save helper', 'async function saveReportFileDownload(' in html),
    ('HTML PDF blob save', "doc.output('blob')" in html),
    ('HTML old blind Excel success removed', 'Excel berhasil dibuat dengan dashboard' not in html),
    ('HTML old blind PDF success removed', 'PDF berhasil dibuat dengan dashboard' not in html),
    ('Java native save method', 'saveReportFile(String filename, String mimeType, String base64Payload)' in activity),
    ('Java bridge imports', all(x in activity for x in ['import android.content.ContentValues;','import android.provider.MediaStore;','import java.io.OutputStream;'])),
]
failed = [label for label, ok in checks if not ok]
if failed:
    raise SystemExit('Post-patch verification failed: ' + ', '.join(failed))
HTML.write_text(html, encoding='utf-8')
ACTIVITY.write_text(activity, encoding='utf-8')
print('Patched report exports: declared charts; Excel/PDF saved through native Android storage; logs actual save path after write succeeds.')
