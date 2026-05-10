-- Bundle D: multi-file generation. Track how many slot files the
-- generator produced for this app (vs. fixed 2-3 file output before).
-- See vibemill/generator.py and the GENERATOR.md "Multi-file
-- generation" section.

alter table apps add column file_count integer;
