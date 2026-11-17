OpenMHS is independent and is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# sim.lock.json: a package's record of passing on its real upstream simulator

A simulator package may now carry `sim.lock.json`, the record of a gate run with `--backend sim` against its upstream
installed at the pinned commit (decided by the owner on 2026-11-17; written by claude-opus-5-5, a model and not a
human). It names the environment (container platform, base image, Python, install commands, author pins, every
resolved distribution), the digest of the passing sim report and the fake gate digest at that moment. CI cannot repeat
the run and never trusts the file; the market shows it only while it still describes the package.

## What changed

- `MHS/schema/sim-lock.schema.json`; gate G1 validates the file when it is present (`G1.INVALID_FILE`), like
  `RESULT.json`. The file is outside the package lock and does not change the fake gate digest.
- `mhs.sim_lock`: `staleness()` says why a record no longer describes its package: `fake_gate_digest` is not
  `RESULT.json` `gate.digest` (the driver or the SDK result changed), the upstream commit is not the card's pin, or the
  package no longer passes. `market_sim()` gives the market field for a fresh record.
- `MHS/drivers/market.json` entries gain `sim: {status, platform, python, checked_at}` for a fresh record; entries
  without one are unchanged (`python3 -m mhs market build --check` stays current with no record).
- `MHS/handoff/tools/collect.py` warns `SIM_LOCK_STALE` (fails with `--strict`): run the simulator again after
  changing the package, or remove the record.

Tests: `MHS/sdk/tests/core/test_sim_lock.py` (schema, freshness, G1, market). SDK suite 3,955 OK (5 skipped).
