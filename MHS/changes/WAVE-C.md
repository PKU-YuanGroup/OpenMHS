# WAVE-C — the 113 driver cards recon wave A opened, and four gate fixes they needed

The 113 dispatchable cards after recon wave A (`MHS/changes/RECON-A.md`: 111 cards the recon review made driver tasks,
and two whose existing entries gained the proposals' entry symbols, the Opentrons modules and a partner's Tecan
Genesis scripts) ran unattended like the earlier waves: `run_wave.py --jobs 10` with the
DeepSeek Harness in headless mode (`deepseek-v4.1-flash:1017`, one fresh session per card, batch `wC`), 113 cards in
1 hour 13 minutes, a median of 357 seconds per card (90th percentile 506 s, longest 742 s), none timed out. The harness
counted 1,120 million tokens, 97 % of them cache reads (29 million input and 7 million output tokens were not cached).
By family: 57 Gymnasium, 25 python-object, 13 SCPI, 11 serial, 7 MuJoCo; 34 of the cards state no licence. No file
outside the cards' directories was written and no clone changed.

The run gave 101 gate passes and 12 blocked cards. Seven blocks were Python 2 upstreams (`G7.NATIVE_NOT_FOUND`: the
gate parses the native class with Python 3's `ast`), two of them before any package was written; two were gate defects
the authors reported as `SDK_BUG` with a minimal repro (rp2daq, HumanoidGen); three had no stop or no class to drive
(the Tecan Genesis scripts of `gh.tolland/python-tecan-genesis`, RoboPianist's dm_control task, the AS7265x functions).
Two passes carried a warning a model review does not accept: an `UNSOURCED_LIMIT_GATE_WARNING` (the servo arm of
`gh.itheima1/mcp_robot`) and seven `UNVERIFIABLE_CITATION` lines (a Siglent programming guide PDF).

## Gate fixes (SDK)

- **G7 reads Python 2 source** (`mhs.driver.upstream`): when `ast` rejects a module, the reading is lenient. Indentation
  tabs expand to Python 2's 8 columns, `print` and `exec` statements become `pass`, `except E, e:`, `0777`, `10L` and
  `ur''` are respelled, and every other line the parser still rejects is left out, one at a time, so every class keeps
  the line the clone shows. `Surface.legacy` names the files read that way, and G7 warns `G7.LEGACY_SOURCE`: a member
  defined only on a line left out is not seen, and the clone cannot be imported under Python 3, so `native.py` ports it.
  `PLATFORM_UNSUPPORTED` no longer covers Python 2 source (`MHS/handoff/PLAYBOOK.md` section 5).
- **G7 sees attributes a helper sets** (rp2daq): a class that hands itself to another class of the clone
  (`Rp2daq_internals(externals=self)`), whose methods call `setattr(self._e, <computed name>, ...)`, gets an open
  surface, so a name the fake uses is `MAYBE_ABSENT` when it occurs in the clone (the firmware's commands are documented
  in `docs/PYTHON_REFERENCE.md`) and still an error when it occurs nowhere.
- **G7 knows the Gymnasium environment interface** (HumanoidGen): when the native class of a `GymnasiumDriver` has a
  base outside the clone (ManiSkill's `BaseEnv`), `action_space`, `observation_space`, `reset`, `step` and the other
  names of `gymnasium.Env` are `MAYBE_ABSENT` even when no file of the clone names them; any other name is still
  `NOT_UPSTREAM`.
- **G4 reads the CJK degree sign** (the servo arm): a line where U+5EA6 directly follows a number (a Chinese comment
  "0-180" plus that sign) states degrees, so its numbers also count in radians, as for `deg` and `°`; the same sign after
  another character is part of a word (speed, temperature) and does not count.

Tests: `tests/driver/test_upstream.py` (a Python 2 module with tabs, print statements, a continuation line, an octal
literal and `except E, e:`; a helper that sets attributes on its owner, and one that does not),
`tests/driver/test_check.py` (a Python 2 tutorial upstream passes G7 with `LEGACY_SOURCE`; a Gymnasium native class with
an external base has `action_space` as `MAYBE_ABSENT` and an invented method as `NOT_UPSTREAM`) and
`tests/driver/test_ref_values.py` (the degree sign after a number, not after a word). `MHS/sdk/docs/driver-authoring.md`
and `MHS/handoff/REVIEW.md` item 2 describe the new readings.

With the fixes, five Python 2 packages (Newport SMC100, two syringe pumps, a uEye camera, a Newport 1918 power meter),
rp2daq and HumanoidGen pass the gate and their repository tests without a change to the package. The two Python 2
cards without a package ran again (batch `wC-retry`, 2 cards in 8 minutes): the Thorlabs APT motor of `gh.mcleu/pyapt`
passes, the Waters-compatible liquid handler is blocked by the review (below).

## Model review

Claude (claude-opus-5-5, a model, not a human) worked through `MHS/handoff/REVIEW.md` for every package
(`reviewed_by` stays null; the record is the last paragraph of each `RESULT.json`): it re-ran the gate, read every
sourced `Limit` of the hardware packages against its cited line (98 limits), every e-stop and `safe_state=True`
action, the risk against the hazard table of `MHS/spec/04-safety.md`, every `native.py` of a hardware package, and
scanned all package code for reflection, dynamic imports, subprocesses, file writes, network use, home-directory
paths and CJK text. Decisions:

- **Accepted after reviewer edits (6):**
  - `gh.filipdominec/rp2daq`: its stop sent a stepper to the position read just before, so a moving stepper stopped
    and crept back at speed 1 while the call waited; it now sends a relative move of 0, which the documentation says
    stops a moving stepper at once. The stepper target became `operator_required` (the firmware's
    +/-2,147,000,000 guards an overflow, not the travel).
  - `gh.itheima1/mcp_robot`: the joint limit also cites the docstring line that states the degrees.
  - `gh.quantumllama/python-lab-drivers`: the waveform list and the duty cycle, cited only to the PDF, became
    `operator_required`, and the PDF facts a note (the reviewer read pages 19 and 20 through a text extraction).
  - `gh.samdejong86/agilent33600`: the e-stop wrote an amplitude of 0 V, which the instrument clips to its minimum
    while the DC offset stays on; it now writes `OUTPUT1 OFF`, the off form of the clone's `OUTPUT1 ON`.
  - `gh.kajalbiju/psi_bluesky_backend`: the e-stop wrote only the manual heater output (HSET 0), which does not stop a
    PID loop that is heating; it writes TSET 0 first.
  - `gh.williamtsalter/fielddinomicroscopy`: one non-ASCII character in `facts.md`.
- **Blocked by the review (4), all for a stop that does not stop**, the case of velmex and k10cr1 in the earlier waves:
  - the Tecan Genesis scripts of `gh.erikbgithub/python3-tecan-genesis` (discarding queued commands does not stop a
    moving arm; the same instrument's other card blocked itself for this);
  - the SmartEM Verios client (no stage stop, no beam blank, and its setup unblanks the beam);
  - the SpectraMax of `gh.sciencecorp/galago-tools` (its e-stop closed the drawer: a motion that queues behind a
    running read for up to 60 s);
  - the liquid handler of `gh.dwinters42/liquidhandler` (no stop in the protocol; its e-stop sent a speed outside the
    protocol's range).

  The reviewer removed each package's ineffective e-stop and safe-state flag, so the gate refuses it for the missing
  stop (`G3.NO_ESTOP`) and does not contradict its `RESULT.json`; the authors' versions are kept in
  `work/handoff-runs/wC/reviewer-originals/` (not exported).
- **Judgement calls accepted as written:**
  - The KUKA KR C4 client of `gh.akselov/digital-twin-opcua` cannot end a PTP motion (its e-stop holds the next
    target), and its independent stop is the controller's `$STOPMESS` interrupt.
  - `gh.emb-ai/robobenchmart` subclasses the Gymnasium bridge to publish no observation schema it cannot source.
  - The two Keithley source-measure units (2400, 2450: about 200 V) are R3 as their authors set; low-voltage bench
    supplies stay R1, as the earlier waves had both.
  - Image actions write a temporary PGM or BMP and return its path (`image_ref`), as the earlier camera packages do.
- **Blocks accepted (3):**
  - `gh.tolland/python-tecan-genesis`: no stop; the Python 2 reason is gone.
  - `gh.google-research/robopianist`: a programmatic dm_control task; waits for a dm_control helper.
  - `gh.liamsgithub/as7265x-spectrometer`: module-level functions over I2C, no class. G7 needs a module surface for
    such upstreams; that is SDK work.

22 override entries record the shape the packages showed (`MHS/registry/overrides/labs.json` and `robots.json`, prefix
"Model review of wave C:"). Twenty-one cards are now direct drivers that keep their family:
- commands assembled at run time;
- framed or binary protocols;
- environments without the Gymnasium interface or with a ctypes simulator;
- the two Tecan cards, for a later run.

`gh.rlagent/factor-world` is a `GymnasiumDriver` family-config. Two Gymnasium packages
(RoboCasa and its G1 variant) found a bridge gap: a `Dict` action space whose keys already start with `action.` gives
limit paths the bridge cannot resolve, so both are direct Drivers; the gap is recorded here, not fixed.

## Result

After the review, 106 packages of the wave pass the gate and 7 are blocked: the four above, the Tecan card that
blocked itself, RoboPianist and the AS7265x functions.

The registry was rebuilt twice, before and after the status changes, and `prepare.py --sync` ran each time. It now
counts:

| state | cards |
|---|---|
| dispatchable | 0 (every card that reached that state ran) |
| done | 499 (484 pass, 11 blocked, 4 skip-proposed) |
| recon | 289 (the 286 `untriaged` cards of wave 6 and three cards whose entry module is not importable by name) |
| waiting for a helper | 252 |
| skip | 1,416 |
| reference | 292 |
| bridge-runtime | 215 |
| quarantined | 4 |

The 378 packages that passed before this wave were re-gated with the changed gate, and all kept their digests.

Checks:

- All 484 passing packages pass `collect.py --strict` except `gh.amsikking/thorlabs_mcm3000`, which still waits for a
  human to accept its PDF citation (`MHS/changes/WAVE-B2.md`).
- `validate.py --no-corpus` passes and the pilot check counts 20 of 20 finished.
- The SDK suite (2,094 tests), the registry suite (276) and the OpenAI4S integration tests (129) pass.
- `tools/oss_export_check.py` passes.
