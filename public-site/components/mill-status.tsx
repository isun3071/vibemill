"use client";

import { useEffect, useState } from "react";

// Hours between mill ticks. Must match the systemd timer's OnCalendar
// cadence. If you change deploy/systemd/vibemill.timer, change this too.
const INTERVAL_HOURS = 4;
const INTERVAL_MS = INTERVAL_HOURS * 60 * 60 * 1000;

// "Active" = shipped at least one app within (interval + buffer). Buffer
// absorbs systemd's 15-minute jitter plus slow run completions. If no app
// shipped in the last 5 hours, the mill reads as idle.
const ACTIVE_BUFFER_MS = 1 * 60 * 60 * 1000; // 1h buffer past interval
const ACTIVE_WINDOW_MS = INTERVAL_MS + ACTIVE_BUFFER_MS;

function pad(n: number, w = 2): string {
  return n.toString().padStart(w, "0");
}

function formatDuration(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return `${pad(h)}:${pad(m)}:${pad(sec)}`;
}

/** Mill status indicator. Active state + ticking countdown to next batch.
 *
 *  Active state: derived from lastShippedAt. If the most recent ship was
 *  within (INTERVAL_HOURS + 1h buffer), the mill is "active." Otherwise
 *  it's "idle" (cron paused, errored, or never started).
 *
 *  Next-batch ETA: lastShippedAt + INTERVAL_HOURS, falling back to the
 *  next interval-boundary from now if the lastShipped value is stale.
 *  This self-corrects to whatever cadence the cron actually runs at,
 *  without needing to read the systemd schedule.
 */
export function MillStatus({ lastShippedAt }: { lastShippedAt: string | null }) {
  const [mounted, setMounted] = useState(false);
  const [now, setNow] = useState<number>(0);

  useEffect(() => {
    setMounted(true);
    setNow(Date.now());
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const lastShipped = lastShippedAt ? new Date(lastShippedAt).getTime() : null;
  const isActive = mounted && lastShipped !== null && (now - lastShipped) < ACTIVE_WINDOW_MS;

  let nextRunAt: number | null = null;
  if (mounted) {
    if (lastShipped !== null && lastShipped + INTERVAL_MS > now) {
      nextRunAt = lastShipped + INTERVAL_MS;
    } else {
      // Stale or missing lastShipped: fall back to the next interval boundary from now.
      nextRunAt = Math.ceil(now / INTERVAL_MS) * INTERVAL_MS;
    }
  }

  const countdownText = mounted && nextRunAt !== null
    ? formatDuration(nextRunAt - now)
    : "--:--:--";

  return (
    <div className="w-full px-6 sm:px-10 max-w-7xl mx-auto">
      <div className="font-mono text-xs uppercase tracking-wider text-ink-muted dark:text-moon-muted flex flex-wrap items-center justify-center gap-x-6 gap-y-2 border-y border-ink/10 dark:border-moon/10 py-3">
        <span className="flex items-center gap-2">
          <span
            aria-hidden
            className={`inline-block w-2 h-2 rounded-full ${
              !mounted
                ? "bg-ink-faint dark:bg-moon-faint"
                : isActive
                  ? "bg-emerald-600 dark:bg-emerald-500"
                  : "bg-rose-700 dark:bg-rose-500"
            }`}
          />
          {!mounted ? "Mill status" : isActive ? "Mill active" : "Mill idle"}
        </span>
        <span className="text-ink-faint dark:text-moon-faint" aria-hidden>·</span>
        <span>
          Next batch in{" "}
          <span className="text-ink dark:text-moon tabular-nums">
            {countdownText}
          </span>
        </span>
      </div>
    </div>
  );
}
