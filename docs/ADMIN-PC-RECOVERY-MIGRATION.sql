-- Ani Games Ready Admin V12.1.5: targeted recovery enrollment
-- Apply to each Supabase project used by the Admin app only after reviewing its schema.
-- This migration does not move, delete, or rewrite rental/session/transaction rows.

CREATE OR REPLACE FUNCTION api.create_device_recovery_enrollment(
  p_device_id uuid,
  p_minutes bigint DEFAULT 30
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO public, pg_catalog
AS $function$
DECLARE
  uid uuid := auth.uid();
  d public.devices%ROWTYPE;
  raw text;
  code_hash text;
  enrollment_id uuid;
  expires timestamptz;
  mins bigint;
BEGIN
  IF uid IS NULL THEN RAISE EXCEPTION 'AUTH_REQUIRED'; END IF;
  IF p_device_id IS NULL THEN RAISE EXCEPTION 'DEVICE_ID_REQUIRED'; END IF;

  SELECT * INTO d
  FROM public.devices
  WHERE id = p_device_id
  FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'RECOVERY_DEVICE_NOT_FOUND'; END IF;
  IF NOT private.is_owner_access(d.org_id) THEN RAISE EXCEPTION 'OWNER_ONLY'; END IF;
  IF coalesce(d.metadata, '{}'::jsonb) ? 'pairingDuplicateArchivedAt' THEN
    RAISE EXCEPTION 'RECOVERY_TARGET_ARCHIVED';
  END IF;

  raw := upper(substr(md5(random()::text || clock_timestamp()::text || uid::text || d.id::text), 1, 8));
  code_hash := encode(extensions.digest(raw, 'sha256'), 'hex');
  mins := greatest(1::bigint, least(coalesce(p_minutes, 30::bigint), 1440::bigint));
  expires := now() + (mins * interval '1 minute');

  -- Target UUID is encoded in the internal label. redeem_device enforces it server-side.
  INSERT INTO public.device_enrollments(org_id, code_hash, label, expires_at)
  VALUES (d.org_id, code_hash, '__RECOVERY__:' || d.id::text || ':' || coalesce(d.client_id, ''), expires)
  RETURNING id INTO enrollment_id;

  INSERT INTO public.audit_logs(org_id, actor_user_id, action, target_type, target_id, payload)
  VALUES (
    d.org_id, uid, 'create_device_recovery_enrollment', 'device', d.id::text,
    jsonb_build_object('enrollment_id', enrollment_id, 'target_client_id', d.client_id, 'expires_at', expires)
  );

  RETURN jsonb_build_object(
    'id', enrollment_id,
    'code', raw,
    'expires_at', expires,
    'target_device_id', d.id,
    'target_client_id', d.client_id
  );
END
$function$;

REVOKE ALL ON FUNCTION api.create_device_recovery_enrollment(uuid, bigint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION api.create_device_recovery_enrollment(uuid, bigint) TO authenticated;

CREATE OR REPLACE FUNCTION api.redeem_device(
  p_code text,
  p_client_id text,
  p_device_name text,
  p_app_version text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO public, pg_catalog
AS $function$
DECLARE
  e public.device_enrollments%ROWTYPE;
  d public.devices%ROWTYPE;
  v_token text;
  v_token_hash text;
  is_existing boolean := false;
  token_rows integer := 0;
  recovery_target uuid := NULL;
BEGIN
  IF coalesce(trim(p_client_id), '') = '' THEN RAISE EXCEPTION 'CLIENT_ID_REQUIRED'; END IF;

  SELECT * INTO e
  FROM public.device_enrollments
  WHERE code_hash = encode(extensions.digest(upper(trim(p_code)), 'sha256'), 'hex')
    AND (expires_at IS NULL OR expires_at > now())
  ORDER BY created_at DESC
  LIMIT 1
  FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'INVALID_ENROLLMENT'; END IF;

  IF left(coalesce(e.label, ''), 13) = '__RECOVERY__:' THEN
    BEGIN
      recovery_target := split_part(e.label, ':', 2)::uuid;
    EXCEPTION WHEN invalid_text_representation THEN
      RAISE EXCEPTION 'INVALID_ENROLLMENT';
    END;
    -- Recovery codes are one-use, even if presented again by the same PC.
    IF e.used_at IS NOT NULL THEN RAISE EXCEPTION 'INVALID_ENROLLMENT'; END IF;

    SELECT * INTO d
    FROM public.devices
    WHERE id = recovery_target AND org_id = e.org_id
    FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'RECOVERY_DEVICE_NOT_FOUND'; END IF;
    IF NOT (
      d.client_id = trim(p_client_id)
      OR coalesce(d.metadata->'clientIdAliases', '[]'::jsonb) ? trim(p_client_id)
    ) THEN
      RAISE EXCEPTION 'RECOVERY_DEVICE_ID_MISMATCH';
    END IF;
    is_existing := true;
  ELSE
    -- Existing standard pairing behavior remains unchanged.
    SELECT * INTO d
    FROM public.devices
    WHERE org_id = e.org_id
      AND (client_id = trim(p_client_id) OR coalesce(metadata->'clientIdAliases', '[]'::jsonb) ? trim(p_client_id))
    ORDER BY CASE WHEN client_id = trim(p_client_id) THEN 0 ELSE 1 END, created_at ASC
    LIMIT 1
    FOR UPDATE;
    is_existing := FOUND;
  END IF;

  IF is_existing THEN
    IF e.used_at IS NOT NULL AND e.redeemed_device_id IS NOT NULL AND e.redeemed_device_id <> d.id THEN
      RAISE EXCEPTION 'INVALID_ENROLLMENT';
    END IF;
    UPDATE public.devices
    SET device_name = CASE
          WHEN client_id = trim(p_client_id)
          THEN coalesce(nullif(trim(metadata->>'custom_device_name'), ''), nullif(trim(p_device_name), ''), device_name)
          ELSE device_name
        END,
        app_version = coalesce(nullif(trim(p_app_version), ''), app_version),
        status = 'online',
        last_seen_at = now(),
        metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
          'last_repaired_at', now(),
          'pairing_mode', CASE WHEN recovery_target IS NOT NULL THEN 'resume-existing-targeted' ELSE 'resume-existing' END
        )
    WHERE id = d.id;
    UPDATE public.device_enrollments
    SET used_at = coalesce(used_at, now()), redeemed_device_id = coalesce(redeemed_device_id, d.id)
    WHERE id = e.id;
  ELSE
    -- Never let a targeted recovery code fall through to the new-device insert path.
    IF recovery_target IS NOT NULL THEN RAISE EXCEPTION 'RECOVERY_DEVICE_NOT_FOUND'; END IF;
    IF e.used_at IS NOT NULL THEN RAISE EXCEPTION 'INVALID_ENROLLMENT'; END IF;
    INSERT INTO public.devices(org_id, client_id, device_name, status, app_version, last_seen_at, metadata)
    VALUES (
      e.org_id, trim(p_client_id), coalesce(nullif(trim(p_device_name), ''), trim(p_client_id)),
      'online', nullif(trim(p_app_version), ''), now(), jsonb_build_object('enrolled_at', now())
    )
    RETURNING * INTO d;
    UPDATE public.device_enrollments SET used_at = now(), redeemed_device_id = d.id WHERE id = e.id;
  END IF;

  v_token := replace(gen_random_uuid()::text || gen_random_uuid()::text, '-', '');
  v_token_hash := encode(extensions.digest(v_token, 'sha256'), 'hex');
  UPDATE public.device_tokens
  SET token_hash = v_token_hash, created_at = now(), revoked_at = NULL
  WHERE device_id = d.id;
  GET DIAGNOSTICS token_rows = ROW_COUNT;
  IF token_rows = 0 THEN
    INSERT INTO public.device_tokens(device_id, token_hash) VALUES (d.id, v_token_hash);
  END IF;

  INSERT INTO public.audit_logs(org_id, actor_device_id, action, target_type, target_id, payload)
  VALUES (
    e.org_id, d.id,
    CASE WHEN is_existing THEN 'device_repaired' ELSE 'device_enrolled' END,
    'device', d.id::text,
    jsonb_build_object(
      'client_id', p_client_id,
      'device_name', p_device_name,
      'resumed_existing', is_existing,
      'token_rotated_in_place', token_rows > 0,
      'recovery_targeted', recovery_target IS NOT NULL
    )
  );

  RETURN jsonb_build_object(
    'device_id', d.id,
    'org_id', d.org_id,
    'token', v_token,
    'client_id', p_client_id,
    'resumed_existing', is_existing,
    'token_rotated_in_place', token_rows > 0,
    'recovery_targeted', recovery_target IS NOT NULL
  );
END
$function$;

-- Preserve existing execute grants for redeem_device to avoid changing current callers.
