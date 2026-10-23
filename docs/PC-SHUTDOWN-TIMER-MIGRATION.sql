-- AniGames PC Shutdown Timer migration.
-- Review first, then apply independently to DB1 and DB2 before enabling the Admin controls.
-- This migration only extends the command allowlist/RPC validation; it does NOT enqueue or run shutdown.
-- PC Billing also performs a local active/paused rental guard immediately before Windows powerAction.

begin;

 -- Preserve the current command constraint verbatim and only add the three timer commands.
-- Fail closed if the expected constraint is absent; do not guess the live allowlist.
do $migration$
declare
  prior_check text;
begin
  select pg_get_expr(conbin, conrelid)
    into prior_check
  from pg_constraint
  where conrelid = 'public.device_commands'::regclass
    and conname = 'device_commands_command_check'
    and contype = 'c';

  if prior_check is null then
    raise exception 'DEVICE_COMMAND_CHECK_NOT_FOUND: inspect schema before applying timer migration';
  end if;

  alter table public.device_commands drop constraint device_commands_command_check;
  execute format(
    'alter table public.device_commands add constraint device_commands_command_check check ((%s) or command = any (array[%L::text, %L::text, %L::text]))',
    prior_check, 'shutdown_timer_set', 'shutdown_timer_cancel', 'shutdown_timer_status'
  );
end;
$migration$;

create or replace function api.admin_command(
  p_org_id uuid,
  p_device_id uuid,
  p_command text,
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_catalog
as $function$
declare
  a public.admin_accounts%rowtype;
  d public.devices%rowtype;
  s public.rental_sessions%rowtype;
  cid uuid;
  sid uuid;
  timer_seconds integer;
begin
  if auth.uid() is null then raise exception 'UNAUTHENTICATED'; end if;

  select * into a from public.admin_accounts
  where auth_user_id = auth.uid() and status = 'active' limit 1;
  if not found then raise exception 'ADMIN_ACCOUNT_NOT_CONFIGURED'; end if;
  if a.role <> 'SUPER_ADMIN' and a.org_id is distinct from p_org_id then
    raise exception 'ORG_ACCESS_DENIED';
  end if;

  select * into d from public.devices
  where id = p_device_id and org_id = p_org_id limit 1;
  if not found or not private.admin_can_access_device(p_device_id, p_org_id) then
    raise exception 'DEVICE_ACCESS_DENIED';
  end if;
  if d.status = 'disabled' then raise exception 'DEVICE_DISABLED'; end if;
  if coalesce(d.last_heartbeat_at, d.last_seen_at) is null
     or coalesce(d.last_heartbeat_at, d.last_seen_at) < now() - interval '45 seconds'
     or d.status <> 'online' then
    raise exception 'PC_OFFLINE_COMMAND_BLOCKED';
  end if;

  if p_command not in (
    'restart_billing','restart_pc','restart','logoff','logout','pause','resume',
    'stop','shutdown','refresh','wake','add_time','show_admin_message',
    'shutdown_timer_set','shutdown_timer_cancel','shutdown_timer_status'
  ) then
    raise exception 'COMMAND_NOT_ALLOWED';
  end if;

  if p_command like 'shutdown_timer_%' and not private.is_owner_access(p_org_id) then
    raise exception 'OWNER_ONLY';
  end if;

  if p_command = 'show_admin_message'
     and length(btrim(coalesce(p_payload->>'message',''))) not between 1 and 240 then
    raise exception 'INVALID_ADMIN_MESSAGE';
  end if;

  if p_command = 'shutdown_timer_set' then
    if coalesce(p_payload->>'seconds','') !~ '^[0-9]{1,5}$' then
      raise exception 'INVALID_SHUTDOWN_TIMER_SECONDS';
    end if;
    timer_seconds := (p_payload->>'seconds')::integer;
    if timer_seconds < 60 or timer_seconds > 86400 then
      raise exception 'INVALID_SHUTDOWN_TIMER_SECONDS';
    end if;
    if exists (
      select 1 from public.rental_sessions
      where org_id = p_org_id and device_id = p_device_id
        and status in ('active','paused')
    ) then
      raise exception 'ACTIVE_RENTAL_SHUTDOWN_BLOCKED';
    end if;
  end if;

  if p_command in ('pause','resume','stop') then
    if nullif(p_payload->>'session_id','') is null then raise exception 'SESSION_ID_REQUIRED'; end if;
    sid := (p_payload->>'session_id')::uuid;
    select * into s from public.rental_sessions
    where id = sid and org_id = p_org_id and device_id = p_device_id for update;
    if not found then raise exception 'SESSION_NOT_FOUND'; end if;
    if p_command = 'pause' and s.status <> 'active' then raise exception 'SESSION_NOT_ACTIVE'; end if;
    if p_command = 'resume' and s.status <> 'paused' then raise exception 'SESSION_NOT_PAUSED'; end if;
    if p_command = 'stop' and s.status not in ('active','paused') then raise exception 'SESSION_NOT_OPEN'; end if;
  end if;

  insert into public.device_commands(org_id, device_id, command, payload, status, created_by)
  values (p_org_id, p_device_id, p_command, coalesce(p_payload,'{}'::jsonb), 'queued', auth.uid())
  returning id into cid;

  insert into public.audit_logs(org_id, actor_user_id, action, target_type, target_id, payload)
  values (
    p_org_id, auth.uid(), 'remote_command', 'device', p_device_id::text,
    jsonb_build_object('command',p_command,'command_id',cid,'payload',coalesce(p_payload,'{}'::jsonb))
  );

  return jsonb_build_object('ok',true,'command_id',cid,'device_id',p_device_id,'command',p_command);
end;
$function$;

create or replace function api.queue_command(
  p_org_id uuid,
  p_device_id uuid,
  p_command text,
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_catalog
as $function$
declare
  uid uuid := auth.uid();
  cid uuid;
  timer_seconds integer;
begin
  if uid is null then raise exception 'AUTH_REQUIRED'; end if;
  if not private.is_owner_access(p_org_id) then raise exception 'OWNER_ONLY'; end if;
  if not exists(select 1 from public.devices where id=p_device_id and org_id=p_org_id) then
    raise exception 'DEVICE_NOT_FOUND';
  end if;

  if p_command not in (
    'restart_billing','restart_pc','restart','logoff','logout','pause','resume',
    'stop','shutdown','add_time','set_theme','refresh','wake','upsert_rental',
    'show_admin_message','shutdown_timer_set','shutdown_timer_cancel','shutdown_timer_status'
  ) then
    raise exception 'INVALID_COMMAND';
  end if;

  if p_command = 'show_admin_message'
     and length(btrim(coalesce(p_payload->>'message',''))) not between 1 and 240 then
    raise exception 'INVALID_ADMIN_MESSAGE';
  end if;

  if p_command = 'shutdown_timer_set' then
    if coalesce(p_payload->>'seconds','') !~ '^[0-9]{1,5}$' then
      raise exception 'INVALID_SHUTDOWN_TIMER_SECONDS';
    end if;
    timer_seconds := (p_payload->>'seconds')::integer;
    if timer_seconds < 60 or timer_seconds > 86400 then
      raise exception 'INVALID_SHUTDOWN_TIMER_SECONDS';
    end if;
    if exists (
      select 1 from public.rental_sessions
      where org_id = p_org_id and device_id = p_device_id
        and status in ('active','paused')
    ) then
      raise exception 'ACTIVE_RENTAL_SHUTDOWN_BLOCKED';
    end if;
  end if;

  insert into public.device_commands(org_id,device_id,command,payload,status,created_by)
  values(p_org_id,p_device_id,p_command,coalesce(p_payload,'{}'::jsonb),'queued',uid)
  returning id into cid;

  insert into public.device_command_logs(command_id,org_id,device_id,status,result)
  values(cid,p_org_id,p_device_id,'queued',coalesce(p_payload,'{}'::jsonb));

  insert into public.audit_logs(org_id,actor_user_id,action,target_type,target_id,payload)
  values(p_org_id,uid,'queue_device_command','device_command',cid,
         jsonb_build_object('command',p_command,'device_id',p_device_id));

  return jsonb_build_object('command_id',cid,'status','queued');
end;
$function$;

commit;
