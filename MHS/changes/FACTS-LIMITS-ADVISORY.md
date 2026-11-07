OpenMHS is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Flag stale limit prose during package collection

Package `facts.md` pages can retain obsolete action-space references after their generated contracts change. The collector now adds a bounded `FACTS_LIMITS_REVIEW` advisory when a recognizable limits paragraph disagrees with the step-bound references in `reference.json`. It does not interpret arbitrary prose as proof, change limits, accept warnings, or replace source review.

The helper has twelve focused matching, mismatch and boundary cases. Three stale package pages were corrected after comparison with their current contracts: google-research/football, kscalelabs/kbot and openai/robogym. A 582-package page scan then found no advisory. This is a prose consistency result, not a complete gate pass or evidence of upstream simulator equivalence.

The standalone collector disables bytecode before importing its advisory helper, preserving the no-bytecode authoring/checking boundary even without an environment variable. The integrated regressions for this fix and regenerated indexes passed twenty tests. Existing `UNSOURCED_LIMIT_GATE_WARNING` and `UNVERIFIABLE_CITATION` handling remains strict; the historical vendor-PDF warning is still unaccepted.

Source: `MHS/handoff/tools/facts_limits.py`, `collect.py` and `test_facts_limits.py`. Originals, page scan and test evidence are retained in `work/handoff-runs/mhs-build-20261102/`.
