from pathlib import Path

html_path = Path("android/app/src/main/assets/web/admin.html")
html = html_path.read_text(encoding="utf-8")

old = """if(!recoveringPartial){
   // A fresh catch-up sync is required before starting a new epoch/switch ID.
   const sync=await requestDbSync({holdQuiesce:true});
   if(!sync||sync.ok===false||sync.ready!==true)throw new Error('SYNC_NOT_READY: final sync/hash/auth/gateway verification did not complete; active database was not switched.');
   [d1,d2]=await Promise.all([
    globalRouteStatus(DB1_URL,DB1_ROUTE_KEY,'wzkjpycjizexxcxrfdvr'),
    globalRouteStatus(DB2_URL,DB2_ROUTE_KEY,'xcdbipgsvohesxhxydep')
   ]);
  }else{"""

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

n = html.count(old)
if n == 0 and new in html:
    print("Copy-first switch guard already applied.")
else:
    if n != 1:
        raise SystemExit("Expected exactly one global switch sync block; found " + str(n))
    html = html.replace(old, new, 1)
    html_path.write_text(html, encoding="utf-8")
    print("DB cutover preflight now redirects to Database & Sync on parity mismatch; no implicit copy is started.")
