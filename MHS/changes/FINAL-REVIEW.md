# FINAL-REVIEW — a rehearsal of the handoff kit, and the fixes it led to

A model played the part of the one that will run the kit and integrated two pilot repositories (a serial R2 pump and a simulator)
from the prompt and the playbook alone. Both packages passed the gate, and the run exposed gaps in the kit: a gate message that
pushed towards falsifying a command, a `--strict` check that could never pass, a CI contradiction for driver pull requests, and
prompt and playbook rules that were missing. They are fixed below. The record is `_archive/optimization-2026-10/REHEARSAL.md`.

## What changed

- **Gate and SDK.** G4 reads a range written without spaces (`[5-6000]`) as both ends. G2 `BACKENDS_DIFFER` is an error and prints
  the value to write (`new --like` writes the backends of its template kind). The scaffolded lock takes `install` from the card.
  G7's message says how the checked token is taken and that a command assembled from parts needs a direct driver, never an
  altered syntax. The console summary of `mhs.driver check` names the warning codes of every `warn` gate, so the warnings are no
  longer visible only with `--verbose`.
- **`collect.py`.** `RESULT_DIGEST_STALE` (RESULT.json is a pass whose `gate.digest` is not this gate run's digest),
  `UNVERIFIABLE_CITATION` (a ref into a PDF), `EXEMPLAR_RESIDUE` without the false positive on family vocabulary and over every
  text file of the package, `DECISION_DEVIATION` as a note, the other gate warning codes as a note. With a signed `reviewed_by`
  the reading-list warnings are printed as accepted, so `--strict` (CI) can pass for a reviewed package. The check found a stale
  digest in the xArm exemplar and in the tutorial; both were refreshed and a README line about a warning that no longer exists was
  removed.
- **A contradiction in CI.** The `suites` job ran `validate.py`, which fails until the registry is rebuilt after a package is
  added, while a driver pull request may change nothing outside its own directory: every driver pull request would have failed.
  `validate.py --allow-stale-cards` (used by CI) turns exactly the two lagging comparisons into a warning; `prepare.py --sync`
  copies the rebuilt cards over the packages' `task.json`. The maintainer's step after merges is in the playbook and CONTRIBUTING.
- **`run_wave.py`.** The loop of the playbook as a script for many cards, one at a time: it prepares each card, renders the prompt,
  runs the command that starts the user's own agent (never through a shell, with the card's time box as the limit), re-runs the gate
  and records one line per card. It starts no model itself and has no sandbox of its own. `dispatch.py` gained `select_cards`, which
  both use.
- **Recon tasks.** About a third of the cards (965) cannot be given to a driver-writing model, and the kit had a format for the result
  but no prompt and no check. `RECON-PROMPT.md` (rendered by `render_prompt.py --recon` or `run_wave.py --recon`) asks for one proposal
  file; `check_recon.py` validates its shape, its card, every cited `path:LINE` and every entry symbol against the pinned clone, prints the
  cited lines for the maintainer and drafts registry override entries (`--emit-overrides`). It cannot tell whether the evidence means what
  the model says, and nothing writes into `MHS/registry/overrides/` by itself.
- **Harness guide.** `HARNESS.md` and `harness-system.txt`: one prompt is one repository, what an agent harness has to do (no human,
  repository root, shell and file tools only, no connectors, a confined sandbox, a fresh context and the true model name per run), the
  one generic system prompt, how `run_wave.py` starts it, an example for Claude Code on DeepSeek (not run here), the order of a whole
  corpus and a cost estimate from the rehearsal. `DRV-081` names the recon prompt and the guide.
- **The prompt you type.** `MASTER-PROMPT.md` and `render_prompt.py --master`: one message for an interactive harness that makes it fetch
  (`dispatch.py --todo`, new: the next card nobody has started), do and check (`collect.py`, `check_recon.py`) the prompt of one card after the
  other, with small batches, a progress file, stop conditions and a clean start per repository. Both per-repository prompts now say that every
  file is English only (the export check rejects other scripts).
  A fresh model followed it through one pilot card (pass, one gate run); what it found is fixed: python prefixes instead of an export, RESULT.json
  validated by `collect.py` (`RESULT_SCHEMA`), the `catalogue_requests` entry shape, the definition of the two sources, a measurable time box,
  the two runtime behaviours of reads and e-stops that broke its tests.
- **Prompt, playbook, guide, review checklist.** Choosing the shape of a driver and switching a card's decision; R2 and R3
  hardware (SAFE-045 and the exemplars to read); PDF citations; numbers in fakes; large arrays in fakes; the other files `new
  --like` copies; the lock; the gate order and the cheap checks; overlay keys; the troubleshooting rows that were missing.

## Tests

`MHS/sdk/tests/handoff/test_tools.py` (collect verdicts and residue, `prepare.py --sync`, `run_wave.py` with a stub agent, the recon prompt, `check_recon.py` and the recon mode of the runner), `tests/driver/test_ref_values.py`,
`tests/driver/test_check.py` (backends error, warning summary), `tests/driver/test_cli.py` (install block),
`MHS/registry/tests/test_overlays_index_validate.py` (stale cards).

## Not changed

The rehearsal ran a stronger model than DeepSeek and one repository per shape. The 20-repository pilot is the real measurement of
how many gate runs a weaker model needs. A serial R2 exemplar does not exist; the thermostat example and the julabo exemplar
stand in for it.
