-- Bundle G: synthetic-prompt pipeline + matcher blend. See sqlite mirror.

alter table apps add column synthetic_track text;
alter table apps add column blend_partner_archetype text;
