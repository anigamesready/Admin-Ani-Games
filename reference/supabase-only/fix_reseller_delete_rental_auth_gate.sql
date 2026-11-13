-- REFERENCE ONLY — DO NOT EXECUTE ON REDMI DB AND DO NOT DEPLOY TO SUPABASE FROM THIS BRANCH.
-- Source: anigamesready/Admin-Ani-Games/backend-patches/fix_reseller_delete_rental_auth_gate.sql
-- This SQL belongs to the existing Supabase backend and depends on its private.billing_account_by_token()
-- function, Supabase schema/permissions, and existing audit/device-command tables.
-- Its behavior must be PORTED into the DB Android API, not copied as a migration.
--
-- Key business rules to preserve:
-- 1. The reseller session token is the authentication proof; reseller auth_user_id may be NULL.
-- 2. Token must resolve to an active RESELLER_ADMIN account in the requested org.
-- 3. Refuse deletion while an active/paused rental session exists.
-- 4. Refuse deletion while a valid offline lease remains.
-- 5. Deletion is org-scoped and uses a transaction/advisory lock.
-- 6. If rental is PC-assigned, enqueue best-effort sync command and audit event.
-- 7. Delete must not require the PC to be online.
--
-- ---- Original source (reference only) ----
-- Ani Games Reseller backend hotfix (2026-11-06)
-- Fixes reseller-global rental deletion for token-authenticated reseller accounts.
-- The reseller accounts in both DBs intentionally have auth_user_id = NULL.
-- Authentication is already validated by private.billing_account_by_token().
-- Apply this same function definition to DB1 (primary) and DB2 (backup).
-- No Android/WebView rebuild is required.

CREATE OR REPLACE FUNCTION api.billing_reseller_delete_rental_global(
  p_session_token text,
  p_org_id uuid,
  p_rental_id uuid
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  a public.billing_control_accounts%ROWTYPE;
  r public.rental_accounts%ROWTYPE;
  cid uuid;
  v_lease_until timestamptz;
BEGIN
  a := private.billing_account_by_token(p_session_token);

  -- Session token is the auth proof; do not require auth_user_id.
  IF a.role IS DISTINCT FROM 'RESELLER_ADMIN'
     OR a.org_id IS DISTINCT FROM p_org_id THEN
    RAISE EXCEPTION 'ORG_ACCESS_DENIED';
  END IF;
  IF p_org_id IS NULL OR p_rental_id IS NULL THEN
    RAISE EXCEPTION 'RENTAL_ID_REQUIRED';
  END IF;

  SELECT * INTO r
  FROM public.rental_accounts
  WHERE id = p_rental_id AND org_id = p_org_id
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'RENTAL_NOT_FOUND';
  END IF;

  PERFORM pg_advisory_xact_lock(
    hashtextextended(p_org_id::text || ':' || upper(trim(r.code)), 0)
  );

  -- Preserve protections against deleting a rental with an active timer.
  IF EXISTS (
    SELECT 1
    FROM public.rental_sessions s
    WHERE s.org_id = p_org_id
      AND s.status IN ('active', 'paused')
      AND (
        s.rental_account_id = r.id
        OR upper(trim(s.code)) = upper(trim(r.code))
      )
  ) THEN
    RAISE EXCEPTION 'RENTAL_ACTIVE_TIMER_LOCKED';
  END IF;

  IF to_regclass('public.rental_offline_leases') IS NOT NULL THEN
    EXECUTE $sql$
      SELECT l.lease_until
      FROM public.rental_offline_leases l
      WHERE l.rental_account_id = $1
        AND l.lease_until > now()
      ORDER BY l.lease_until DESC
      LIMIT 1
      FOR UPDATE
    $sql$ INTO v_lease_until USING r.id;

    IF v_lease_until IS NOT NULL THEN
      RAISE EXCEPTION 'RENTAL_ACTIVE_OFFLINE_LEASE';
    END IF;
  END IF;

  -- A null created_by/actor_user_id is valid for token-authenticated reseller
  -- accounts. DB rental deletion is immediate and does not wait for PC online.
  IF r.device_id IS NOT NULL THEN
    INSERT INTO public.device_commands(
      org_id, device_id, command, payload, status, created_by
    )
    VALUES (
      p_org_id,
      r.device_id,
      'delete_rental',
      jsonb_build_object(
        'code', r.code,
        'source', 'reseller-global-delete'
      ),
      'queued',
      a.auth_user_id
    )
    RETURNING id INTO cid;

    INSERT INTO public.device_command_logs(
      command_id, org_id, device_id, status, result
    )
    VALUES (
      cid,
      p_org_id,
      r.device_id,
      'queued',
      jsonb_build_object(
        'source', 'reseller-global-delete',
        'rental_account_id', r.id,
        'code', r.code,
        'billing_account_id', a.id,
        'billing_username', a.username
      )
    );
  END IF;

  INSERT INTO public.audit_logs(
    org_id, actor_user_id, action, target_type, target_id, payload
  )
  VALUES (
    p_org_id,
    a.auth_user_id,
    'reseller_delete_rental_global',
    'rental_account',
    r.id::text,
    jsonb_build_object(
      'code', r.code,
      'device_id', r.device_id,
      'command_id', cid,
      'billing_account_id', a.id,
      'billing_username', a.username,
      'history_preserved', true,
      'deleted_from_global_rental_list', true
    )
  );

  DELETE FROM public.rental_accounts
  WHERE id = r.id AND org_id = p_org_id;

  RETURN jsonb_build_object(
    'ok', true,
    'id', r.id,
    'org_id', p_org_id,
    'code', r.code,
    'device_id', r.device_id,
    'command_id', cid,
    'history_preserved', true
  );
END
$function$;

