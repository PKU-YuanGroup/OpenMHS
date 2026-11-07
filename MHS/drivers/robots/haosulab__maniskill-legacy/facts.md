# Facts and tags for gh.haosulab/maniskill-legacy

Every fact cites its source at commit `58964d08b4c7d2e14c5e6e287dbb9430d900f54d`: `vendor_doc` for README text and
`upstream_code` for a Python or YAML code/comment line (`path/in/clone:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| ManiSkill environments are built on the OpenAI Gym interface | vendor_doc | README.md:65 |
| The basic example constructs an environment with `gym.make('OpenCabinetDoor-v0')` | vendor_doc | README.md:135 |
| `OpenCabinetDoor-v0` is registered through `gym.register` with entry point `mani_skill.env.open_cabinet_door_drawer:OpenCabinetDoorEnv` | upstream_code | mani_skill/env/__init__.py:11-14 |
| The action space is `Box(low=-1, high=1, shape=agent.action_range().shape)` | upstream_code | mani_skill/env/base_env.py:95 |
| The mobile_a2_single_arm robot config has 13 controllable joints | upstream_code | mani_skill/assets/config_files/robots/mobile_a2_single_arm.yml:18-30 |
| Each step clips the action to [-1, 1] and scales it to the agent's action range | upstream_code | mani_skill/env/base_env.py:538-542 |
| `step` advances `frame_skip` control steps of the agent and the scene and returns `obs, reward, done, info` | upstream_code | mani_skill/env/base_env.py:544-571 |
| One environment step covers `frame_skip / control_frequency` seconds | upstream_code | mani_skill/env/base_env.py:97 |
| The `BaseEnv` constructor's default `frame_skip` is 5 and its default `max_episode_steps` is 200 | upstream_code | mani_skill/env/base_env.py:69-70 |
| The mobile_a2_single_arm robot config sets `control_frequency` to 100 | upstream_code | mani_skill/assets/config_files/robots/mobile_a2_single_arm.yml:4 |
| In state mode `get_obs` returns `get_state(with_controller_state=False)` | upstream_code | mani_skill/env/base_env.py:636-640 |
| `get_state` concatenates the actor states, the padded articulation states, the task info and the agent state | upstream_code | mani_skill/env/base_env.py:471-479 |
| `get_pad_articulation_state` returns the 13 pose/velocity values then `2 * max_dof` internal values | upstream_code | mani_skill/utils/misc.py:51-57 |
| `OpenCabinetEnvBase.configure_env` sets `cabinet_max_dof` to 8 | upstream_code | mani_skill/env/open_cabinet_door_drawer.py:35-36 |
| The target indicator is an 8-element zero vector with a 1 at the target joint's active index | upstream_code | mani_skill/env/open_cabinet_door_drawer.py:158-159 |
| The state-mode observation space is a `Box` whose bounds are -inf and inf | upstream_code | mani_skill/env/base_env.py:423-427 |
| `target_qpos = lmin + (lmax - lmin) * custom['open_extent']` | upstream_code | mani_skill/env/open_cabinet_door_drawer.py:51-53 |
| The open_cabinet_door config sets `custom.open_extent` to 0.9 | upstream_code | mani_skill/assets/config_files/open_cabinet_door.yml:48-49 |
| The success flag `open_enough` is true when the target joint's qpos is at least `target_qpos` | upstream_code | mani_skill/env/open_cabinet_door_drawer.py:234-240 |
| `seed` sets the main seed and a numpy `RandomState` from it | upstream_code | mani_skill/env/base_env.py:183-185 |
| `reset(level)` seeds the level RNG from `level` and, when `level` is None, draws a 32-bit level from the main RNG | upstream_code | mani_skill/env/base_env.py:138-142 |

## Limits

The driver declares no Limits: the catalogue classes `cap.world.step.v1`, `cap.world.reset.v1` and
`cap.world.seed.v1` are all R0 and the only numeric bounds are the catalogue's own (`ticks` 1 to 10000, `seed` >= 0)
plus the action space, which the bridge derives from the deployed environment's `action_space` (the fake's
`Box([-1] * 13, [1] * 13)`; the upstream `BaseEnv` builds the same bounds with the agent's action-range shape at
`mani_skill/env/base_env.py:95`). There is no operator-required bound: a simulated environment has no physical
envelope to narrow.

## Fidelity

`fidelity = {...}` in `driver.py` declares the model as deployed: engine `analytic:mani_skill_open_cabinet_door_v0`,
level F0 (kinematic/analytic, no rigid-body dynamics), determinism `seeded` with `seed_control` `parameter`,
timestep 50 ms (`frame_skip / control_frequency = 5 / 100` s from `mani_skill/env/base_env.py:97` and
`mani_skill/assets/config_files/robots/mobile_a2_single_arm.yml:4`), `realtime_factor` 0, clock `lockstep`, reset
`full`, no snapshot and restore. The gaps say what is not modelled (dynamics, contacts, actuators, the full state
values, the upstream dense reward, rendering) and that the fake was not compared with the SAPIEN environment.

## Safety

The device is a simulator: mode `simulated`, risk R0 (the catalogue floor of all three `cap.world.*` classes), no
hardware backend and no physical effect. The e-stop is the runtime's software latch; after it no step or reset is
accepted until `mhs.safety.reset` clears the latch, and the state stays readable. A simulator needs no independent
hardware stop and this package claims none.

Tags: maniskill, manipulation, cabinet-door, simulation, gym, gymnasium
