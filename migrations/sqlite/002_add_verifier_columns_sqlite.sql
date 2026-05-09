-- Add verifier verdict + notes columns to apps.
-- See GENERATOR.md "Verification pass" section.

alter table apps add column verifier_verdict text;
alter table apps add column verifier_notes text;
