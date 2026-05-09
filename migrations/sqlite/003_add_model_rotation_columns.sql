-- Add per-app model identity columns to support generator + README rotation.
-- See ANTI_PATTERNS.md rule 5 v4 (fingerprint variance via substrate rotation)
-- and OPERATIONS.md "Generator substrate composition".
--
-- Recorded for fingerprint-pattern analysis later. Does NOT appear in the
-- generated app's footer (rule 10: do not advertise the satire).

alter table apps add column generator_model text;
alter table apps add column readme_model text;
