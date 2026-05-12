import { supabase } from "./supabase";

export type App = {
  id: string;
  prompt: string;
  archetype: string;
  layout_archetype: string | null;
  github_url: string | null;
  vercel_url: string | null;
  // Bundle H: HF Spaces rail for Python (Gradio) archetypes.
  // deploy_target is 'vercel' or 'hf_spaces'. Live URL lives in
  // vercel_url for JS apps, hf_space_url for Python apps.
  deploy_target: string | null;
  hf_space_url: string | null;
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

/** The live URL for an app, regardless of which rail deployed it. */
export function liveUrlOf(app: App): string | null {
  if (app.deploy_target === "hf_spaces") return app.hf_space_url ?? null;
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
  "deploy_target, hf_space_url, screenshot_path, source, source_metadata, " +
  "status, tier, readme_persona, verifier_verdict, synthetic_track, " +
  "blend_partner_archetype, created_at, retired_at";

/** Latest live apps with a live URL on either rail, newest first.
 *  Drives the home grid. */
export async function getLiveApps(limit = 24): Promise<App[]> {
  const { data, error } = await supabase
    .from("apps")
    .select(APP_COLUMNS)
    .eq("status", "live")
    .or("vercel_url.not.is.null,hf_space_url.not.is.null")
    .order("created_at", { ascending: false })
    .limit(limit);
  if (error) {
    console.error("[queries] getLiveApps:", error.message);
    return [];
  }
  return (data ?? []) as unknown as App[];
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

/** Counts since 00:00 UTC today. Operating-data line under the grid. */
export async function getTodayCounts(): Promise<DailyCounts> {
  const startOfDay = new Date();
  startOfDay.setUTCHours(0, 0, 0, 0);
  const since = startOfDay.toISOString();

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
