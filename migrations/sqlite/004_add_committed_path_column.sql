-- Add committed_path column to apps. Records whether this app was
-- generated via the committed-QA path (random ~7% sample, independent
-- of input score). See OPERATIONS.md "Committed-path workflow" and
-- ANTI_PATTERNS.md rule 5 v4 for the rationale.
--
-- SQLite stores boolean as integer (0/1). Default 0.

alter table apps add column committed_path integer not null default 0;
