-- Add readme_persona column to apps. Records which README persona was
-- rolled for this app (enthusiastic, minimalist, technical_maximalist,
-- corporate, vibes, humble, chatgpt_loud). See readme_writer.py and
-- ANTI_PATTERNS.md rule 5 v4.

alter table apps add column readme_persona text;
