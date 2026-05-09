-- Vibe Mill — Supabase schema (canonical Postgres)
-- Project: vibemill-inventory
--
-- This is the public mirror schema. The orchestrator's local SQLite is the
-- source of truth; this database receives snapshots after each cron tick.
--
-- Apply as a single migration on a fresh Supabase project.
-- The SQLite translation lives at migrations/sqlite/001_init.sql.
-- Tables that exist only in SQLite (audit_log, llm_calls) are not in
-- this file: they are operational and never pushed to the public mirror.

-- =========================================================================
-- apps: every app the mill has produced (live, archived, stillborn)
-- =========================================================================
create table if not exists apps (
  id                      text primary key,
  prompt                  text not null,
  archetype               text not null,
  archetype_score         integer not null,
  tied_archetypes         jsonb,
  github_url              text,
  vercel_url              text,
  screenshot_path         text,
  screenshot_status       text not null default 'pending',
  generation_cost_usd     numeric(8, 6),
  generation_seconds      integer,
  retry_count             integer not null default 0,
  source                  text not null,
  source_metadata         jsonb,
  status                  text not null default 'live',
  death_cause             text,
  views_total             integer not null default 0,
  views_peak_concurrent   integer not null default 0,
  declared_viral_at       timestamptz,
  viral_extension_until   timestamptz,
  created_at              timestamptz not null default now(),
  retired_at              timestamptz
);

create index idx_apps_status on apps(status);
create index idx_apps_archetype on apps(archetype);
create index idx_apps_created_at on apps(created_at desc);
create index idx_apps_source on apps(source);

-- =========================================================================
-- rejections: news stories and user prompts that did not pass guard/matcher
-- =========================================================================
create table if not exists rejections (
  id                      uuid primary key default gen_random_uuid(),
  source                  text not null,
  prompt                  text not null,
  rejection_stage         text not null,
  rejection_reason        text,
  best_archetype          text,
  best_score              integer,
  all_scores              jsonb,
  source_metadata         jsonb,
  created_at              timestamptz not null default now()
);

create index idx_rejections_created_at on rejections(created_at desc);
create index idx_rejections_stage on rejections(rejection_stage);

-- =========================================================================
-- subscribers: email list for "new app shipped" notifications (V1+)
-- =========================================================================
create table if not exists subscribers (
  id                      uuid primary key default gen_random_uuid(),
  email                   text unique not null,
  subscribed_at           timestamptz not null default now(),
  unsubscribed_at         timestamptz,
  unsubscribe_token       text not null unique,
  bounced                 boolean not null default false,
  bounce_count            integer not null default 0
);

create index idx_subscribers_active on subscribers(unsubscribed_at) where unsubscribed_at is null;

-- =========================================================================
-- user_submissions: Mode 2 prompt submissions (V1+)
-- =========================================================================
create table if not exists user_submissions (
  id                      uuid primary key default gen_random_uuid(),
  prompt                  text not null,
  display_name            text,
  email                   text,
  rate_limit_key          text not null,
  submitted_at            timestamptz not null default now(),
  processed_at            timestamptz,
  status                  text not null default 'pending',
  app_id                  text references apps(id),
  rejection_id            uuid references rejections(id)
);

create index idx_user_submissions_status on user_submissions(status);
create index idx_user_submissions_rate_limit on user_submissions(rate_limit_key, submitted_at);

-- =========================================================================
-- news_cache: dedupe news stories across cron ticks
-- =========================================================================
create table if not exists news_cache (
  url                     text primary key,
  headline                text not null,
  feed_source             text not null,
  published_at            timestamptz,
  fetched_at              timestamptz not null default now(),
  guard_status            text,
  matched_archetype       text,
  matcher_score           integer,
  resulted_in_app         text references apps(id)
);

create index idx_news_cache_fetched_at on news_cache(fetched_at desc);

-- =========================================================================
-- view_events: append-only view tracking for viral detection (V1+)
-- =========================================================================
create table if not exists view_events (
  id                      bigserial primary key,
  app_id                  text not null references apps(id),
  recorded_at             timestamptz not null default now(),
  views_in_window         integer not null,
  concurrent_users        integer not null
);

create index idx_view_events_app_recorded on view_events(app_id, recorded_at desc);

-- =========================================================================
-- Row Level Security
-- =========================================================================
-- Public read access to apps, rejections, news_cache (for the public site).
-- Subscribers and user_submissions are server-side writable only.
-- The orchestrator uses the service role key, which bypasses RLS.

alter table apps enable row level security;
alter table rejections enable row level security;
alter table news_cache enable row level security;
alter table subscribers enable row level security;
alter table user_submissions enable row level security;
alter table view_events enable row level security;

create policy "public read apps"
  on apps for select
  using (true);

create policy "public read rejections"
  on rejections for select
  using (true);

create policy "public read news_cache"
  on news_cache for select
  using (true);

-- subscribers: no public policies; only service role writes
-- user_submissions: no public policies; only service role writes (Next.js API route uses service role)
-- view_events: no public policies; only service role writes
