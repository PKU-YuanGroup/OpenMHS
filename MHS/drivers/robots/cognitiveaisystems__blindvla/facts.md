OpenMHS is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Facts and tags for gh.cognitiveaisystems/blindvla

Every fact cites its source at commit `06855fcb91d65c88ca351a2d45af0be860a91987` (`upstream_code`, the clone's text).
The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not
from this page.

| fact | source | ref |
|---|---|---|
| Empty-v1 is registered with max_episode_steps=200000 | upstream_code | ManiSkill/mani_skill/envs/tasks/empty_env.py:17 |
| EmptyEnv loads the Panda robot by default (robot_uids='panda') | upstream_code | ManiSkill/mani_skill/envs/tasks/empty_env.py:24 |
| EmptyEnv supports only the reward mode 'none' | upstream_code | ManiSkill/mani_skill/envs/tasks/empty_env.py:19 |
| With reward mode 'none' the environment returns a zero reward tensor | upstream_code | ManiSkill/mani_skill/envs/sapien_env.py:611-612 |
| EmptyEnv.evaluate returns an empty dictionary, so info carries no success or fail key | upstream_code | ManiSkill/mani_skill/envs/tasks/empty_env.py:47-48 |
| With no success or fail in info, step returns terminated as a zero boolean tensor | upstream_code | ManiSkill/mani_skill/envs/sapien_env.py:959-963 |
| BaseEnv's supported observation modes start with 'state' | upstream_code | ManiSkill/mani_skill/envs/sapien_env.py:117 |
| When no observation mode is given, BaseEnv takes the first supported mode | upstream_code | ManiSkill/mani_skill/envs/sapien_env.py:270-271 |
| A state observation flattens the agent and extra observation dictionaries into one array | upstream_code | ManiSkill/mani_skill/envs/sapien_env.py:502-504 |
| An agent's proprioceptive observation is its qpos and qvel | upstream_code | ManiSkill/mani_skill/agents/base_agent.py:337 |
| Panda's arm controller lists seven joints and its gripper controller lists two joint names | upstream_code | ManiSkill/mani_skill/agents/robots/panda/panda.py:53-65 |
| Panda's rest keyframe stores nine joint values | upstream_code | ManiSkill/mani_skill/agents/robots/panda/panda.py:36-47 |
| Panda's first controller configuration is pd_joint_delta_pos | upstream_code | ManiSkill/mani_skill/agents/robots/panda/panda.py:186-189 |
| When no control mode is given, an agent uses the first supported control mode | upstream_code | ManiSkill/mani_skill/agents/base_agent.py:106-109 |
| An agent serves a control mode whose configuration is a dict with a CombinedController | upstream_code | ManiSkill/mani_skill/agents/base_agent.py:258-266 |
| The pd_joint_delta_pos arm config sets lower=-0.1, upper=0.1 and use_delta=True and does not set normalize_action | upstream_code | ManiSkill/mani_skill/agents/robots/panda/panda.py:90-98 |
| The mimic gripper config sets lower=-0.01 and upper=0.04 and does not set normalize_action | upstream_code | ManiSkill/mani_skill/agents/robots/panda/panda.py:177-184 |
| PDJointPosControllerConfig defaults normalize_action to True | upstream_code | ManiSkill/mani_skill/agents/controllers/pd_joint_pos.py:121 |
| PDJointPosMimicControllerConfig subclasses PDJointPosControllerConfig and only sets its controller class | upstream_code | ManiSkill/mani_skill/agents/controllers/pd_joint_pos.py:134-135 |
| The mimic gripper controller reduces its two joints to one action dimension | upstream_code | ManiSkill/mani_skill/agents/controllers/pd_joint_pos.py:126-131 |
| A controller calls _clip_and_scale_action_space when its config sets normalize_action | upstream_code | ManiSkill/mani_skill/agents/controllers/base_controller.py:65-67 |
| _clip_and_scale_action_space replaces the single action space with normalize_action_space of the original one | upstream_code | ManiSkill/mani_skill/agents/controllers/base_controller.py:154-158 |
| normalize_action_space returns Box(-1, 1) with the shape and dtype of the space it is given | upstream_code | ManiSkill/mani_skill/utils/gym_utils.py:108-110 |
| clip_and_scale_action clips an action to [-1, 1] and scales it to 0.5 * (high + low) + 0.5 * (high - low) * action | upstream_code | ManiSkill/mani_skill/utils/gym_utils.py:102-105 |
| The combined controller flattens the single action spaces of its controllers into one space | upstream_code | ManiSkill/mani_skill/agents/controllers/base_controller.py:281-285 |
| A controller exposes its single action space and batches it only when there is more than one environment | upstream_code | ManiSkill/mani_skill/agents/controllers/base_controller.py:68-72 |
| An agent's action spaces are those of its current controller | upstream_code | ManiSkill/mani_skill/agents/base_agent.py:292-314 |
| BaseEnv takes its action space and single action space from its agent | upstream_code | ManiSkill/mani_skill/envs/sapien_env.py:316-319 |
| BaseEnv's default num_envs is 1 | upstream_code | ManiSkill/mani_skill/envs/sapien_env.py:187 |
| The simulation frequency is 100 Hz and the control frequency is 20 Hz | upstream_code | ManiSkill/mani_skill/utils/structs/types.py:80-83 |
| The MSTimeLimit wrapper truncates at the registered max_episode_steps | upstream_code | ManiSkill/mani_skill/utils/registration.py:249-254 |
| TimeLimitWrapper reports truncated when elapsed_steps is at least max_episode_steps | upstream_code | ManiSkill/mani_skill/utils/registration.py:160-163 |

## Limits

The driver declares no `Limit`. The only numeric bounds are the environment's action space, which the Gymnasium
bridge derives from the backend object and attaches to `cap.world.step.v1` `action.values`: eight values from -1 to 1,
the normalised action ManiSkill serves for the Panda's default `pd_joint_delta_pos` controllers. Neither controller
config sets `normalize_action` (panda.py:90-98 and :177-184), whose default is True (pd_joint_pos.py:121, inherited
by the mimic config, :134-135), so each controller replaces its space with `Box(-1, 1)` of its shape
(base_controller.py:65-67 and :154-158, gym_utils.py:108-110), and the combined controller flattens the seven arm
values and the one gripper value into one space (base_controller.py:281-285). `driver.py` cites that `Box` line as
`action_space_ref`, so the bound has source `upstream_code` and the ref
`ManiSkill/mani_skill/utils/gym_utils.py:108-110`. Each value is clipped to -1 .. 1 and scaled before it is applied
(gym_utils.py:102-105): an arm value v moves its joint target by 0.1 v (the -0.1 .. 0.1 of the arm config), and the
gripper value sets the target 0.015 + 0.025 v, so -1 .. 1 spans the -0.01 .. 0.04 of the gripper config. The fake's
`Box` reproduces the bounds and its `step` the scaling; a value outside the bounds is refused by the bridge with
`MHS.SAFETY.ENVELOPE_VIOLATION` before any `step` call. The bridge also derives `ticks` (1 to its `max_ticks` of
10000) and the non-negative `seed`. There is no operator-required bound: the device is simulated at R0.

The observation is the flattened state observation: qpos and qvel of the nine Panda joints, 18 numbers in total
(base_agent.py:337 and the nine joint names in panda.py:53-65). Empty-v1's default observation mode is the first
supported mode, `state` (sapien_env.py:117 and :270-271), which `get_obs` flattens into one array (sapien_env.py:502-504).
The fake returns exactly those 18 numbers; it does not return camera images.

## Fidelity contract

`driver.py` declares engine `analytic:Empty-v1`, level `F0` (kinematic: no dynamics), determinism `seeded` with
`seed_control` `parameter`, timestep 50 ms (the control frequency is 20 Hz, types.py:82), `realtime_factor` 0,
clock `lockstep`, reset `full`, and no snapshot/restore. The gaps say that the fake does not simulate SAPIEN/PhysX
contacts, forces, actuators, sensors or noise; that its action is ManiSkill's normalised one, which it clips and
scales as the controllers do; that it was not compared with upstream ManiSkill; that the zero joint start state and
instantaneous target-to-position update are placeholders; the same target is now assigned to both fingers as the pinned mimic controller broadcasts; external asset joint limits and drive dynamics remain unmodelled; and that the registered 200000-step time limit is modelled but not
exercised by a package test.

## Safety

The driver is simulated at R0 (`world.sim`). The runtime owns the latch: `mhs.safety.estop` latches before any native
call, no step or reset is accepted afterwards until `mhs.safety.reset`, and the last observation stays readable.
No hardware backend, no physical e-stop and no operator-required limit apply to a simulator.

Tags: blindvla, maniskill, empty, panda, gymnasium, simulation

## Mimic target relation

Pinned ManiSkill/mani_skill/agents/controllers/pd_joint_pos.py:84-86 broadcasts one absolute action target to the full finger joint shape. The fake now assigns that target to both finger entries. This corrects a sign error only; it does not infer the absent external Panda URDF joint limits, model forces/contact, or claim that a negative configured drive target is a physically reached joint position.
