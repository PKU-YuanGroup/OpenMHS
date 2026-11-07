# Facts and tags for gh.luccachiang/gsworld

Every fact cites its source at commit `532950475cc80a97c7050fd94858a1a8841dbf2c`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or `upstream_code`
(`path/in/clone.py:LINE`). The same facts are in `facts = [Fact(text, source=..., ref=...)]` in `driver.py`; the
reference file is generated from the driver, not from this page.

Tags: `gsworld`, `mani-skill`, `sapien`, `fr3`, `fr3-umi`, `robot-arm`, `reinforcement-learning`, `simulation`,
`gymnasium`.

| fact | source | ref |
|---|---|---|
| RealFr3-v1 is registered with max_episode_steps=200000 | upstream_code | `gsworld/mani_skill/envs/tasks/real_fr3_env.py:22` |
| RealFr3 subclasses BaseEnv and is described as a dummy environment for showcasing robots in an empty scene | upstream_code | `gsworld/mani_skill/envs/tasks/real_fr3_env.py:23-27` |
| RealFr3 supports the reward modes none, dense and sparse, in that order | upstream_code | `gsworld/mani_skill/envs/tasks/real_fr3_env.py:24` |
| The RealFr3 constructor's default robot_uids is panda and it passes robot_uids to BaseEnv | upstream_code | `gsworld/mani_skill/envs/tasks/real_fr3_env.py:29-30` |
| Fr3Umi is registered as the agent uid fr3_umi | upstream_code | `gsworld/mani_skill/agents/robots/panda/fr3_umi.py:15-17` |
| Fr3Umi names seven FR3 arm joints and two FR3 finger joints | upstream_code | `gsworld/mani_skill/agents/robots/panda/fr3_umi.py:41-53` |
| The Fr3Umi arm pd_joint_delta_pos controller bounds every arm joint delta to -0.1 to 0.1 and applies it as a delta | upstream_code | `gsworld/mani_skill/agents/robots/panda/fr3_umi.py:78-86` |
| The Fr3Umi gripper position controller bounds the gripper command to -0.01 to 0.04 | upstream_code | `gsworld/mani_skill/agents/robots/panda/fr3_umi.py:114-121` |
| The Fr3Umi controller map binds pd_joint_delta_pos to the arm delta controller and the gripper position controller | upstream_code | `gsworld/mani_skill/agents/robots/panda/fr3_umi.py:123-126` |
| fr3_umi_task_init_qpos is a nine-value FR3 UMI start configuration | upstream_code | `gsworld/constants.py:63-73` |
| RealFr3._load_scene builds a ground and sets collision group bit 30 | upstream_code | `gsworld/mani_skill/envs/tasks/real_fr3_env.py:112-114` |
| RealFr3._initialize_episode does nothing (pass) | upstream_code | `gsworld/mani_skill/envs/tasks/real_fr3_env.py:116-117` |
| RealFr3.evaluate returns an empty dict and _get_obs_extra returns an empty dict, so the task adds no reward term and no extra observation | upstream_code | `gsworld/mani_skill/envs/tasks/real_fr3_env.py:119-123` |
| RealFr3 configures wrist_cam and right_cam at 640x480 with near 0.01 and far 100 | upstream_code | `gsworld/mani_skill/envs/tasks/real_fr3_env.py:47-50` |
| RealFr3 configures a 640x480 render camera with near 0.01 and far 100 | upstream_code | `gsworld/mani_skill/envs/tasks/real_fr3_env.py:65-67` |
| The GSWorld wrapper configures sim_freq=100 and control_freq=20 for its moving-robot environment | upstream_code | `gsworld/mani_skill/utils/wrappers/gs_world_wrapper.py:89` |
| The Franka motion-planning example defaults to sim_freq 100 and control_freq 20 | upstream_code | `gsworld/mani_skill/examples/motionplanning/franka/run_with_gs.py:60-61` |

## What is served and what is not

The driver is `RealFr3(GymnasiumDriver)` with `env_id = "RealFr3-v1"` and
`native = "gsworld.mani_skill.envs.tasks.real_fr3_env:RealFr3"`, one of the card's AST-confirmed entry symbols. The
deployment selects `robot_uids="fr3_umi"`, `control_mode="pd_joint_delta_pos"` and a 100 Hz simulation / 20 Hz
control configuration. The bridge derives `cap.world.step.v1` (`{ticks, action}`), `cap.world.reset.v1`
(`{seed, options}`) and `cap.world.seed.v1` (`{seed}`) from the environment object.

The real action space is assembled by the external ManiSkill package. The clone states the Fr3Umi controller's
physical bounds (arm delta -0.1 to 0.1, gripper -0.01 to 0.04) but not the normalisation or the exact action
dimension. The fake therefore publishes a placeholder `Box(-1, 1)` of eight normalised values: seven arm deltas and
one mimic-gripper command. A deployment on the `sim` backend must inspect the real environment's `action_space`
before trusting that shape.

Only the fake backend is available in this package: `fake.py` is a pure-Python kinematic stand-in (fidelity F0) with
the upstream class's `reset`, `step` and `close` surface. It starts from `fr3_umi_task_init_qpos` plus placeholder
noise, scales arm deltas by 0.1, maps the gripper command onto -0.01 to 0.04, returns the 18-value qpos/qvel
observation, and truncates at the registered 200000 steps. The upstream agent reset and keyframe selection are done
by the external ManiSkill `BaseAgent` and are not reproduced; reset options are accepted and ignored by the fake.
The real environment's state observation also includes controller state assembled by the external ManiSkill
`BaseAgent`, and its two 640x480 cameras and render camera are not modelled: the gymnasium bridge serves the scalar
world state only. There are no rigid-body dynamics, contacts, sensors or rendering, and the fake was never compared
with an upstream run. The upstream `sim` path (`gymnasium.make`, which needs ManiSkill/SAPIEN) was not run.

The task card records the upstream licence as `NOASSERTION` with `license_class` `unknown`; this package makes no
separate licence determination.

No Limits are declared by the driver. The bridge derives the step limits from the fake's action space; the
`action.values` rule is `-1 .. 1` with no source and the bridge's derived ref
`action_space of the fake backend .fake:FakeRealFr3`, not a clone line, because the action space is external to the
clone. This is recorded in RESULT.json notes. The device is simulated (R0), so no limit is `operator_required` and no
e-stop hardware exists.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:RealFr3-v1`, level F0 (kinematic stand-in, no
rigid-body dynamics), determinism `seeded` with `seed_control` `parameter`, timestep 50 ms (the configured 20 Hz
control period from `sim_freq=100` / `control_freq=20`), `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot and restore. The gaps say what is not modelled and that the package was not compared with the upstream
SAPIEN environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.
