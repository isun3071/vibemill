-- Add per-app model identity columns to support generator + README rotation.
-- See ANTI_PATTERNS.md rule 5 v4 (fingerprint variance via substrate rotation)
-- and OPERATIONS.md "Generator substrate composition".

alter table apps add column generator_model text;
alter table apps add column readme_model text;
