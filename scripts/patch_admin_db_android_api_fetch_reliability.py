#!/usr/bin/env python3
"""Make DB Android API health checks preflight-free and clarify WebView fetch failures."""
from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
WEB = ROOT / "android/app/src/main/assets/web"
MARKER = "ANI-DB-ANDROID-API-FETCH-RELIABILITY-V1"

for name in ("admin.html", "index.html", "admin-control.html"):
    path = WEB / name
    if not path.is_file():
        raise SystemExit("ADMIN_API_PAGE_NOT_FOUND: " + name)
    source = path.read_text(encoding="utf-8")
    if MARKER in source:
        if source.count(MARKER) != 1 or "if(body!==null)headers['content-type']='application/json';" not in source:
            raise SystemExit("API_FETCH_PATCH_MARKER_BUT_INCOMPLETE: " + name)
        print("PASS: fetch reliability patch already applied to " + name)
        continue

    pattern = re.compile(
        r"(?ms)^async function localJson\(path,body=null,method='POST',(?:token|accessToken)=''\)\{.*?^\}"
    )
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise SystemExit(f"EXPECTED_ONE_LOCAL_JSON_HELPER_{name}: found {len(matches)}")

    replacement = r"""// ANI-DB-ANDROID-API-FETCH-RELIABILITY-V1
async function localJson(path,body=null,method='POST',token=''){
 const headers={};
 if(body!==null)headers['content-type']='application/json';
 if(token)headers.authorization='Bearer '+token;
 const base=localApiBase();
 let response;
 try{
  response=await fetch(base+path,{method,headers,cache:'no-store',...(body===null?{}:{body:JSON.stringify(body)})});
 }catch(e){
  const detail=String(e?.message||e||'network unavailable').slice(0,100);
  if(/Failed to fetch|NetworkError|Load failed|fetch failed/i.test(detail)){
   const origin=new URL(base).origin;
   throw new Error('API_FETCH_FAILED: koneksi ke '+origin+' gagal. Pastikan server Termux port 8788 online atau alamat HTTPS gateway aktif. Detail: '+detail);
  }
  throw e;
 }
 const data=await response.json().catch(()=>({}));
 if(!response.ok)throw new Error(data.error||data.message||('HTTP_'+response.status));
 return data;
}"""
    source = source[:matches[0].start()] + replacement + source[matches[0].end():]
    if source.count(MARKER) != 1 or "if(body!==null)headers['content-type']='application/json';" not in source:
        raise SystemExit("API_FETCH_PATCH_INSERTION_FAILED: " + name)
    path.write_text(source, encoding="utf-8")
    print("PASS: preflight-free health request and clear network diagnostics applied to " + name)

print("PASS: Admin pages retain authenticated JSON POST requests; only bodyless GET avoids Content-Type preflight.")
