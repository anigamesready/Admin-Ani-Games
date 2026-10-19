from pathlib import Path
import re

html_path = Path("android/app/src/main/assets/web/admin.html")
html = html_path.read_text(encoding="utf-8")

new = """if(!recoveringPartial){
   const a=d1.route,b=d2.route;
   const dataMismatch=!a.data_parity_ready||!b.data_parity_ready||!a.backup_ready||!b.backup_ready||!a.auth_parity_ready||!b.auth_parity_ready;
   if(dataMismatch){
    const note='Pengecekan otomatis menemukan data atau login DB1 dan DB2 belum identik. Belum ada data yang disalin dan database aktif tidak berubah. Diarahkan ke Database & Sync: jalankan Preview perbedaan, sinkronkan dari DB aktif ke standby, lalu verifikasi login owner/admin sebelum mencoba pindah lagi.';
    try{const summary=$('dbSyncPreviewSummary');if(summary)summary.textContent=note;const routeState=$('dbSyncRouteState');if(routeState)routeState.textContent=note;tab('databaseTools');}catch(_){}
    throw new Error('DB_SYNC_REQUIRED: parity data/auth belum cocok; Admin diarahkan ke Database & Sync untuk preview, copy, dan verifikasi lebih dahulu.');
   }
   if(!routeReadyForSwitch(a)||!routeReadyForSwitch(b)||a.schema_version!==b.schema_version){
    const note='Data/auth ditandai cocok, tetapi gateway bersama, versi schema, atau pemeriksaan parity terbaru belum lulus. Pindah DB tetap dikunci sampai pemeriksaan tersebut lulus.';
    try{const summary=$('dbSyncPreviewSummary');if(summary)summary.textContent=note;tab('databaseTools');}catch(_){}
    throw new Error('CUTOVER_GATEWAY_OR_SCHEMA_NOT_READY: '+note);
   }
  }else{"""

if "DB_SYNC_REQUIRED: parity data/auth belum cocok" in html:
    print("Copy-first switch guard already applied.")
    raise SystemExit(0)

pattern = re.compile(
    r"if\(!recoveringPartial\)\s*\{[\s\S]*?"
    r"const sync=await requestDbSync\(\{holdQuiesce:true\}\);[\s\S]*?"
    r"\[d1,d2\]=await Promise\.all\(\[[\s\S]*?"
    r"globalRouteStatus\(DB2_URL,DB2_ROUTE_KEY,'xcdbipgsvohesxhxydep'\)\s*\]\);\s*\}\s*else\s*\{"
)
matches = list(pattern.finditer(html))
if len(matches) != 1:
    old = """if(!recoveringPartial){
   // A fresh catch-up sync is required before starting a new epoch/switch ID.
   const sync=await requestDbSync({holdQuiesce:true});
   if(!sync||sync.ok===false||sync.ready!==true)throw new Error('SYNC_NOT_READY: final sync/hash/auth/gateway verification did not complete; active database was not switched.');
   [d1,d2]=await Promise.all([
    globalRouteStatus(DB1_URL,DB1_ROUTE_KEY,'wzkjpycjizexxcxrfdvr'),
    globalRouteStatus(DB2_URL,DB2_ROUTE_KEY,'xcdbipgsvohesxhxydep')
   ]);
  }else{"""
    if html.count(old) == 1:
        html = html.replace(old, new, 1)
    else:
        raise SystemExit("Expected one guarded DB switch sync block; regex matches=" + str(len(matches)) + ", exact matches=" + str(html.count(old)))
else:
    match = matches[0]
    html = html[:match.start()] + new + html[match.end():]

if "DB_SYNC_REQUIRED: parity data/auth belum cocok" not in html:
    raise SystemExit("Post-patch DB switch guard token missing")
if "ROUTE_FINAL_CONFIRMATION_FAILED" not in html or "function requestGlobalDbSwitch()" not in html:
    raise SystemExit("Global DB switch integrity checks missing")

html_path.write_text(html, encoding="utf-8")
print("DB cutover preflight updated: parity mismatch is redirected to Database & Sync; no implicit copy is started.")
