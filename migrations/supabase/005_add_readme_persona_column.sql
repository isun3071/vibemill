-- Add readme_persona column to apps. Records which README persona was
-- rolled for this app. See readme_writer.py.

alter table apps add column readme_persona text;
