-- Vibe Mill — local SQLite schema (source of truth)
-- File: /home/ian/vibemill/data/vibemill.sqlite
--
-- Translated from migrations/supabase/001_init.sql with:
--   jsonb        -> text (JSON-encoded)
--   uuid         -> text (uuid4 generated app-side)
--   gen_random_uuid() removed; orchestrator passes uuid4()
--   timestamptz  -> text (ISO-8601 UTC, '%Y-%m-%dT%H:%M:%SZ')
--   now()        -> CURRENT_TIMESTAMP (UTC)
--   numeric(8,6) -> real
--   bigserial    -> integer primary key autoincrement
--   RLS dropped (no row-level security in SQLite)
--
-- Adds two SQLite-only operational tables not present in the Supabase mirror:
--   llm_calls — cost ledger; powers the daily cost cap. See OPERATIONS.md.
--   audit_log — state-change audit trail. See SECURITY.md.

pragma foreign_keys = on;
pragma journal_mode = wal;

-- =========================================================================
-- apps
-- =========================================================================
create table if not exists apps (
  id                      text primary key,
  prompt                  text not null,
  archetype               text not null,
  archetype_score         integer not null,
  tied_archetypes         text,
  github_url              text,
  vercel_url              text,
  screenshot_path         text,
  screenshot_status       text not null default 'pending',
  generation_cost_usd     real,
  generation_seconds      integer,
  retry_count             integer not null default 0,
  source                  text not null,
  source_metadata         text,
  status                  text not null default 'live',
  death_cause             text,
  views_total             integer not null default 0,
  views_peak_concurrent   integer not null default 0,
  declared_viral_at       text,
  viral_extension_until   text,
  created_at              text not null default current_timestamp,
  retired_at              text
);

create index if not exists idx_apps_status on apps(status);
create index if not exists idx_apps_archetype on apps(archetype);
create index if not exists idx_apps_created_at on apps(created_at desc);
create index if not exists idx_apps_source on apps(source);

-- =========================================================================
-- rejections
-- =========================================================================
create table if not exists rejections (
  id                      text primary key,
  source                  text not null,
  prompt                  text not null,
  rejection_stage         text not null,
  rejection_reason        text,
  best_archetype          text,
  best_score              integer,
  all_scores              text,
  source_metadata         text,
  created_at              text not null default current_timestamp
);

create index if not exists idx_rejections_created_at on rejections(created_at desc);
create index if not exists idx_rejections_stage on rejections(rejection_stage);

-- =========================================================================
-- subscribers (V1+)
-- =========================================================================
create table if not exists subscribers (
  id                      text primary key,
  email                   text unique not null,
  subscribed_at           text not null default current_timestamp,
  unsubscribed_at         text,
  unsubscribe_token       text not null unique,
  bounced                 integer not null default 0,
  bounce_count            integer not null default 0
);

create index if not exists idx_subscribers_active
  on subscribers(unsubscribed_at) where unsubscribed_at is null;

-- =========================================================================
-- user_submissions (V1+)
-- =========================================================================
create table if not exists user_submissions (
  id                      text primary key,
  prompt                  text not null,
  display_name            text,
  email                   text,
  rate_limit_key          text not null,
  submitted_at            text not null default current_timestamp,
  processed_at            text,
  status                  text not null default 'pending',
  app_id                  text references apps(id),
  rejection_id            text references rejections(id)
);

create index if not exists idx_user_submissions_status on user_submissions(status);
create index if not exists idx_user_submissions_rate_limit
  on user_submissions(rate_limit_key, submitted_at);

-- =========================================================================
-- news_cache
-- =========================================================================
create table if not exists news_cache (
  url                     text primary key,
  headline                text not null,
  feed_source             text not null,
  published_at            text,
  fetched_at              text not null default current_timestamp,
  guard_status            text,
  matched_archetype       text,
  matcher_score           integer,
  resulted_in_app         text references apps(id)
);

create index if not exists idx_news_cache_fetched_at on news_cache(fetched_at desc);

-- =========================================================================
-- view_events (V1+)
-- =========================================================================
create table if not exists view_events (
  id                      integer primary key autoincrement,
  app_id                  text not null references apps(id),
  recorded_at             text not null default current_timestamp,
  views_in_window         integer not null,
  concurrent_users        integer not null
);

create index if not exists idx_view_events_app_recorded
  on view_events(app_id, recorded_at desc);

-- =========================================================================
-- llm_calls (SQLite only): cost ledger powering the daily cost cap.
-- The cap check is:
--   select coalesce(sum(cost_usd), 0)
--   from llm_calls
--   where called_at >= start_of_today_utc
-- =========================================================================
create table if not exists llm_calls (
  id                      integer primary key autoincrement,
  called_at               text not null default current_timestamp,
  model                   text not null,
  purpose                 text not null,    -- 'guard' | 'matcher' | 'generator' | 'readme'
  tokens_in               integer not null default 0,
  tokens_out              integer not null default 0,
  cost_usd                real    not null default 0,
  latency_ms              integer,
  app_id                  text,             -- nullable; set when the call is associated with an app
  ok                      integer not null default 1
);

create index if not exists idx_llm_calls_called_at on llm_calls(called_at desc);
create index if not exists idx_llm_calls_app on llm_calls(app_id);

-- =========================================================================
-- audit_log (SQLite only): state-change trail. Never pushed to Supabase.
-- =========================================================================
create table if not exists audit_log (
  id                      integer primary key autoincrement,
  ts                      text not null default current_timestamp,
  operator                text not null,    -- 'orchestrator' | 'cli'
  operation               text not null,    -- 'app.create', 'app.retire', 'app.viral_extend', ...
  target                  text,             -- app_id or other identifier
  reason                  text
);

create index if not exists idx_audit_log_ts on audit_log(ts desc);
create index if not exists idx_audit_log_target on audit_log(target);
