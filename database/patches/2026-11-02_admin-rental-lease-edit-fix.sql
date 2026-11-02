-- AniGames Admin V12.1.42
-- Rental master-data edits are independent of PC online/offline status.
-- Safety invariants:
--   1) An active/paused rental session still blocks sensitive edits and disable.
--   2) A valid rental_offline_leases row is NOT deleted or shortened by admin edits.
--   3) Keeping that lease preserves the anti-duplicate reservation until natural expiry.
--   4) The lease-holding PC receives current master data on its next online lookup.

CREATE OR REPLACE FUNCTION api.admin_update_rental_global(
  p_org_id uuid,
  p_rental_id uuid,
  p_code text,
  p_category text,
  p_minutes bigint,
  p_client_label text,
  p_expiry_at timestamp with time zone,
  p_status text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  uid uuid := auth.uid();
  r public.rental_accounts%ROWTYPE;
  c text := upper(trim(coalesce(p_code,'')));
  cat text := coalesce(nullif(trim(p_category),''),'reguler');
  st text := coalesce(p_status,'');
  secs bigint;
  expiry timestamptz := p_expiry_at;
  active_row boolean;
  v_lease_until timestamptz;
  v_lease_device_id uuid;
BEGIN
  IF uid IS NULL THEN RAISE EXCEPTION 'UNAUTHENTICATED'; END IF;
  IF NOT COALESCE(private.is_owner_access(p_org_id), false)
     AND NOT EXISTS (
       SELECT 1 FROM public.org_members m
       WHERE m.org_id=p_org_id AND m.auth_user_id=uid AND m.role='reseller_admin'
     ) THEN
    RAISE EXCEPTION 'ADMIN_ORG_ACCESS_DENIED';
  END IF;

  IF p_rental_id IS NULL OR c='' OR length(c)>120 OR c='__TEST10__' THEN
    RAISE EXCEPTION 'RENTAL_FIELDS_INVALID';
  END IF;
  IF p_minutes IS NULL OR p_minutes<0 OR p_minutes>525600 THEN
    RAISE EXCEPTION 'RENTAL_MINUTES_INVALID';
  END IF;
  IF cat NOT IN ('reguler','mingguan','bulanan','hemat','sultan','mega hemat') THEN
    RAISE EXCEPTION 'RENTAL_CATEGORY_INVALID';
  END IF;
  IF st NOT IN ('active','expired','disabled') THEN
    RAISE EXCEPTION 'RENTAL_STATUS_INVALID';
  END IF;
  IF expiry IS NOT NULL AND expiry<=now() THEN RAISE EXCEPTION 'EXPIRY_MUST_BE_FUTURE'; END IF;

  secs := p_minutes*60;
  IF secs=0 AND st='active' THEN st:='expired'; END IF;

  SELECT * INTO r
  FROM public.rental_accounts
  WHERE id=p_rental_id AND org_id=p_org_id
  FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'RENTAL_NOT_FOUND'; END IF;

  PERFORM pg_advisory_xact_lock(hashtextextended(p_org_id::text||':'||c,0));
  IF EXISTS (
    SELECT 1 FROM public.rental_accounts x
    WHERE x.org_id=p_org_id AND upper(trim(x.code))=c AND x.id<>r.id
  ) THEN
    RAISE EXCEPTION 'CODE_ALREADY_EXISTS';
  END IF;

  active_row := EXISTS(
    SELECT 1 FROM public.rental_sessions s
    WHERE s.rental_account_id=r.id AND s.status IN ('active','paused')
  );
  IF active_row AND (
       c<>upper(trim(r.code))
       OR secs<>r.remaining_seconds
       OR expiry IS DISTINCT FROM r.expiry_at
       OR st<>'active'
  ) THEN
    RAISE EXCEPTION 'RENTAL_ACTIVE_TIMER_LOCKED';
  END IF;

  -- A lease is a temporary reservation against duplicate use, not a lock
  -- on the owner-controlled master rental record.
  SELECT l.lease_until,l.device_id
    INTO v_lease_until,v_lease_device_id
  FROM public.rental_offline_leases l
  WHERE l.rental_account_id=r.id
  FOR UPDATE;

  UPDATE public.rental_accounts
  SET code=c,
      category=cat,
      remaining_seconds=secs,
      expiry_at=expiry,
      client_label=nullif(trim(p_client_label),''),
      status=st,
      updated_at=now(),
      metadata=coalesce(metadata,'{}'::jsonb)
        || jsonb_build_object('source','admin-global-edit','adminEditedAt',now())
  WHERE id=r.id;

  INSERT INTO public.audit_logs(org_id,actor_user_id,action,target_type,target_id,payload)
  VALUES(
    p_org_id,uid,'admin_update_rental_global','rental_account',r.id,
    jsonb_build_object(
      'old_code',r.code,'new_code',c,
      'old_minutes',floor(r.remaining_seconds/60.0),'new_minutes',p_minutes,
      'old_status',r.status,'new_status',st,
      'lease_preserved',v_lease_until>now(),
      'lease_until',v_lease_until,
      'lease_device_id',v_lease_device_id,
      'device_independent_edit',true
    )
  );

  RETURN jsonb_build_object(
    'ok',true,'id',r.id,'org_id',p_org_id,'code',c,'category',cat,
    'remaining_seconds',secs,'expiry_at',expiry,'status',st,
    'device_id',r.device_id,
    'lease_preserved',v_lease_until>now(),
    'lease_until',v_lease_until,
    'lease_device_id',v_lease_device_id
  );
END
$function$;

CREATE OR REPLACE FUNCTION api.admin_disable_rental_global(
  p_org_id uuid,
  p_rental_id uuid
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  uid uuid := auth.uid();
  r public.rental_accounts%ROWTYPE;
  v_lease_until timestamptz;
  v_lease_device_id uuid;
BEGIN
  IF uid IS NULL THEN RAISE EXCEPTION 'UNAUTHENTICATED'; END IF;
  IF NOT COALESCE(private.is_owner_access(p_org_id), false)
     AND NOT EXISTS (
       SELECT 1 FROM public.org_members m
       WHERE m.org_id=p_org_id AND m.auth_user_id=uid AND m.role='reseller_admin'
     ) THEN
    RAISE EXCEPTION 'ADMIN_ORG_ACCESS_DENIED';
  END IF;

  SELECT * INTO r
  FROM public.rental_accounts
  WHERE id=p_rental_id AND org_id=p_org_id
  FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'RENTAL_NOT_FOUND'; END IF;

  IF EXISTS(
    SELECT 1 FROM public.rental_sessions s
    WHERE s.rental_account_id=r.id AND s.status IN ('active','paused')
  ) THEN
    RAISE EXCEPTION 'RENTAL_ACTIVE_TIMER_LOCKED';
  END IF;

  -- Keep a valid lease as the anti-duplicate reservation until it expires.
  SELECT l.lease_until,l.device_id
    INTO v_lease_until,v_lease_device_id
  FROM public.rental_offline_leases l
  WHERE l.rental_account_id=r.id
  FOR UPDATE;

  UPDATE public.rental_accounts
  SET status='disabled',
      updated_at=now(),
      metadata=coalesce(metadata,'{}'::jsonb)
        || jsonb_build_object('source','admin-global-disable','adminEditedAt',now())
  WHERE id=r.id;

  INSERT INTO public.audit_logs(org_id,actor_user_id,action,target_type,target_id,payload)
  VALUES(
    p_org_id,uid,'admin_disable_rental_global','rental_account',r.id,
    jsonb_build_object(
      'code',r.code,
      'lease_preserved',v_lease_until>now(),
      'lease_until',v_lease_until,
      'lease_device_id',v_lease_device_id,
      'device_independent_edit',true
    )
  );

  RETURN jsonb_build_object(
    'ok',true,'id',r.id,'code',r.code,'status','disabled',
    'lease_preserved',v_lease_until>now(),
    'lease_until',v_lease_until,
    'lease_device_id',v_lease_device_id
  );
END
$function$;
