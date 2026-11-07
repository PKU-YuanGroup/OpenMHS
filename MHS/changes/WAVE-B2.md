# WAVE-B2 — rounds 2 to 6 of wave B, unattended, and what their review changed

Rounds 2 to 6 of wave B ran unattended: `run_wave.py --jobs 10` with the DeepSeek Harness in headless mode
(`deepseek-v4.1-flash:1017`, one fresh session per card), 216 cards in 2 hours 1 minute, a median of 5.4 minutes per card,
none timed out. The gate passed 209; four cards stopped blocked and three proposed a skip. The harness counted 1,998 million
tokens, 98 % of them cache reads (44.5 million input and 13.0 million output tokens were not cached).

One file outside the cards' directories changed: the agent of `gh.unitreerobotics/unitree_mujoco` ran `git checkout` on a
file of its read-only clone, to get past the first gate defect below. The agent of `gh.dgretton/pyhamilton` wrote
`.git/info/attributes` in its clone and removed it again, which the runner's check did not see.

## Gate and kit changes

- **Paths that differ only in case.** Two clones track file names that differ only in case (`terrain.STL` and
  `terrain.stl`; `BACK.stl` and `Back.stl`). On a case-insensitive file system (macOS) they share one file, so `git status`
  always reports one of them modified and G1 failed with `CLONE_MODIFIED`; both cards stopped blocked. `UpstreamTree.modified`
  now leaves such paths out while the file holds the content of one of them, and G1 notes it (`G1.CLONE_NOTE`); a content
  that is neither is still a modification (`PinnedCloneTests`). The message of `G1.CLONE_MODIFIED` said "restore it", which
  the agent read as an instruction; it now says never to write in the clone.
- **G7 and a card file that only registers the class.** A card's entry symbol may point at the gym `register(...)` call
  (`gym-aloha/gym_aloha/__init__.py`) rather than the module that defines the class (`env.py`). `class_surface` looked only in
  that file and G7 failed with `NATIVE_NOT_FOUND`; it now falls back to the module path (`SurfaceTests`). The model found the
  cause and wrote the minimal repro.
- **G4 reads more number forms.** Thousands separators (`5,000 to 2,147,400,000 samples`), Python literals (`750_000`,
  `0b1111_1111`, `65_535`), symmetric bounds (`±5`, `abs(x) > 1000` for that number, a line that speaks of a magnitude for
  all its numbers) and a quantity in another unit of the same dimension (`0.08 m` shows 80 for a limit in `mm`, through
  `mhs.units`). A tolerance (`±0.5`) does not make the other numbers of its line symmetric (`NumbersInTests`). Twelve
  `UNSOURCED_LIMIT_GATE_WARNING` lines of six packages were these forms; each was checked against its line.
- **`EXEMPLAR_RESIDUE` and the upstream's own names.** `gh.sail-research-lab/robust-gymnasium` registers its own
  `CartPole-v1`, the environment id of the Gymnasium exemplar, and two more packages cite upstream lines with `CartpoleEnv`
  or `cartpole`. `collect.py` no longer reports a name that an upstream line the package cites shows
  (`CollectResidueTests`). Two real residues were edited out: a `cartpole` tag of a single inverted pendulum and an SR860
  display name in the exemplar's words.
- **Outside writes in `.git`.** `run_wave.py` also lists the settings of a clone's `.git` that change what git reports
  (`config`, `info/`, `hooks/`); a file written and removed again still changes the time of its directory
  (`ParallelRunWaveTests`).
- **SIGINT always stops the runner.** A job started with `&` by a non-interactive shell inherits SIGINT as ignored, and
  Python then installs no handler, so such a runner did not stop on SIGINT; `run_wave.py` now handles SIGINT and SIGTERM
  itself and ignores both while it stops its agents. The interrupt test starts the runner with SIGINT ignored.
- **MuJoCo references named the build host.** The limit of `action.ctrl` cited the absolute path of the model file, so 40
  reference files (three of them from wave A) carried a home directory; `tools/oss_export_check.py` refused them. The bridge
  now takes a model name, which `MujocoDriver` sets to the model's path in its clone (`models/arm.xml:actuator_ctrlrange`),
  or to `model_path` without a git checkout (`MujocoFamilyTests`); the 40 references were regenerated.
- `PROMPT.md` hard rule 1 now says that a git command that writes (checkout, restore, stash, reset, clean, config) modifies
  the clone, and that a model stops blocked `SDK_BUG` instead of restoring a modified clone.

## Model review of the 216 packages

- Three packages changed from blocked to pass with the gate fixes: `gh.unitreerobotics/unitree_mujoco`,
  `gh.openquadruped/spot_mini_mini` and `gh.abrar2652/imitation-learning-aloha`; the reviewer's note is first in their
  RESULT.json.
- `gh.biologytools/bioimager` drives a Cobolt diode-pumped laser: raised from R2 to R3 for the device and its emission write
  (Cobolt's datasheets class the 04-01 series heads 3B, the higher-power heads 4). Its safe-state action stays callable
  without a permit (SAFE-029).
- Accepted as they stopped: `gh.mattgbiz/velmex-xyz-stagecontrol-python` is blocked (the upstream class has no stop, the case
  of `gh.quantumquadrate/k10cr1`); `gh.thinksrs/srsgui` and `gh.usnistgov/labbench` are frameworks, and
  `gh.simpler-env/simplerenv` is the superproject of the passing `gh.simpler-env/maniskill2_real2sim`: three skip overrides.
- 29 cards got overrides for the shape their package showed: 26 direct drivers (commands assembled at run time, framed or
  binary protocols, ctypes SDKs, simulators without the Gymnasium or MJCF shape) that keep the card's family, so that the
  entry symbols and the floor stay those the package was checked against, and three `GymnasiumDriver` family-configs for
  gym wrappers the cards had as MuJoCo models. One of the 26, `gh.huggingface/lerobot-libero`, had a partner override, which
  now says direct driver.
- Checked on every package: the risk against the hazard of the device (lasers, pumps, liquid handlers, arms, mobile bases,
  heaters and the TEM are R2 or R3; the cameras, stages, meters and supplies R0 or R1), the provenance, the R0/R1 wording of
  `native.py`, reflection and dynamic imports, subprocess, network and file writes, the stop paths and the licence (no card
  of this batch needs the owner's decision). Two cameras write their frame to the system temporary directory and return
  its path, as `cap.sensing.image.v1` defines; simulators with camera observations return smaller arrays of the declared
  shape and name the real size, as `PLAYBOOK.md` section 8 allows.
- `gh.amsikking/thorlabs_mcm3000` passes the gate but waits for a human: the upstream class has no stop, and its e-stop
  sends the vendor Stop Command that only the PDF `MCM3000_Direct_Serial_Communication.pdf` states (page 2). The reviewer
  matched the frame against the page's figure (header only: 65 04, channel, stop mode, 00 00), but a PDF citation is a
  human's to accept (`UNVERIFIABLE_CITATION`), so `collect.py --strict` warns until `reviewed_by` is signed.
- The unitree clone's `terrain.STL` holds the content of the other tracked path than before the run; both contents are
  tracked at the pinned commit, and the gate accepts either.

After the review: registry rebuilt twice (before and after the status changes), `prepare.py --sync`, 300 packages pass the
gate and 299 pass `collect.py --strict` with no warning (the one above waits for a signature), `validate.py --no-corpus`
passes and the pilot check counts 20 of 20 finished.
