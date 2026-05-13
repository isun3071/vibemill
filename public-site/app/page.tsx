import { Hero } from "@/components/hero";
import { AppGrid } from "@/components/app-grid";
import { AboutTeaser } from "@/components/about-teaser";
import { MillStatus } from "@/components/mill-status";
import { getLastShippedAt } from "@/lib/queries";

// SSR on every request. Next 14's App Router caches `fetch()` calls (and
// supabase-js uses fetch under the hood), which would freeze the grid for
// the lifetime of the ISR window. force-dynamic skips that cache layer.
// Acceptable: the orchestrator runs every 4 hours, so SSR cost is bounded.
export const dynamic = "force-dynamic";

type HomePageProps = {
  searchParams: { page?: string };
};

export default async function HomePage({ searchParams }: HomePageProps) {
  const raw = parseInt(searchParams.page ?? "1", 10);
  const page = Number.isFinite(raw) && raw > 0 ? raw : 1;
  const lastShippedAt = await getLastShippedAt();
  return (
    <>
      <Hero />
      <MillStatus lastShippedAt={lastShippedAt} />
      <AppGrid page={page} />
      <AboutTeaser />
    </>
  );
}
