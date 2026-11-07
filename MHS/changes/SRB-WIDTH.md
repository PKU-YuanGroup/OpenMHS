# SRB-WIDTH — the Space Robotics Bench fake takes the seven action values of the default Franka and observes its hand

GYM-SPACE-REF found that the fake of `gh.andrejorsula/space_robotics_bench` serves a six-value action while the upstream adds
the Franka hand's gripper command to the arm's pose command (`MHS/changes/GYM-SPACE-REF.md`, "Found, not fixed"). A reading
of the clone at the pinned commit `7528ff81f1ac0b34ba259b1ae150fdb4f6a90b5e` confirms it: in the configuration the package
serves, `total_action_dim` is 7. The fake now has seven values, and because its space is then the upstream's, `driver.py`
sets `action_space_ref`, so the derived step bounds are `upstream_code`. Two more steps, which the user asked for, add the
hand's two finger joints to the fake's observation, which the gripper value opens and closes, and serve each observation
group as one vector, as the upstream flattens them. The gate's findings, and so its digest, did not change.

## The reading

- The package serves `srb/_manipulation` with its default `TaskCfg` (`srb/tasks/manipulation/_manipulation/__init__.py:6-17`),
  which overrides no robot (`task.py:32-45`), so the robot is `ManipulationEnvCfg`'s `assets.Franka()`
  (`srb/core/env/manipulation/env.py:68`).
- `_add_robot` starts an empty `ActionGroup` (`srb/core/env/common/base/env_cfg.py:557`), adds the robot's action terms
  (`:564-576`) and, for a manipulator whose end effector is an `ActiveTool`, the tool's terms after them (`:761-778`); the
  groups' command mappings are concatenated in the same order (`:800-802`).
- The Franka's group is a differential IK relative pose command (`srb/assets/robot/manipulation/franka.py:91-106`). Its end
  effector is `FrankaHand()` (`:89`), an `ActiveTool` (`srb/assets/object/tool/franka_hand.py:17`) whose group holds one
  `BinaryJointPositionActionCfg` for the finger joints (`:53-61`). GYM-SPACE-REF cited `franka_hand.py:37-39`, which at this
  commit is the end of the spawn configuration.
- The action space is `Box(low=-1.0, high=1.0, shape=(self.action_manager.total_action_dim,))`
  (`srb/core/env/common/base/direct/impl.py:353-357`). The sum is Isaac Lab's, outside the clone: the `action_dim` of each
  term, 6 for a relative pose IK command and 1 for a binary joint action. The local Isaac Lab clone writes them at
  `source/isaaclab/isaaclab/managers/action_manager.py:217-218`, `controllers/differential_ik.py:98-105` and
  `envs/mdp/actions/binary_joint_actions.py:107-108` (`robots/isaac-sim/isaaclab` at `dd2f470f`; the Space Robotics Bench
  `Dockerfile:228` pins Isaac Lab `7455d3df`, which that shallow clone does not hold).
- The clone agrees on its own: the IK group maps a command to the whole six-value twist
  (`srb/core/action/group/manipulation/task_space.py:17-22`; the CLI probes it with `torch.zeros(6)`, `srb/__main__.py:461`),
  the binary group to one value (`srb/core/action/group/common/joint.py:51-52`), and direct teleoperation steps the
  environment with their concatenation (`srb/__main__.py:539-554`). The docs say each active tool's action group is part of
  the action space of the whole system (`docs/src/config/robot.md:77`).

So the default width is 6 + 1 = 7. Another robot, end effector or action group (`env.robot=...`, `env.robot.actions=...`,
`docs/src/config/robot.md:80`) changes it at run time; the package serves the default.

## The package

- **`fake.py`.** `ACTION_DIM = POSE_ACTION_DIM + GRIPPER_ACTION_DIM`, 6 + 1, cites the lines above and is no longer marked
  `# placeholder`. The six pose values move the first six joints as before; the gripper value moves the hand (next section).
  It enters the action-rate penalty, which the upstream takes as the mean over the whole action
  (`srb/tasks/manipulation/_manipulation/task.py:192-196`).
- **`driver.py`.** `action_space_ref = f"{DIRECT}:353-357"` after `backends`, and the fidelity gap that named six elements now
  names the seven and what the fake still does differently (no inverse kinematics, no hand actuator). No `Fact` stated a
  width, so the facts are unchanged.
- **`facts.md`.** The Limits paragraph names the seven values, where they come from and the ref; the fidelity paragraph no
  longer speaks of a reduced action width.
- **`test_driver.py`.** The actions have seven values, the short action that must be refused has six, and the truncation case
  lost a remark that called the width a placeholder.
- **References.** `python3 -m mhs.driver reference <dir>` regenerated `reference.json` and `REFERENCE.md`: `action.values`
  has `length` 7, and its bound `[-1.0] * 7 .. [1.0] * 7` is `upstream_code: srb/core/env/common/base/direct/impl.py:353-357`
  where it read `no source: action_space of the fake backend`; the gap and `provenance.manifest_digest` changed with it,
  nothing else.
- **Result.** `RESULT.json` got one sentence at the end of its `MODEL REVIEW` paragraph that names the changed files and says
  that the six-element width its notes name was one short (`MHS/handoff/REVIEW.md` section 5). `gate.digest` is the re-run
  gate's, `sha256:30934c05...`, the value it had: the stable digest covers the gate's findings, and none changed.
  `driver.lock.json` is untouched: `authored_by.kind` stays `model` and `reviewed_by` stays null.
- **Originals.** The changed files as they were, `CHANGELOG.md` included, are in `work/handoff-runs/srb-width/originals/`
  (not exported), as they were after this first step in `after-width/` and after the second in `after-hand/` beside it,
  with `update_result.py`, `update_result2.py` and `update_result3.py`, which wrote the three sentences, and the logs.

## The hand's joints

After the first step had passed its checks, the user asked for the hand's joints in the fake's observation as well.

- **Upstream.** `proprio_dyn` carries `joint_pos_end_effector_normalized`, the end effector's joint positions scaled to
  -1..1 between their soft limits (`srb/tasks/manipulation/_manipulation/task.py:79-89`, `:156-170`, `:249-252`). The
  gripper command sets the finger joints' targets to the close command 0.0 or the open command 0.04
  (`srb/assets/object/tool/franka_hand.py:54-61`); Isaac Lab's `BinaryJointAction`, outside the clone, takes a negative value
  as close and any other as open (`source/isaaclab/isaaclab/envs/mdp/actions/binary_joint_actions.py:134-140` of the local
  Isaac Lab clone). The fingers start open (`franka_hand.py:40`), and the default reset writes the default joints of every
  articulation back (`srb/core/env/common/base/event_cfg.py:30-34`, `srb/core/mdp/events.py:60-82`).
- **What no text line says.** The finger joints and their limits are defined in `franka_hand.usdz`, a binary USD of the
  `assets/srb_assets` submodule (at the commit the pinned commit records, `6b544013`). It holds a left and a right finger, so
  the fake has two joints, but no line counts them or states their limits: the count is marked `# placeholder`, and so is the
  normalization, which takes the close and the open command as the limits (an open hand reads 1.0, a closed one -1.0).
- **`fake.py`.** `HAND_JOINT_COUNT = 2` and `HAND_CLOSED, HAND_OPEN = 0.0, 0.04`; the observation space and the observation
  gain `proprio_dyn.joint_pos_end_effector_normalized`. A negative gripper value closes the hand at once, any other value opens
  it, and a reset opens it. The arm and its trajectory are unchanged.
- **`driver.py`, `facts.md`.** The observation gap names the hand vector, and the action gap says that the gripper value sets
  the hand joints to its command without the hand's actuator; the fidelity paragraph of `facts.md` follows.
- **`test_driver.py`.** The reward case also checks the length of the hand vector, and a new case checks that the hand starts
  open, closes on a negative value without moving the arm, opens on zero and opens again at a reset.
- **References and result.** `reference.json` and `REFERENCE.md` were regenerated (the two gaps and the manifest digest
  changed), and `RESULT.json` got a second sentence in its `MODEL REVIEW` paragraph.

## One vector per group

After the second step, the user asked for the observation in the upstream's layout as well.

- **Upstream.** `Task` returns its observation as groups of named members
  (`srb/tasks/manipulation/_manipulation/task.py:235-253`) and overrides `extract_step_return` (`task.py:62`), so
  `DirectEnv._get_observations` flattens them (`srb/core/env/common/base/direct/impl.py:433-435`, `:454-458`):
  `_flatten_observations` concatenates each group's members, sorted by name, into one vector (`:543-556`). The observation
  space is built from one such observation, a `Box` per group as long as its vector and bounded by its dtype's range
  (`:362-423`). So `proprio` is the 3D position before the 6D rotation, and `proprio_dyn` the hand's joints before the
  arm's, although `task.py:249-252` lists the arm first.
- **`fake.py`.** A `_flatten` helper does what `_flatten_observations` does, and `_observation` passes it the members under
  the upstream names, in the upstream order. The observation space is built from the first observation, so the bridge
  serves `proprio.values` and `proprio_dyn.values`, nine values each. The Boxes stay unbounded, marked `# placeholder`; the
  bridge derives its limits from the action space only. `POSITION_SIZE` and `ROTATION_6D_SIZE`, which only sized the
  member Boxes, are gone, and the comments on `JOINT_COUNT` and the end-effector constants keep what they said.
- **`driver.py`, `facts.md`.** The observation gap says that each group is one vector in sorted name order and what each
  holds; the fidelity paragraph of `facts.md` follows. No `Fact` stated the layout, so the facts are unchanged.
- **`test_driver.py`.** The reward case checks that the observation has the two groups, of 3 + 6 and 2 + 7 values, and the
  gripper case reads the hand from the first two values of `proprio_dyn` and the arm from the other seven.
- **References and result.** `reference.json` was regenerated (the observation gap and the manifest digest changed; in
  `REFERENCE.md` only the manifest digest), and `RESULT.json` got a third sentence in its `MODEL REVIEW` paragraph.

## Why the ref

The three conditions of GYM-SPACE-REF now hold: neither the space nor a constant it uses is a placeholder, the fake's bounds
and width are the upstream's for the configuration the package serves, and the cited statement writes -1.0 and 1.0, which G4
finds (G4 has no finding). The width comes from a name there, as in 16 of the 71 refs of GYM-SPACE-REF
(`shape=(n_actions,)` in gymnasium-robotics, `shape=(self.num_actions,)` in dexrobot_isaac); a reviewer reads it against the
lines above.

## Result

- `python3 -m mhs.driver check <dir> --backend fake` passes after each step, with that step's cases among the repository
  tests; G4 has no finding, the warnings are the ones `RESULT.json` names (G6.NO_NATIVE_CALL, G7.MAYBE_ABSENT x2,
  G8.NO_UNIT x4), and the digest stayed `sha256:30934c05...`. A first run also warned G1.BYTECODE, for a `__pycache__` that
  a check of the fake from the shell had left in the package; it was moved to `work/handoff-runs/srb-width/moved-aside/`
  and the gate re-run.
- `collect.py <dir> --strict` passes after each step, with no note beyond the gate's warnings.
- `validate.py --no-corpus` passes after each step.
- `build_registry.py --check` finds no generated file that differs, so the registry needs no rebuild: its records copy
  `gate.digest`, which did not change. A first check stopped because `MHS/drivers/**` changed during the build, when
  another session was editing six other Gymnasium packages (01:45-01:49); the re-run after those edits passed. The second
  step waited until that session's checks were done (02:22) before it edited the package, and its check, run after the
  edits, finds no file that differs either. The third step's first check (04:02-04:13) stopped the same way, while two
  other sessions edited the squint and gym-duckietown packages (04:01-04:05); the re-run after those edits (04:14-04:25),
  with their changes in the tree, finds no file that differs.
- `tools/build_changelog.py` indexes this record.
- `tools/oss_export_check.py`, run after the second step's checks with the changes of `GYM-SPACE-REF-2.md` in the tree,
  passes. In a fresh export of the 13,255 tracked files it runs the generators' `--check` modes, the SDK, registry and spec
  suites, the site build and its freshness check, the thermostat gate, the gates of the four exemplars and the OpenAI4S
  integration tests. After the third step only its static checks were re-run (`--skip-suites`, OK); the suites inside the
  export were not, as that step changed no SDK, registry, spec or site code.
