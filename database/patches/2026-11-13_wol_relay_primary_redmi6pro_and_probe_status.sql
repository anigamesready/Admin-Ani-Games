-- Ani WoL Relay: pin the Redmi 6 Pro standby installation as the only active gateway.
-- Additive migration; old relay registrations are retained for audit/recovery.

ALTER TABLE public.wol_relay_devices
  ADD COLUMN IF NOT EXISTS is_primary boolean NOT NULL DEFAULT false;

UPDATE public.wol_relay_devices
SET is_primary = (id = '27c0e8e9-6354-4c68-b8f5-89fc2949a2a0'::uuid),
    updated_at = now()
WHERE org_id = (
  SELECT org_id FROM public.wol_relay_devices
  WHERE id = '27c0e8e9-6354-4c68-b8f5-89fc2949a2a0'::uuid
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM public.wol_relay_devices
    WHERE id = '27c0e8e9-6354-4c68-b8f5-89fc2949a2a0'::uuid
      AND is_primary = true AND revoked_at IS NULL
  ) THEN
    RAISE EXCEPTION 'RELAY_PRIMARY_REDDMI6PRO_NOT_FOUND';
  END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS wol_relay_one_primary_per_org_idx
  ON public.wol_relay_devices(org_id)
  WHERE is_primary = true AND revoked_at IS NULL;

COMMENT ON COLUMN public.wol_relay_devices.is_primary IS
  'Owner-selected Android WoL gateway. Only the primary relay receives direct probes and Wake-on-LAN commands.';

CREATE OR REPLACE FUNCTION api.wol_relay_status()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'pg_catalog'
AS $function$
DECLARE
  a public.admin_accounts%ROWTYPE;
  v_relays jsonb;
BEGIN
  IF auth.uid() IS NULL THEN RAISE EXCEPTION 'UNAUTHENTICATED'; END IF;
  SELECT * INTO a FROM public.admin_accounts
   WHERE auth_user_id = auth.uid() AND status = 'active' LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION 'ADMIN_ACCOUNT_NOT_CONFIGURED'; END IF;
  IF a.role <> 'SUPER_ADMIN' THEN RAISE EXCEPTION 'ADMIN_ROLE_REQUIRED'; END IF;

  SELECT coalesce(jsonb_agg(jsonb_build_object(
    'relay_id', id, 'relay_name', relay_name, 'is_primary', is_primary,
    'status', CASE
      WHEN revoked_at IS NOT NULL THEN 'revoked'
      WHEN last_seen_at > now() - interval '90 seconds' THEN 'online'
      ELSE 'offline'
    END,
    'app_version', app_version, 'model', model, 'last_seen_at', last_seen_at,
    'battery_percent', battery_percent, 'battery_temp_c', battery_temp_c,
    'charging', charging, 'battery_health', battery_health,
    'last_packet_at', last_packet_at, 'last_error', last_error
  ) ORDER BY last_seen_at DESC NULLS LAST), '[]'::jsonb)
  INTO v_relays
  FROM public.wol_relay_devices
  WHERE org_id = a.org_id AND is_primary = true AND revoked_at IS NULL;

  RETURN jsonb_build_object('ok', true, 'relays', v_relays);
END
$function$;

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
   WHERE auth_user_id = auth.uid() AND status = 'active' LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION 'ADMIN_ACCOUNT_NOT_CONFIGURED'; END IF;
  IF a.role <> 'SUPER_ADMIN' THEN RAISE EXCEPTION 'ADMIN_ROLE_REQUIRED'; END IF;

  SELECT * INTO relay FROM public.wol_relay_devices
   WHERE org_id = a.org_id AND is_primary = true AND revoked_at IS NULL LIMIT 1;
  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok', false, 'error', 'WOL_RELAY_PRIMARY_NOT_CONFIGURED');
  END IF;

  UPDATE public.wol_relay_probes SET status = 'expired'
   WHERE relay_id = relay.id AND status = 'pending' AND expires_at <= now();
  DELETE FROM public.wol_relay_probes
   WHERE relay_id = relay.id AND requested_at < now() - interval '1 day';

  IF relay.last_seen_at IS NULL OR relay.last_seen_at <= now() - interval '90 seconds' THEN
    RETURN jsonb_build_object(
      'ok', false, 'error', 'WOL_RELAY_OFFLINE',
      'relay_id', relay.id, 'relay_name', relay.relay_name, 'last_seen_at', relay.last_seen_at
    );
  END IF;

  INSERT INTO public.wol_relay_probes(org_id, relay_id, requested_by, expires_at)
  VALUES (a.org_id, relay.id, auth.uid(), now() + interval '45 seconds')
  RETURNING id INTO v_probe_id;

  RETURN jsonb_build_object(
    'ok', true, 'probe_id', v_probe_id, 'relay_id', relay.id,
    'relay_name', relay.relay_name, 'expires_in_seconds', 45
  );
END
$function$;

CREATE OR REPLACE FUNCTION api.wol_relay_enqueue(p_target_device_id uuid)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'pg_catalog'
AS $function$
DECLARE
  a public.admin_accounts%ROWTYPE;
  target public.devices%ROWTYPE;
  relay public.wol_relay_devices%ROWTYPE;
  v_mac text;
  v_command_id uuid;
  v_expires timestamptz := now() + interval '90 seconds';
BEGIN
  IF auth.uid() IS NULL THEN RAISE EXCEPTION 'UNAUTHENTICATED'; END IF;
  SELECT * INTO a FROM public.admin_accounts
   WHERE auth_user_id = auth.uid() AND status = 'active' LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION 'ADMIN_ACCOUNT_NOT_CONFIGURED'; END IF;
  IF a.role <> 'SUPER_ADMIN' THEN RAISE EXCEPTION 'ADMIN_ROLE_REQUIRED'; END IF;

  SELECT * INTO target FROM public.devices
   WHERE id = p_target_device_id AND org_id = a.org_id LIMIT 1;
  IF NOT FOUND OR NOT private.admin_can_access_device(p_target_device_id, a.org_id) THEN
    RAISE EXCEPTION 'WAKE_TARGET_ACCESS_DENIED';
  END IF;
  IF target.status = 'disabled' THEN RAISE EXCEPTION 'WAKE_TARGET_DISABLED'; END IF;
  IF target.status = 'online'
     AND coalesce(target.last_heartbeat_at, target.last_seen_at) > now() - interval '45 seconds' THEN
    RAISE EXCEPTION 'WAKE_TARGET_ALREADY_ONLINE';
  END IF;

  v_mac := upper(regexp_replace(coalesce(target.metadata->>'wolLanMac', ''), '[^0-9A-F]', '', 'g'));
  IF v_mac !~ '^[0-9A-F]{12}$' OR v_mac IN ('000000000000','FFFFFFFFFFFF') THEN
    RAISE EXCEPTION 'WAKE_TARGET_MAC_NOT_REPORTED';
  END IF;

  SELECT * INTO relay FROM public.wol_relay_devices
   WHERE org_id = a.org_id AND is_primary = true
     AND status = 'online' AND revoked_at IS NULL
     AND last_seen_at > now() - interval '90 seconds'
   LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION 'WOL_RELAY_OFFLINE'; END IF;

  IF EXISTS (
    SELECT 1 FROM public.wol_relay_commands c
     WHERE c.target_device_id = p_target_device_id
       AND c.status IN ('queued','delivered','packet_sent')
       AND c.created_at > now() - interval '120 seconds'
  ) THEN
    RAISE EXCEPTION 'WOL_COMMAND_ALREADY_PENDING';
  END IF;

  INSERT INTO public.wol_relay_commands(
    org_id, relay_id, target_device_id, target_mac, target_device_name,
    status, expires_at, created_by
  ) VALUES (
    a.org_id, relay.id, target.id,
    substr(v_mac,1,2)||':'||substr(v_mac,3,2)||':'||substr(v_mac,5,2)||':'||
    substr(v_mac,7,2)||':'||substr(v_mac,9,2)||':'||substr(v_mac,11,2),
    left(coalesce(target.device_name, target.client_id, 'PC target'), 100),
    'queued', v_expires, auth.uid()
  ) RETURNING id INTO v_command_id;

  INSERT INTO public.audit_logs(org_id, actor_user_id, action, target_type, target_id, payload)
  VALUES (
    a.org_id, auth.uid(), 'android_wol_queued', 'device', target.id::text,
    jsonb_build_object('command_id',v_command_id,'relay_id',relay.id,'target_device_id',target.id)
  );

  RETURN jsonb_build_object(
    'ok', true, 'command_id', v_command_id, 'relay_id', relay.id,
    'relay_name', relay.relay_name, 'target_device_id', target.id,
    'target_device_name', left(coalesce(target.device_name, target.client_id, 'PC target'), 100),
    'expires_at', v_expires
  );
END
$function$;
