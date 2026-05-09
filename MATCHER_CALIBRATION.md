# Matcher Calibration Notes

The matcher prompt was calibrated against 15 hardcoded fixtures
(`scripts/calibrate_matcher.py`). The first baseline run revealed
a strong Tracker preference: when input contains quantifiable or
status-update elements, the matcher scores Tracker above more-
specific archetypes (disruption_visualizer, mutual_aid_coordinator,
case_file_browser, etc).

This is consistent with our hypothesis about the genre: Tracker
(status-board, count-something display) is the modal form of
vibecoded slop. The 11 other archetypes exist as variations and
edge cases, not as evenly-distributed alternatives.

V0 ships with Tracker implemented because Tracker is what the
matcher selects for the majority of inputs. The remaining
archetypes are stubbed; their judgment exists in the matcher
even when their build code does not.

This is also a falsifiable claim: if production data over the
first month shows the matcher selecting non-Tracker archetypes
more frequently than calibration suggests, the typology hypothesis
needs revision. Calibration runs are stored in 
data/calibration_runs/ for longitudinal comparison.