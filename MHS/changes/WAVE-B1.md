# WAVE-B1 — the first round of wave B, unattended, and what its review changed

Round 1 of wave B ran unattended: `run_wave.py --jobs 10` with the DeepSeek Harness in headless mode
(`deepseek-v4.1-flash:1017`, one fresh session per card), 50 cards in 55 minutes, about 10 minutes per card. The gate passed
49; one card stopped blocked. No file outside the cards' directories changed. The harness counted 637 million tokens, 98 %
of them cache reads (10.8 million input and 3.5 million output tokens were not cached).

The prompt rules of wave A held: every laser, pump, liquid handler and drone was declared R2 or above without help, and no
R1 package claimed a review lock.

## Gate changes

- **R3 drivers could not be checked.** An R3 hardware session needs an authenticated approval authority (SAFE-033/034),
  and the gate's hardware view had none, so G6 crashed with `MHS.SAFETY.APPROVAL_REQUIRED` for every R3 driver (the
  electron microscope's high-voltage control here, the high-voltage supply of wave A). The model located the cause in
  `mhs/driver/check.py`. The gate is now the approval authority of its own in-process server for an R3 view over the fake
  backend, as principal `gate:fake-backend`; R2 keeps its fail-closed permits, and a server that serves hardware never gets
  this verifier (`TutorialTests`).
- **A floor of 0 needs no citation.** G4 warned when a rating line (`OutputSpec(1, 30.0, 3.0, ...)`) did not show the 0 of
  a voltage or current range, which the setter states elsewhere. A bound of 0 is no longer reported missing: it is the floor
  of a magnitude and can only narrow a range (`NumbersInTests`).

## Model review of the 50 packages

- Both R3 packages now pass: `gh.nion-software/nionswift-instrumentation-kit` (blocked here) and `gh.silab-bonn/basil`
  (blocked in wave A); their RESULT.json changed from blocked to pass, with the reviewer's note before the author's.
- `gh.beniroquai/opentrons-microscope-platereader` drives a NEJE laser engraver: raised from R2 to R3 (an engraving laser
  burns material, which only a class 4 source does). Its `native.py` runs `exec` on a parsed subset of the upstream script
  (imports, two constants, the class), because importing the script would open a serial port and move the head: accepted.
- Gate notes checked and accepted: `G7.MAYBE_ABSENT` of two packages (methods of base classes the gate does not follow) and
  one `G6.NO_NATIVE_CALL` (a call through a native sub-object).
- Eleven cards got `direct-driver` overrides. For the driver pack `gh.alexshkarin/pylablib-v0` the first override changed
  the family to `python-object`, the registry then picked other entry symbols and a higher floor, and the package failed
  G3 and G7: its override keeps the family `scpi`. `PLAYBOOK.md` section 3 now says to keep the family of a driver pack.

After the review: registry rebuilt, `prepare.py --sync`, 88 packages pass `collect.py --strict` with no warning, and
`validate.py --no-corpus` passes. The registry test that wanted more than 300 dispatchable cards now counts the cards
whose package recorded a result too: a finished card leaves the dispatchable set by design.
