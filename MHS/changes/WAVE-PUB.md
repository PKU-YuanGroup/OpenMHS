# WAVE-PUB — the 80 cards that wait for a publication decision, and what their review changed

After wave B, the dispatchable cards left were the 80 marked `publish_review: required` (`PUB`): their licence is unknown,
network-copyleft, proprietary or source-available, so a driver may be written but the owner decides before it is published.
They ran unattended like wave B: `run_wave.py --jobs 10` with the DeepSeek Harness in headless mode
(`deepseek-v4.1-flash:1017`, one fresh session per card), 80 cards in 54 minutes, a median of 6.2 minutes per card, none
timed out. The gate passed 78; one card stopped blocked and one proposed a skip. No file outside the cards' directories
changed and `collect.py` warned about none. The harness counted 768 million tokens, 97 % of them cache reads (24.5 million
input and 4.7 million output tokens were not cached).

The licences of the 80 cards: 72 state none (`NOASSERTION`), four are AGPL-3.0, three proprietary and one CC-BY-NC-SA-4.0.
Each package's review note repeats that it may not be published before the owner's decision.

## Model review of the 80 packages

- `gh.nbush257/pyexpcontrol` drives the analog laser output of a Neuropixels rig controller. Its README says the output
  drives a "cobalt MLD laser" (`README.md:50`), and Cobolt classes every 06-01 series MLD head 3B, so the device and its
  `laser_amplitude` write were raised from R2 to R3; the GPIO pins share the controller. Its safe-state action stays
  callable without a permit (SAFE-029).
- `gh.histedlab/scanimage-python-control` bound `hSI.startFocus`, which starts a focus acquisition: a two-photon microscope
  scans its laser over the sample. Its e-stop is `close()`, the client's only teardown, which does not stop an acquisition
  (the author's `safe_state` said so), and no line of the clone names a ScanImage stop. The reviewer removed the action, so
  the package keeps the zoom read and the `operator_required` zoom write at R1: a driver must be able to stop what it
  starts.
- Accepted as they stopped: `gh.aayustark007/gym-webots` is blocked (its environment runs inside the Webots simulator, an
  external application without a helper), and `gh.samueldeleglise/pyivi`, a Windows-only wrapper over the IVI drivers a
  vendor installs, gets a skip override.
- 15 cards got overrides for the shape their package showed: 13 direct drivers (commands assembled at run time, framed or
  binary protocols, multi-line replies) that keep the card's family, and two `GymnasiumDriver` family-configs for gym
  environments the cards had as MuJoCo models.
- Checked on every package: the risk against the hazard of the device (the pumps, liquid handlers, hot plates, the PCR
  cycler, the reactor heaters, the arms and the Spot quadruped are R2; no other package needed R3), the provenance, the
  R0/R1 wording of `native.py`, reflection, dynamic imports, subprocess and file writes, and the stop paths. Spot's e-stop
  cuts motor power at once, and its `safe_state` says that the robot is then not held up; the Keithley 2400's source
  ranges are `operator_required`. One `native.py` loads the upstream two-file library from a path the operator gives; that
  module defines constants and classes only, so loading it runs nothing.

No change to the SDK or the kit was needed. After the review: registry rebuilt, `prepare.py --sync`, 378 packages pass the
gate and 377 pass `collect.py --strict` with no warning (`gh.amsikking/thorlabs_mcm3000` still waits for a human to accept
its PDF citation, `MHS/changes/WAVE-B2.md`), `validate.py --no-corpus` passes and the pilot check counts 20 of 20 finished.
