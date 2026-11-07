OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Driver packages: rules, states and gate tools

- [REVIEW.md](REVIEW.md): the review rules every driver package meets (stops, resets, simulator hazards, companion
  sources, evidence).
- [PLAYBOOK.md](PLAYBOOK.md): what a registry card holds, the package states and the blocked codes.
- [BLOCKED.md](BLOCKED.md): why each blocked record is blocked and what would change it.
- `tools/`: `collect.py` re-runs the gate over finished packages and summarises them (`--strict` in CI),
  `dispatch.py` lists cards by state, `prepare.py` copies a card into a package directory and keeps `task.json` in
  step with the registry, `show_refs.py` prints the source lines a package cites, `facts_limits.py` checks sourced
  limits.

Every package's evidence is fake `contract_checked`; no package has been run on hardware, and a hardware backend needs a
human `reviewed_by` signature before any use.
