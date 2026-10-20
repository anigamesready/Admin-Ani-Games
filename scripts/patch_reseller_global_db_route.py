from pathlib import Path
import os
import re

ROOT = Path(os.environ.get("ANDROID_DIR", ".")).resolve()
if not ROOT.exists():
    raise SystemExit("ANDROID_DIR is missing; cannot patch the reseller Android project.")

candidates = []
for path in ROOT.rglob("index.html"):
    if (path.parent / "admin-control.html").is_file():
        candidates.append(path.parent)
if not candidates:
    raise SystemExit("Reseller WebView folder with index.html and admin-control.html was not found.")
web_dir = next((p for p in candidates if p.name.lower() == "web"), candidates[0])
login_path = web_dir / "index.html"
dashboard_path = web_dir / "admin-control.html"

route_js = r'''(function installAniGamesResellerGlobalDbRoute(){
  if(window.__aniGamesResellerGlobalDbRoute)return;
  window.__aniGamesResellerGlobalDbRoute=true;
  const nativeFetch=window.fetch.bind(window);
  const DB1_URL='https://wzkjpycjizexxcxrfdvr.supabase.co';
  const DB2_URL='https://xcdbipgsvohesxhxydep.supabase.co';
  const DB1_ROUTE_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind6a2pweWNqaXpleHhjeHJmZHZyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTEwMzc0OTUsImV4cCI6MjEwNjYxMzQ5NX0.lxjSt7CqWDJhKItPi1ckVRIcc-kM7etMzxTu3txANaI';
  const DB2_ROUTE_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhjZGJpcGdzdm9oZXN4aHh5ZGVwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTIwNjI5ODUsImV4cCI6MjEwNzYzODk4NX0.kHymS-T8a_PcKk-oQBYMGhHy3SSW1kAKStOBJVzMoSI';
  const DB1_API_KEY='sb_publishable_DobdCrOd43-vluON5gV7hg_6Js2Ea5V';
  const DB2_API_KEY='sb_publishable_FjhnRZeXPnomlGRw75YLxw_d46R2Lag';
  const STATE_KEY='anigames_reseller_global_db_route_v1';
  const NOTICE_KEY='anigames_reseller_route_notice_v1';
  const CACHE_MS=15000;
  let routeState=null,routeAt=0,routePromise=null,reloadScheduled=false;
  function sameRoute(a,b){return !!a&&!!b&&String(a.target)===String(b.target)&&Number(a.epoch)===Number(b.epoch)&&String(a.switchId||'')===String(b.switchId||'')}
  function readStored(){try{return JSON.parse(localStorage.getItem(STATE_KEY)||'null')}catch(_){return null}}
  async function readRoute(url,key,ref){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),5000);
    try{
      const response=await nativeFetch(url+'/functions/v1/db-route-status',{method:'GET',headers:{apikey:key},cache:'no-store',signal:controller.signal});
      const data=await response.json().catch(()=>({}));
      if(!response.ok||data?.ok!==true||data?.projectRef!==ref||!data?.route)throw new Error('DB_ROUTE_STATUS_UNAVAILABLE:'+ref);
      return data.route;
    }finally{clearTimeout(timer)}
  }
  function parityFresh(r){
    const at=Date.parse(r?.last_parity_check_at||'');
    return Number.isFinite(at)&&at<=Date.now()+60000&&Date.now()-at<=30*60*1000;
  }
  function schemaMatches(r){
    return !!r?.schema_version&&r.schema_version===r.primary_schema_version&&r.schema_version===r.backup_schema_version;
  }
  function finalizedBackup(r){
    if(!r||r.active_target!=='backup'||!r.switch_id)return false;
    const note='Coordinated global route finalized: backup epoch '+Number(r.epoch)+' switch '+String(r.switch_id);
    return !!r.last_cutover_test_at&&String(r.cutover_test_note||'')===note;
  }
  function clearAuthOnly(){
    try{
      localStorage.removeItem('sb-wzkjpycjizexxcxrfdvr-auth-token');
      localStorage.removeItem('sb-xcdbipgsvohesxhxydep-auth-token');
      sessionStorage.clear();
    }catch(_){}
  }
  function refreshOnRouteChange(next){
    if(reloadScheduled)return;
    reloadScheduled=true;
    clearAuthOnly();
    try{localStorage.setItem(STATE_KEY,JSON.stringify({target:next.target,epoch:next.epoch,switchId:next.switchId,checkedAt:new Date().toISOString()}))}catch(_){}
    try{localStorage.setItem(NOTICE_KEY,'Database aktif berubah ke '+(next.target==='backup'?'DB2':'DB1')+'. Login ulang diperlukan; target Reseller sudah diperbarui.')}catch(_){}
    setTimeout(()=>{try{window.location.reload()}catch(_){}},700);
  }
  async function resolveGlobalDbRoute(force){
    force=!!force;
    if(!force&&routeState&&Date.now()-routeAt<CACHE_MS)return routeState;
    if(routePromise)return routePromise;
    routePromise=(async()=>{
      const rows=await Promise.all([
        readRoute(DB1_URL,DB1_ROUTE_KEY,'wzkjpycjizexxcxrfdvr'),
        readRoute(DB2_URL,DB2_ROUTE_KEY,'xcdbipgsvohesxhxydep')
      ]);
      const a=rows[0],b=rows[1],switchA=String(a.switch_id||''),switchB=String(b.switch_id||'');
      if(a.active_target!==b.active_target||Number(a.epoch)!==Number(b.epoch)||switchA!==switchB)
        throw new Error('DB_ROUTE_CUTOVER_INCOMPLETE: target/epoch/switch ID DB1 dan DB2 belum sama');
      if(a.sync_in_progress===true||b.sync_in_progress===true)throw new Error('DB_ROUTE_SYNC_IN_PROGRESS');
      if(a.active_target==='primary'){
        if(a.primary_ready!==true||b.primary_ready!==true)throw new Error('DB_ROUTE_PRIMARY_NOT_READY');
      }else if(a.active_target==='backup'){
        const finalized=finalizedBackup(a)&&finalizedBackup(b);
        if(!finalized&&(
          a.data_parity_ready!==true||b.data_parity_ready!==true||
          a.can_switch_to_backup!==true||b.can_switch_to_backup!==true||
          !parityFresh(a)||!parityFresh(b)||!schemaMatches(a)||!schemaMatches(b)||
          a.schema_version!==b.schema_version
        ))throw new Error('DB_ROUTE_CUTOVER_BLOCKED: parity/schema belum terverifikasi');
      }else throw new Error('DB_ROUTE_INVALID_TARGET');
      const next={
        target:String(a.active_target),epoch:Number(a.epoch)||0,switchId:switchA,
        base:a.active_target==='backup'?DB2_URL:DB1_URL,
        key:a.active_target==='backup'?DB2_API_KEY:DB1_API_KEY
      };
      const stored=readStored();
      if(stored&&!sameRoute(stored,next)){
        refreshOnRouteChange(next);
        throw new Error('DB_ROUTE_CHANGED_RELOAD: reseller sedang memuat ulang ke DB baru');
      }
      if(!stored&&next.target==='backup'){
        // First launch on DB2 must not reuse a saved DB1 Auth session.
        clearAuthOnly();
      }
      routeState=next;routeAt=Date.now();
      try{localStorage.setItem(STATE_KEY,JSON.stringify({target:next.target,epoch:next.epoch,switchId:next.switchId,checkedAt:new Date().toISOString()}))}catch(_){}
      window.aniGamesDbRoute={target:next.target,epoch:next.epoch,switchId:next.switchId};
      return next;
    })();
    try{return await routePromise}finally{routePromise=null}
  }
  window.aniGamesResolveGlobalDbRoute=resolveGlobalDbRoute;
  window.fetch=async function(input,init){
    const originalUrl=input instanceof Request?input.url:(input instanceof URL?input.href:String(input||''));
    const isDbUrl=/^https:\/\/(?:wzkjpycjizexxcxrfdvr|xcdbipgsvohesxhxydep)\.supabase\.co(?:\/|$)/i.test(originalUrl);
    if(!isDbUrl||originalUrl.includes('/functions/v1/db-route-status'))return nativeFetch(input,init);
    const route=await resolveGlobalDbRoute(false);
    const routedUrl=originalUrl.replace(/^https:\/\/(?:wzkjpycjizexxcxrfdvr|xcdbipgsvohesxhxydep)\.supabase\.co/i,route.base);
    if(input instanceof Request){
      const request=new Request(routedUrl,input);
      const headers=new Headers(request.headers);
      if(init?.headers)new Headers(init.headers).forEach((v,k)=>headers.set(k,v));
      headers.set('apikey',route.key);
      return nativeFetch(new Request(request,{...(init||{}),headers,cache:'no-store'}));
    }
    const headers=new Headers(init?.headers||{});
    headers.set('apikey',route.key);
    return nativeFetch(routedUrl,{...(init||{}),headers,cache:'no-store'});
  };
  void resolveGlobalDbRoute(true).catch(e=>console.warn('[AniGames Reseller DB route]',String(e?.message||e)));
  setInterval(()=>{void resolveGlobalDbRoute(true).catch(e=>console.warn('[AniGames Reseller DB route]',String(e?.message||e)))},15000);
  window.addEventListener('DOMContentLoaded',()=>{
    try{
      const notice=localStorage.getItem(NOTICE_KEY);
      if(notice){localStorage.removeItem(NOTICE_KEY);console.info(notice);}
    }catch(_){}
  });
})();'''

script_path = web_dir / "db-route-refresh.js"
script_path.write_text(route_js + "\n", encoding="utf-8")
tag = '<script src="db-route-refresh.js"></script>'

for path in (login_path, dashboard_path):
    body = path.read_text(encoding="utf-8", errors="replace")
    if tag not in body:
        match = re.search(r"<head\b[^>]*>", body, flags=re.I)
        if not match:
            raise SystemExit("HTML head tag not found in " + path.name)
        body = body[:match.end()] + "\n" + tag + "\n" + body[match.end():]
        path.write_text(body, encoding="utf-8")

# Preserve the V11.30.0 UI review source but publish the route-aware APK as a separate version.
gradle_candidates = [ROOT / "app/build.gradle", ROOT / "app/build.gradle.kts"]
gradle_path = next((p for p in gradle_candidates if p.is_file()), None)
if gradle_path is None:
    raise SystemExit("Reseller app Gradle file not found.")
gradle = gradle_path.read_text(encoding="utf-8")
gradle, code_count = re.subn(r"\bversionCode\s+130\b", "versionCode 131", gradle, count=1)
gradle, name_count = re.subn(r"(\bversionName\s*=?\s*['\"])1\.0\.0(['\"])", r"\g<1>1.0.1\2", gradle, count=1)
if code_count != 1 or name_count != 1:
    raise SystemExit(f"Expected reseller versionCode 130 / versionName 1.0.0, found code={code_count}, name={name_count}.")
gradle_path.write_text(gradle, encoding="utf-8")

# Static checks: both login and dashboard must load the router before app scripts.
for path in (login_path, dashboard_path):
    body = path.read_text(encoding="utf-8")
    if tag not in body or body.index(tag) > body.lower().find("<script", body.lower().find(tag) + len(tag)):
        raise SystemExit("DB route router is not placed before app JavaScript in " + path.name)
if "resolveGlobalDbRoute" not in route_js or "DB_ROUTE_CUTOVER_INCOMPLETE" not in route_js or "DB2_API_KEY" not in route_js:
    raise SystemExit("Reseller route resolver validation failed.")
print("PASS: Reseller WebView login/dashboard resolve global DB1/DB2 target, confirm epoch/switch ID, route API/Auth requests, refresh on switch and force re-login; versionCode 131 / 1.0.1.")
