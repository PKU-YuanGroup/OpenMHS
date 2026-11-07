# WAVE-A — ten side-by-side sessions, their model review, and the SDK defects they found

Batch wA was the rest of the pilot and of wave 1: 28 cards in ten DeepSeek Harness sessions at once (`deepseek-v4.1-flash:1017`,
two or three cards each, `dispatch.py --only` giving every session its own share). All ten ended within 20 to 30 minutes. The
model reported 23 passes and 5 blocked cards; `collect.py` agreed. No file outside the 28 driver directories changed, and no
clone was written to.

## SDK defects (all three found by the model and reported as `SDK_BUG` or as a warning it could not clear)

- **MuJoCo state.** `MujocoDriver` declared the state fields `observation` and `tick`, while `MujocoBridge` publishes
  `time_ms, qpos, qvel, ctrl, tick, timestep_ms, seed`, so every MuJoCo package failed `G6.READ_INVALID`. Three models stopped
  with a minimal repro; one worked around it with a private hook (`_state_fields`), which a config-only family driver must
  not override. The family now declares the published fields (`families.py`; `MujocoFamilyTests`).
- **MuJoCo reset.** The family's reset schema was empty, and an empty binding schema inherits the catalogue class's
  fields (`seed`, `scenario`, `options`) without descriptions (`G8.NO_DESCRIPTION`). The family now declares `seed` only,
  described as unused by a MuJoCo reset; `scenario` and `options` are refused (`MujocoFamilyTests`).
- **Degrees.** G4 compared a radian bound with a cited line in degrees (`util.degrees(-25)`) and warned. A line that states
  its angles in degrees now also shows them in radians (`check.py`; `NumbersInTests`).

`tools/oss_export_check.py` refused any CJK text outside the registry's provenance, including the path of a vendor manual a
driver cites (the Chinese-named Markdown API document in `assets/`, the only complete one of the Dobot SDK). A whole cited path token
with a file extension is now allowed inside `MHS/drivers/`; prose in another language is still refused (`ExportCheckTests`).

## Model review of the 28 packages

Reviewer `claude-opus-5-5` (`REVIEW.md` section 5); `reviewed_by` stays null everywhere.

- **Risk raised** to what `MHS/spec/04-safety.md` says the device is: four lasers (`gh.python-microscope/microscope`, a Cobolt
  head; `gh.czbiohub-sf/copylot`, a Vortran Stradus; `gh.ledger-donjon/pypdm`; `gh.complight/fisbareadybeam`) and the syringe
  pump `gh.florian-lapp/nesp-lib-py` from R1 to R2; the arm `gh.dobot-arm/tcp-ip-python-v4` to R2 with the controller's
  emergency-stop button as `estop_physical_ref`; the high-voltage supply `gh.silab-bonn/basil` to R3. The floor of a card
  comes from its catalogue classes, and the models had used extension ids and `cap.device.configure.v1`, whose floors are
  low. FISBA and basil gained a `safe_state=True` action over their e-stop's native call. At R2 and R3 their hardware
  backends now wait for a human signature.
- **basil is blocked**: the gate cannot exercise an R3 hardware driver (its behaviour checks open a session, and R3 needs an
  authenticated approval authority the gate does not configure). An SDK task.
- **Limits**: `gh.zayfod/pycozmo`'s joint bound is `operator_required` (the lift's arm angle is derived from heights and shown
  on no line; `site-limits.example.json` carries the converted values); `gh.anki/cozmo-python-sdk` is clean with the G4 fix.
- **Claims**: three R1 packages (`pylablib`, `openflexure_microscope_software`, the Dobot one before its raise) still said
  the loader refuses their hardware backend; the exemplars' `native.py` sentence (julabo, xArm) that they copy now says it
  holds at R2 and R3 only.
- **MuJoCo**: `aloha_sim`, `robopal` and `panda_mujoco_gym` pass after the SDK fixes (RESULT.json changed from blocked to
  pass, with the reviewer's note before the author's); `flybody`'s private-hook workaround and the reset overrides of two
  packages were removed.
- **Blocked and kept**: `gh.quantumquadrate/k10cr1` (the upstream has no stop command, and the model refused to invent the
  APT stop frame), `gh.neuracoreai/bigym` (needs a Gymnasium helper that takes a caller-built environment; no package).
- **Overrides**: seven cards that said `SerialDriver` or `ScpiDriver` for a framed protocol or commands built from parts are
  now `direct-driver` (`MHS/registry/overrides/labs.json`), pinned to wave 1, where they were done (without the pin two
  pilot cards moved to wave 2). The registry test that capped the overrides at 130 entries keeps only its floor of 90:
  reviews and recon results add entries by design (`PLAYBOOK.md` sections 3 and 7).

After the review the registry was rebuilt twice and `prepare.py --sync` run: the 20 pilot cards are finished (all pass),
37 packages pass `collect.py --strict` with no warning, and `validate.py --no-corpus` passes.

## Kit changes

- `PROMPT.md` rule 3 sets `risk` from what the device can do, not only from the card's floor, and says that an x-cap id
  carries the risk of the hazard it controls; `REVIEW.md` item 12 asks the reviewer to compare `risk` with the hazard table.
