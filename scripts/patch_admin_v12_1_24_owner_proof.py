from pathlib import Path
import re

HTML=Path("android/app/src/main/assets/web/admin.html")
GRADLE=Path("android/app/build.gradle")
html=HTML.read_text(encoding="utf-8")
gradle=GRADLE.read_text(encoding="utf-8")
marker="V12.1.24-CROSS-PROJECT-OWNER-PROOF"
if marker in html:
    if "versionCode 52" not in gradle or "versionName '12.1.24'" not in gradle:
        raise SystemExit("V12.1.24 marker/version mismatch")
    print("PASS: Admin V12.1.24 owner-proof patch already applied")
    raise SystemExit(0)
if "V12.1.23-FINAL-ADMIN-PACKAGE" not in html or "versionName '12.1.23'" not in gradle:
    raise SystemExit("Expected V12.1.23 source")

def replace_fn(src,sig,replacement,label):
    pat=re.compile(r"(?ms)^"+re.escape(sig)+r".*?^\}")
    matches=list(pat.finditer(src))
    if len(matches)!=1: raise SystemExit(f"{label}: expected one function, found {len(matches)}")
    return src[:matches[0].start()]+replacement.rstrip()+src[matches[0].end():]

sync_fn=r"""
async function dbSyncCall(action,payload={}){
 const token=await adminAccessToken();
 const dest=DB_TARGET==='backup'?{url:DB1_URL,key:DB1_KEY,ref:'wzkjpycjizexxcxrfdvr'}:{url:DB2_URL,key:DB2_KEY,ref:'xcdbipgsvohesxhxydep'};
 const state=window.__aniGamesStandbyOwnerProof;
 const proofExempt=['verify-owner-login','verify-cutover-parity','status'].includes(action);
 if(!proofExempt&&(!state||state.projectRef!==dest.ref||!state.proof||Date.now()>=Number(state.expiresAt||0)))
  throw new Error('TARGET_OWNER_PROOF_REQUIRED: verifikasi login Owner DB tujuan lebih dulu.');
 const body={...payload,action,accessToken:token};
 if(!proofExempt)body.ownerProof=state.proof;
 const response=await fetch(dest.url+'/functions/v1/db-sync-apply',{method:'POST',headers:{apikey:dest.key,'content-type':'application/json',authorization:'Bearer '+token},body:JSON.stringify(body),cache:'no-store'});
 const data=await response.json().catch(()=>({}));
 if(!response.ok||data?.ok!==true)throw new Error(String(data?.error||('DB_SYNC_HTTP_'+response.status)));
 return data;
}
"""
html=replace_fn(html,"async function dbSyncCall(action,payload={}){",sync_fn,"Owner proof request routing")

# The backend returns a signed, 30-minute proof only after validating the source Owner and target-project password.
# Store that proof in runtime memory; never put the password, proof or access token into localStorage.
anchor="  window.__dbTargetLoginVerifiedAt=Date.now();window.__dbTargetLoginProjectRef=ref;"
if html.split(anchor).count(anchor)!=1: raise SystemExit("Owner proof storage anchor mismatch")
html=html.replace(anchor, """  if(!result?.ownerProof||!Number.isFinite(Number(result.expiresAt))||Number(result.expiresAt)<=Date.now())throw new Error('TARGET_OWNER_PROOF_NOT_ISSUED');
  window.__aniGamesStandbyOwnerProof={projectRef:ref,proof:String(result.ownerProof),expiresAt:Number(result.expiresAt)};
"""+anchor,1)
html=html.replace("window.__dbTargetLoginVerifiedAt=0;window.__dbTargetLoginProjectRef='';",
                  "window.__aniGamesStandbyOwnerProof=null;window.__dbTargetLoginVerifiedAt=0;window.__dbTargetLoginProjectRef='';",1)

syncAnchor="  dbSyncStatus('Semua halaman selesai. Memverifikasi row count + SHA-256 untuk 12 tabel…');"
if html.count(syncAnchor)!=1: raise SystemExit("Active session reconciliation anchor mismatch")
html=html.replace(syncAnchor,"""  dbSyncStatus('Merekonsiliasi sesi aktif standby yang tidak ada di sumber. Riwayat tidak dihapus…');
  const sessionReconcile=await dbSyncCall('reconcile-active-sessions',{runId});
  if(sessionReconcile?.ok!==true||sessionReconcile?.matched!==true)throw new Error('ACTIVE_SESSION_RECONCILIATION_NOT_CONFIRMED');
  dbSyncStatus('Sesi aktif/paused cocok. Memverifikasi seluruh baris sumber 12 tabel; riwayat ekstra target dipertahankan…');""",1)

html=html.replace("// V12.1.23-FINAL-ADMIN-PACKAGE","// V12.1.23-FINAL-ADMIN-PACKAGE\n// "+marker,1)
for needed in ["ownerProof=state.proof","TARGET_OWNER_PROOF_REQUIRED","dbSyncCall('reconcile-active-sessions')",marker]:
    if needed not in html: raise SystemExit("Owner proof implementation marker missing: "+needed)
if "localStorage.setItem('aniGamesStandbyOwnerProof'" in html or 'localStorage.setItem("aniGamesStandbyOwnerProof"' in html:
    raise SystemExit("Owner proof must remain in memory only")
if "dbSyncCall('sync-core')" in html: raise SystemExit("Legacy 2-table Sync path remains")

gradle=gradle.replace("versionCode 51","versionCode 52",1).replace("versionName '12.1.23'","versionName '12.1.24'",1)
HTML.write_text(html,encoding="utf-8")
GRADLE.write_text(gradle,encoding="utf-8")
Path("VERSION.txt").write_text("AniGames Admin Android V12.1.24 FINAL — source Owner authorization + signed target-Owner proof in memory; full incremental 12-table source-row hash verification; active-session reconciliation; no deletes\n",encoding="utf-8")
print("PASS: Admin V12.1.24 stores only an expiring signed proof in memory and reconciles active sessions before hash verification.")
