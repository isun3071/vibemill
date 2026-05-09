-- Add committed_path column to apps. Records whether this app was
-- generated via the committed-QA path (random ~7% sample, independent
-- of input score). See OPERATIONS.md "Committed-path workflow".

alter table apps add column committed_path boolean not null default false;
