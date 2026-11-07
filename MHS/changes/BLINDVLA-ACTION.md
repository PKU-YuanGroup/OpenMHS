# BLINDVLA-ACTION — BlindVLA's fake serves ManiSkill's normalised action, -1 to 1 per value

SQUINT-ACTION found that the fake of `gh.cognitiveaisystems/blindvla` (`Empty-v1`) serves the raw ranges of the Panda's
`pd_joint_delta_pos` controllers as its action bounds, while the ManiSkill that BlindVLA vendors normalises both
controllers (`MHS/changes/SQUINT-ACTION.md`, "Found, not fixed"). A reading of the clone at the pinned commit
`06855fcb91d65c88ca351a2d45af0be860a91987` confirms it. The fake now serves `Box(-1, 1, (8,))` and clips and scales each
value in `step`, as the controllers do. Because the clone holds the line that writes the normalised space, the driver
cites it as `action_space_ref`, and the step bound is `upstream_code`. The gate's findings, and so its digest, did not
change.

## The reading

The clone `robots/cognitiveaisystems/blindvla` was read at its HEAD, the pinned commit, with plain reads and
`git --no-optional-locks`; every ManiSkill path below is in the clone's vendored `ManiSkill/` tree.

- **The configuration.** `Empty-v1` registers `EmptyEnv` with `max_episode_steps=200000`
  (`ManiSkill/mani_skill/envs/tasks/empty_env.py:17`), and `EmptyEnv.__init__` only sets `robot_uids="panda"` (`:24-25`);
  the driver passes no kwargs. `BaseEnv` defaults `num_envs` to 1 and `control_mode` to None
  (`ManiSkill/mani_skill/envs/sapien_env.py:187`, `:190`) and hands that None to the agent (`:291`, `:406-413`), which
  takes the first of its controller configs (`ManiSkill/mani_skill/agents/base_agent.py:106-109`): Panda's
  `pd_joint_delta_pos`, a dict of an arm and a gripper config (`ManiSkill/mani_skill/agents/robots/panda/panda.py:186-189`).
  Only `panda.py:18` declares `uid = "panda"`, and only `empty_env.py:17` registers `Empty-v1`.
- **The controllers.** `arm_pd_joint_delta_pos` is a `PDJointPosControllerConfig` over the seven arm joints with
  `lower=-0.1`, `upper=0.1` and `use_delta=True` (`panda.py:90-98`), and `gripper_pd_joint_pos` a
  `PDJointPosMimicControllerConfig` over the two finger joints with `lower=-0.01` and `upper=0.04` (`:177-184`). Neither
  sets `normalize_action`, while `arm_pd_joint_pos` next to them sets it to False (`:88`). The default of
  `PDJointPosControllerConfig.normalize_action` is True (`ManiSkill/mani_skill/agents/controllers/pd_joint_pos.py:121`);
  the mimic config only changes the controller class (`:134-135`), whose limits keep one row for the two joints
  (`:126-131`).
- **Normalisation.** A controller builds the `Box` of its configured bounds (`pd_joint_pos.py:30-33`) and, when its config
  normalises, calls `_clip_and_scale_action_space` in `__init__`
  (`ManiSkill/mani_skill/agents/controllers/base_controller.py:62-67`). That keeps the configured bounds and replaces the
  space with `normalize_action_space`'s `Box(-1, 1, shape=action_space.shape, dtype=action_space.dtype)`
  (`base_controller.py:154-164`, `ManiSkill/mani_skill/utils/gym_utils.py:108-110`). Every action is then clipped to
  [-1, 1] and scaled to `0.5 * (high + low) + 0.5 * (high - low) * action` (`base_controller.py:131-132`, `:166-169`,
  `gym_utils.py:102-105`) before `set_action` uses it: the arm adds it to the current joint positions
  (`pd_joint_pos.py:76-81`), and the mimic gripper broadcasts its one value to both finger joints as their target
  (`:84-86`).
- **One space.** The agent serves a dict config with a `CombinedController` (`base_agent.py:258-266`), which builds the two
  controllers (`base_controller.py:198-201`) and flattens their normalised spaces into one float32 `Box`
  (`:281-285`, `ManiSkill/mani_skill/agents/utils.py:28-56`); with one environment the space is not batched
  (`base_controller.py:205-209`). The agent's spaces are its controller's (`base_agent.py:292-314`), the environment's are
  the agent's (`sapien_env.py:316-321`), and `gym.make` adds only the `MSTimeLimit` wrapper
  (`ManiSkill/mani_skill/utils/registration.py:242-256`), whose `step` changes only `truncated` (`:160-168`). No other line
  of the vendored ManiSkill sets `normalize_action` for this control mode: the other hits are Panda's other modes (False,
  `panda.py:88`, `:135`, `:160`), the default configs of `BaseAgent` that Panda's replace, other robots' and one task's
  configs, the controller code, and the trajectory conversion tools, which assert it for the delta controllers they
  convert (`ManiSkill/mani_skill/trajectory/utils/actions/conversion.py:27`).

So the upstream action space is `Box(-1, 1, (8,))`, float32. The package's step contract accepted only -0.1..0.1 of an
arm value's range and -0.01..0.04 of the gripper's, and refused the rest: nine tenths of the arm's and more than nine
tenths of the gripper's. A value it accepted also did something else upstream: the old fake moved an arm joint by the
value itself, ten times what ManiSkill moves it, and took the gripper value as the target, where ManiSkill sets
`0.015 + 0.025 * value`.

## The package

- **`fake.py`.** `ACTION_LOW` and `ACTION_HIGH` are -1.0 and 1.0, and the action space is `Box([-1.0] * 8, [1.0] * 8)`. The
  configs' ranges keep their names (`ARM_LOW`/`ARM_HIGH`, `GRIPPER_LOW`/`GRIPPER_HIGH`) and are now what a value is scaled
  to. A module function `clip_and_scale` does what `clip_and_scale_action` does, and `step` applies it to each value before
  the arm adds its deltas and the gripper sets its target, which the kinematic stand-in reaches at once, as before. The
  module docstring says where the space comes from; the space and the ranges carry no `# placeholder`, as before. The
  placeholder finger relation (the second finger takes the negated target) and the zero start state keep their mark.
- **`driver.py`.** `GYM_UTILS` names the vendored `gym_utils.py`, and `action_space_ref = f"{GYM_UTILS}:108-110"` follows
  `backends`. The two Facts that called the configs' ranges the action's bounds now say what their lines set (`lower`,
  `upper`, `use_delta`) and that they do not set `normalize_action`. Ten new Facts cite the steps of the reading, from the
  dict config's `CombinedController` to the environment taking the agent's spaces; all cite the package's own clone
  (`MHS/handoff/REVIEW.md` item 4), and the first six Facts are as they were. The docstring gives the step action as
  eight values in -1 .. 1 and says that the step bounds cite a line. The first fidelity gap says that the joints add the
  scaled deltas; a new gap, the fourth of eight, gives the normalised action, the scaling, and the placeholder finger
  relation next to the upstream's broadcast. The first two gaps, which the MCP step tool shows clipped to 80 characters,
  keep their place; the step tool's driver-owned part went from 1,357 to 1,323 bytes (G8's limit is 2,048).
- **`facts.md`.** The fact table follows `driver.py` row for row (32 rows). The Limits paragraph, which still gave the
  bound the source `upstream_code` and the ref `Empty-v1:action_space` from before GYM-LIMITS, now gives -1..1, the ref,
  the ManiSkill lines and the scaling; the fidelity paragraph names the new gap.
- **`test_driver.py`.** The bounds case steps with 1.0 and -1.0 for the arm and the gripper and expects 1.01 and -1.01 to
  be refused. The kinematic case steps 0.5 and 0.2 and expects arm deltas of 0.05 and the gripper target 0.02. A new case,
  `test_the_controllers_scale_the_action`, steps `[1, -1, 0.5, -0.5, 0.25, 0, 0, 1]`, expects the arm deltas 0.1, -0.1,
  0.05, -0.05, 0.025, 0, 0 and the target 0.04, and then shows that the gripper value is a target, not a delta: -1 sets
  -0.01, and 0 sets 0.015 twice. The ticks and e-stop cases step values whose scaled deltas they check (four steps of
  0.25 make 0.1; 0.5 makes 0.05).
- **References.** `python3 -m mhs.driver reference <dir>` regenerated `reference.json` and `REFERENCE.md`. Against the
  originals, the `cap.world.step.v1` `action.values` bound reads `[-1.0] * 8 .. [1.0] * 8` with source `upstream_code`
  and the ref `ManiSkill/mani_skill/utils/gym_utils.py:108-110` (before: `no source: action_space of the fake backend
  .fake:FakeEmptyEnv`); the facts, the gaps and `provenance.manifest_digest` changed with it, nothing else.
- **Result.** `RESULT.json` got one sentence at the end of its `MODEL REVIEW` paragraph that names the changed files and
  the lines (`MHS/handoff/REVIEW.md` section 5); its notes above never stated the bounds. `gate.digest` is the re-run
  gate's, `sha256:3c082d6a...`, the value it had: the stable digest covers the gate's findings, and none changed.
  `driver.lock.json` is untouched: `authored_by.kind` stays `model` and `reviewed_by` stays null.
- **Originals.** The eight changed files of the package as they were, with its unchanged `driver.lock.json` and
  `task.json`, its two registry records (`MHS/registry/repos/` and `MHS/registry/tasks/`) and `CHANGELOG.md` are in
  `work/handoff-runs/blindvla-action/originals/` (not exported), with `update_result.py`, which wrote the sentence and
  the digest, `tool_sizes.py`, which measured the MCP tools as G8 does, and the logs.

## The ref

GYM-SPACE-REF gave this package no ref because its bounds came from two places ("bounds in two config blocks
(panda.py:90-98 and :177-184)", `work/handoff-runs/gym-space-ref/decisions.json`), which held for the raw ranges. With
the normalised space the three conditions of `MHS/changes/GYM-SPACE-REF.md` ("The reading") hold:

- neither the space nor a constant it uses is marked `# placeholder`;
- the fake's space has the upstream's bounds and width for the configuration served: -1..1 for eight values;
- one span of the cited file writes the numbers, and G4 finds them there: `normalize_action_space`
  (`ManiSkill/mani_skill/utils/gym_utils.py:108-110`) writes `spaces.Box(-1, 1, ...)` for both controllers.

Unlike squint, whose ManiSkill is another repository (`MHS/changes/SQUINT-ACTION.md`, "Why no ref"), BlindVLA vendors
ManiSkill, so the line is in the package's own clone: G4 reads it (no `REF_MISSING`), and the Facts that cite ManiSkill
are facts of this repository. The span is the function the ManiSkill package cites
(`mani_skill/utils/gym_utils.py:110-112` in `robots/mani-skill/maniskill`), two lines higher in this vendored copy. The width 8 is not on the line
(`shape=action_space.shape`); the Facts and the new gap say where it comes from.

## Result

- `python3 -m mhs.driver check <dir> --backend fake` passes: G1 to G5, G7 and G9 (the ten repository tests, the new case
  among them) pass, G4 has no finding for the ref or the new Facts, and the warnings are the ones `RESULT.json` names
  (G6.NO_NATIVE_CALL, G8.NO_UNIT x4). The digest is `sha256:3c082d6a...`, which a baseline run before the edits also
  gave. No `__pycache__` was left in the package.
- `MHS/handoff/tools/show_refs.py <dir>` prints the ref and the 32 Facts next to the cited lines: 0 bad citations.
- `collect.py <dir> --strict` passes with no warning; its one note lists the gate's warnings.
- `validate.py --no-corpus` passes.
- `build_registry.py --check` finds no generated file that differs (06:15-06:33, with no edit of `MHS/drivers/**` or
  `MHS/registry/overrides/**` during it), so the registry needs no rebuild: the package's record copies `gate.digest`, the
  status and the file names, and none of them changed.
- `tools/build_changelog.py` indexes this record.
- Follow-up verification on 2026-11-02: `tools/oss_export_check.py` passes on the combined state containing this
  change and the other completed changes. In a fresh export of the 13,259 tracked files, the handoff baseline run
  checks the generators, the SDK, registry and spec suites, the site build and its freshness, the thermostat gate,
  the gates of the four exemplars and the OpenAI4S integration tests. This is the subsequent baseline result, not a
  check run during the original focused session.
- A session that rewrote the stale step-bound sentences of 117 other `facts.md` pages at the same time
  (`work/handoff-runs/gym-facts-source/`) found this package's page already rewritten here and left it alone. The clone has
  no `index.lock`, and its status is clean.

## Found, not fixed

- **The finger relation.** The fake gives the second finger joint the negated gripper target (`# placeholder`), while the
  mimic controller broadcasts its one value to both finger joints as their drive target (`pd_joint_pos.py:84-86`), so
  upstream both finger joints are driven to the same value. The new gap says so. A faithful stand-in would also need the
  finger joints' limits, since the configured lower bound -0.01 is "a trick to have force when the object is thin"
  (`panda.py:179`), and those limits are in the Panda URDF (`panda.py:19`), an asset the clone does not hold.
