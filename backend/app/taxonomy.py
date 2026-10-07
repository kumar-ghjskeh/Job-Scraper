"""Shared taxonomy constants, with no imports of their own.

These are read by the API, the scrape engine, the snapshot writer and the frontend's
mirror, and they used to live inside snapshot.py and scrape_engine.py. That made
main.py import snapshot -> scrape_engine -> every scraper adapter just to read a
frozenset of category names, which is a lot of module-loading on an API that does no
scraping, and a real startup risk on a deployment that installs only
requirements.txt.

Nothing here imports anything, so it is safe to pull in from any layer.
"""
from __future__ import annotations

# Categories the default view hides. MUST stay identical in all four deciders:
# this module, frontend/src/lib/query.ts, frontend/src/lib/corpus.ts, and the
# relevance gate in backend/app/main.py (which imports it from here).
#
# RTL design and design verification are the whole scope of this board. The rest are
# real engineering disciplines whose postings are kept — they are simply not what
# this board is for, so the default view hides them and the include_adjacent toggle
# still reaches them.
HIDDEN_CATEGORIES = {
    "Software / Compiler",      # firmware and software developer roles
    "Unknown",                  # nothing identifiable in the title
    "Adjacent / Backup",        # architecture/modelling, analog, RF, packaging, non-engineering
    "Physical Design",          # floorplan, place-and-route, STA, timing closure, signoff
    "Post-Silicon Validation",  # lab bring-up and characterisation, after the chip exists
    "DFT",                      # design-for-test: scan, ATPG, MBIST
    "EDA / Verification Tools", # CAD, methodology, flow and tooling work
}

# After this many consecutive failed runs a source is auto-quarantined (skipped) so
# broken endpoints never keep throwing errors into the dashboard.
ERROR_QUARANTINE_THRESHOLD = 8

# After this many consecutive runs where the SOURCE returned zero postings, a source
# is reported as stalled. Judged on the source's own output, not on what survives the
# relevance filter — a healthy board with no RTL/DV openings is not a stall.
#
# Not quarantined either: a board really can be empty, and skipping it would mean
# never noticing when it refills. At 8 runs/day this is about a day and a half of
# silence, which no active employer sustains.
EMPTY_STALL_THRESHOLD = 12
