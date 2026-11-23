-- AniGames dual-DB transition guard (2026-10-18)
-- Apply the matching DB1 or DB2 file only to that Supabase project.
-- This is a SECURITY DEFINER route-control change; it does not modify application rows.
-- A promotion to backup, or failback from backup to primary, requires:
--   * schema version parity (primary_schema_version = backup_schema_version)
--   * data_parity_ready + routing_gateway_ready
--   * last_parity_check_at within the last 30 minutes and not in the future.
-- Existing initial primary routing remains unchanged.
CREATE OR REPLACE FUNCTION api.db_route_set(p_target text, p_epoch bigint, p_reason text DEFAULT NULL::text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO public, pg_catalog
AS $function$
DECLARE
  v_active_target text;
  v_epoch bigint;
  v_primary_ready boolean;
  v_backup_ready boolean;
  v_data_parity_ready boolean;
  v_gateway_ready boolean;
  v_parity_checked_at timestamptz;
  v_primary_schema text;
  v_backup_schema text;
  v_ready boolean;
  v_version text;
  v_updated timestamptz;
  v_switch_id uuid;
BEGIN
  IF auth.uid() IS NULL THEN RAISE EXCEPTION 'AUTH_REQUIRED'; END IF;
  IF p_target IS NULL OR p_target NOT IN ('primary', 'backup') THEN RAISE EXCEPTION 'INVALID_DB_TARGET'; END IF;
  IF p_epoch IS NULL THEN RAISE EXCEPTION 'ROUTE_EPOCH_REQUIRED'; END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM public.org_members m
    JOIN public.organizations o ON o.id = m.org_id
    WHERE m.auth_user_id = auth.uid()
      AND m.role = 'owner'
      AND o.status = 'active'
  ) THEN RAISE EXCEPTION 'OWNER_ONLY'; END IF;

  SELECT active_target, epoch, primary_ready, backup_ready, data_parity_ready,
         routing_gateway_ready, last_parity_check_at, primary_schema_version,
         backup_schema_version,
         CASE p_target WHEN 'primary' THEN primary_schema_version WHEN 'backup' THEN backup_schema_version ELSE NULL END
  INTO v_active_target, v_epoch, v_primary_ready, v_backup_ready, v_data_parity_ready,
       v_gateway_ready, v_parity_checked_at, v_primary_schema, v_backup_schema, v_version
  FROM public.db_route_control
  WHERE id = 1
  FOR UPDATE;

  IF NOT FOUND THEN RAISE EXCEPTION 'ROUTE_CONTROL_NOT_CONFIGURED'; END IF;
  IF p_epoch <= COALESCE(v_epoch, 0) THEN RAISE EXCEPTION 'ROUTE_EPOCH_NOT_NEWER'; END IF;

  -- Both directions are gated. This prevents failover and failback using stale readiness.
  IF p_target = 'backup' OR (p_target = 'primary' AND v_active_target = 'backup') THEN
    IF NOT COALESCE(v_data_parity_ready, false) OR NOT COALESCE(v_gateway_ready, false) THEN
      RAISE EXCEPTION USING ERRCODE = '55000',
        MESSAGE = 'DB_TARGET_NOT_READY: transition requires data parity and routing gateway readiness';
    END IF;
    IF v_parity_checked_at IS NULL OR v_parity_checked_at < now() - interval '30 minutes'
       OR v_parity_checked_at > now() + interval '1 minute' THEN
      RAISE EXCEPTION USING ERRCODE = '55000',
        MESSAGE = 'DB_TARGET_NOT_READY: parity check is missing, stale, or from the future';
    END IF;
    IF COALESCE(v_primary_schema, '') = '' OR COALESCE(v_backup_schema, '') = ''
       OR v_primary_schema <> v_backup_schema THEN
      RAISE EXCEPTION USING ERRCODE = '55000',
        MESSAGE = 'DB_TARGET_NOT_READY: primary/backup schema versions do not match';
    END IF;
  END IF;

  IF p_target = 'primary' THEN
    v_ready := COALESCE(v_primary_ready, false);
    IF NOT v_ready THEN
      RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'DB_TARGET_NOT_READY: primary is not marked ready';
    END IF;
  ELSE
    v_ready := COALESCE(v_backup_ready, false) AND COALESCE(v_data_parity_ready, false) AND COALESCE(v_gateway_ready, false);
    IF NOT v_ready THEN
      RAISE EXCEPTION USING ERRCODE = '55000',
        MESSAGE = 'DB_TARGET_NOT_READY: backup requires backup_ready, data_parity_ready, and routing_gateway_ready';
    END IF;
  END IF;

  v_switch_id := gen_random_uuid();
  UPDATE public.db_route_control
  SET active_target = p_target, epoch = p_epoch, updated_at = now(), updated_by = auth.uid(),
      reason = NULLIF(left(trim(COALESCE(p_reason, '')), 160), ''),
      sync_ready = v_ready, schema_version = v_version, switch_id = v_switch_id
  WHERE id = 1
  RETURNING updated_at INTO v_updated;

  RETURN jsonb_build_object(
    'ok', true, 'active_target', p_target, 'epoch', p_epoch, 'updated_at', v_updated,
    'local_profile', 'backup', 'project_ref', 'xcdbipgsvohesxhxydep',
    'sync_ready', v_ready, 'schema_version', v_version, 'switch_id', v_switch_id,
    'data_parity_ready', v_data_parity_ready, 'routing_gateway_ready', v_gateway_ready
  );
END;
$function$;
