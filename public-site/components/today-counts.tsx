"use client";

import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";
import type { DailyCounts } from "@/lib/queries";

/** Compute the viewer's local midnight, expressed as an ISO timestamp in UTC
 *  for use against Supabase's TIMESTAMPTZ comparison. new Date(y, m, d) returns
 *  a Date interpreted in the viewer's local timezone; toISOString() then
 *  converts back to UTC so Supabase can compare. */
function localMidnightISO(): string {
  const now = new Date();
  const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return midnight.toISOString();
}

async function fetchCountsSince(sinceISO: string): Promise<DailyCounts> {
  const [shippedRes, guardRes, matcherRes] = await Promise.all([
    supabase
      .from("apps")
      .select("id", { count: "exact", head: true })
      .gte("created_at", sinceISO)
      .eq("status", "live"),
    supabase
      .from("rejections")
      .select("id", { count: "exact", head: true })
      .gte("created_at", sinceISO)
      .eq("rejection_stage", "guard"),
    supabase
      .from("rejections")
      .select("id", { count: "exact", head: true })
      .gte("created_at", sinceISO)
      .eq("rejection_stage", "matcher"),
  ]);
  return {
    shipped: shippedRes.count ?? 0,
    guardRejected: guardRes.count ?? 0,
    matcherRejected: matcherRes.count ?? 0,
  };
}

/** Today counts widget. SSR renders the UTC count as a fallback so the line
 *  is never blank on first paint. After hydration the client recomputes
 *  using the viewer's local midnight and refetches, so the displayed counts
 *  match what "today" feels like to the viewer rather than to UTC. */
export function TodayCounts({ initial }: { initial: DailyCounts }) {
  const [counts, setCounts] = useState<DailyCounts>(initial);

  useEffect(() => {
    let cancelled = false;
    fetchCountsSince(localMidnightISO())
      .then((c) => {
        if (!cancelled) setCounts(c);
      })
      .catch((err) => {
        // On error, keep the SSR fallback. Log so dev sees it in console.
        console.warn("[today-counts] client refetch failed:", err);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <p className="font-mono text-xs text-ink-faint dark:text-moon-faint mt-10 text-center">
      Today: {counts.shipped} shipped &middot; {counts.guardRejected}{" "}
      guard-rejected &middot; {counts.matcherRejected} matcher-rejected
    </p>
  );
}
