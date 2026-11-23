import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
const DB1_URL="https://wzkjpycjizexxcxrfdvr.supabase.co";
const DB1_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind6a2pweWNqaXpleHhjeHJmZHZyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTEwMzc0OTUsImV4cCI6MjEwNjYxMzQ5NX0.lxjSt7CqWDJhKItPi1ckVRIcc-kM7etMzxTu3txANaI";
const DB2_URL="https://xcdbipgsvohesxhxydep.supabase.co";
const DB2_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhjZGJpcGdzdm9oZXN4aHh5ZGVwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTIwNjI5ODUsImV4cCI6MjEwNzYzODk4NX0.kHymS-T8a_PcKk-oQBYMGhHy3SSW1kAKStOBJVzMoSI";
const H={"access-control-allow-origin":"*","access-control-allow-methods":"POST,OPTIONS","access-control-allow-headers":"authorization,content-type,apikey,x-client-info","content-type":"application/json; charset=utf-8"};
const out=(s:number,d:unknown)=>new Response(JSON.stringify(d),{status:s,headers:{...H,"cache-control":"no-store"}});
const serviceKey=()=>Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")||Deno.env.get("SUPABASE_SECRET_KEY")||"";
function db(){const k=serviceKey();if(!k)throw new Error("ROUTE_BACKEND_NOT_CONFIGURED");const url=Deno.env.get("SUPABASE_URL")||"";return createClient(url,k,{auth:{persistSession:false,autoRefreshToken:false}})}
async function routeAt(url:string,key:string){
 const r=await fetch(url+"/functions/v1/db-route-status",{headers:{apikey:key},cache:"no-store"});
 const d:any=await r.json().catch(()=>({}));
 if(!r.ok||d?.ok!==true||d?.readOnly!==true||!d?.route)throw new Error("ROUTE_STATUS_UNAVAILABLE");
 const route=d.route,parity=Date.parse(route.last_parity_check_at||"");
 const fresh=Number.isFinite(parity)&&Date.now()-parity<=30*60*1000&&parity<=Date.now()+60000;
 const schema=!!route.schema_version&&route.schema_version===route.primary_schema_version&&route.schema_version===route.backup_schema_version;
 const ready=route.backup_ready===true&&route.auth_parity_ready===true&&route.data_parity_ready===true&&route.routing_gateway_ready===true&&fresh&&schema;
 return {projectRef:d.projectRef,route,fresh,schema,ready};
}
async function authorize(token:string,admin:any){
 if(!token)throw new Error("OWNER_TOKEN_REQUIRED");
 // The Admin app can have a session minted by either project. Verify against the
 // matching Supabase Auth endpoint, then independently require owner membership
 // in this coordinator's local database before allowing a route-control write.
 const candidates=[{url:DB1_URL,key:DB1_KEY,ref:"wzkjpycjizexxcxrfdvr"},{url:DB2_URL,key:DB2_KEY,ref:"xcdbipgsvohesxhxydep"}];
 let user:any=null,authProjectRef="";
 for(const target of candidates){
  try{
   const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),3500);
   try{
    const response=await fetch(target.url+"/auth/v1/user",{headers:{apikey:target.key,authorization:"Bearer "+token},cache:"no-store",signal:ctl.signal});
    if(response.ok){const candidate:any=await response.json();if(candidate?.id){user=candidate;authProjectRef=target.ref;break}}
   }finally{clearTimeout(timer)}
  }catch(_){}
 }
 if(!user)throw new Error("OWNER_SESSION_INVALID");
 const {data:rows,error}=await admin.from("org_members").select("org_id").eq("auth_user_id",user.id).eq("role","owner");
 if(error)throw new Error("OWNER_ROLE_LOOKUP_FAILED");
 const orgIds=(rows||[]).map((x:any)=>String(x.org_id)).filter(Boolean);
 if(!orgIds.length)throw new Error("OWNER_ONLY");
 const {data:orgs,error:orgError}=await admin.from("organizations").select("id").in("id",orgIds).eq("status","active");
 if(orgError||!orgs?.length)throw new Error("ACTIVE_OWNER_ONLY");
 return {id:String(user.id),email:String(user.email||""),authProjectRef,orgIds};
}
function requireBackupReadiness(a:any,b:any){
 if(a.projectRef!=="wzkjpycjizexxcxrfdvr"||b.projectRef!=="xcdbipgsvohesxhxydep")throw new Error("PROJECT_ID_MISMATCH");
 if(a.route?.sync_in_progress===true||b.route?.sync_in_progress===true)throw new Error("SYNC_IN_PROGRESS: wait for DB Sync to complete before switching");
 if(!a.ready||!b.ready||!a.schema||!b.schema||!a.fresh||!b.fresh)throw new Error("CUTOVER_BLOCKED: both DBs require verified recent table and auth parity, schema equality and gateway readiness");
 if(a.route.schema_version!==b.route.schema_version)throw new Error("SCHEMA_VERSION_MISMATCH");
}
async function localRoute(admin:any){
 const {data,error}=await admin.from("db_route_control").select("active_target,epoch,switch_id,updated_at,schema_version,primary_schema_version,backup_schema_version,primary_ready,backup_ready,auth_parity_ready,data_parity_ready,routing_gateway_ready,last_parity_check_at,sync_in_progress").eq("id",1).single();
 if(error||!data)throw new Error("LOCAL_ROUTE_CONTROL_UNAVAILABLE");return data;
}
async function handler(req:Request){
 if(req.method==="OPTIONS")return new Response(null,{status:204,headers:H});
 if(req.method!=="POST")return out(405,{ok:false,error:"method_not_allowed"});
 let body:any={};try{body=await req.json()}catch(_){return out(400,{ok:false,error:"invalid_json"})}
 try{
  const admin=db(),token=String((req.headers.get("authorization")||"").replace(/^Bearer\s+/i,"")||body.accessToken||"");
  const user=await authorize(token,admin),action=String(body.action||""),url=Deno.env.get("SUPABASE_URL")||"";
  const localRef=new URL(url).hostname.split(".")[0];
  const remote=localRef==="wzkjpycjizexxcxrfdvr"?await routeAt(DB2_URL,DB2_KEY):await routeAt(DB1_URL,DB1_KEY);
  const local=await localRoute(admin);
  const current={projectRef:localRef,route:local,fresh:!!local.last_parity_check_at&&Date.now()-Date.parse(local.last_parity_check_at)<=30*60*1000&&Date.parse(local.last_parity_check_at)<=Date.now()+60000,schema:!!local.schema_version&&local.schema_version===local.primary_schema_version&&local.schema_version===local.backup_schema_version,ready:local.backup_ready===true&&local.auth_parity_ready===true&&local.data_parity_ready===true&&local.routing_gateway_ready===true,syncInProgress:local.sync_in_progress===true};
  if(action==="status")return out(200,{ok:true,local:current,remote});
  const target=String(body.target||"");
  if(action==="switch"){
   if(target!=="primary"&&target!=="backup")throw new Error("INVALID_DB_TARGET");
   if(local.syncInProgress||remote.route?.sync_in_progress===true)throw new Error("SYNC_IN_PROGRESS: wait for DB Sync to complete before switching");
   if(target==="backup"||local.route.active_target==="backup")requireBackupReadiness(localRef==="wzkjpycjizexxcxrfdvr"?current:remote,localRef==="wzkjpycjizexxcxrfdvr"?remote:current);
   const epoch=Math.trunc(Number(body.epoch)),switchId=String(body.switchId||""),reason=String(body.reason||"Admin global DB switch").slice(0,160);
   if(!Number.isInteger(epoch)||epoch<1||!switchId)throw new Error("SWITCH_EPOCH_OR_ID_REQUIRED");
   if(local.route.active_target===target&&Number(local.route.epoch)===epoch&&String(local.route.switch_id||"")===switchId)return out(200,{ok:true,idempotent:true,projectRef:localRef,target,epoch,switchId});
   if(epoch!==Number(local.route.epoch)+1)throw new Error("ROUTE_EPOCH_CONFLICT: current="+local.route.epoch);
   const {data,error}=await admin.from("db_route_control").update({active_target:target,epoch,switch_id:switchId,reason,updated_at:new Date().toISOString(),updated_by:user.id,sync_ready:true}).eq("id",1).select("active_target,epoch,switch_id,updated_at").single();
   if(error||!data)throw new Error("LOCAL_ROUTE_WRITE_FAILED");
   return out(200,{ok:true,projectRef:localRef,...data});
  }
  if(action==="finalize"){
   const epoch=Math.trunc(Number(body.epoch)),switchId=String(body.switchId||"");
   const againLocal=await localRoute(admin);
   const againRemote=localRef==="wzkjpycjizexxcxrfdvr"?await routeAt(DB2_URL,DB2_KEY):await routeAt(DB1_URL,DB1_KEY);
   if(Number(againLocal.epoch)!==epoch||String(againLocal.switch_id||"")!==switchId||againLocal.active_target!==target||
      Number(againRemote.route.epoch)!==epoch||String(againRemote.route.switch_id||"")!==switchId||againRemote.route.active_target!==target){
     throw new Error("CROSS_DB_ROUTE_MISMATCH: retry the same switch ID and epoch");
   }
   if(target==="backup"||target==="primary")requireBackupReadiness(localRef==="wzkjpycjizexxcxrfdvr"?current:againRemote,localRef==="wzkjpycjizexxcxrfdvr"?againRemote:current);
   const {data,error}=await admin.schema("api").rpc("db_route_activate_runtime");
   if(error||data?.ok!==true)throw new Error("MAINTENANCE_SCHEDULER_ACTIVATION_FAILED");
   const now=new Date().toISOString();
   const {error:finalError}=await admin.from("db_route_control").update({last_cutover_test_at:now,cutover_test_note:"Coordinated global route finalized: "+target+" epoch "+epoch+" switch "+switchId}).eq("id",1);
   if(finalError)throw new Error("CUTOVER_AUDIT_WRITE_FAILED");
   return out(200,{ok:true,projectRef:localRef,target,epoch,switchId,runtime:data});
  }
  return out(400,{ok:false,error:"unknown_action"});
 }catch(e){
  const m=e instanceof Error?e.message:"route_coordinator_failed";
  const status=/OWNER|SESSION/.test(m)?403:/INVALID_|REQUIRED|MISMATCH|CONFLICT|BLOCKED|READY/.test(m)?409:/NOT_CONFIGURED|UNAVAILABLE|FAILED/.test(m)?503:400;
  return out(status,{ok:false,error:m});
 }
}
Deno.serve(handler);
