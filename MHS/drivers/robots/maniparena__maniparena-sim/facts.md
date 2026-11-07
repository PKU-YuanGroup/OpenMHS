# Facts and tags for gh.maniparena/maniparena-sim

Every fact cites the clone at commit `bc40c5f7c0f58ca86a53a2ab1a45a8e5a4a0916b`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| ManipArena-Sim is the simulation environment for the ManipArena bimanual manipulation benchmark, built on Isaac Lab and IsaacLab-Arena | vendor_doc | README.md:3 |
| SUPPORTED_SDK_ROBOTS lists quanta_x1, quanta_x2 and artixon_arm_6a | upstream_code | src/maniparena_sim/environment/sdk_builder.py:11 |
| build_sdk_ros2_gym_env is documented to return (gym_env, embodiment) for the selected public SDK robot | upstream_code | src/maniparena_sim/environment/sdk_builder.py:106-107 |
| The SDK ROS2 builder supports exactly one environment and raises when num_envs is not 1 | upstream_code | src/maniparena_sim/environment/sdk_builder.py:118-119 |
| sdk_simulation_timing defaults physics_dt to 1/120 s, decimation to 6 and render_interval to 2 | upstream_code | src/maniparena_sim/environment/sdk_builder.py:45-49 |
| The SDK builder assigns env_cfg.decimation = decimation before it makes the gym environment | upstream_code | src/maniparena_sim/environment/sdk_builder.py:173 |
| AssembledEnvironment is documented to wrap a scene, an embodiment and a task into a lazily built gym environment | upstream_code | src/maniparena_sim/environment/assembled_environment.py:17-18 |
| build_gym_environment calls gym.make(env_name, cfg=env_cfg, **env_kwargs).unwrapped and returns that environment | upstream_code | src/maniparena_sim/environment/assembled_environment.py:103-109 |
| get_env builds the gym environment with build_gym_environment when it is not built yet and returns it | upstream_code | src/maniparena_sim/environment/assembled_environment.py:180-183 |
| The builder configuration defaults the seed to 42 when the caller supplies none | upstream_code | src/maniparena_sim/environment/assembled_environment.py:170 |
| The SDK launcher calls build_sdk_ros2_gym_env and then gym_env.reset() | upstream_code | scripts/sdk_ros2.py:135-140 |
| The evaluation loop unpacks obs, _, terminated, truncated, _ = gym_env.step(actions), the Gymnasium five-tuple | upstream_code | scripts/eval.py:369-371 |
| The SDK runtime exposes robot state and either Cartesian or joint commands, without recording | vendor_doc | README.md:91 |
| The desktop SDK uses the fruit tabletop scene with an empty task and has no automatic timeout or success reset | vendor_doc | README.md:100-101 |
| The prerequisites are Ubuntu 22.04 or 24.04 with an NVIDIA GPU, Python 3.12, CUDA 12.8 and Isaac Sim 6.x binary wheels | vendor_doc | README.md:36-44 |
| The installer pins Isaac Sim to the wheels isaacsim[all,extscache]==6.0.1.0 | vendor_doc | docs/install.md:13 |
| The project dependencies are numpy, PyYAML, av, pyarrow, msgpack, msgpack-numpy and websockets, with no serial, VISA, USB or vendor hardware package | upstream_code | pyproject.toml:11-19 |
| The quanta_x2 SDK guide states that ee is the default arm_control mode and that joint mode subscribes to joint commands instead | vendor_doc | docs/quanta_x2_sdk.md:35 |
| The artixon SDK guide gives the per-arm joint order as left_arm_joint1..6 and right_arm_joint1..6 and the angle unit as radians | vendor_doc | docs/artixon_arm_6a_sdk.md:29 |
| The README states Apache License 2.0 | vendor_doc | README.md:258 |

## Contract notes

**DEVIATION FROM THE CARD.** The card proposes the `GymnasiumDriver` family-config, but the clone has no registered
Gymnasium id and no environment class of its own. `build_sdk_ros2_gym_env` is a builder function
(`sdk_builder.py:106-107`) and `AssembledEnvironment.build_gym_environment` uses a name that
`IsaacLabArenaEnvironment` registers at composition time (`assembled_environment.py:103`). A `GymnasiumDriver` derives
its contract from `env_id` and the spaces, so this package uses a direct `Driver` over the card's class entry symbol
`AssembledEnvironment` instead.

**Capabilities.** `cap.world.step.v1` takes `ticks` and an action object `{values: [...]}`; the driver validates the
values against the live environment's `action_space` shape because the width is selected by the robot and
`arm_control` mode (three SDK robots at `sdk_builder.py:11`; Cartesian or joint control at `README.md:91`), not fixed
in the clone. `cap.world.reset.v1` forwards `seed` and `options` to the environment's `reset` and accepts only the
`default` scenario. `cap.world.seed.v1` records the seed the next reset applies.

**Limits.** The driver declares none. The catalogue class carries the `ticks` bound (1..10000) and the seed minimum
(0), and they are enforced by the runtime before the driver. No numeric action bound is declared because the action
space belongs to the configured embodiment; a bound copied from one SDK configuration would be wrong for the others.
The device is simulated R0, so no limit is `operator_required`.

**Fidelity contract** (`driver.py`, `fidelity = {...}`): engine `maniparena_sim:AssembledEnvironment/gymnasium`, level
F0 (a kinematic stand-in, no Isaac Sim physics), determinism `seeded` with `seed_control` `parameter`, `timestep_ms`
50.0 (physics_dt 1/120 s x default decimation 6, `sdk_builder.py:45-49` and `:173`), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. The gaps name the missing physics, the smaller fake action and
observation arrays, the single-environment reduction and the unrun upstream stack.

**Safety:** simulated R0 device. The e-stop is the runtime's software latch; the clone has no native stop and the
driver declares none. After an e-stop no step, reset or seed is accepted until `mhs.safety.reset` clears the latch,
and the last observation and tick stay readable.

**License:** the card records `NOASSERTION` / `unknown` and the clone has no `LICENSE` file; the only license
statement found is `README.md:258`, which says Apache License 2.0. The lock keeps the card's `NOASSERTION`. No
hardware or sim backend was installed or run.

Tags: bimanual, manipulation, isaac-sim, isaac-lab, isaaclab-arena, simulation, gymnasium
