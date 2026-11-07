# WAVE-D — the 92 driver cards recon wave B opened, and git kept out of the clones twice more

The 92 dispatchable cards after recon wave B (`MHS/changes/RECON-B.md`) ran unattended like the earlier waves:
`run_wave.py --jobs 10` with the DeepSeek Harness in headless mode (`deepseek-v4.1-flash:1017`, one fresh session per
card, batch `wD`). They are 81 Gymnasium, 9 MuJoCo and 2 python-object cards, 26 of wave 3 and 66 of wave 6, most of them
Isaac Lab and Isaac Gym task packs and environments over CoppeliaSim, Webots, AirSim, CARLA, Unreal and other external
engines. 18 cards need the owner's publication decision: 15 state no licence, and the others are an AGPL-3.0, a
non-commercial and an MIT repository whose licence scan asks for a review.

The run started twice. The first start stopped after 21 cards because git did not work for the agents (below). The
second ran all 92 cards in 56 minutes, a median of 337 seconds per card (90th percentile 464 s, longest 667 s), and none
timed out. The harness counted 824 million tokens, 98 % of them cache reads (16 million input and 5 million output
tokens were not cached); the stopped start had used 112 million. Every one of the 92 packages passed the gate at the
first run, and every one passed again outside the agents' environment.

## The first start: a git setting without its key

The runner passes git's `core.hooksPath` to each agent (recon wave B). It used `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_0`
and `GIT_CONFIG_VALUE_0`. The DeepSeek Harness drops from the environment of its tools every name that matches
`KEY`, `PASSWORD`, `SECRET` or `TOKEN` in any case, and every `DSH_*` name. The key went missing and the count arrived,
so every git command of the agents failed (`missing config key GIT_CONFIG_KEY_0`).

The gate then read the clones' working trees instead of the pinned commits (`G1.CLONE_NOTE`, `G2.NOT_GIT`,
`G4.WORKTREE`), and the agents' gate digests differed from a gate run outside. Ten of the first eleven `RESULT.json`
notes described the failure, some of them wrongly ("the clone has no git metadata"). One agent set
`GIT_CONFIG_COUNT=0` to work around it, which also switched the hooks setting off.

- **Stopped.** The run was stopped after 21 cards: 11 had finished and 10 were interrupted. Their logs and packages are
  kept in `work/handoff-runs/wD-attempt1/`, with the packages under `moved-aside/`; nothing was deleted.
- **Exemplar report.** One agent's gate run had rewritten the Gymnasium exemplar's `check-report.json`. A gate run
  outside wrote it again, and its digest was unchanged.
- **Runner fix.** `run_wave.py` now passes the setting in `GIT_CONFIG_PARAMETERS`, the variable `git -c` passes to
  git's children.
- **Checks.** A runner test removes the credential-shaped names from the stub agent's environment, as dsh does, and asks
  git for the setting. A one-command real dsh run showed the variable, a working `git rev-parse` in a clone and the
  hooks path.
- **Docs.** `MHS/handoff/HARNESS.md` names the dsh rule.

The wave then ran again from its first card.

## Git-lfs hooks from the gate itself

After the second run the runner listed four new hooks in the `.git/hooks` of `gh.lightwheelai/lw-benchhub`
(`post-checkout`, `post-commit`, `post-merge`, `pre-push`), written in the second its agent ended. The agent's own git
commands had sent git-lfs's hooks to the run's hooks directory, as designed.

The hooks in the clone came from the gate run that the runner makes itself after every card (`collect.py`):
- the gate's `UpstreamTree.modified()` runs `git status --porcelain` before and after the gate;
- the clone's own `.git/config` sets an LFS filter, so that status ran git-lfs;
- git-lfs installs its hooks when they are missing;
- the runner's own environment has no hooks setting.

- **Restored.** The hooks were moved to `work/handoff-runs/wD/moved-aside/lw-benchhub-git-hooks/`, and the clone is as
  it was.
- **Gate fix** (`mhs.driver.upstream`). Every git command of the gate runs with `core.hooksPath` set to an empty
  temporary directory of its process, passed in `GIT_CONFIG_PARAMETERS` after the caller's entries. A filter of a clone
  can therefore install no hook into it. Nothing else changes in what git reports, and the 576 passing packages kept
  their gate digests.
- **Test** (`tests/driver/test_upstream.py`). It builds a clone whose clean filter writes into git's hooks directory,
  makes the filtered file stat-dirty and checks that `modified()` leaves `.git/hooks` empty. Without the fix the filter
  writes there.

111 clones configure an LFS filter in `.git/config`. 60 of them hold git-lfs hooks dated 2026-10-20, before this work
began, and were left as they are. No clone's `.git` settings changed while the review ran.

## Model review

Claude (claude-opus-5-5, a model, not a human) worked through `MHS/handoff/REVIEW.md` for every package. `reviewed_by`
stays null, and the record is the last paragraph of each `RESULT.json`.

The reviewer:
- re-ran the gate;
- read the two hardware packages line by line against their clones, `native.py` included;
- read every stop and safe-state path, and the risk against the hazard table of `MHS/spec/04-safety.md`;
- scanned all package code for reflection, dynamic imports, subprocesses, file writes, network use, home-directory
  paths and CJK text;
- read every deviation from a card.

A token comparison of all 1,789 facts with their cited lines at the pinned commit flagged 194, mostly paraphrase and
derived numbers. The reviewer read the 58 whose numbers are not on the cited lines and a sample of the others, and
found no fact that the cited code does not support.

Decisions:

- **Accepted after reviewer edits (2).** Both are R2 hardware drivers.
  - **The Unitree Go2 of `gh.machines-in-motion/go2py`.**
    - `cap.motion.stop.v1` sent only the low-level damping command, which does not end a body-velocity command that
      the sport controller is executing. It now sends zero body velocity and then the damping command, as the e-stop
      does.
    - The safe state claimed a sport-mode Damp request, which the Python interface cannot send. It now says what is
      sent.
    - The joint command now says that its target is sent at once, without the 0.5 s ramp of the upstream FSM.
  - **The Duke Humanoid V1 of `gh.generalroboticslab/dukehumanoidhardwarecontrol`.**
    - The e-stop, the safe-state action and the teardown called `BipedController.shutdown()`, which never returns:
      its sensor stop joins a `multiprocessing` child that never sees the stop flag.
    - They now make the motor part of the upstream's own termination: every torque limit is set to 0, which the motor
      loop writes to the drives every cycle, then the loop's terminate flag is set, then the command values are set
      to 0.
    - The fake's `shutdown`, which cleared values the upstream's does not, is gone.

  Each `RESULT.json` names what stays for the human reviewer:
  - the Go2's damping command reaches `/lowcmd` while the sport controller still balances;
  - the biped falls without joint torque unless it is supported;
  - a termination inside the biped's `step()` waits in the same `shutdown()`;
  - the biped takes commands and a reset flag from any sender on UDP port 9871.

  The authors' files are kept in `work/handoff-runs/wD/reviewer-originals/` (not exported).
- **Accepted as written (90).** Three of them are direct Drivers of Gymnasium-family cards, and three override entries
  now record that shape (prefix "Model review of wave D:"):
  - Constraints-as-Terminations: its `step` returns the constraint probability in the terminated slot;
  - LeibnizGym: TrifingerEnv derives from the clone's own `IsaacEnvBase` and has no Gym spaces, so recon wave B's
    boundary note that lists LeibnizGym among the suites with Gym spaces was wrong for it;
  - ManipArena: its environment name is registered at composition time.
- **Blocked:** none.

Judgement calls accepted as written:
- the two Go2 environments named after ROS 2 build their Isaac Lab task with `gym.make`, and ROS 2 only publishes their
  sensors;
- VisFly's driver adapts a stable-baselines3 `VecEnv` to the Gymnasium contract and raises on a result it does not
  know;
- two simulated packages declare R1, above their R0 floor.

## Found, not fixed

- **Gymnasium action limits from a fake.** `GymnasiumBridge.action_limits` labels the bounds of the action space it reads
  `source: upstream_code`, `ref: <env>:action_space`, whichever backend that space comes from. A reference file
  generated on a package's fake therefore publishes the fake's bounds. In many packages those bounds are placeholder
  test data: wave D's Go2 task of `gh.sallu-786/go2_isaac_ros2` publishes -1..1 over three values for a 12-joint task.
  About 200 packages of all waves publish limits derived from an action space. The fix is SDK work: a derived limit
  must say where its space came from. Fixed since: `MHS/changes/GYM-LIMITS.md`.
- **G6 and a stop through a held object.** Gate G6 counts calls on and assignments to the native object itself, not
  calls on an object it holds. The Duke Humanoid's motor stop goes through `self.native.motor`. `driver-authoring.md`
  now says so, and `REVIEW.md` item 5 names the join without a timeout.

## Result

The registry was rebuilt twice, before and after the review, and `prepare.py --sync` ran each time. It now counts:

| state | cards |
|---|---|
| dispatchable | 0 (every card that reached that state ran) |
| done | 591 (576 pass, 11 blocked, 4 skip-proposed) |
| recon | 3 (the three wave-4 driver cards whose entry module is not importable by name) |
| waiting for a helper | 255 |
| skip | 1,526 |
| reference | 319 |
| bridge-runtime | 269 |
| quarantined | 4 |

Checks:

- All 576 passing packages pass the gate and `collect.py --strict`, except `gh.amsikking/thorlabs_mcm3000`, which
  still waits for a human to accept its PDF citation (`MHS/changes/WAVE-B2.md`).
- `validate.py --no-corpus` passes, and the pilot check counts 20 of 20 finished.
- The SDK suite (2,098 tests, with the new gate and runner tests), the registry suite (276) and the OpenAI4S
  integration tests (129) pass.
- `tools/oss_export_check.py` passes.
