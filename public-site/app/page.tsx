import { Hero } from "@/components/hero";
import { AppGrid } from "@/components/app-grid";
import { AboutTeaser } from "@/components/about-teaser";

// SSR on every request. Next 14's App Router caches `fetch()` calls (and
// supabase-js uses fetch under the hood), which would freeze the grid for
// the lifetime of the ISR window. force-dynamic skips that cache layer.
// Acceptable: the orchestrator runs every 4 hours, so SSR cost is bounded.
export const dynamic = "force-dynamic";

export default function HomePage() {
  return (
    <>
      <Hero />
      <AppGrid />
      <AboutTeaser />
    </>
  );
}
