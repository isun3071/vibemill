import { createClient } from "@supabase/supabase-js";

// Read-only public client. Uses the anon key, which is constrained by RLS
// (see migrations/supabase/001_init.sql) to SELECT on apps, rejections,
// news_cache. The orchestrator writes via the service role key in Python;
// this client never writes.
//
// Placeholders are used at build time when env is not set so `next build`
// can construct the client without crashing. At runtime in production the
// real env vars from Vercel are used; queries against the placeholder
// host fail and the query helpers in lib/queries.ts return empty results.
const supabaseUrl =
  process.env.NEXT_PUBLIC_SUPABASE_URL || "https://placeholder.supabase.co";
const supabaseAnonKey =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "placeholder-anon-key";

if (
  !process.env.NEXT_PUBLIC_SUPABASE_URL ||
  !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
) {
  console.warn(
    "[vibemill public-site] NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY are not set; using placeholders. Queries will return empty results."
  );
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: { persistSession: false },
});
