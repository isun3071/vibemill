-- Bundle D: multi-file generation. Track how many slot files the
-- generator produced for this app.

alter table apps add column file_count integer;
