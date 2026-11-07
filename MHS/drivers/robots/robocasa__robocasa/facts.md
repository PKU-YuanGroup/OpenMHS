# Facts and tags for gh.robocasa/robocasa

Every fact cites its source at commit `456174f62b89b8fca99eaaf33949c29fec9cfc2a`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| RoboCasa is a large-scale simulation framework for training robots to perform everyday tasks, not a hardware SDK | vendor_doc | README.md:5 |
| The documented entry point creates an environment with gym.make('robocasa/PickPlaceCounterToCabinet', split='pretrain', seed=0) | vendor_doc | README.md:78-82 |
| The wrapper registers every environment as 'robocasa/<class>' with the wrapper class as the entry point | upstream_code | robocasa/wrappers/gym_wrapper.py:400-420 |
| RoboCasaGymEnv is a gymnasium.Env subclass | upstream_code | robocasa/wrappers/gym_wrapper.py:143 |
| RoboCasaGymEnv forwards unknown attributes to the inner robosuite environment through __getattr__ | upstream_code | robocasa/wrappers/gym_wrapper.py:395-397 |
| The wrapper's action space is a Dict of five Box fields with low -1 and high 1: action.gripper_close (1 element), action.end_effector_position (3), action.end_effector_rotation (3), action.base_motion (4) and action.control_mode (1) | upstream_code | robocasa/wrappers/gym_wrapper.py:83-102 |
| The final action_space is PandaOmronKeyConverter.deduce_action_space(env), not the space built from the composite controller | upstream_code | robocasa/wrappers/gym_wrapper.py:268 |
| unmap_action reads the five fields as input_action['action.gripper_close'], ['action.end_effector_position'], ['action.end_effector_rotation'], ['action.base_motion'] and ['action.control_mode'] before calling the inner environment | upstream_code | robocasa/wrappers/gym_wrapper.py:121-140 |
| The wrapper maps the robot observation to state.gripper_qpos, state.base_position, state.base_rotation, state.end_effector_position_relative and state.end_effector_rotation_relative | upstream_code | robocasa/wrappers/gym_wrapper.py:303-311 |
| The mapped state observations are Box(-1, 1) | upstream_code | robocasa/wrappers/gym_wrapper.py:72-76 |
| The camera configuration is three views named robot0_agentview_left, robot0_agentview_right and robot0_eye_in_hand, all 256 by 256 pixels | upstream_code | robocasa/wrappers/gym_wrapper.py:35-47 |
| The observation space adds one Box(0, 255) of shape (height, width, 3) per video.* camera and a Text(max_length=256) annotation.human.task_description | upstream_code | robocasa/wrappers/gym_wrapper.py:244-267 |
| reset(seed) replaces the inner environment RNG with numpy.random.default_rng(seed); options is accepted but not used | upstream_code | robocasa/wrappers/gym_wrapper.py:342-346 |
| step calls the inner environment, reports reward 1.0 when _check_success() is true and 0.0 otherwise, always sets truncated False and returns the inner environment's done flag | upstream_code | robocasa/wrappers/gym_wrapper.py:374-385 |
| Kitchen passes control_freq 20, horizon 1000 and ignore_done True to robosuite; one control signal therefore advances the simulation by 50 ms | upstream_code | robocasa/environments/kitchen/kitchen.py:381-383 |
| Kitchen._check_success returns False by default and the task subclasses implement the success test | upstream_code | robocasa/environments/kitchen/kitchen.py:1542-1551 |
| The package pins MuJoCo 3.3.1 and asserts that version at import | upstream_code | robocasa/__init__.py:1005-1007 |
| Each environment is built with robosuite.make, the MuJoCo-backed engine | upstream_code | robocasa/utils/env_utils.py:138 |
| The kitchen assets downloaded by the setup script are around 10GB | vendor_doc | README.md:65 |
| render returns the cached camera frame and refuses before a reset or step; close delegates to the inner environment | upstream_code | robocasa/wrappers/gym_wrapper.py:387-393 |

## Shape of the driver and the card deviation

The card proposed a `GymnasiumDriver`, but that bridge cannot publish this wrapper's contract: the wrapper's Dict
action keys already start with `action.` (`gym_wrapper.py:95-98`) and `unmap_action` reads them
(`gym_wrapper.py:121-140`), while the gymnasium bridge prefixes every Dict key with `action.` when it derives limits.
The reference run therefore failed with `limit path 'action.action.gripper_close' does not resolve in the input
schema`. This package is a direct `Driver` over the card's first entry symbol
`robocasa.wrappers.gym_wrapper:RoboCasaGymEnv`; it names the five numeric action fields without the upstream prefix,
bounds each element by the upstream `-1..1`, and restores the `action.<field>` keys before the native `step` call.
The Python interface is unchanged; only the names of the MHS input fields differ from the upstream dictionary keys.

## Limits

The only driver-declared limits are the five action fields, each a `Field("array", items="number", length=N)` with
`Limit(min=-1, max=1, source="upstream_code", ref="robocasa/wrappers/gym_wrapper.py:97-98")`. The cited lines show
`low=-1, high=1` for every action Box. `ticks` (1 to 10000) and `seed` (at least 0) are catalogue class schema
fields, not device bounds, so they carry no driver Limit and a value outside them is an input refusal rather than an
envelope refusal. The device is simulated and declares no operator-required limit, so no `site-limits.example.json`
is needed.

## Fidelity

The only served backend is the package fake, so the package claims F0 with `engine`
`custom:robocasa/PickPlaceCounterToCabinet (kinematic fake stand-in)`, `timestep_ms` 50 (one `control_freq=20`
control step, `kitchen.py:381`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore, and
determinism `seeded` with `seed_control` `parameter`. The gaps say that the fake has no dynamics, contacts, MuJoCo,
robosuite, task success, reward or real camera, and that the upstream wrapper would be an F1 MuJoCo model if it were
installed and run.

## Safety

The device is simulated (`mode = "simulated"`) and R1: every step advances a simulated robot arm and mobile base,
which the safety spec classifies as simulation stepping, and there is no physical effect outside the process. There
is no hardware backend and no independent hardware e-stop to cite, and none is claimed. The runtime's software e-stop
latches the endpoint: after it, `cap.world.step.v1` and `cap.world.reset.v1` are refused until `mhs.safety.reset`
clears the latch, and the observation and tick stay readable. The driver's `@estop` closes the wrapper (the native
`close` at `gym_wrapper.py:392-393`), and its `@reset` hook reopens the wrapper at the recorded seed, so the safe
state is a stopped, still readable simulation rather than a live process.

## Tags

robocasa, kitchen, manipulation, mobile-base, mujoco, robosuite, gymnasium, simulation, reinforcement-learning
