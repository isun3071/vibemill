-- Three-tier output calibration. Per generation, the orchestrator rolls
-- a tier (slop / mean_good / banger) at fixed weights independent of
-- input score. Tier determines whether web search runs, how many build
-- attempts, and whether reasoning is forced. See vibemill/tiers.py and
-- OPERATIONS.md "Three-tier output calibration".

alter table apps add column tier text;
alter table apps add column web_searched integer not null default 0;
alter table apps add column search_queries_count integer not null default 0;
alter table apps add column search_total_cost real not null default 0;
