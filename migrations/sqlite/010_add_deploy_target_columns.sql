-- Bundle H: Python rail via Hugging Face Spaces.
--
-- deploy_target distinguishes vercel-deployed (Next.js) apps from
-- hf_spaces-deployed (Gradio) apps. hf_space_url holds the live URL for
-- HF-deployed apps; vercel_url still holds it for Vercel-deployed apps.
-- The public site picks the right one based on deploy_target.

alter table apps add column deploy_target text;
alter table apps add column hf_space_url text;
