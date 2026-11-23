// Read-only route status endpoint. Dependency-free to reduce cold-start overhead.
const DB1_REF = "wzkjpycjizexxcxrfdvr";
const DB2_REF = "xcdbipgsvohesxhxydep";
const ROUTE_SELECT = [
  "active_target","epoch","updated_at","updated_by","reason","sync_ready",
  "schema_version","switch_id","primary_ready","backup_ready","auth_parity_ready",
  "auth_verified_user_ids","sync_in_progress","sync_write_quiesce",
  "sync_write_quiesce_at","data_parity_ready","routing_gateway_ready",
  "primary_schema_version","backup_schema_version","last_schema_check_at",
  "last_parity_check_at","last_parity_check_note","last_cutover_test_at",
  "cutover_test_note"
].join(",");

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store",
};

function json(status: number, body: unknown, elapsedMs?: number): Response {
  const headers = new Headers(CORS);
  if (elapsedMs !== undefined) {
    headers.set("Server-Timing", `route-status;dur=${Math.max(0, elapsedMs)}`);
    headers.set("X-Route-Status-Ms", String(Math.max(0, elapsedMs)));
  }
  return new Response(JSON.stringify(body), { status, headers });
}

function projectRefFromUrl(url: string): string {
  try { return new URL(url).hostname.split(".")[0] || ""; }
  catch { return ""; }
}

function secretFromEnv(projectRef: string): string {
  const direct = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")
    || Deno.env.get("SUPABASE_SECRET_KEY");
  if (direct) return direct;
  const raw = Deno.env.get("SUPABASE_SECRET_KEYS") || "";
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") {
      const projectKey = parsed[projectRef];
      if (typeof projectKey === "string" && projectKey) return projectKey;
      const profileKey = parsed[projectRef === DB1_REF ? "primary" : "backup"];
      if (typeof profileKey === "string" && profileKey) return profileKey;
      if (typeof parsed.default === "string" && parsed.default) return parsed.default;
      const first = Object.values(parsed).find(v => typeof v === "string" && v.length > 0);
      if (typeof first === "string") return first;
    }
  } catch { /* fail closed below */ }
  return "";
}

function parityFresh(r: Record<string, unknown>, now = Date.now()): boolean {
  const ts = Date.parse(String(r.last_parity_check_at || ""));
  return Number.isFinite(ts) && ts <= now + 60_000 && now - ts <= 30 * 60 * 1000;
}

function buildRoute(r: Record<string, any>, projectRef: string) {
  const fresh = parityFresh(r);
  const versionsMatch = !!r.schema_version
    && r.schema_version === r.primary_schema_version
    && r.schema_version === r.backup_schema_version;
  const authParity = r.auth_parity_ready === true;
  const dataParity = r.data_parity_ready === true;
  const gateway = r.routing_gateway_ready === true;
  const syncReady = r.sync_ready === true;
  const note = String(r.last_parity_check_note || "");
  const hashProof = note.includes("CORE_PARITY_HASH_PASS")
    && note.includes("ACTIVE_SESSION_HASH_PASS");
  const canSwitch = r.primary_ready === true && r.backup_ready === true
    && dataParity && gateway && syncReady && versionsMatch && fresh
    && hashProof && r.sync_in_progress !== true && r.sync_write_quiesce !== true;
  return {
    active_target: r.active_target, epoch: Number(r.epoch),
    updated_at: r.updated_at, updated_by: r.updated_by || null,
    reason: r.reason || null,
    local_profile: projectRef === DB2_REF ? "backup" : "primary",
    project_ref: projectRef, sync_ready: r.sync_ready === true,
    schema_version: r.schema_version || null, switch_id: r.switch_id || null,
    primary_ready: r.primary_ready === true, backup_ready: r.backup_ready === true,
    backup_native_optional: true,
    auth_parity_ready: authParity,
    auth_verified_user_ids: Array.isArray(r.auth_verified_user_ids) ? r.auth_verified_user_ids : [],
    auth_parity_optional: true,
    sync_in_progress: r.sync_in_progress === true,
    sync_write_quiesce: r.sync_write_quiesce === true,
    sync_write_quiesce_at: r.sync_write_quiesce_at || null,
    data_parity_ready: dataParity, routing_gateway_ready: gateway,
    primary_schema_version: r.primary_schema_version || null,
    backup_schema_version: r.backup_schema_version || null,
    can_switch_to_backup: canSwitch, can_switch_to_primary: canSwitch,
    last_schema_check_at: r.last_schema_check_at || null,
    last_parity_check_at: r.last_parity_check_at || null,
    last_parity_check_note: r.last_parity_check_note || null,
    last_cutover_test_at: r.last_cutover_test_at || null,
    cutover_test_note: r.cutover_test_note || null,
  };
}

Deno.serve(async (req: Request) => {
  const start = performance.now();
  const elapsed = () => Math.round(performance.now() - start);
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "GET") return json(405, { ok: false, error: "method_not_allowed" }, elapsed());

  const baseUrl = (Deno.env.get("SUPABASE_URL") || "").replace(/\/+$/, "");
  const projectRef = projectRefFromUrl(baseUrl);
  const knownProject = projectRef === DB1_REF || projectRef === DB2_REF;
  const secret = secretFromEnv(projectRef);
  if (!baseUrl || !knownProject || !secret) {
    return json(503, {
      ok: false, readOnly: true, projectRef: projectRef || "unknown",
      error: !knownProject ? "project_config_invalid" : "server_config_missing",
    }, elapsed());
  }

  const restUrl = new URL(`${baseUrl}/rest/v1/db_route_control`);
  restUrl.searchParams.set("id", "eq.1");
  restUrl.searchParams.set("select", ROUTE_SELECT);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 3200);

  try {
    const response = await fetch(restUrl.toString(), {
      method: "GET",
      headers: { apikey: secret, Authorization: `Bearer ${secret}`, Accept: "application/json" },
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) {
      return json(503, {
        ok: false, readOnly: true, projectRef,
        error: "route_backend_http_error", upstream_status: response.status,
      }, elapsed());
    }
    const rows = await response.json().catch(() => null);
    if (!Array.isArray(rows) || rows.length !== 1 || !rows[0]) {
      return json(503, { ok: false, readOnly: true, projectRef, error: "route_unavailable" }, elapsed());
    }
    const route = rows[0] as Record<string, any>;
    if (!["primary", "backup"].includes(String(route.active_target))
      || !Number.isInteger(Number(route.epoch)) || Number(route.epoch) < 1) {
      return json(503, { ok: false, readOnly: true, projectRef, error: "route_authority_invalid" }, elapsed());
    }
    return json(200, {
      ok: true, readOnly: true, projectRef,
      route: buildRoute(route, projectRef),
      servedAt: new Date().toISOString(),
      statusCheckMs: elapsed(),
    }, elapsed());
  } catch (error) {
    const timeout = error instanceof Error && (error.name === "AbortError" || error.name === "TimeoutError");
    return json(503, {
      ok: false, readOnly: true, projectRef,
      error: timeout ? "route_query_timeout" : "route_status_failed",
    }, elapsed());
  } finally {
    clearTimeout(timer);
  }
});
