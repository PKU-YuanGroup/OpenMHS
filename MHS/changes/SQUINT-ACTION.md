# SQUINT-ACTION — squint's fake serves ManiSkill's normalised action, -1 to 1 per joint

GYM-SPACE-REF-2 found that the fake of `gh.aalmuzairee/squint` (`SO101LiftCube-v1`) serves its controller's per-step joint
deltas as the action bounds, while ManiSkill normalises that controller's action to -1..1 (`MHS/changes/GYM-SPACE-REF-2.md`,
"Found, not fixed"). A reading of the clone at the pinned commit `7086fd516eda7df585a5261c541e0670a6d916b4` and of the
ManiSkill clone confirms it. The fake now serves `Box(-1, 1, (6,))` and scales each value to its joint delta in `step`, as
the controller does. The bound keeps no source, because the lines that write it are ManiSkill's. The gate's findings, and
so its digest, did not change.

## The reading

- **The configuration.** `SO101LiftCube-v1` registers `LiftCube` with `max_episode_steps=50` (`envs/lift.py:407-410`), and
  `Lift.__init__` defaults to `robot_uids="so101"` and `control_mode="pd_joint_target_delta_pos"` (`envs/lift.py:59-61`);
  the driver passes no kwargs. At the pinned commit `git grep` finds `normalize_action` only in the `pd_joint_pos` config
  (False, `envs/robot/so101.py:93`) and the `pd_joint_vel` config (True, `:119`), and `action_space` only in the trainer and
  an example script, which read it. No class of the clone replaces the space.
- **The controller.** `pd_joint_delta_pos` is a `PDJointPosControllerConfig` over the robot's active joints with lower
  `[-0.1] * 5 + [-0.2]`, upper `[0.1] * 5 + [0.2]` and `use_delta=True` (`envs/robot/so101.py:97-106`), and
  `pd_joint_target_delta_pos` is a deep copy with `use_target = True` (`:108-109`). Neither sets `normalize_action`. The six
  bounds are those of the six active joints, five arm joints and the gripper (`:73-82`; the URDF has six movable joints).
- **ManiSkill.** squint installs `mani_skill_nightly` without a version (`environment.yaml:15`), so ManiSkill was read in the
  clone `robots/mani-skill/maniskill` at `62ff3a5896b4d5b4cf0ac4c8d79afe600c9404a3` (2026-08-01; squint's pinned commit is
  of 2026-09-04; the clone is shallow, so how long these lines have stood was not read):
  - `PDJointPosControllerConfig.normalize_action` defaults to True (`mani_skill/agents/controllers/pd_joint_pos.py:131`),
    and the controller's own space is `Box(low, high)` of the configured bounds (`:44-47`);
  - when the config normalises, `BaseController.__init__` replaces that space
    (`mani_skill/agents/controllers/base_controller.py:70-72`) with `normalize_action_space`'s
    `Box(-1, 1, shape=action_space.shape, dtype=action_space.dtype)` (`mani_skill/utils/gym_utils.py:110-112`), and keeps the
    configured bounds for the scaling (`base_controller.py:158-168`);
  - every action is clipped to [-1, 1] and scaled to `0.5 * (high + low) + 0.5 * (high - low) * action`
    (`base_controller.py:135-136`, `gym_utils.py:104-107`) before `set_action` adds it to the previous target
    (`pd_joint_pos.py:81-87`);
  - the agent builds the controller of a single config, not a dict, directly, with no combined controller
    (`mani_skill/agents/base_agent.py:261-276`); the agent and the environment take its space as it is (`:298-320`,
    `mani_skill/envs/sapien_env.py:332-337`), and `gym.make` adds only the `MSTimeLimit` wrapper
    (`mani_skill/utils/registration.py:242-257`), which keeps it.
- **The clone agrees.** The deploy script clips the policy's scaled action to [-1, 1] before it steps the robot
  (`deploy.py:524-527`).

So the upstream action space is `Box(-1, 1, (6,))`. The package's step contract accepted only -0.1..0.1 of it for an arm
joint and -0.2..0.2 for the gripper, and refused the rest: nine tenths of an arm joint's range and four fifths of the
gripper's.

## The package

- **`fake.py`.** `ACTION_LOW` and `ACTION_HIGH` are `[-1.0] * 6` and `[1.0] * 6`; the controller's bounds moved to
  `DELTA_LOW` and `DELTA_HIGH`. `step` clips each value to -1..1, scales it to its joint delta as `clip_and_scale_action`
  does, and adds the deltas to the joint targets, which the kinematic stand-in reaches at once, as before; the placeholder
  grasp reads the scaled gripper delta, whose sign is the action's. The two bounds, the two delta lists and the width
  `JOINTS = 6` are no longer marked `# placeholder`: their comment cites the squint lines and names the ManiSkill lines,
  and the module docstring says that the action space is the upstream's. The other numbers keep their mark.
- **`driver.py`.** The docstring gives the step bounds as -1..1 and says why they have no source. The `Fact` on
  `envs/robot/so101.py:97-109` also says `use_delta=True` and that the config does not set `normalize_action`, which the
  cited lines show; no `Fact` cites ManiSkill, another repository (`MHS/handoff/REVIEW.md` item 4). The first fidelity gap
  says that the joints add the scaled deltas, and a new gap, the sixth of seven, says where -1..1 comes from and that
  ManiSkill is not pinned. The first two gaps, which the MCP tool descriptions show, keep their place.
- **`facts.md`.** The controller row adds `normalize_action`. The Limits paragraph, which still gave the bound the source
  `SO101LiftCube-v1:action_space` from before GYM-LIMITS, now gives -1..1, its `no source` ref and the ManiSkill lines; the
  fidelity paragraph names the new gap.
- **`test_driver.py`.** The bounds case steps with 1.0 and -1.0 and expects 1.01 and -1.01 to be refused. A new case,
  `test_the_controller_scales_the_action_to_the_joint_deltas`, checks that `[1.0, -0.5, 0, 0, 0, 1.0]` moves the joints by
  0.1, -0.05, 0, 0, 0 and 0.2. The docstring excepts the action space from the placeholder numbers.
- **References.** `python3 -m mhs.driver reference <dir>` regenerated `reference.json` and `REFERENCE.md`. Against the
  originals, the `cap.world.step.v1` `action.values` bound reads `[-1.0] * 6 .. [1.0] * 6`, still `no source: action_space of
  the fake backend .fake:FakeSO101LiftCube`; the Fact, the gaps and `provenance.manifest_digest` changed with it, nothing
  else.
- **Result.** `RESULT.json` got one sentence at the end of its `MODEL REVIEW` paragraph that names the changed files and the
  ManiSkill lines (`MHS/handoff/REVIEW.md` section 5). `gate.digest` is the re-run gate's, `sha256:45798dd7...`, the value it
  had: the stable digest covers the gate's findings, and none changed. `driver.lock.json` is untouched: `authored_by.kind`
  stays `model` and `reviewed_by` stays null.
- **Originals.** The eight changed files of the package as they were, `CHANGELOG.md` and the package's registry record are in
  `work/handoff-runs/squint-action/originals/` (not exported), with `update_result.py`, which wrote the sentence and the
  digest, and the logs.

## Why no ref

GYM-SPACE-REF gives a package a ref only when the space is not a placeholder, has the upstream's bounds and width for the
configuration served, and one span of the cited file writes the numbers where G4 finds them (`MHS/changes/GYM-SPACE-REF.md`,
"The reading"). The first two conditions now hold; the third does not:

- the lines that write -1 and 1 for this space are ManiSkill's (`mani_skill/utils/gym_utils.py:110-112`), and G4 reads a ref
  in the package's own clone, which has no such file (`REF_MISSING`);
- the squint lines that define the controller, `envs/robot/so101.py:97-109`, write the deltas: G4's reading of them shows
  neither -1.0 nor 1.0, so a ref there would warn `REF_VALUE`;
- `deploy.py:524`, `np.clip(action * args.action_scale, -1, 1)`, shows both, and G4 would accept it, but it clips a
  policy's output before the robot's step; it does not build the environment's space. A ref there would be a real line that
  does not state the bound (`MHS/handoff/REVIEW.md` item 2).

This is the case of GYM-SPACE-REF's five packages whose bounds come from two places: the width and the deltas come from the
clone, the normalisation from ManiSkill. The bound stays without a source, and the new gap and `facts.md` name the ManiSkill
lines for a reviewer.

## Result

- `python3 -m mhs.driver check <dir> --backend fake` passes: G1 to G5 and G9 (the repository tests, the new case among
  them) pass, and the warnings are the ones `RESULT.json` names (G6.NO_NATIVE_CALL, G7.MAYBE_ABSENT x5, G8.NO_UNIT x4). The
  digest is `sha256:45798dd7...`, which a baseline run before the edits also gave. No `__pycache__` was left in the package.
- `collect.py <dir> --strict` passes with no warning; its one note lists the gate's warnings.
- `validate.py --no-corpus` passes.
- `build_registry.py --check` finds no generated file that differs, so the registry needs no rebuild: its records copy
  `gate.digest`, which did not change. A first check (04:04-04:15) stopped because `MHS/drivers/**` changed during the
  build, when another session was editing the gym-duckietown package (04:04-04:05); the re-run after those edits
  (04:16-04:27) passed.
- `tools/build_changelog.py` indexes this record.
- Follow-up verification on 2026-11-02: `tools/oss_export_check.py` passes on the combined state containing this
  change and the other completed changes. In a fresh export of the 13,259 tracked files, the handoff baseline run
  checks the generators, the SDK, registry and spec suites, the site build and its freshness, the thermostat gate,
  the gates of the four exemplars and the OpenAI4S integration tests. This is the subsequent baseline result, not a
  check run during the original focused session.

## Found, not fixed

- **BlindVLA's fake looks like the same mistake.** `gh.cognitiveaisystems/blindvla` serves `Empty-v1` with the Panda's
  `pd_joint_delta_pos`, which its fake takes to be the default control mode, and the fake's space is the raw bounds of the
  two controllers: -0.1..0.1 for seven arm joints and -0.01..0.04 for the gripper (`fake.py:34-35`, `:68`). BlindVLA vendors
  ManiSkill, and at its pinned commit `06855fcb91d65c88ca351a2d45af0be860a91987` neither config sets `normalize_action`
  (`ManiSkill/mani_skill/agents/robots/panda/panda.py:90-98`, `:177-184`), whose default is True
  (`ManiSkill/mani_skill/agents/controllers/pd_joint_pos.py:121`); the mimic gripper config inherits it (`:134`), and the
  combined controller flattens the spaces of the controllers it builds, each normalised by its own `__init__`
  (`ManiSkill/mani_skill/agents/controllers/base_controller.py:65-67`, `:198-202`, `:281-285`). So its upstream space
  is most likely `Box(-1, 1, (8,))`. Unlike squint, that package's own clone holds the normalised `Box` line
  (`ManiSkill/mani_skill/utils/gym_utils.py:108-110`), so a fix could cite it. GYM-SPACE-REF filed the package under bounds
  from two places.
