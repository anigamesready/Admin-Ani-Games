import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
const DB1_URL = "https://wzkjpycjizexxcxrfdvr.supabase.co";
const DB1_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind6a2pweWNqaXpleHhjeHJmZHZyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTEwMzc0OTUsImV4cCI6MjEwNjYxMzQ5NX0.lxjSt7CqWDJhKItPi1ckVRIcc-kM7etMzxTu3txANaI";
const DB2_URL = "https://xcdbipgsvohesxhxydep.supabase.co";
const DB2_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhjZGJpcGdzdm9oZXN4aHh5ZGVwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTIwNjI5ODUsImV4cCI6MjEwNzYzODk4NX0.kHymS-T8a_PcKk-oQBYMGhHy3SSW1kAKStOBJVzMoSI";
const SELF_URL=Deno.env.get("SUPABASE_URL")||DB1_URL;
const SELF_REF=new URL(SELF_URL).hostname.split(".")[0];
const SELF_KEY=Deno.env.get("SUPABASE_ANON_KEY")||Deno.env.get("SUPABASE_PUBLISHABLE_KEY")||(SELF_REF==="wzkjpycjizexxcxrfdvr"?DB1_KEY:DB2_KEY);
const PEER_URL=SELF_REF==="wzkjpycjizexxcxrfdvr"?DB2_URL:DB1_URL;
const PEER_REF=SELF_REF==="wzkjpycjizexxcxrfdvr"?"xcdbipgsvohesxhxydep":"wzkjpycjizexxcxrfdvr";
const PEER_KEY=SELF_REF==="wzkjpycjizexxcxrfdvr"?DB2_KEY:DB1_KEY;
const TABLES:Record<string,string> = {"themes":"id","organizations":"id","org_members":"id","devices":"id","device_tokens":"id","device_enrollments":"id","rental_accounts":"id","billing_control_accounts":"id","billing_control_sessions":"id","device_commands":"id","device_command_logs":"id","device_heartbeats":"id","device_trial_requests":"id","admin_accounts":"id","admin_pc_access":"id","admin_alert_events":"id","audit_logs":"id","usage_events":"id","superadmin_access_codes":"user_id","superadmin_audit":"id","rental_sessions":"id","billing_transactions":"id"};
const H={"access-control-allow-origin":"*","access-control-allow-methods":"POST,OPTIONS","access-control-allow-headers":"authorization,content-type,apikey,x-client-info","content-type":"application/json; charset=utf-8"};
const out=(s:number,d:unknown)=>new Response(JSON.stringify(d),{status:s,headers:{...H,"cache-control":"no-store"}});
const serviceKey=()=>Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")||Deno.env.get("SUPABASE_SECRET_KEY")||"";
function stable(v:any):string{if(v===null||typeof v!=="object")return JSON.stringify(v);if(Array.isArray(v))return "["+v.map(stable).join(",")+"]";return "{"+Object.keys(v).sort().map(k=>JSON.stringify(k)+":"+stable(v[k])).join(",")+"}";}
async function sha(v:string){const d=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(v));return Array.from(new Uint8Array(d),b=>b.toString(16).padStart(2,"0")).join("");}
function client(){const k=serviceKey();if(!k)throw new Error("SYNC_BACKEND_NOT_CONFIGURED");return createClient(SELF_URL,k,{auth:{persistSession:false,autoRefreshToken:false}})}
async function authorize(token:string,admin:any){
 if(!token)throw new Error("OWNER_TOKEN_REQUIRED");
 const r=await fetch(SELF_URL+"/auth/v1/user",{headers:{apikey:SELF_KEY,authorization:"Bearer "+token},cache:"no-store"});
 if(!r.ok)throw new Error("OWNER_SESSION_INVALID");
 const user=await r.json();
 const {data:members,error}=await admin.from("org_members").select("org_id").eq("auth_user_id",user.id).eq("role","owner");
 if(error)throw new Error("OWNER_ROLE_LOOKUP_FAILED");
 const ids=(members||[]).map((x:any)=>String(x.org_id)).filter(Boolean);
 if(!ids.length)throw new Error("OWNER_ONLY");
 const {data:orgs,error:orgErr}=await admin.from("organizations").select("id,status").in("id",ids).eq("status","active");
 if(orgErr||!orgs?.length)throw new Error("ACTIVE_OWNER_ONLY");
 return {id:String(user.id),email:String(user.email||""),orgIds:orgs.map((x:any)=>String(x.id))};
}
async function activeAuthIds(admin:any){
 const {data:members,error:memberError}=await admin.from("org_members").select("auth_user_id").eq("role","owner");
 if(memberError)throw new Error("AUTH_MEMBERSHIP_LOOKUP_FAILED");
 const {data:accounts,error:accountError}=await admin.from("admin_accounts").select("auth_user_id").eq("status","active");
 if(accountError)throw new Error("AUTH_ADMIN_LOOKUP_FAILED");
 return [...new Set([...(members||[]).map((x:any)=>String(x.auth_user_id||"")),...(accounts||[]).map((x:any)=>String(x.auth_user_id||""))].filter(Boolean))].sort();
}
async function getPage(admin:any,table:string,offset:number,limit:number){
 const pk=TABLES[table];if(!pk)throw new Error("TABLE_NOT_ALLOWED");
 const {data,error,count}=await admin.from(table).select("*",{count:"exact"}).order(pk,{ascending:true}).range(offset,offset+limit-1);
 if(error)throw new Error("SOURCE_READ_FAILED:"+table+":"+error.message);
 return {rows:data||[],count:count??0,offset,limit,more:(data||[]).length===limit};
}
async function tableHash(admin:any,table:string){
 const pk=TABLES[table];if(!pk)throw new Error("TABLE_NOT_ALLOWED");
 const items:string[]=[];let offset=0;
 while(true){const page=await getPage(admin,table,offset,500);for(const row of page.rows)items.push(stable(row));offset+=page.rows.length;if(!page.more)break;if(offset>250000)throw new Error("SYNC_ROW_LIMIT_EXCEEDED:"+table)}
 return {table,count:offset,hash:await sha(items.join("\n"))};
}
async function recordAuthVerification(admin:any,userId:string){
 const routeResp=await fetch(PEER_URL+"/functions/v1/db-route-status",{headers:{apikey:PEER_KEY},cache:"no-store"});
 const status=await routeResp.json().catch(()=>({})),route=status?.route;
 if(!routeResp.ok||status?.projectRef!==PEER_REF||!Array.isArray(route?.auth_verified_user_ids)||!route.auth_verified_user_ids.includes(userId)){
  throw new Error("TARGET_LOGIN_VERIFICATION_NOT_FOUND");
 }
 const ids=await activeAuthIds(admin);
 const {data:current,error}=await admin.from("db_route_control").select("auth_verified_user_ids,data_parity_ready,routing_gateway_ready,backup_ready").eq("id",1).single();
 if(error)throw new Error("ROUTE_CONTROL_LOOKUP_FAILED");
 const verified=[...new Set([...(current.auth_verified_user_ids||[]).map(String),userId])];
 const ready=ids.every(id=>verified.includes(id))&&ids.every(id=>route.auth_verified_user_ids.includes(id));
 const {error:updateError}=await admin.from("db_route_control").update({
   auth_verified_user_ids:verified,auth_parity_ready:ready,
   last_parity_check_note:ready?"All active owner/admin accounts completed a successful login test on both databases.":"Login verification recorded for "+verified.length+"/"+ids.length+" active owner/admin accounts."
 }).eq("id",1);
 if(updateError)throw new Error("AUTH_VERIFICATION_RECORD_FAILED");
 return {verifiedUserCount:verified.length,requiredUserCount:ids.length,authParityReady:ready};
}
async function handler(req:Request){
 if(req.method==="OPTIONS")return new Response(null,{status:204,headers:H});
 if(req.method!=="POST")return out(405,{ok:false,error:"method_not_allowed"});
 let body:any={};try{body=await req.json()}catch(_){return out(400,{ok:false,error:"invalid_json"})}
 try{
  const admin=client(),token=String((req.headers.get("authorization")||"").replace(/^Bearer\s+/i,"")||body.accessToken||"");
  const auth=await authorize(token,admin),action=String(body.action||"");
  if(action==="authorize")return out(200,{ok:true,projectRef:SELF_REF,userId:auth.id,role:"owner",orgCount:auth.orgIds.length});
  if(action==="manifest"){
   const tables:any[]=[];
   for(const [table,pk] of Object.entries(TABLES)){
    const {count,error}=await admin.from(table).select(pk,{count:"exact",head:true});
    if(error)throw new Error("SOURCE_COUNT_FAILED:"+table);
    tables.push({table,count:count??0});
   }
   const activeIds=await activeAuthIds(admin);
   return out(200,{ok:true,projectRef:SELF_REF,tables,auth:{activeUserIds:activeIds,activeUserCount:activeIds.length}});
  }
  if(action==="auth-members")return out(200,{ok:true,projectRef:SELF_REF,userIds:await activeAuthIds(admin)});
  if(action==="page"){
   const table=String(body.table||""),offset=Math.max(0,Math.trunc(Number(body.offset)||0)),limit=Math.min(500,Math.max(1,Math.trunc(Number(body.limit)||250)));
   if(!TABLES[table])return out(400,{ok:false,error:"TABLE_NOT_ALLOWED"});
   return out(200,{ok:true,projectRef:SELF_REF,table,...await getPage(admin,table,offset,limit)});
  }
  if(action==="hash"){
   const table=String(body.table||"");if(!TABLES[table])return out(400,{ok:false,error:"TABLE_NOT_ALLOWED"});
   return out(200,{ok:true,projectRef:SELF_REF,...(await tableHash(admin,table))});
  }
  if(action==="mark-not-ready"||action==="start-sync"){
   const note=String(body.note||"Cross-database sync is in progress; active route remains online.").slice(0,500);
   const {error}=await admin.from("db_route_control").update({sync_in_progress:true,data_parity_ready:false,routing_gateway_ready:false,sync_ready:false,last_parity_check_at:null,last_parity_check_note:note}).eq("id",1);
   if(error)throw new Error("SYNC_LOCK_FAILED");
   return out(200,{ok:true,readiness:"sync_in_progress",projectRef:SELF_REF});
  }
  if(action==="finish-sync"){
   const {error}=await admin.from("db_route_control").update({sync_in_progress:false,data_parity_ready:false,routing_gateway_ready:false,sync_ready:false,last_parity_check_at:null,last_parity_check_note:"Sync was stopped or not verified. Route changes remain blocked until a complete parity check succeeds."}).eq("id",1);
   if(error)throw new Error("SYNC_UNLOCK_FAILED");
   return out(200,{ok:true,projectRef:SELF_REF});
  }
  if(action==="record-auth-verification"){
   if(String(body.userId||"")!==auth.id)throw new Error("AUTH_VERIFICATION_USER_MISMATCH");
   return out(200,{ok:true,projectRef:SELF_REF,...(await recordAuthVerification(admin,auth.id))});
  }
  if(action==="mark-ready"){
   const targetRouteResp=await fetch(PEER_URL+"/functions/v1/db-route-status",{headers:{apikey:PEER_KEY},cache:"no-store"});
   const targetStatus=await targetRouteResp.json().catch(()=>({})),route=targetStatus?.route;
   const fresh=route?.last_parity_check_at&&Date.now()-Date.parse(route.last_parity_check_at)<=30*60*1000&&Date.parse(route.last_parity_check_at)<=Date.now()+60000;
   const versionsMatch=!!route?.schema_version&&route.schema_version===route.primary_schema_version&&route.schema_version===route.backup_schema_version;
   const local={};
   const {data:own,error:ownError}=await admin.from("db_route_control").select("schema_version,auth_parity_ready,auth_verified_user_ids,data_parity_ready").eq("id",1).single();
   if(ownError)throw new Error("SOURCE_ROUTE_LOOKUP_FAILED");
   if(!targetRouteResp.ok||targetStatus?.projectRef!==PEER_REF||route?.auth_parity_ready!==true||route?.data_parity_ready!==true||route?.backup_ready!==true||route?.routing_gateway_ready!==true||!fresh||!versionsMatch||own.auth_parity_ready!==true)throw new Error("DB2_PARITY_OR_AUTH_PROOF_NOT_READY");
   const now=new Date().toISOString(),note=String(route.last_parity_check_note||"Cross-database table hashes verified").slice(0,500);
   const version=String(own.schema_version||route.schema_version);
   const {error}=await admin.from("db_route_control").update({backup_ready:true,data_parity_ready:true,routing_gateway_ready:true,sync_ready:true,auth_parity_ready:true,primary_schema_version:version,backup_schema_version:version,schema_version:version,last_schema_check_at:now,last_parity_check_at:now,last_parity_check_note:"Cross-database business-table hashes match and all active owner/admin logins are verified. "+note,sync_in_progress:false}).eq("id",1);
   if(error)throw new Error("SOURCE_ROUTE_READY_UPDATE_FAILED");
   return out(200,{ok:true,ready:true,verifiedAt:now,projectRef:SELF_REF});
  }
  return out(400,{ok:false,error:"unknown_action"});
 }catch(e){const m=e instanceof Error?e.message:"sync_export_failed";const status=/OWNER|SESSION|ACTIVE_OWNER|AUTH_VERIFICATION/.test(m)?403:/TABLE_NOT_ALLOWED|invalid_json/.test(m)?400:/FAILED|NOT_CONFIGURED|LIMIT/.test(m)?503:400;return out(status,{ok:false,error:m})}
}
Deno.serve(handler);
