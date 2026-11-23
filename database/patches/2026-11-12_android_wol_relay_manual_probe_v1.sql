-- Additive-only WoL manual probe. No PC Billing, rental, reseller or reporting schema changes.
CREATE TABLE IF NOT EXISTS public.wol_relay_probes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  relay_id uuid NOT NULL REFERENCES public.wol_relay_devices(id) ON DELETE CASCADE,
  nonce uuid NOT NULL DEFAULT gen_random_uuid(),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','online','expired')),
  requested_by uuid,
  requested_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  responded_at timestamptz
);
CREATE INDEX IF NOT EXISTS wol_relay_probes_pending_idx
  ON public.wol_relay_probes(relay_id, requested_at DESC)
  WHERE status='pending';

ALTER TABLE public.wol_relay_probes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.wol_relay_probes FROM anon, authenticated, PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.wol_relay_probes TO service_role;

-- Owner/Admin asks for a single live check. This is the only operation that
-- creates a probe; idle relay polling does not write status rows.
CREATE OR REPLACE FUNCTION api.wol_relay_probe_request()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'pg_catalog'
AS $function$
DECLARE
  a public.admin_accounts%ROWTYPE;
  relay public.wol_relay_devices%ROWTYPE;
  v_probe_id uuid;
BEGIN
  IF auth.uid() IS NULL THEN RAISE EXCEPTION 'UNAUTHENTICATED'; END IF;
  SELECT * INTO a FROM public.admin_accounts
   WHERE auth_user_id=auth.uid() AND status='active' LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION 'ADMIN_ACCOUNT_NOT_CONFIGURED'; END IF;
  IF a.role <> 'SUPER_ADMIN' THEN RAISE EXCEPTION 'ADMIN_ROLE_REQUIRED'; END IF;

  SELECT * INTO relay FROM public.wol_relay_devices
   WHERE org_id=a.org_id AND revoked_at IS NULL
   ORDER BY created_at DESC LIMIT 1;
  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok',false,'error','WOL_RELAY_NOT_REGISTERED');
  END IF;

  UPDATE public.wol_relay_probes
     SET status='expired'
   WHERE relay_id=relay.id AND status='pending' AND expires_at<=now();

  DELETE FROM public.wol_relay_probes
   WHERE relay_id=relay.id AND requested_at < now()-interval '1 day';

  INSERT INTO public.wol_relay_probes(org_id,relay_id,requested_by,expires_at)
  VALUES(a.org_id,relay.id,auth.uid(),now()+interval '45 seconds')
  RETURNING id INTO v_probe_id;

  RETURN jsonb_build_object(
    'ok',true,'probe_id',v_probe_id,'relay_id',relay.id,
    'relay_name',relay.relay_name,'expires_in_seconds',45
  );
END
$function$;

CREATE OR REPLACE FUNCTION api.wol_relay_probe_status(p_probe_id uuid)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'pg_catalog'
AS $function$
DECLARE
  a public.admin_accounts%ROWTYPE;
  p public.wol_relay_probes%ROWTYPE;
  relay public.wol_relay_devices%ROWTYPE;
  v_status text;
BEGIN
  IF auth.uid() IS NULL THEN RAISE EXCEPTION 'UNAUTHENTICATED'; END IF;
  SELECT * INTO a FROM public.admin_accounts
   WHERE auth_user_id=auth.uid() AND status='active' LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION 'ADMIN_ACCOUNT_NOT_CONFIGURED'; END IF;
  IF a.role <> 'SUPER_ADMIN' THEN RAISE EXCEPTION 'ADMIN_ROLE_REQUIRED'; END IF;

  SELECT * INTO p FROM public.wol_relay_probes
   WHERE id=p_probe_id AND org_id=a.org_id LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION 'WOL_RELAY_PROBE_NOT_FOUND'; END IF;
  SELECT * INTO relay FROM public.wol_relay_devices WHERE id=p.relay_id LIMIT 1;

  v_status := CASE
    WHEN p.status='online' THEN 'online'
    WHEN p.status='expired' OR p.expires_at<=now() THEN 'expired'
    ELSE 'pending'
  END;

  RETURN jsonb_build_object(
    'ok',true,'probe_id',p.id,'status',v_status,
    'responded_at',p.responded_at,'relay_name',relay.relay_name,
    'battery_percent',relay.battery_percent,'battery_temp_c',relay.battery_temp_c,
    'charging',relay.charging,'app_version',relay.app_version,'model',relay.model
  );
END
$function$;

-- Called only by the authenticated relay token via the Edge Function service role.
-- The row write happens only after a manual Admin challenge, not every poll.
CREATE OR REPLACE FUNCTION api.wol_relay_probe_ack(
  p_relay_id uuid,
  p_token_hash text,
  p_probe_id uuid,
  p_nonce uuid,
  p_metrics jsonb DEFAULT '{}'::jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path TO 'public', 'pg_catalog'
AS $function$
DECLARE
  n integer;
BEGIN
  UPDATE public.wol_relay_probes p SET
    status='online',
    responded_at=now()
  FROM public.wol_relay_devices r
  WHERE p.id=p_probe_id
    AND p.relay_id=p_relay_id
    AND p.nonce=p_nonce
    AND p.status='pending'
    AND p.expires_at>now()
    AND r.id=p_relay_id
    AND r.token_hash=p_token_hash
    AND r.revoked_at IS NULL;
  GET DIAGNOSTICS n = ROW_COUNT;
  IF n <> 1 THEN RAISE EXCEPTION 'WOL_RELAY_PROBE_NOT_PENDING'; END IF;

  UPDATE public.wol_relay_devices SET
    status='online',
    last_seen_at=now(),
    app_version=left(coalesce(p_metrics->>'appVersion',app_version),64),
    model=left(coalesce(p_metrics->>'model',model),100),
    battery_percent=CASE WHEN (p_metrics->>'batteryPercent') ~ '^[0-9]{1,3}$'
      THEN least(100,greatest(0,(p_metrics->>'batteryPercent')::integer)) ELSE battery_percent END,
    battery_temp_c=CASE WHEN (p_metrics->>'batteryTemperatureC') ~ '^-?[0-9]{1,3}(\.[0-9]{1,2})?$'
      THEN (p_metrics->>'batteryTemperatureC')::numeric ELSE battery_temp_c END,
    charging=CASE WHEN p_metrics ? 'charging' THEN (p_metrics->>'charging')::boolean ELSE charging END,
    battery_health=left(coalesce(p_metrics->>'batteryHealth',battery_health),40),
    updated_at=now()
  WHERE id=p_relay_id AND token_hash=p_token_hash AND revoked_at IS NULL;

  RETURN jsonb_build_object('ok',true,'status','online','responded_at',now());
END
$function$;

-- Read-only idle polling: no heartbeat/status write unless there is a command
-- to lease. Also return outstanding one-shot probes for the Android service.
CREATE OR REPLACE FUNCTION api.wol_relay_poll(p_relay_id uuid, p_token_hash text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path TO 'public', 'pg_catalog'
AS $function$
DECLARE
  c public.wol_relay_commands%ROWTYPE;
  p public.wol_relay_probes%ROWTYPE;
  n integer;
BEGIN
  PERFORM 1 FROM public.wol_relay_devices
   WHERE id=p_relay_id AND token_hash=p_token_hash AND revoked_at IS NULL;
  IF NOT FOUND THEN RAISE EXCEPTION 'INVALID_WOL_RELAY_TOKEN'; END IF;

  -- Lease a queued or timed-out command only when one actually exists.
  SELECT * INTO c FROM public.wol_relay_commands
   WHERE relay_id=p_relay_id
     AND expires_at>now()
     AND (status='queued' OR (status='delivered' AND delivered_at < now()-interval '30 seconds'))
   ORDER BY created_at ASC
   LIMIT 1 FOR UPDATE SKIP LOCKED;

  IF FOUND THEN
    UPDATE public.wol_relay_commands SET status='delivered',delivered_at=now()
     WHERE id=c.id;
  ELSE
    c := NULL;
  END IF;

  SELECT * INTO p FROM public.wol_relay_probes
   WHERE relay_id=p_relay_id AND status='pending' AND expires_at>now()
   ORDER BY requested_at DESC LIMIT 1;

  RETURN jsonb_build_object(
    'ok',true,
    'command',CASE WHEN c.id IS NULL THEN NULL ELSE jsonb_build_object(
      'id',c.id,'targetMac',c.target_mac,'targetDeviceName',c.target_device_name,'expiresAt',c.expires_at
    ) END,
    'probe',CASE WHEN p.id IS NULL THEN NULL ELSE jsonb_build_object(
      'id',p.id,'nonce',p.nonce,'expiresAt',p.expires_at
    ) END
  );
END
$function$;

REVOKE ALL ON FUNCTION api.wol_relay_probe_request() FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION api.wol_relay_probe_status(uuid) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION api.wol_relay_probe_ack(uuid,text,uuid,uuid,jsonb) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION api.wol_relay_poll(uuid,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION api.wol_relay_probe_request() TO authenticated;
GRANT EXECUTE ON FUNCTION api.wol_relay_probe_status(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION api.wol_relay_probe_ack(uuid,text,uuid,uuid,jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION api.wol_relay_poll(uuid,text) TO service_role;
