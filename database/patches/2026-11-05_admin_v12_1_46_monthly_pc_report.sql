-- V12.1.46 monthly combined and per-PC rental report breakdown.
CREATE OR REPLACE FUNCTION api.report_rental_period_breakdown(
  p_org_id uuid,
  p_from timestamptz,
  p_to timestamptz
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'pg_catalog'
AS $function$
DECLARE
  v_combined jsonb := '[]'::jsonb;
  v_per_pc jsonb := '[]'::jsonb;
BEGIN
  IF auth.uid() IS NULL THEN RAISE EXCEPTION 'AUTH_REQUIRED'; END IF;
  IF p_org_id IS NULL OR NOT private.user_has_org_access(p_org_id) THEN RAISE EXCEPTION 'ORG_ACCESS_DENIED'; END IF;
  IF p_from IS NULL OR p_to IS NULL OR p_to <= p_from THEN RAISE EXCEPTION 'INVALID_REPORT_RANGE'; END IF;
  IF p_to - p_from > interval '740 days' THEN RAISE EXCEPTION 'REPORT_RANGE_TOO_LARGE'; END IF;

  WITH month_ranges AS (
    SELECT gs::date AS month_start, (gs + interval '1 month')::date AS next_month_start
    FROM generate_series(
      date_trunc('month', p_from AT TIME ZONE 'Asia/Jakarta'),
      date_trunc('month', (p_to - interval '1 microsecond') AT TIME ZONE 'Asia/Jakarta'),
      interval '1 month'
    ) AS gs
  ),
  sessions_by_month AS MATERIALIZED (
    SELECT to_char(m.month_start, 'YYYY-MM') AS month_key,
      COALESCE(ra.id::text, 'legacy:' || upper(COALESCE(ra.code, s.code, '-'))) AS member_key,
      COALESCE(ra.code, s.code, '-') AS rental_id,
      COALESCE(NULLIF(BTRIM(ra.client_label), ''), NULLIF(BTRIM(s.metadata->>'clientLabel'), ''), '-') AS rental_name,
      COALESCE(s.device_id::text, 'unknown') AS pc_key,
      COALESCE(NULLIF(BTRIM(d.device_name), ''), NULLIF(BTRIM(d.client_id), ''), 'PC tidak diketahui') AS pc_name,
      CASE WHEN lower(COALESCE(s.status, '')) = 'paused' THEN 0::bigint
        ELSE GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (
          LEAST(COALESCE(s.ended_at, s.deadline_at, now()), p_to, now(),
            (m.next_month_start::timestamp AT TIME ZONE 'Asia/Jakarta'))
          - GREATEST(s.started_at, p_from,
            (m.month_start::timestamp AT TIME ZONE 'Asia/Jakarta'))
        )))::bigint)
      END AS played_seconds
    FROM month_ranges m
    JOIN public.rental_sessions s
      ON s.started_at < LEAST(p_to, (m.next_month_start::timestamp AT TIME ZONE 'Asia/Jakarta'))
     AND COALESCE(s.ended_at, s.deadline_at, now()) > GREATEST(p_from, (m.month_start::timestamp AT TIME ZONE 'Asia/Jakarta'))
    LEFT JOIN public.rental_accounts ra ON ra.id = s.rental_account_id
    LEFT JOIN public.devices d ON d.id = s.device_id
    WHERE s.org_id = p_org_id AND COALESCE(s.session_type, 'rental') <> 'free_test'
  ),
  grouped AS (
    SELECT month_key, member_key, MAX(rental_id) rental_id, MAX(rental_name) rental_name,
      SUM(played_seconds)::bigint total_play_seconds, COUNT(*)::bigint total_sessions
    FROM sessions_by_month GROUP BY month_key, member_key
  )
  SELECT COALESCE(jsonb_agg(jsonb_build_object(
      'month', month_key, 'member_key', member_key, 'rental_id', rental_id, 'rental_name', rental_name,
      'total_play_seconds', total_play_seconds, 'total_sessions', total_sessions
    ) ORDER BY month_key, total_play_seconds DESC, total_sessions DESC, rental_id), '[]'::jsonb)
  INTO v_combined FROM grouped;

  WITH month_ranges AS (
    SELECT gs::date AS month_start, (gs + interval '1 month')::date AS next_month_start
    FROM generate_series(
      date_trunc('month', p_from AT TIME ZONE 'Asia/Jakarta'),
      date_trunc('month', (p_to - interval '1 microsecond') AT TIME ZONE 'Asia/Jakarta'),
      interval '1 month'
    ) AS gs
  ),
  sessions_by_month AS MATERIALIZED (
    SELECT to_char(m.month_start, 'YYYY-MM') AS month_key,
      COALESCE(ra.id::text, 'legacy:' || upper(COALESCE(ra.code, s.code, '-'))) AS member_key,
      COALESCE(ra.code, s.code, '-') AS rental_id,
      COALESCE(NULLIF(BTRIM(ra.client_label), ''), NULLIF(BTRIM(s.metadata->>'clientLabel'), ''), '-') AS rental_name,
      COALESCE(s.device_id::text, 'unknown') AS pc_key,
      COALESCE(NULLIF(BTRIM(d.device_name), ''), NULLIF(BTRIM(d.client_id), ''), 'PC tidak diketahui') AS pc_name,
      CASE WHEN lower(COALESCE(s.status, '')) = 'paused' THEN 0::bigint
        ELSE GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (
          LEAST(COALESCE(s.ended_at, s.deadline_at, now()), p_to, now(),
            (m.next_month_start::timestamp AT TIME ZONE 'Asia/Jakarta'))
          - GREATEST(s.started_at, p_from,
            (m.month_start::timestamp AT TIME ZONE 'Asia/Jakarta'))
        )))::bigint)
      END AS played_seconds
    FROM month_ranges m
    JOIN public.rental_sessions s
      ON s.started_at < LEAST(p_to, (m.next_month_start::timestamp AT TIME ZONE 'Asia/Jakarta'))
     AND COALESCE(s.ended_at, s.deadline_at, now()) > GREATEST(p_from, (m.month_start::timestamp AT TIME ZONE 'Asia/Jakarta'))
    LEFT JOIN public.rental_accounts ra ON ra.id = s.rental_account_id
    LEFT JOIN public.devices d ON d.id = s.device_id
    WHERE s.org_id = p_org_id AND COALESCE(s.session_type, 'rental') <> 'free_test'
  ),
  grouped AS (
    SELECT month_key, pc_key, member_key, MAX(pc_name) pc_name, MAX(rental_id) rental_id,
      MAX(rental_name) rental_name, SUM(played_seconds)::bigint total_play_seconds, COUNT(*)::bigint total_sessions
    FROM sessions_by_month GROUP BY month_key, pc_key, member_key
  )
  SELECT COALESCE(jsonb_agg(jsonb_build_object(
      'month', month_key, 'pc_id', pc_key, 'pc_name', pc_name, 'member_key', member_key,
      'rental_id', rental_id, 'rental_name', rental_name,
      'total_play_seconds', total_play_seconds, 'total_sessions', total_sessions
    ) ORDER BY month_key, pc_name, total_play_seconds DESC, total_sessions DESC, rental_id), '[]'::jsonb)
  INTO v_per_pc FROM grouped;

  RETURN jsonb_build_object('timezone', 'Asia/Jakarta', 'from', p_from, 'to', p_to,
    'combined_rows', v_combined, 'pc_rows', v_per_pc);
END;
$function$;

REVOKE ALL ON FUNCTION api.report_rental_period_breakdown(uuid, timestamptz, timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION api.report_rental_period_breakdown(uuid, timestamptz, timestamptz) FROM anon;
GRANT EXECUTE ON FUNCTION api.report_rental_period_breakdown(uuid, timestamptz, timestamptz) TO authenticated;
