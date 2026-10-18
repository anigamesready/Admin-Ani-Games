import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
const cors = {"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"authorization, apikey, content-type, x-client-info","Access-Control-Allow-Methods":"GET, OPTIONS"};
const json=(status:number,body:unknown)=>new Response(JSON.stringify(body),{status,headers:{...cors,"Content-Type":"application/json","Cache-Control":"no-store"}});
Deno.serve(async(req:Request)=>{
 if(req.method==="OPTIONS")return new Response("ok",{headers:cors});
 if(req.method!=="GET")return json(405,{ok:false,error:"method_not_allowed"});
 const url=Deno.env.get("SUPABASE_URL")||"",serviceKey=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")||Deno.env.get("SUPABASE_SECRET_KEY")||"";
 if(!url||!serviceKey)return json(503,{ok:false,readOnly:true,error:"server_config_missing"});
 let projectRef="unknown";try{projectRef=new URL(url).hostname.split(".")[0]||"unknown"}catch(_){}
 try{
  const db=createClient(url,serviceKey,{auth:{persistSession:false,autoRefreshToken:false}});
  const {data:r,error}=await db.from("db_route_control").select("active_target,epoch,updated_at,updated_by,reason,sync_ready,schema_version,switch_id,primary_ready,backup_ready,auth_parity_ready,auth_verified_user_ids,data_parity_ready,routing_gateway_ready,primary_schema_version,backup_schema_version,last_schema_check_at,last_parity_check_at,last_parity_check_note,last_cutover_test_at,cutover_test_note").eq("id",1).maybeSingle();
  if(error||!r)return json(503,{ok:false,readOnly:true,projectRef,error:"route_unavailable"});
  const fresh=!!r.last_parity_check_at&&Date.now()-Date.parse(r.last_parity_check_at)<=30*60*1000&&Date.parse(r.last_parity_check_at)<=Date.now()+60000;
  const versionsMatch=!!r.schema_version&&r.schema_version===r.primary_schema_version&&r.schema_version===r.backup_schema_version;
  const authParity=r.auth_parity_ready===true;
  const dataParity=r.data_parity_ready===true;
  const gateway=r.routing_gateway_ready===true;
  const readiness=authParity&&dataParity&&gateway&&fresh&&versionsMatch;
  return json(200,{ok:true,readOnly:true,projectRef,route:{
   active_target:r.active_target,epoch:Number(r.epoch),updated_at:r.updated_at,updated_by:r.updated_by||null,reason:r.reason||null,
   local_profile:projectRef==="xcdbipgsvohesxhxydep"?"backup":"primary",project_ref:projectRef,
   sync_ready:r.sync_ready===true,schema_version:r.schema_version||null,switch_id:r.switch_id||null,
   primary_ready:r.primary_ready===true,backup_ready:r.backup_ready===true,auth_parity_ready:authParity,
   auth_verified_user_ids:Array.isArray(r.auth_verified_user_ids)?r.auth_verified_user_ids:[],
   data_parity_ready:dataParity,routing_gateway_ready:gateway,
   primary_schema_version:r.primary_schema_version||null,backup_schema_version:r.backup_schema_version||null,
   can_switch_to_backup:r.backup_ready===true&&readiness,
   can_switch_to_primary:r.primary_ready===true&&readiness,
   last_schema_check_at:r.last_schema_check_at||null,last_parity_check_at:r.last_parity_check_at||null,
   last_parity_check_note:r.last_parity_check_note||null,last_cutover_test_at:r.last_cutover_test_at||null,
   cutover_test_note:r.cutover_test_note||null
  },servedAt:new Date().toISOString()});
 }catch(_){return json(503,{ok:false,readOnly:true,projectRef,error:"route_status_failed"})}
});