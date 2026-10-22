import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
const cors = {"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"authorization, apikey, content-type, x-client-info","Access-Control-Allow-Methods":"GET, OPTIONS"};
const json=(status:number,body:unknown)=>new Response(JSON.stringify(body),{status,headers:{...cors,"Content-Type":"application/json","Cache-Control":"no-store"}});
function keyFromEnvMap(name:string):string{
 const raw=Deno.env.get(name)||"";
 try{const parsed=JSON.parse(raw);if(parsed&&typeof parsed==="object"){if(typeof parsed.default==="string"&&parsed.default)return parsed.default;const first=Object.values(parsed).find(v=>typeof v==="string"&&v.length>0);if(typeof first==="string")return first;}}catch(_){}
 return "";
}
function serverSecretKey():string{return Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")||Deno.env.get("SUPABASE_SECRET_KEY")||keyFromEnvMap("SUPABASE_SECRET_KEYS");}
Deno.serve(async(req:Request)=>{
 if(req.method==="OPTIONS")return new Response("ok",{headers:cors});
 if(req.method!=="GET")return json(405,{ok:false,error:"method_not_allowed"});
 const url=Deno.env.get("SUPABASE_URL")||"",serviceKey=serverSecretKey();
 if(!url||!serviceKey)return json(503,{ok:false,readOnly:true,error:"server_config_missing"});
 let projectRef="unknown";try{projectRef=new URL(url).hostname.split(".")[0]||"unknown"}catch(_){}
 try{
  const db=createClient(url,serviceKey,{auth:{persistSession:false,autoRefreshToken:false}});
  const {data:r,error}=await db.from("db_route_control").select("active_target,epoch,updated_at,updated_by,reason,sync_ready,schema_version,switch_id,primary_ready,backup_ready,auth_parity_ready,auth_verified_user_ids,sync_in_progress,sync_write_quiesce,sync_write_quiesce_at,data_parity_ready,routing_gateway_ready,primary_schema_version,backup_schema_version,last_schema_check_at,last_parity_check_at,last_parity_check_note,last_cutover_test_at,cutover_test_note").eq("id",1).maybeSingle();
  if(error||!r)return json(503,{ok:false,readOnly:true,projectRef,error:"route_unavailable"});
  const parityTs=Date.parse(String(r.last_parity_check_at||""));
  const fresh=Number.isFinite(parityTs)&&Date.now()-parityTs<=30*60*1000&&parityTs<=Date.now()+60000;
  const versionsMatch=!!r.schema_version&&r.schema_version===r.primary_schema_version&&r.schema_version===r.backup_schema_version;
  const authParity=r.auth_parity_ready===true,dataParity=r.data_parity_ready===true,gateway=r.routing_gateway_ready===true,syncReady=r.sync_ready===true;
  const parityNote=String(r.last_parity_check_note||"");
  const hashProof=parityNote.includes("CORE_PARITY_HASH_PASS")&&parityNote.includes("ACTIVE_SESSION_HASH_PASS");
  const canSwitch=r.primary_ready===true&&r.backup_ready===true&&dataParity&&gateway&&syncReady&&versionsMatch&&fresh&&hashProof&&r.sync_in_progress!==true&&r.sync_write_quiesce!==true;
  return json(200,{ok:true,readOnly:true,projectRef,route:{
   active_target:r.active_target,epoch:Number(r.epoch),updated_at:r.updated_at,updated_by:r.updated_by||null,reason:r.reason||null,
   local_profile:projectRef==="xcdbipgsvohesxhxydep"?"backup":"primary",project_ref:projectRef,
   sync_ready:r.sync_ready===true,schema_version:r.schema_version||null,switch_id:r.switch_id||null,
   primary_ready:r.primary_ready===true,backup_ready:r.backup_ready===true,backup_native_optional:true,
   auth_parity_ready:authParity,auth_verified_user_ids:Array.isArray(r.auth_verified_user_ids)?r.auth_verified_user_ids:[],auth_parity_optional:true,
   sync_in_progress:r.sync_in_progress===true,sync_write_quiesce:r.sync_write_quiesce===true,sync_write_quiesce_at:r.sync_write_quiesce_at||null,
   data_parity_ready:dataParity,routing_gateway_ready:gateway,primary_schema_version:r.primary_schema_version||null,backup_schema_version:r.backup_schema_version||null,
   can_switch_to_backup:canSwitch,can_switch_to_primary:canSwitch,last_schema_check_at:r.last_schema_check_at||null,last_parity_check_at:r.last_parity_check_at||null,
   last_parity_check_note:r.last_parity_check_note||null,last_cutover_test_at:r.last_cutover_test_at||null,cutover_test_note:r.cutover_test_note||null
  },servedAt:new Date().toISOString()});
 }catch(_){return json(503,{ok:false,readOnly:true,projectRef,error:"route_status_failed"});}
});