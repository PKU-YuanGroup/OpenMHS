OpenMHS is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Duckietown status messages

The MultiMap fake used internal episode codes in `info["Simulator"]["msg"]`. Pinned upstream `c76a7fec7f739db4f624f40ca83ce99383665558`, `src/gym_duckietown/simulator.py:1681,1687-1705`, exposes an empty string during an episode and explanatory sentences for an invalid pose or the step limit. The fake now copies those observable messages.

Ten package cases pass through the stock adapter, server and client, including all three message outcomes. This fixes L07 in the continuing handoff; the declared F0 image, lane, randomization and steering dynamics remain placeholders. No upstream simulator or hardware was executed.

Changed package files are `fake.py`, `test_driver.py`, `facts.md` and the model-review paragraph in `RESULT.json`. References and lock provenance are unchanged. Full gate validation waits for the pending generated task-card synchronization; this record does not claim that the current complete corpus passed. Originals, test output and hashes are in `work/handoff-runs/mhs-build-20261102/development/duckietown-msg/`.
