-- Keep the Android WoL primary slot when the same phone is reinstalled and paired again.
-- A new installation only takes over if the current primary is stale and reports the same model.

CREATE OR REPLACE FUNCTION api.wol_relay_register(
  p_code_hash text,
  p_token_hash text,
  p_relay_name text,
  p_installation_id text,
  p_app_version text,
  p_model text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path TO 'public', 'pg_catalog'
AS $function$
DECLARE
  v_org uuid;
  v_relay_id uuid;
  v_primary public.wol_relay_devices%ROWTYPE;
  v_take_primary boolean := false;
BEGIN
  UPDATE public.wol_relay_enrollments
     SET used_at = now()
   WHERE code_hash = p_code_hash
     AND used_at IS NULL
     AND expires_at > now()
   RETURNING org_id INTO v_org;

  IF v_org IS NULL THEN RAISE EXCEPTION 'WOL_RELAY_ENROLLMENT_INVALID'; END IF;

  SELECT * INTO v_primary
    FROM public.wol_relay_devices
   WHERE org_id = v_org AND is_primary = true AND revoked_at IS NULL
   LIMIT 1;

  IF NOT FOUND THEN
    v_take_primary := true;
  ELSIF (v_primary.last_seen_at IS NULL
      OR v_primary.last_seen_at <= now() - interval '90 seconds')
    AND lower(coalesce(v_primary.model, '')) = lower(coalesce(p_model, '')) THEN
    UPDATE public.wol_relay_devices
       SET is_primary = false, updated_at = now()
     WHERE id = v_primary.id;
    v_take_primary := true;
  END IF;

  INSERT INTO public.wol_relay_devices(
    org_id, relay_name, installation_id, token_hash, app_version, model,
    status, last_seen_at, revoked_at, is_primary
  ) VALUES (
    v_org,
    left(coalesce(nullif(btrim(p_relay_name), ''), 'Ani WoL Relay'), 100),
    p_installation_id, p_token_hash, p_app_version, p_model,
    'online', now(), NULL, v_take_primary
  )
  ON CONFLICT (org_id, installation_id) DO UPDATE SET
    relay_name = EXCLUDED.relay_name,
    token_hash = EXCLUDED.token_hash,
    app_version = EXCLUDED.app_version,
    model = EXCLUDED.model,
    status = 'online',
    last_seen_at = now(),
    revoked_at = NULL,
    is_primary = wol_relay_devices.is_primary OR EXCLUDED.is_primary,
    updated_at = now()
  RETURNING id INTO v_relay_id;

  RETURN jsonb_build_object(
    'ok', true,
    'relay_id', v_relay_id,
    'org_id', v_org,
    'is_primary', (
      SELECT d.is_primary FROM public.wol_relay_devices d WHERE d.id = v_relay_id
    )
  );
END
$function$;
