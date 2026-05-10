-- Three-tier output calibration. Per generation, the orchestrator rolls
-- a tier (slop / mean_good / banger) at fixed weights independent of
-- input score. See vibemill/tiers.py and OPERATIONS.md
-- "Three-tier output calibration".

alter table apps add column tier text check (tier in ('slop', 'mean_good', 'banger'));
alter table apps add column web_searched boolean not null default false;
alter table apps add column search_queries_count integer not null default 0;
alter table apps add column search_total_cost numeric(10, 6) not null default 0;
