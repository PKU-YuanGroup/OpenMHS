# RECON-A — the 680 recon cards of wave 4, and the override entry symbols they needed

The 680 recon cards of wave 4 (`untriaged`: triage could not tell what the repository is) ran unattended like the driver waves:
`run_wave.py --recon --jobs 10` with the DeepSeek Harness in headless mode (`deepseek-v4.1-flash:1017`, one fresh session per
card, batch `rA`), 680 cards in 1 hour 45 minutes, a median of 78 seconds per card (90th percentile 162 s, longest 402 s), none
timed out. Each run wrote one proposal file under `MHS/handoff/recon/` and no driver. The harness counted 605 million tokens, 64 %
of them cache reads (215 million input and 11 million output tokens were not cached). This was the first recon run at scale.

674 proposals passed `check_recon.py` at once. Five cards failed on a kit defect: their clone directory differs from the package id
(a trailing dash, a truncated name), and the prompt named the file after the driver directory while the checker wanted the package
id. Three agents renamed their file to satisfy the checker, so the runner found no proposal and listed the renamed file as a write
outside the card. The checker now names the file after the card's driver directory, as the prompt does (14 cards differ); the three
files were moved to those names. One agent ended its turn without writing; a second run of that card passed. All 680 are valid.

## What the proposals said

332 `skip`, 106 `bridge-runtime`, 99 `reference`, 2 `untriaged`, and 141 that make the repository a driver task: 34
`direct-driver` and 107 `family-config` (64 Gymnasium, 13 MuJoCo, 16 SCPI, 11 serial, 2 ROS, 1 SiLA 2).

## Model review

Claude (claude-opus-5-5, a model, not a human) read the entry symbol and every cited line of the 141 driver proposals, and one line
per proposal of the other 539 (`reviewed_by` does not apply here: no driver package was written). It accepted 119 driver proposals
as they were (two of them only add entry symbols to existing entries) and changed or replaced 22:

- Six LIBERO derivatives (LIBERO-Para, LIBERO-Safety, LIBERO-10-R, LIBERO-Plus, LIBERO-Pro, RoboMemArena) are new BDDL task files over
  a copy of LIBERO's environment code, so they are `skip:duplicate_of` `gh.lifelong-robot-learning/libero`. LIBERO itself, a
  flagship whose override said "recon decides", becomes a direct `Driver` over `OffScreenRenderEnv` (MuJoCo family), the shape the
  passing `gh.huggingface/lerobot-libero` package has. The variational-automation benchmark, which has its own environment class,
  stays a driver task.
- Two duplicates of passing or richer cards: a PyTorch port of Transporter Nets copies the Ravens environments, and an older PyMoDAQ
  seabreeze plugin is the viewer `gh.pymodaq/pymodaq_plugins_oceaninsight` ships.
- Wrappers of another repository's code are not drivers: Cheshire's liquid-handler classes wrap PyLabRobot backends (reference),
  a collection of benchmark wrappers points to its successor (reference), dm_control2gym and a PettingZoo adapter re-export other
  packages' environments, and EnvPool re-implements existing tasks for throughput (skip, tooling). PyVenus runs HSL through
  Hamilton's Venus and implements no device function, so it is SDK work (bridge-runtime).
- No environment interface to drive: a G1 sim2sim script, a G1 policy whose environment sits in a training script with an absent
  model, RoboTwin 2.0-Plus (gym.Env subclasses without reset or step), a Windows-only COCO/ChemSep process simulator, and a
  one-function E4407B screen-capture script (skip).
- Two Gymnasium environments that talk through rospy/MAVROS or ROS 2 nodes take the `ros` family, so they wait for the ROS helper.

Four cards had curated `untriaged` overrides, which the recon results replace: AC Dev Lab is a host, pyacq a framework, LIBERO is
above, and Unitree's C++ DDS SDK `unitree_sdk2` is SDK work (the proposal said prior art). Two existing driver entries (Opentrons
modules, the Tecan Genesis scripts) keep their text and gain the proposal's entry symbols. Of the 539 other proposals, one
justification cut at "i.e." was rewritten, a KDS Legato FastCS scaffold that sends no command becomes a skip, and an AirSim
environment becomes `untriaged` in wave 6; the rest stand as proposed. Every one of the 680 cards now has an entry in
`MHS/registry/overrides/labs.json`, `robots.json` or `partners.json`; those whose justification starts "Model review of recon wave
A:" are the reviewer's decisions, the others are the proposal's first sentence.

Review limits: the reviewer checked that each cited line says what the proposal claims and that the strategy fits the guide; it
did not run any upstream code, and the skip and reference proposals were read one line each, so a skipped repository may still hide a
driver.

## Override entry symbols (registry and SDK)

50 of the accepted driver cards had no entry symbol: the scan could not parse their class (Python 2 files, scripts, files only a GUI
imports). An override could change the decision but not the entry symbols, so those cards would have stayed blocked on
`recon:entry_symbol`. An override entry may now carry `entry_symbols` (1 to 5 `{symbol, file, line}`, direct-driver and
family-config only; `overrides.schema.json`, `triage.check_override`): the card takes them instead of the scan's, with the new
confidence `override` (`taskcard.schema.json`), and `validate.py` checks that each name is defined on or just after its line, the
rule `check_recon.py` applies. `check_recon.py --emit-overrides` writes a driver proposal's symbols into its entry. A module that
is not importable by name (`2230G`, a path with a space) cannot be an override symbol, so three cards (two Keithley supplies, the
Thorlabs beam-profiler examples) stay recon cards. The decision record does not carry the symbols. In the SDK, `mhs.driver new`
puts an `override` symbol first, and `G7.NOT_AN_ENTRY_SYMBOL` is an error for an `override` symbol as for an `ast` one. The driver
prompt now points a model at the recon proposal behind its card (`{RECON_FILE}`) and tells it to read the notes first.

## English-only proposals

The proposals go into the open-source export, which refuses CJK text and home-directory paths. Two proposals had them: one quoted
a Chinese README title, one cited a Windows user-profile path. The reviewer reworded those two evidence lines in English (the
cited `path:LINE` is unchanged). `check_recon.py` now refuses CJK text in notes and in the text of an evidence line (a cited path
may still name a file in its own language) and any home-directory path, so the next recon model fixes this itself.

## Result

After the rebuild: 113 cards are dispatchable (1 in wave 2, 103 in wave 3, 9 in wave 6; 34 of them state no licence, so their
packages wait for the owner's publication decision), 252 wait for a helper (6 more: ROS, pymmcore-plus, SiLA 2), 289 are recon
cards (286 `untriaged` in wave 6 and the three above), 1,416 skip, 292 reference and 215 bridge-runtime. The 386 done packages are
unchanged: their task cards changed only their rank, which the gate digest does not cover (the 211 re-gated passing packages kept
their digests). `validate.py --no-corpus` passes; three registry tests that pinned cards this run decided were updated.
