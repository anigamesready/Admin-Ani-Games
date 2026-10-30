-- AniGames Admin V12.1.7: low-volume PC end/stop alerts.
-- Apply this migration in BOTH Supabase projects (DB1 and DB2).
-- Alerts are event-driven (session expiry/manual stop); heartbeats and rental rows are untouched.
-- Device-side insert is authenticated by the existing device token hash. Admin reads are owner-only.

CREATE TABLE IF NOT EXISTS public.admin_alert_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  device_id uuid NOT NULL REFERENCES public.devices(id) ON DELETE CASCADE,
  source_event_id text NOT NULL,
  event_type text NOT NULL CHECK (event_type IN ('session_expired', 'session_stopped')),
  message text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (device_id, source_event_id)
);

CREATE INDEX IF NOT EXISTS admin_alert_events_org_created_idx
  ON public.admin_alert_events (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS admin_alert_events_device_created_idx
  ON public.admin_alert_events (device_id, created_at DESC);

ALTER TABLE public.admin_alert_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.admin_alert_events FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION api.device_emit_admin_alert(
  p_token text,
  p_event_id text,
  p_event_type text,
  p_message text,
  p_payload jsonb DEFAULT '{}'::jsonb,
  p_occurred_at timestamptz DEFAULT now()
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO public, pg_catalog
AS $function$
DECLARE
  device_row public.devices%ROWTYPE;
  event_id uuid;
  safe_message text;
  safe_payload jsonb;
BEGIN
  IF coalesce(trim(p_token), '') = '' THEN RAISE EXCEPTION 'INVALID_DEVICE_TOKEN'; END IF;
  IF coalesce(trim(p_event_id), '') = '' OR length(p_event_id) > 120 THEN RAISE EXCEPTION 'INVALID_EVENT_ID'; END IF;
  IF p_event_type NOT IN ('session_expired', 'session_stopped') THEN RAISE EXCEPTION 'INVALID_ADMIN_ALERT_TYPE'; END IF;
  safe_message := left(regexp_replace(coalesce(p_message, ''), '[[:cntrl:]]', ' ', 'g'), 240);
  IF safe_message = '' THEN RAISE EXCEPTION 'EMPTY_ADMIN_ALERT_MESSAGE'; END IF;

  SELECT d.* INTO device_row
  FROM public.device_tokens t
  JOIN public.devices d ON d.id = t.device_id
  WHERE t.token_hash = encode(extensions.digest(trim(p_token), 'sha256'), 'hex')
    AND t.revoked_at IS NULL
  ORDER BY t.created_at DESC
  LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION 'INVALID_DEVICE_TOKEN'; END IF;

  safe_payload := CASE WHEN jsonb_typeof(coalesce(p_payload, '{}'::jsonb)) = 'object'
    THEN coalesce(p_payload, '{}'::jsonb) ELSE '{}'::jsonb END;

  INSERT INTO public.admin_alert_events(
    org_id, device_id, source_event_id, event_type, message, payload, occurred_at
  )
  VALUES(
    device_row.org_id, device_row.id, trim(p_event_id), p_event_type, safe_message,
    safe_payload, coalesce(p_occurred_at, now())
  )
  ON CONFLICT (device_id, source_event_id) DO NOTHING
  RETURNING id INTO event_id;

  -- Keep this small event table bounded. This cleanup is event-triggered, not a timer/log loop.
  DELETE FROM public.admin_alert_events
  WHERE created_at < now() - interval '30 days';

  RETURN jsonb_build_object('accepted', true, 'duplicate', event_id IS NULL);
END
$function$;

CREATE OR REPLACE FUNCTION api.admin_recent_alerts(
  p_org_id uuid,
  p_since timestamptz DEFAULT (now() - interval '2 minutes')
)
RETURNS TABLE(
  id uuid,
  device_id uuid,
  device_name text,
  client_id text,
  source_event_id text,
  event_type text,
  message text,
  payload jsonb,
  occurred_at timestamptz,
  created_at timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO public, pg_catalog
AS $function$
DECLARE
  uid uuid := auth.uid();
  since_at timestamptz := greatest(coalesce(p_since, now() - interval '2 minutes'), now() - interval '24 hours');
BEGIN
  IF uid IS NULL THEN RAISE EXCEPTION 'AUTH_REQUIRED'; END IF;
  IF p_org_id IS NULL THEN RAISE EXCEPTION 'ORG_ID_REQUIRED'; END IF;
  IF NOT private.is_owner_access(p_org_id) THEN RAISE EXCEPTION 'OWNER_ONLY'; END IF;

  RETURN QUERY
    SELECT e.id, e.device_id, coalesce(d.device_name, d.client_id, 'PC')::text,
           d.client_id::text, e.source_event_id, e.event_type, e.message,
           e.payload, e.occurred_at, e.created_at
    FROM public.admin_alert_events e
    JOIN public.devices d ON d.id = e.device_id AND d.org_id = e.org_id
    WHERE e.org_id = p_org_id AND e.created_at >= since_at
    ORDER BY e.created_at ASC
    LIMIT 100;
END
$function$;

REVOKE ALL ON FUNCTION api.device_emit_admin_alert(text, text, text, text, jsonb, timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION api.device_emit_admin_alert(text, text, text, text, jsonb, timestamptz) TO anon, authenticated;
REVOKE ALL ON FUNCTION api.admin_recent_alerts(uuid, timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION api.admin_recent_alerts(uuid, timestamptz) TO authenticated;
