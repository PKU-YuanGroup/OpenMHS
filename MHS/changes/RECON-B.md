# RECON-B — the 285 recon cards of wave 6, and git hooks kept out of the clones

The recon cards of wave 6 (`untriaged` cards that need a GPU, Windows or an external engine) ran unattended as recon
wave A had (`MHS/changes/RECON-A.md`): `run_wave.py --recon --wave 6 --jobs 10` with the DeepSeek Harness in headless
mode (`deepseek-v4.1-flash:1017`, batch `rB`). 285 cards ran in 58 minutes, a median of 108 seconds per card (90th
percentile 188 s, longest 345 s), and none timed out; the 286th card of the wave, `gh.bilalkabas/drl-nav`, already had
its proposal from wave A and was skipped. The harness counted 357 million tokens, 95 % of them cache reads. All 285
proposals passed `check_recon.py` at the first run. One run changed a clone, below.

## Git hooks in a clone

The recon agent of `gh.lightwheelai/lw-benchhub` ran only read-only git commands in its clone (`log`, `status`,
`diff --stat`), but the clone's own git configuration has Git LFS filters, and a `git status` over a modified LFS file
runs git-lfs, which installs its hooks when they are missing. The runner listed the four new files of `.git/hooks`
(`post-checkout`, `post-commit`, `post-merge`, `pre-push`). They were moved to
`work/handoff-runs/rB/moved-aside/lw-benchhub-git-hooks/` (not deleted), and the clone is as it was.

`run_wave.py` now runs each agent with git's `core.hooksPath` set to `<runs>/git-hooks` (through `GIT_CONFIG_COUNT`,
`GIT_CONFIG_KEY_n` and `GIT_CONFIG_VALUE_n`, appended after any the caller sets). No hook of a clone runs, and git-lfs
writes its hooks there instead of into a clone. A runner test has the stub agent ask git for the setting. (Wave D
replaced the three variables with `GIT_CONFIG_PARAMETERS`, because the DeepSeek Harness drops `GIT_CONFIG_KEY_0` from
its tools' environment, and gave the gate's own git commands a hooks directory: `MHS/changes/WAVE-D.md`.)

## What the proposals said

| proposal | cards |
|---|---|
| `skip` | 102 |
| `family-config` | 97 (87 Gymnasium, 10 MuJoCo) |
| `bridge-runtime` | 57 |
| `reference` | 26 |
| `direct-driver` | 3 |
| `untriaged` | none |

Most of the Gymnasium cards are Isaac Lab or Isaac Gym task packs. The others are environments over CoppeliaSim,
Webots, CARLA, AirSim, Habitat, Unreal and other external engines.

## Model review

Claude (claude-opus-5-5, a model, not a human) read the entry symbols and every cited line of the 100 driver proposals
and one line per proposal of the other 185 (`reviewed_by` does not apply: no driver package was written). It also checked
every proposed entry symbol against the tree the gate reads: the file at the pinned commit, with the class or function
defined on the cited line. It accepted the proposals, with these changes:

- **ros family.** Three Gymnasium environments whose reset and step talk through ROS take the `ros` family and wait for
  the ROS helper, by the rule of wave A: gym-gazebo2 (ROS 2), the deprecated gym-gazebo (ROS 1) and a PX4 drone
  environment over MAVROS.
- **skip.** Four repositories have no environment to drive:
  - a RealSense wrapper whose only output is images;
  - a Webots youBot scaffold whose step returns an empty observation;
  - RAMP-sim, whose step takes no action;
  - RMBench, whose task classes have no reset or step, the RoboTwin pattern its platform card shows as well.
- **skip:duplicate_of.** Seven copies:
  - an Isaac Lab manipulation template and an Isaac Lab fork, of `gh.isaac-sim/isaaclab`;
  - a HumanoidBench copy, of `gh.carlosferrazza/humanoid-bench`, whose package passes;
  - LIBERO-Recovery, of LIBERO;
  - the RLBench perturbation suite Colosseum, of `gh.stepjam/rlbench`;
  - two OmniIsaacGymEnvs forks, of `gh.isaac-sim/omniisaacgymenvs`.
- **A submodule.** The Duke Humanoid's controller lives in a submodule, which the gate cannot read from the
  superproject's clone. The superproject becomes `reference`/`host`. The submodule's own repository,
  `gh.generalroboticslab/dukehumanoidhardwarecontrol`, at the same commit, becomes the direct driver over
  `BipedController`; triage had skipped it as peripheral.
- **Entry symbols.** Two entry symbols named Isaac Lab's external `ManagerBasedRLEnv` at a `gym.register` line and were
  dropped; their cards keep the local configuration class.
- **Earlier decisions.**
  - Three curated `untriaged` external-engine entries are replaced by the proposals, as wave A replaced its curated
    `untriaged` entries: robo-gym becomes a Gymnasium card, LuckyRobots and RoboDK `bridge-runtime`.
  - Wave A's `untriaged` decision for the AirSim environment of `gh.bilalkabas/drl-nav` becomes a Gymnasium card,
    like the AirSim environments of this wave.

  Wave C showed that such external-engine environments pass the gate over a fake, with the engine as their sim backend.

One boundary is the proposals' own, and the review kept it:
- Isaac Gym task suites with Gym spaces and reset and step (IsaacGymEnvs, OmniIsaacGymEnvs, LeibnizGym, the DexHand
  task) are Gymnasium cards. (LeibnizGym was not: its TrifingerEnv has no Gym spaces, and wave D made it a direct
  driver, `MHS/changes/WAVE-D.md`.)
- Isaac Gym training frameworks without that interface (`legged_gym` and its many derivatives) are skips.

Review limits: no upstream code was run, and the 185 non-driver proposals were read one line each.

## Entry files the gate cannot read

`check_recon.py` read a cited file from the working tree, and the gate reads the git object store at the pinned commit,
so an entry class in a submodule passed one and would fail the other. For driver proposals, the checker now refuses an
entry file that the clone's tree at the pinned commit does not contain, such as a submodule or an untracked file. It uses
`git cat-file -e`, which runs no filter. `RECON-PROMPT.md` tells the recon model the same and asks it to name the
submodule's repository instead. A handoff test cites a file the clone never committed.

Across all 965 proposals the rule found three cases. Two are wave-A proposals whose cards are `bridge-runtime` (their
entry symbols are only a record), and the third is the Duke Humanoid's, which this review replaced.

## Result

After the rebuild, no `untriaged` card is left:

| state | cards |
|---|---|
| dispatch | 92 (26 in wave 3, 66 in wave 6) |
| recon | 3 (the three wave-4 driver cards whose entry module is not importable by name) |
| waiting for a helper | 255 |
| skip | 1,526 |
| reference | 319 |
| bridge-runtime | 269 |
| done | 499 |
| quarantined | 4 |

The 92 dispatchable cards are 81 Gymnasium, 9 MuJoCo and 2 python-object cards. 18 of them state no licence, so their
packages wait for the owner's publication decision.

Checks:

- `check_recon.py --all --force` finds 964 of 965 proposals valid. The one invalid file is the Duke Humanoid's, which
  fails the new rule.
- `validate.py --no-corpus` passes.
- One registry test pinned three shipped hardware-first recon cards (OpenWBT, FurnitureBench, the Duke Humanoid), which
  this wave decided. It now checks their decisions, and the two synthetic tests beside it carry the rule.
- The SDK suite (with the new runner and checker tests), the registry suite, the OpenAI4S integration tests and
  `tools/oss_export_check.py` pass.
