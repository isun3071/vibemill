-- Bundle C: layout-archetype rotation within Tracker. Records which of
-- the 8 visual layouts (dashboard, long_form, map_dominant, chart_dominant,
-- editorial, card_feed, list_dominant, split_view) was rolled for this app.
-- See vibemill/layouts.py for weights and the rotation contract.
-- Nullable so prior rows (pre-Bundle-C) keep parsing.

alter table apps add column layout_archetype text;
