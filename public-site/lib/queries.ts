import { supabase } from "./supabase";

export type App = {
  id: string;
  prompt: string;
  archetype: string;
  layout_archetype: string | null;
  github_url: string | null;
  vercel_url: string | null;
  // Bundle H: HF Spaces rail for Python (Gradio) archetypes.
  // Bundle I: github_only for Flask apps (no separate live URL —
  // github_url doubles as the live URL).
  // deploy_target is 'vercel' | 'hf_spaces' | 'github_only'.
  deploy_target: string | null;
  hf_space_url: string | null;
  // Bundle I: explicit substrate ('nextjs' | 'gradio' | 'flask').
  substrate: string | null;
  screenshot_path: string | null;
  source: string;
  source_metadata: Record<string, unknown> | null;
  status: string;
  tier: string | null;
  readme_persona: string | null;
  verifier_verdict: string | null;
  synthetic_track: string | null;
  blend_partner_archetype: string | null;
  created_at: string;
  retired_at: string | null;
};

/** The live URL for an app, regardless of which rail deployed it.
 *  Bundle I: github_only apps' "live" URL is the GitHub repo itself —
 *  there is no separate deployment. */
export function liveUrlOf(app: App): string | null {
  if (app.deploy_target === "hf_spaces") return app.hf_space_url ?? null;
  if (app.deploy_target === "github_only") return app.github_url ?? null;
  return app.vercel_url ?? null;
}

export type Rejection = {
  id: string;
  source: string;
  prompt: string;
  rejection_stage: string;
  rejection_reason: string | null;
  best_archetype: string | null;
  best_score: number | null;
  created_at: string;
};

const APP_COLUMNS =
  "id, prompt, archetype, layout_archetype, github_url, vercel_url, " +
  "deploy_target, hf_space_url, substrate, screenshot_path, source, " +
  "source_metadata, status, tier, readme_persona, verifier_verdict, " +
  "synthetic_track, blend_partner_archetype, created_at, retired_at";

/** Homepage filter selections. The grid reads these from URL search params
 *  via the <AppFilters> client component, which writes them on change.
 *  - q: free-text substring match against the app id (the github repo slug)
 *  - archetype: exact archetype string (e.g. "tracker", "ai_agent")
 *  - tier: exact tier string ("slop" | "mean_good" | "banger")
 *  - since: relative window key ("24h" | "7d" | "30d"); absent means all time */
export type AppFilters = {
  q?: string;
  archetype?: string;
  tier?: string;
  since?: string;
};

const SINCE_WINDOWS_MS: Record<string, number> = {
  "24h": 86_400_000,
  "7d": 604_800_000,
  "30d": 2_592_000_000,
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function applyFilters(query: any, filters?: AppFilters): any {
  let q = query;
  if (filters?.q) {
    // Match against the app id (which is the human-readable github slug).
    // ilike is case-insensitive substring.
    q = q.ilike("id", `%${filters.q}%`);
  }
  if (filters?.archetype) {
    q = q.eq("archetype", filters.archetype);
  }
  if (filters?.tier) {
    q = q.eq("tier", filters.tier);
  }
  if (filters?.since && SINCE_WINDOWS_MS[filters.since]) {
    const since = new Date(Date.now() - SINCE_WINDOWS_MS[filters.since]).toISOString();
    q = q.gte("created_at", since);
  }
  return q;
}

/** Latest live apps with a live URL on any rail, newest first.
 *  Bundle I: github_only apps don't have vercel_url or hf_space_url
 *  but DO have github_url; filter on that disjunction.
 *  Supabase .range(from, to) is inclusive on both ends; offset is the
 *  starting row, limit determines the slice size. */
export async function getLiveApps(
  limit = 24,
  offset = 0,
  filters?: AppFilters,
): Promise<App[]> {
  let query = supabase
    .from("apps")
    .select(APP_COLUMNS)
    .eq("status", "live")
    .or("vercel_url.not.is.null,hf_space_url.not.is.null,github_url.not.is.null");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  query = applyFilters(query as any, filters);
  const { data, error } = await query
    .order("created_at", { ascending: false })
    .range(offset, offset + limit - 1);
  if (error) {
    console.error("[queries] getLiveApps:", error.message);
    return [];
  }
  return (data ?? []) as unknown as App[];
}

/** Total live-apps count, used by pagination math. Accepts the same
 *  filters as getLiveApps so pagination reflects the filtered result. */
export async function getLiveAppsCount(filters?: AppFilters): Promise<number> {
  let query = supabase
    .from("apps")
    .select("id", { count: "exact", head: true })
    .eq("status", "live")
    .or("vercel_url.not.is.null,hf_space_url.not.is.null,github_url.not.is.null");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  query = applyFilters(query as any, filters);
  const { count, error } = await query;
  if (error) {
    console.error("[queries] getLiveAppsCount:", error.message);
    return 0;
  }
  return count ?? 0;
}

/** Timestamp of the most recent shipped app, for the mill-status indicator
 *  (active state + countdown). ISO string or null if none shipped yet. */
export async function getLastShippedAt(): Promise<string | null> {
  const { data, error } = await supabase
    .from("apps")
    .select("created_at")
    .eq("status", "live")
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (error) {
    console.error("[queries] getLastShippedAt:", error.message);
    return null;
  }
  return (data?.created_at as string | undefined) ?? null;
}


/** Retired apps for the cemetery, newest-retired first. */
export async function getRetiredApps(limit = 48): Promise<App[]> {
  const { data, error } = await supabase
    .from("apps")
    .select(APP_COLUMNS)
    .eq("status", "retired")
    .order("retired_at", { ascending: false })
    .limit(limit);
  if (error) {
    console.error("[queries] getRetiredApps:", error.message);
    return [];
  }
  return (data ?? []) as unknown as App[];
}

export async function getAppById(id: string): Promise<App | null> {
  const { data, error } = await supabase
    .from("apps")
    .select(APP_COLUMNS)
    .eq("id", id)
    .maybeSingle();
  if (error) {
    console.error("[queries] getAppById:", error.message);
    return null;
  }
  return (data ?? null) as unknown as App | null;
}

export async function getRejections(limit = 100): Promise<Rejection[]> {
  const { data, error } = await supabase
    .from("rejections")
    .select(
      "id, source, prompt, rejection_stage, rejection_reason, best_archetype, best_score, created_at"
    )
    .order("created_at", { ascending: false })
    .limit(limit);
  if (error) {
    console.error("[queries] getRejections:", error.message);
    return [];
  }
  return (data ?? []) as unknown as Rejection[];
}

export type DailyCounts = {
  shipped: number;
  guardRejected: number;
  matcherRejected: number;
};

/** Counts since `sinceISO`. Defaults to 00:00 UTC today.
 *
 *  Bundle L+2: the SSR pass calls this without an argument (UTC fallback).
 *  After hydration the TodayCounts client component refetches using the
 *  viewer's local midnight, so the displayed counts match what "today"
 *  feels like to the viewer rather than to UTC. The label stays "Today";
 *  the underlying since-time is what shifts.
 */
export async function getTodayCounts(sinceISO?: string): Promise<DailyCounts> {
  let since: string;
  if (sinceISO) {
    since = sinceISO;
  } else {
    const startOfDay = new Date();
    startOfDay.setUTCHours(0, 0, 0, 0);
    since = startOfDay.toISOString();
  }

  const [shippedRes, guardRes, matcherRes] = await Promise.all([
    supabase
      .from("apps")
      .select("id", { count: "exact", head: true })
      .gte("created_at", since)
      .eq("status", "live"),
    supabase
      .from("rejections")
      .select("id", { count: "exact", head: true })
      .gte("created_at", since)
      .eq("rejection_stage", "guard"),
    supabase
      .from("rejections")
      .select("id", { count: "exact", head: true })
      .gte("created_at", since)
      .eq("rejection_stage", "matcher"),
  ]);

  return {
    shipped: shippedRes.count ?? 0,
    guardRejected: guardRes.count ?? 0,
    matcherRejected: matcherRes.count ?? 0,
  };
}
