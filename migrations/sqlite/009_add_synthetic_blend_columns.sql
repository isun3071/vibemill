-- Bundle G: synthetic-prompt pipeline + matcher blend.
-- synthetic_track records which hackathon-track group/slug an app came from
-- (None for news-source apps). blend_partner_archetype records the secondary
-- archetype if the matcher rolled a 2-archetype blend.

alter table apps add column synthetic_track text;
alter table apps add column blend_partner_archetype text;
