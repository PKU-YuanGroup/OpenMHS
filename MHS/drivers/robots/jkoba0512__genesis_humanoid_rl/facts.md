# Facts and tags for gh.jkoba0512/genesis_humanoid_rl

Every fact cites its source at commit `32e5bd1a1e516bf4caedcb31f1a8ee366f2efebc`: `vendor_doc` (a text file of the
clone such as README.md or an asset README) or `upstream_code` (a code file of the clone with a line). The same facts
are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The environment imports Env and spaces from gymnasium | upstream_code | src/genesis_humanoid_rl/environments/humanoid_env.py:8 |
| HumanoidWalkingEnv subclasses gymnasium.Env | upstream_code | src/genesis_humanoid_rl/environments/humanoid_env.py:24 |
| reset loads the Unitree G1 from assets/robots/g1/g1_29dof.urdf and spawns it at (0, 0, 1.0) | upstream_code | src/genesis_humanoid_rl/environments/humanoid_env.py:98-105 |
| The action space is Box(low=-1.0, high=1.0, shape=(num_joints,), dtype=np.float32) | upstream_code | src/genesis_humanoid_rl/environments/humanoid_env.py:129-131 |
| The observation space is an unbounded Box of 3 + 4 + 3 * num_joints + 1 values: base position (3), orientation quaternion (4), joint positions, joint velocities, previous action and target velocity (1) | upstream_code | src/genesis_humanoid_rl/environments/humanoid_env.py:133-139 |
| The constructor defaults are simulation_fps=100, control_freq=20, episode_length=1000 and target_velocity=1.0 | upstream_code | src/genesis_humanoid_rl/environments/humanoid_env.py:35-38 |
| The scene uses dt=1.0/simulation_fps, 10 substeps and show_viewer=False | upstream_code | src/genesis_humanoid_rl/environments/humanoid_env.py:78-84 |
| Each control step advances simulation_fps // control_freq scene steps | upstream_code | src/genesis_humanoid_rl/environments/humanoid_env.py:169-171 |
| step clips the action to [-1.0, 1.0] and adds action * 0.1 to the current joint positions before position control | upstream_code | src/genesis_humanoid_rl/environments/humanoid_env.py:152-166 |
| An episode is truncated when current_step >= episode_length | upstream_code | src/genesis_humanoid_rl/environments/humanoid_env.py:184 |
| The episode terminates when the base height is below 0.3, abs(x) > 10.0 or abs(y) > 5.0, or the base height is above 2.0 | upstream_code | src/genesis_humanoid_rl/environments/humanoid_env.py:303-320 |
| The reward adds a forward-velocity term capped at 2.0 times target_velocity, a stability term weighted 0.5 and a height term around 0.8 weighted 0.3, and subtracts energy and smoothness penalties capped at 10.0 and 2.0 with weight 0.1 | upstream_code | src/genesis_humanoid_rl/environments/humanoid_env.py:236-279 |
| The observation concatenates base position (3), quaternion (4), joint positions, joint velocities, previous action and target velocity (1) | upstream_code | src/genesis_humanoid_rl/environments/humanoid_env.py:210-220 |
| reset returns (observation, {}) | upstream_code | src/genesis_humanoid_rl/environments/humanoid_env.py:148 |
| reset creates a new Genesis scene and adds the ground plane and the robot on every call | upstream_code | src/genesis_humanoid_rl/environments/humanoid_env.py:77-95 |
| SB3HumanoidEnv constructs a HumanoidWalkingEnv and copies its spaces | upstream_code | src/genesis_humanoid_rl/environments/sb3_wrapper.py:34-48 |
| SB3HumanoidEnv.reset seeds numpy when a seed is given and then resets the wrapped environment | upstream_code | src/genesis_humanoid_rl/environments/sb3_wrapper.py:62-65 |
| make_humanoid_env names the environment HumanoidWalk-v0 and validates the wrapper with check_env | upstream_code | src/genesis_humanoid_rl/environments/sb3_wrapper.py:131-149 |
| The project requires Python >=3.10,<3.11 and depends on genesis-world, stable-baselines3 and gymnasium | upstream_code | pyproject.toml:6-12 |
| The G1 asset README lists the g1_29dof model with 6*2 leg, 3 waist and 7*2 arm joints | vendor_doc | assets/robots/g1/README.md:20 |
| The README describes the project as a full 35-DOF humanoid robot simulation | vendor_doc | README.md:14 |

## Limits

The driver declares no limit of its own. The only bound is the action space, which the Gymnasium bridge derives from
the environment: `Box(low=-1.0, high=1.0, shape=(num_joints,), dtype=np.float32)`
(`src/genesis_humanoid_rl/environments/humanoid_env.py:129-131`) gives `action.values` a per-element minimum of -1.0
and maximum of 1.0, and the bridge's `ticks` input is 1 to `max_ticks` (10000 by default). The device is simulated
(R0), so no limit is `operator_required`.

## Fidelity contract

`driver.py` `fidelity`: engine `genesis`, level F1 (rigid-body dynamics with contacts; the environment builds a
Genesis scene with a ground plane and the G1 URDF, `humanoid_env.py:77-110`), determinism `seeded` with
`seed_control` `parameter`, timestep 50 ms, `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The 50 ms is one environment step: `simulation_fps // control_freq` = 5 scene steps
(`humanoid_env.py:169-171`) of `dt = 1.0/simulation_fps` = 10 ms each (`humanoid_env.py:80`).

The gaps say what is not modelled, above all that this package's fake is a pure Python kinematic stand-in: it runs
no Genesis scene, has 6 stand-in joints instead of the real `robot.n_dofs`, keeps the base at the spawn point, does
not ground the robot, has no rendering, no snapshot/restore and was never compared with the upstream simulator.

## Mock strategy

The card prefers the upstream simulator. It cannot be used here: the upstream package requires Python 3.10 and the
external `genesis-world`, `torch` and `stable-baselines3` dependencies (`pyproject.toml:6-12`), which are not
installed where the gate runs (Python 3.14), and package code never imports or runs the clone. The `fake` backend is
therefore the package fake `FakeHumanoidWalkingEnv`; the upstream simulator path was not run. The fake mirrors the
upstream public surface (`reset`, `step`, `render`, `close`) and its spaces, observation layout and reward and
termination rules, but not its physics.

## Safety

Simulated R0 device. There is no hardware backend and no e-stop path to a machine; the e-stop is the runtime's
software latch. After an e-stop no step or reset is accepted until `mhs.safety.reset` clears the latch (a simulator
needs no operator for that), and the state stays readable.

Tags: humanoid, unitree-g1, genesis, reinforcement-learning, simulation, gymnasium
