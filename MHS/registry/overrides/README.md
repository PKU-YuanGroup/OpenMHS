# Triage overrides

Curated triage decisions that win over the ordered rules in
`MHS/registry/triage.py`. Each `*.json` file in this directory follows
`MHS/registry/schema/overrides.schema.json`:

```json
{
  "$schema": "../schema/overrides.schema.json",
  "overrides_version": "0.9",
  "title": "...",
  "description": "...",
  "overrides": [
    {
      "package_id": "gh.owner/repo",
      "strategy": "direct-driver",
      "role": "device-driver",
      "family": "python-object",
      "reason_code": "override:flagship-driver",
      "partner": "Universal Robots",
      "flagship": true,
      "wave": 0,
      "justification": "One line that says why this decision is right."
    }
  ]
}
```

Rules:

- `package_id`, `strategy`, `role` and `justification` are required. The
  justification is one English line of at most 240 characters.
- `direct-driver` and `family-config` need a `family` from the triage family
  table. The family decides the helper and, for a post-pilot family, the
  `helper:<name>` entry in `blocked_on`.
- A quarantined repo can never be dispatched. An override keeps a quarantine
  that the rule-3 predicate sets.
- `partner` names the early-ecosystem partner (MHS/spec/appendix-d-anthropic-mhs.md,
  section 4) whose product the repo drives. The name records a product
  relationship, not an endorsement, and adds the partner term of the rank
  formula. `flagship` marks the curated flagship list that rule 8 never
  skips. `wave` pins a wave; the exemplars use wave 0.
- `entry_symbols` (direct-driver and family-config only) lists 1 to 5
  `{symbol, file, line}` items confirmed in the clone at the card's commit,
  usually a recon proposal that `MHS/handoff/tools/check_recon.py` checked and
  a maintainer accepted (`--emit-overrides` writes them). They replace the
  scan's entry symbols on the card with confidence `override`, so a card the
  scan found no class for is no longer blocked on `recon:entry_symbol`;
  `validate.py` checks that each name is defined on or just after its line.
- `capability_classes` (direct-driver and family-config only) lists 1 to 8
  stable catalogue classes a reviewer confirmed in the source. They replace
  the scan's name-derived candidate classes on the card and in the record,
  so the card's risk floor, the highest `risk_class` of its classes (CAP-017),
  follows them; there is no separate risk-floor field. A robot card with
  reviewed classes is not marked `needs_recon: motion`. A class that is not
  a stable catalogue class stops `build_registry.py`. An empty list is
  rejected, and this field does not drop MJCF models or the simulator hints.
- `omit_sim_contract: true` (direct-driver and family-config only) says the
  scan's gym registrations, environment classes and MJCF models are not the
  contract the driver serves. `build_card` then leaves `models` empty, skips
  `sim_hints`, and does not prefer `upstream-sim` because of that scan.
  Candidate classes still come from `capability_classes` when that list is
  set, and otherwise from the device API. Use this when the served commands
  are extensions (`x-cap`) that the catalogue cannot name, so
  `capability_classes` has nothing honest to list, and a vendored model would
  otherwise become `cap.world.reset.v1`, `cap.world.step.v1` and
  `cap.world.seed.v1`.
- `publish_review: "required"` makes the card say `publish_review: required`
  whatever its licence class, when a reviewer found licence evidence the
  owner must decide on (a licence file and packaging metadata that disagree,
  a custom licence the scan read as a standard one). An override can add a
  publication review, never waive one.
- `modes` (any strategy) is the record's complete mode set, 1 to 3 of
  `hardware`, `simulated` and `replay` in that order, when a reviewer found
  that the scan's modes are wrong, for example a README-head scan that
  records a real-hardware route as simulated. It replaces the record's modes
  (classification `mode_override`, rule `override:modes`, with the scanned
  modes kept as `scanned_modes`), so `simulation`, `hardware_free`, the
  device plan and the card's `safety.expected_mode` follow it. It never
  removes a hardware mode the scan found: that would lift the hardware rules
  (the e-stop evidence of SAFE-045, the hardware view of the gate) on a
  model-written line. A driver package built in the old mode then fails gate
  G3 `MODE_MISMATCH` until it is rebuilt in the reviewed mode.
  `build_registry.py` refuses `modes` that drop hardware and `modes` on a
  record of tier D or X (no device, no modes); `validate.py` checks both and
  that the record carries the reviewed modes.
- `served_mode` (direct-driver and family-config only) is the constant
  `simulated`. It is for a dual-mode record whose hardware mode stays: the
  record's modes are unchanged (hardware first, and `simulated` still
  present; a `modes` override still cannot drop hardware), and the card's
  `safety.expected_mode` becomes `simulated`. The record stores
  `x-vendor.classification.served_mode` with rule `override:served-mode`.
  `build_registry.py` refuses it unless both modes are present and hardware
  is first. `validate.py` checks that marker and that the card's expected
  mode is `simulated`. The hardware path stays on the record and is not what
  the card serves.
- `companions` (direct-driver and family-config only; user decision of 2026-11-05) lists 1 to 3 companion sources:
  corpus repositories cloned locally at their corpus-lock commit that the package's e-stop, its read-back, its
  declared re-enable and its facts may cite as `companion:<alias>/<path>:<LINE>` (the simulator repository whose
  world control is a simulator package's only stop). Each entry has an `alias`, the companion's `package_id` and
  `commit` (it must be the corpus-lock commit: `build_registry.py` stops on a re-pin, an unknown record or the
  repository itself), a `profile` (`ros1-noetic-gazebo11`), a one-line `reason` and `version_evidence`: items
  `{side, ref, token}` whose `ref` (`path:LINE`) in the tree its side names (`package`, `companion` or
  `companion:<alias>`) shows `token`; with the corpus present the build also checks each clone's HEAD and every
  range. The build copies the entries onto the card with the clone's `local_path`, `repo_url` and licence;
  `validate.py` refuses a card whose companions no override declares and a package `task.json` whose companions
  differ from the card's, and gate G1 refuses a `task.json` that differs from the registry card or declares
  companions without one. An entry restates the card's current decision (strategy, role, family, reason_code) and
  adds only `companions`. An entry may add `lock`, the alias of a clone fetched at one commit under `work/companions`
  and listed in `work/companions/LOCK.json` (the user's authorisation of 2026-11-05), when the companion is not a
  corpus record at the needed version: its `commit` and `profile` must be that LOCK.json entry's, its `package_id`
  the `gh.<owner>/<repo>` (lower case) of the entry's `repo_url`, and the card's package must be in the entry's
  `needed_by`; the build copies the entry's path, `repo_url`, `ref` and licence (`NOASSERTION` with a `licence_note`
  when the LOCK.json licence is not an SPDX expression) onto the card. Without LOCK.json (`validate.py --no-corpus`,
  an export) only the card's shape is checked.
- Each repo appears at most once across all files, and every `package_id`
  must be a registry record. `python3 MHS/registry/triage.py` exits 1 when
  an override names an unknown repo. Within a file, entries are sorted by
  `package_id`.
- An `untriaged` override sends a repo the rules misread to a recon card
  instead of a driver task (with `wave` 6 when it needs an external
  application without a helper, such as a simulator engine); `reference`
  overrides mark hosts and prior art the rules missed.
- Regeneration reads these files and never writes them. Recon results from
  later waves are added here as new entries (`reason_code` `override:recon`;
  a justification that starts "Model review of recon wave A:" is the
  reviewer's own decision, the others are the proposal's first sentence).

Files: `exemplars.json` (the four WP-11 exemplar repos), `partners.json`
(repos for partner products), `labs.json` (lab-automation frameworks,
transports and driver packs) and `robots.json` (robot drivers, flight stacks
and simulation suites); the reviewed entries of later waves are in
`ros-routing-20261102.json`, `ros-wave-b-routing.json`,
`ros-wave-c-routing.json`, `helper-wave-1-routing.json`,
`mode-corrections.json` (routing entries whose record mode a later review
corrected; each repository still appears once across all files) and
`companion-sources-lock.json` (simulator packages whose stop cites a companion fetched under `work/companions`,
with `lock`; record `MHS/changes/COMPANION-LOCKS.md`), `companion-sources.json` (simulator packages whose stop cites a companion
source).
