import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
const DB1_URL="https://wzkjpycjizexxcxrfdvr.supabase.co";
const DB1_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind6a2pweWNqaXpleHhjeHJmZHZyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTEwMzc0OTUsImV4cCI6MjEwNjYxMzQ5NX0.lxjSt7CqWDJhKItPi1ckVRIcc-kM7etMzxTu3txANaI";
const DB2_URL="https://xcdbipgsvohesxhxydep.supabase.co";
const DB2_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhjZGJpcGdzdm9oZXN4aHh5ZGVwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTIwNjI5ODUsImV4cCI6MjEwNzYzODk4NX0.kHymS-T8a_PcKk-oQBYMGhHy3SSW1kAKStOBJVzMoSI";
const SELF_URL=Deno.env.get("SUPABASE_URL")||DB2_URL;
const SELF_REF=new URL(SELF_URL).hostname.split(".")[0];
const SELF_KEY=Deno.env.get("SUPABASE_ANON_KEY")||Deno.env.get("SUPABASE_PUBLISHABLE_KEY")||(SELF_REF==="wzkjpycjizexxcxrfdvr"?DB1_KEY:DB2_KEY);
const PEER_URL=SELF_REF==="wzkjpycjizexxcxrfdvr"?DB2_URL:DB1_URL;
const PEER_REF=SELF_REF==="wzkjpycjizexxcxrfdvr"?"xcdbipgsvohesxhxydep":"wzkjpycjizexxcxrfdvr";
const PEER_KEY=SELF_REF==="wzkjpycjizexxcxrfdvr"?DB2_KEY:DB1_KEY;
const NON_BLOCKING_TABLES=new Set(["device_heartbeats","device_command_logs","audit_logs","usage_events"]);
const TABLES:Record<string,string>={"themes":"id","organizations":"id","org_members":"id","devices":"id","device_tokens":"id","device_enrollments":"id","rental_accounts":"id","billing_control_accounts":"id","billing_control_sessions":"id","device_commands":"id","device_command_logs":"id","device_heartbeats":"id","device_trial_requests":"id","admin_accounts":"id","admin_pc_access":"id","admin_alert_events":"id","audit_logs":"id","usage_events":"id","superadmin_access_codes":"user_id","superadmin_audit":"id","rental_sessions":"id","billing_transactions":"id"};
const H={"access-control-allow-origin":"*","access-control-allow-methods":"POST,OPTIONS","access-control-allow-headers":"authorization,content-type,apikey,x-client-info","content-type":"application/json; charset=utf-8"};
const out=(s:number,d:unknown)=>new Response(JSON.stringify(d),{status:s,headers:{...H,"cache-control":"no-store"}});
const serviceKey=()=>Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")||Deno.env.get("SUPABASE_SECRET_KEY")||"";
function db(){const k=serviceKey();if(!k)throw new Error("SYNC_BACKEND_NOT_CONFIGURED");return createClient(SELF_URL,k,{auth:{persistSession:false,autoRefreshToken:false}})}
function stable(v:any):string{if(v===null||typeof v!=="object")return JSON.stringify(v);if(Array.isArray(v))return "["+v.map(stable).join(",")+"]";return "{"+Object.keys(v).sort().map(k=>JSON.stringify(k)+":"+stable(v[k])).join(",")+"}";}
async function sha(v:string){const d=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(v));return Array.from(new Uint8Array(d),b=>b.toString(16).padStart(2,"0")).join("");}
async function sharedGatewayProbe(expectedRoute:any):Promise<{ready:boolean;reason:string}>{
 const baseRaw=String(Deno.env.get("SHARED_GATEWAY_BASE_URL")||"").trim();
 if(!baseRaw)return {ready:false,reason:"SHARED_GATEWAY_BASE_URL_NOT_CONFIGURED"};
 let base:URL;
 try{base=new URL(baseRaw)}catch(_){return {ready:false,reason:"SHARED_GATEWAY_URL_INVALID"}}
 if(base.protocol!=="https:"||base.username||base.password||base.search||base.hash||base.hostname==="wzkjpycjizexxcxrfdvr.supabase.co"||base.hostname==="xcdbipgsvohesxhxydep.supabase.co")return {ready:false,reason:"SHARED_GATEWAY_MUST_USE_INDEPENDENT_HTTPS_HOST"};
 const endpoint=new URL("/v1/route/resolve",base).toString(),ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),4000);
 try{
  const response=await fetch(endpoint,{method:"GET",headers:{accept:"application/json"},cache:"no-store",signal:ctl.signal});
  const data:any=await response.json().catch(()=>({}));
  if(!response.ok||data?.contract!=="ani-games-dual-db/v1")return {ready:false,reason:"SHARED_GATEWAY_CONTRACT_UNAVAILABLE"};
  const route=data.routing||{},targets=data.targets||{},caps=data.capabilities||{};
  const servedAt=Date.parse(String(data.served_at||"")),gatewayRaw=String(route.gateway_base_url||"");
  let gatewayUrl:URL;try{gatewayUrl=new URL(gatewayRaw)}catch(_){return {ready:false,reason:"SHARED_GATEWAY_BASE_URL_INVALID_IN_RESPONSE"}}
  const requiredCaps=["pc_heartbeat","pc_enrollment","rental_sync","device_commands","admin_alerts"];
  if(route.status!=="ready"||route.allow_reads!==true||route.allow_writes!==true||route.allow_enrollment!==true)return {ready:false,reason:"SHARED_GATEWAY_READ_WRITE_CAPABILITY_NOT_READY"};
  if(targets.primary?.project_ref!=="wzkjpycjizexxcxrfdvr"||targets.backup?.project_ref!=="xcdbipgsvohesxhxydep")return {ready:false,reason:"SHARED_GATEWAY_PROJECT_REF_MISMATCH"};
  if(requiredCaps.some(k=>caps[k]!==true))return {ready:false,reason:"SHARED_GATEWAY_REQUIRED_CAPABILITY_MISSING"};
  if(gatewayUrl.hostname!==base.hostname||gatewayUrl.protocol!=="https:"||gatewayUrl.pathname.replace(/\/+$/,"")!=="/v1")return {ready:false,reason:"SHARED_GATEWAY_URL_MISMATCH"};
  if(!Number.isFinite(servedAt)||Date.now()-servedAt>120000||servedAt>Date.now()+60000)return {ready:false,reason:"SHARED_GATEWAY_STATUS_STALE"};
  if(route.active_target!==expectedRoute?.active_target||Number(route.epoch)!==Number(expectedRoute?.epoch)||String(route.switch_id||"")!==String(expectedRoute?.switch_id||""))return {ready:false,reason:"SHARED_GATEWAY_ROUTE_EPOCH_MISMATCH"};
  return {ready:true,reason:"SHARED_GATEWAY_ROUTE_CONTRACT_VERIFIED"};
 }catch(_){return {ready:false,reason:"SHARED_GATEWAY_PROBE_FAILED"}}
 finally{clearTimeout(timer)}
}
async function sourceCall(token:string,action:string,payload:Record<string,unknown>={}){
 const response=await fetch(PEER_URL+"/functions/v1/db-sync-export",{method:"POST",headers:{apikey:PEER_KEY,"content-type":"application/json",authorization:"Bearer "+token},body:JSON.stringify({action,...payload}),cache:"no-store"});
 const data:any=await response.json().catch(()=>({}));
 if(!response.ok||data?.ok!==true)throw new Error(String(data?.error||("SOURCE_SYNC_HTTP_"+response.status)));
 return data;
}
async function authorize(token:string,admin:any){
 if(!token)throw new Error("OWNER_TOKEN_REQUIRED");
 const response=await fetch(PEER_URL+"/auth/v1/user",{headers:{apikey:PEER_KEY,authorization:"Bearer "+token},cache:"no-store"});
 if(!response.ok)throw new Error("OWNER_SESSION_INVALID");
 const user=await response.json();
 const source=await sourceCall(token,"authorize");
 if(source.userId!==user.id||source.role!=="owner")throw new Error("OWNER_ONLY");
 return {id:String(user.id),email:String(user.email||"")};
}
async function runRow(admin:any,runId:string,userId:string){
 const {data,error}=await admin.from("db_sync_runs").select("id,started_by,started_at,state,summary").eq("id",runId).maybeSingle();
 if(error||!data)throw new Error("SYNC_RUN_NOT_FOUND");
 if(String(data.started_by)!==userId)throw new Error("SYNC_RUN_OWNER_MISMATCH");
 if(data.state!=="running")throw new Error("SYNC_RUN_NOT_RUNNING");
 return data;
}
async function targetHash(admin:any,table:string){
 const pk=TABLES[table];if(!pk)throw new Error("TABLE_NOT_ALLOWED");
 const items:string[]=[];let offset=0;
 while(true){
  const {data,error}=await admin.from(table).select("*").order(pk,{ascending:true}).range(offset,offset+499);
  if(error)throw new Error("TARGET_READ_FAILED:"+table);
  const rows=data||[];for(const row of rows)items.push(stable(row));
  offset+=rows.length;if(rows.length<500)break;
  if(offset>250000)throw new Error("SYNC_ROW_LIMIT_EXCEEDED:"+table);
 }
 return {table,count:offset,hash:await sha(items.join("\n"))};
}
async function activeIds(token:string){const x=await sourceCall(token,"auth-members");return [...new Set((x.userIds||[]).map(String))].sort()}
async function routeRow(admin:any){
 const {data,error}=await admin.from("db_route_control").select("active_target,epoch,switch_id,schema_version,primary_schema_version,backup_schema_version,primary_ready,backup_ready,sync_ready,auth_parity_ready,auth_verified_user_ids,data_parity_ready,routing_gateway_ready,last_parity_check_at,last_parity_check_note").eq("id",1).single();
 if(error||!data)throw new Error("ROUTE_CONTROL_LOOKUP_FAILED");return data;
}
async function verifyTargetLogin(admin:any,token:string,user:any,password:string){
 if(!password)throw new Error("TARGET_DB_PASSWORD_REQUIRED");
 if(!user.email)throw new Error("OWNER_EMAIL_REQUIRED");
 const response=await fetch(SELF_URL+"/auth/v1/token?grant_type=password",{method:"POST",headers:{apikey:SELF_KEY,"content-type":"application/json"},body:JSON.stringify({email:user.email,password}),cache:"no-store"});
 const data:any=await response.json().catch(()=>({}));
 if(!response.ok||!data?.access_token||String(data.user?.id||"")!==user.id)throw new Error("DB2_LOGIN_TEST_FAILED: sign in to DB2 with this account's current DB2 password or reset that password in DB2 first");
 // Do not return/store the target access token.
 const required=await activeIds(token);
 const prior=await routeRow(admin);
 const verified=[...new Set([...(prior.auth_verified_user_ids||[]).map(String),user.id])];
 const targetAuthReady=required.every(id=>verified.includes(id));
 const {error:targetError}=await admin.from("db_route_control").update({auth_verified_user_ids:verified,auth_parity_ready:targetAuthReady,last_parity_check_note:"A real password login test passed on the target database for one active owner/admin. Data readiness is checked separately."}).eq("id",1);
 if(targetError)throw new Error("TARGET_AUTH_VERIFICATION_SAVE_FAILED");
 const source=await sourceCall(token,"record-auth-verification",{userId:user.id});
 const sourceResp=await fetch(PEER_URL+"/functions/v1/db-route-status",{headers:{apikey:PEER_KEY},cache:"no-store"});
 const sourceStatus:any=await sourceResp.json().catch(()=>({}));
 const sourceRoute=sourceStatus?.route;
 const authReady=targetAuthReady&&source.authParityReady===true&&sourceRoute?.auth_parity_ready===true;
 const requiredCount=required.length,verifiedCount=required.filter(id=>verified.includes(id)).length;
 return {ok:true,verifiedUserCount:verifiedCount,requiredUserCount:requiredCount,authParityReady:authReady,message:authReady?"All active owner/admin accounts have verified DB2 login.":"Login verified for this account; any remaining active owner/admin account must verify separately."};
}
async function handler(req:Request){
 if(req.method==="OPTIONS")return new Response(null,{status:204,headers:H});
 if(req.method!=="POST")return out(405,{ok:false,error:"method_not_allowed"});
 let body:any={};try{body=await req.json()}catch(_){return out(400,{ok:false,error:"invalid_json"})}
 try{
  const admin=db(),token=String((req.headers.get("authorization")||"").replace(/^Bearer\s+/i,"")||body.accessToken||"");
  const user=await authorize(token,admin),action=String(body.action||"");
  if(action==="preview"){
   const manifest=await sourceCall(token,"manifest"),tables:any[]=[];
   for(const item of manifest.tables||[]){
    const {count,error}=await admin.from(item.table).select(TABLES[item.table],{count:"exact",head:true});
    if(error)throw new Error("TARGET_COUNT_FAILED:"+item.table);
    tables.push({table:item.table,sourceCount:Number(item.count)||0,targetCount:count??0});
   }
   return out(200,{ok:true,sourceRef:PEER_REF,targetRef:SELF_REF,tables,auth:manifest.auth});
  }
  if(action==="start"){
   const {data:existing,error:existingError}=await admin.from("db_sync_runs").select("id,started_by,started_at,state").eq("state","running").order("started_at",{ascending:false}).limit(1).maybeSingle();
   if(existingError)throw new Error("SYNC_RUN_LOOKUP_FAILED");
   let run=existing;
   if(run&&String(run.started_by)!==user.id)throw new Error("SYNC_ALREADY_RUNNING_FOR_ANOTHER_OWNER");
   if(!run){
    const {data:created,error:insertError}=await admin.from("db_sync_runs").insert({started_by:user.id,state:"running",summary:{mode:"upsert_active_source_to_standby",startedBy:"admin-menu"}}).select("id,started_at,state,started_by").single();
    if(insertError||!created)throw new Error("SYNC_RUN_CREATE_FAILED");
    run=created;
   }
   await sourceCall(token,"start-sync",{note:"Cross-database sync is running. Current active route remains online; route changes are locked until verification."});
   const {error:targetError}=await admin.from("db_route_control").update({sync_in_progress:true,data_parity_ready:false,routing_gateway_ready:false,sync_ready:false,last_parity_check_at:null,last_parity_check_note:"DB Sync in progress. Current global route remains online; cutover locked."}).eq("id",1);
   if(targetError)throw new Error("TARGET_SYNC_LOCK_FAILED");
   const manifest=await sourceCall(token,"manifest");
   return out(200,{ok:true,runId:run.id,startedAt:run.started_at,tables:manifest.tables,sourceRef:PEER_REF,targetRef:SELF_REF});
  }
  if(action==="apply-page"){
   const runId=String(body.runId||"");await runRow(admin,runId,user.id);
   const table=String(body.table||"");if(!TABLES[table])return out(400,{ok:false,error:"TABLE_NOT_ALLOWED"});
   const offset=Math.max(0,Math.trunc(Number(body.offset)||0)),limit=Math.min(500,Math.max(1,Math.trunc(Number(body.limit)||250)));
   const page=await sourceCall(token,"page",{table,offset,limit});
   if(!Array.isArray(page.rows))throw new Error("SOURCE_PAGE_INVALID");
   if(page.rows.length){
    const {error}=await admin.from(table).upsert(page.rows,{onConflict:TABLES[table],ignoreDuplicates:false});
    if(error)throw new Error("TARGET_UPSERT_FAILED:"+table+":"+error.message);
   }
   return out(200,{ok:true,runId,table,offset,processed:page.rows.length,total:Number(page.count)||0,more:page.more===true});
  }
  if(action==="verify-table"){
   const runId=String(body.runId||"");await runRow(admin,runId,user.id);
   const table=String(body.table||"");if(!TABLES[table])return out(400,{ok:false,error:"TABLE_NOT_ALLOWED"});
   const source=await sourceCall(token,"hash",{table}),target=await targetHash(admin,table);
   const matched=Number(source.count)===target.count&&String(source.hash||"")===target.hash;
   const {error}=await admin.from("db_sync_verification").upsert({run_id:runId,table_name:table,source_count:Number(source.count)||0,target_count:target.count,source_hash:String(source.hash||""),target_hash:target.hash,matched,checked_at:new Date().toISOString()},{onConflict:"run_id,table_name"});
   if(error)throw new Error("SYNC_EVIDENCE_SAVE_FAILED:"+table);
   return out(200,{ok:true,runId,table,sourceCount:Number(source.count)||0,targetCount:target.count,matched,required:!NON_BLOCKING_TABLES.has(table)});
  }
  if(action==="verify-owner-login"){
   const password=String(body.password||"");
   return out(200,await verifyTargetLogin(admin,token,user,password));
  }
  if(action==="mark-ready"){
   const runId=String(body.runId||""),run=await runRow(admin,runId,user.id);
   const {data:evidence,error:evidenceError}=await admin.from("db_sync_verification").select("table_name,matched,checked_at").eq("run_id",runId);
   if(evidenceError)throw new Error("SYNC_EVIDENCE_LOOKUP_FAILED");
   const expected=Object.keys(TABLES).filter(name=>!NON_BLOCKING_TABLES.has(name)),byName=new Map((evidence||[]).map((e:any)=>[e.table_name,e]));
   const missing=expected.filter(name=>!byName.has(name)||byName.get(name)?.matched!==true||Date.parse(byName.get(name)?.checked_at||"")<Date.parse(run.started_at));
   if(missing.length)throw new Error("TABLE_PARITY_NOT_VERIFIED:"+missing.join(","));
   const ids=await activeIds(token),route=await routeRow(admin);
   const targetAuthOk=ids.every(id=>(route.auth_verified_user_ids||[]).map(String).includes(id));
   const sourceResp=await fetch(PEER_URL+"/functions/v1/db-route-status",{headers:{apikey:PEER_KEY},cache:"no-store"});
   const sourceStatus:any=await sourceResp.json().catch(()=>({}));
   const sourceRoute=sourceStatus?.route;
   const sourceAuthOk=sourceResp.ok&&sourceRoute?.auth_parity_ready===true&&ids.every((id:string)=>(sourceRoute.auth_verified_user_ids||[]).map(String).includes(id));
   if(!targetAuthOk||!sourceAuthOk){
    const count=ids.filter(id=>(route.auth_verified_user_ids||[]).map(String).includes(id)).length;
    throw new Error("AUTH_VERIFICATION_REQUIRED:"+count+"/"+ids.length);
   }
   const targetVersion=String(route.schema_version||route.primary_schema_version||"");
   const sourceVersion=String(sourceRoute?.schema_version||sourceRoute?.primary_schema_version||"");
   if(!targetVersion||!sourceVersion||targetVersion!==sourceVersion)throw new Error("SCHEMA_VERSION_MISMATCH");
   const gateway=await sharedGatewayProbe(route),gatewayReady=gateway.ready;
   const now=new Date().toISOString();
   const note="Sync run "+runId+" verified: "+expected.length+" critical table hashes match the active source and active owner/admin logins are verified. Volatile heartbeat/audit histories are best-effort. "+(gatewayReady?"Shared gateway resolver independently verified.":"Shared gateway remains unverified ("+gateway.reason+"); cutover stays blocked.");
   const {error:updateError}=await admin.from("db_route_control").update({
    backup_ready:true,data_parity_ready:true,routing_gateway_ready:gatewayReady,sync_ready:gatewayReady,auth_parity_ready:true,
    primary_schema_version:sourceVersion,backup_schema_version:targetVersion,schema_version:targetVersion,
    last_schema_check_at:now,last_parity_check_at:now,last_parity_check_note:note
   }).eq("id",1);
   if(updateError)throw new Error("TARGET_READINESS_UPDATE_FAILED");
   let sourceReady:any;
   try{sourceReady=await sourceCall(token,"mark-ready",{runId})}catch(e){
    await admin.from("db_route_control").update({backup_ready:false,data_parity_ready:false,routing_gateway_ready:false,sync_ready:false,last_parity_check_note:"Target data verified but source readiness update failed; cutover remains blocked."}).eq("id",1);
    throw e;
   }
   const gatewayBothReady=gatewayReady&&sourceReady?.gatewayReady===true;
   if(!gatewayBothReady){
    const blockedNote="Data/schema/auth parity verified, but shared gateway verification is missing or inconsistent ("+gateway.reason+"). Cutover remains blocked.";
    const {error:blockError}=await admin.from("db_route_control").update({backup_ready:true,data_parity_ready:true,routing_gateway_ready:false,sync_ready:false,last_parity_check_note:blockedNote}).eq("id",1);
    if(blockError)throw new Error("GATEWAY_BLOCK_STATUS_SAVE_FAILED");
   }
   const {error:unlockError}=await admin.from("db_route_control").update({sync_in_progress:false}).eq("id",1);
   if(unlockError)throw new Error("TARGET_SYNC_UNLOCK_FAILED");
   const advisory=Object.keys(TABLES).filter(name=>NON_BLOCKING_TABLES.has(name)&&byName.get(name)?.matched!==true);
   const {error:runError}=await admin.from("db_sync_runs").update({state:"verified",completed_at:now,summary:{mode:"upsert_active_source_to_standby",tablesVerified:expected.length,advisoryTables:advisory,authVerified:ids.length,sharedGatewayReady:gatewayBothReady,gatewayReason:gatewayBothReady?null:gateway.reason}}).eq("id",runId);
   if(runError)throw new Error("SYNC_RUN_FINALIZE_FAILED");
   return out(200,{ok:true,runId,verifiedTables:expected.length,advisoryTables:advisory,verifiedOwners:ids.length,dataVerified:true,gatewayReady:gatewayBothReady,ready:gatewayBothReady,sourceRef:PEER_REF,targetRef:SELF_REF,message:gatewayBothReady?"Data parity verified and shared gateway is ready. Active route remains unchanged until the global switch is requested.":"Data/schema/auth parity passed, but shared gateway is not verified; DB2 remains blocked from cutover.",gatewayReason:gatewayBothReady?null:gateway.reason});
  }
  if(action==="abort"){
   const runId=String(body.runId||"");
   const run=await runRow(admin,runId,user.id);
   await sourceCall(token,"finish-sync",{note:"DB Sync was stopped before parity completed. Route switch stays blocked until a clean sync succeeds."});
   const now=new Date().toISOString();
   const {error:unlockError}=await admin.from("db_route_control").update({sync_in_progress:false,data_parity_ready:false,routing_gateway_ready:false,sync_ready:false,last_parity_check_at:null,last_parity_check_note:"DB Sync stopped; a complete table-hash verification is required before any route switch."}).eq("id",1);
   if(unlockError)throw new Error("TARGET_SYNC_UNLOCK_FAILED");
   const {error:runError}=await admin.from("db_sync_runs").update({state:"failed",completed_at:now,summary:{mode:"upsert_active_source_to_standby",aborted:true,reason:"owner_abort"}}).eq("id",runId);
   if(runError)throw new Error("SYNC_RUN_FINALIZE_FAILED");
   return out(200,{ok:true,runId,aborted:true,cutoverReady:false,message:"Sync stopped. Current database remains active; switching stays blocked until sync and parity verification pass."});
  }
  if(action==="status"){
   const route=await routeRow(admin);
   const {data:runs,error}=await admin.from("db_sync_runs").select("id,started_at,completed_at,state,summary").order("started_at",{ascending:false}).limit(5);
   if(error)throw new Error("SYNC_STATUS_LOOKUP_FAILED");
   return out(200,{ok:true,route,runs:runs||[]});
  }
  return out(400,{ok:false,error:"unknown_action"});
 }catch(e){
  const m=e instanceof Error?e.message:"sync_backend_failed";
  const status=/OWNER|SESSION/.test(m)?403:/TABLE_NOT_ALLOWED|invalid_json|PASSWORD/.test(m)?400:/FAILED|NOT_CONFIGURED|LIMIT/.test(m)?503:409;
  return out(status,{ok:false,error:m});
 }
}
Deno.serve(handler);
