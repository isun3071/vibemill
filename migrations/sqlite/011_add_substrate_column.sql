-- Bundle I: Flask substrate via github_only deploy target.
--
-- The substrate column records the literal stack the LLM generated for
-- (nextjs | gradio | flask | ...) for finer-grained analytics. Until now
-- substrate was derivable from (archetype, deploy_target); with Bundle I
-- adding per-archetype Flask routing and the option to mix substrates in
-- future, recording substrate explicitly removes the derivation hop.
--
-- deploy_target gains a third allowed value 'github_only' for Bundle I.
-- No constraint change needed; the column is plain text.

alter table apps add column substrate text;
