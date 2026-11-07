"""OpenMHS driver for gh.jkoba0512/genesis_humanoid_rl: the Genesis Unitree G1 walking environment.

A GymnasiumDriver is configuration only: the bridge derives the contract from the environment's spaces.  Here
``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{values}`` bounded by ``Box(low=-1.0, high=1.0)``
over the joint array, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The
device is a simulated G1 (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.

The upstream is a Gymnasium ``Env`` that wraps the Genesis physics engine and is not registered with
``gymnasium.make``; the environment is constructed directly (``HumanoidWalkingEnv`` or ``make_humanoid_env``) and
needs Python 3.10 and ``genesis-world``/``torch``/``stable-baselines3`` (pyproject.toml:6-12).  The gate runs on
Python 3.14 without those packages and package code never imports the clone, so ``backends`` lists only the
package's pure Python ``FakeHumanoidWalkingEnv``; that is the backend that was checked.  The upstream simulator was
not run.

The ``fidelity`` attribute is the complete contract of the model as deployed (spec 05-fidelity): the engine, level,
determinism, timestep, clock and the gaps that say what is not modelled.  Every fact cites a line of the clone at
the pinned commit (32e5bd1a1e516bf4caedcb31f1a8ee366f2efebc); the fake's array sizes and kinematic rules are test
data, named in the gaps.  This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "src/genesis_humanoid_rl/environments/humanoid_env.py"
WRAPPER = "src/genesis_humanoid_rl/environments/sb3_wrapper.py"


class GenesisHumanoid(GymnasiumDriver):
    device_id = "genesis-humanoid"
    env_id = "HumanoidWalk-v0"
    native = "genesis_humanoid_rl.environments.humanoid_env:HumanoidWalkingEnv"
    backends = {"fake": ".fake:FakeHumanoidWalkingEnv"}
    display_name = "Genesis Humanoid RL (Unitree G1 walking environment)"
    vendor, model = "jkoba0512", "Unitree G1 (Genesis)"
    tags = ["humanoid", "unitree-g1", "genesis", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The environment imports Env and spaces from gymnasium", source="upstream_code", ref=f"{ENV}:8"),
        Fact("HumanoidWalkingEnv subclasses gymnasium.Env", source="upstream_code", ref=f"{ENV}:24"),
        Fact("reset loads the Unitree G1 from assets/robots/g1/g1_29dof.urdf and spawns it at (0, 0, 1.0)",
             source="upstream_code", ref=f"{ENV}:98-105"),
        Fact("The action space is Box(low=-1.0, high=1.0, shape=(num_joints,), dtype=np.float32)",
             source="upstream_code", ref=f"{ENV}:129-131"),
        Fact("The observation space is an unbounded Box of 3 + 4 + 3 * num_joints + 1 values: base position (3), "
             "orientation quaternion (4), joint positions, joint velocities, previous action and target velocity (1)",
             source="upstream_code", ref=f"{ENV}:133-139"),
        Fact("The constructor defaults are simulation_fps=100, control_freq=20, episode_length=1000 and "
             "target_velocity=1.0", source="upstream_code", ref=f"{ENV}:35-38"),
        Fact("The scene uses dt=1.0/simulation_fps, 10 substeps and show_viewer=False", source="upstream_code",
             ref=f"{ENV}:78-84"),
        Fact("Each control step advances simulation_fps // control_freq scene steps", source="upstream_code",
             ref=f"{ENV}:169-171"),
        Fact("step clips the action to [-1.0, 1.0] and adds action * 0.1 to the current joint positions before "
             "position control", source="upstream_code", ref=f"{ENV}:152-166"),
        Fact("An episode is truncated when current_step >= episode_length", source="upstream_code",
             ref=f"{ENV}:184"),
        Fact("The episode terminates when the base height is below 0.3, |x| > 10.0 or |y| > 5.0, or the base "
             "height is above 2.0", source="upstream_code", ref=f"{ENV}:303-320"),
        Fact("The reward adds a forward-velocity term capped at 2.0 times target_velocity, a stability term weighted "
             "0.5 and a height term around 0.8 weighted 0.3, and subtracts energy and smoothness penalties capped at "
             "10.0 and 2.0 with weight 0.1", source="upstream_code", ref=f"{ENV}:236-279"),
        Fact("The observation concatenates base position (3), quaternion (4), joint positions, joint velocities, "
             "previous action and target velocity (1)", source="upstream_code", ref=f"{ENV}:210-220"),
        Fact("reset returns (observation, {})", source="upstream_code", ref=f"{ENV}:148"),
        Fact("reset creates a new Genesis scene and adds the ground plane and the robot on every call",
             source="upstream_code", ref=f"{ENV}:77-95"),
        Fact("SB3HumanoidEnv constructs a HumanoidWalkingEnv and copies its spaces", source="upstream_code",
             ref=f"{WRAPPER}:34-48"),
        Fact("SB3HumanoidEnv.reset seeds numpy when a seed is given and then resets the wrapped environment",
             source="upstream_code", ref=f"{WRAPPER}:62-65"),
        Fact("make_humanoid_env names the environment HumanoidWalk-v0 and validates the wrapper with check_env",
             source="upstream_code", ref=f"{WRAPPER}:131-149"),
        Fact("The project requires Python >=3.10,<3.11 and depends on genesis-world, stable-baselines3 and "
             "gymnasium", source="upstream_code", ref="pyproject.toml:6-12"),
        Fact("The G1 asset README lists the g1_29dof model with 6*2 leg, 3 waist and 7*2 arm joints",
             source="vendor_doc", ref="assets/robots/g1/README.md:20"),
        Fact("The README describes the project as a full 35-DOF humanoid robot simulation", source="vendor_doc",
             ref="README.md:14"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge would derive the
    #: engine, determinism and clock; they are written out so the whole contract reads in one place.  One bridge
    #: tick is one environment step: simulation_fps // control_freq = 5 scene steps of dt = 1.0/simulation_fps =
    #: 10 ms each (humanoid_env.py:35-36, :80, :169-171), so timestep_ms is 50.
    fidelity = {
        "engine": "genesis",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) seeds Gymnasium's generator (humanoid_env.py:75) and SB3HumanoidEnv.reset seeds "
                     "numpy (sb3_wrapper.py:62-63), but the reset draws no random initial state: the G1 is spawned, "
                     "grounded and settled deterministically.  cap.world.seed.v1 supplies the seed of the next "
                     "reset; the fake repeats a trajectory for every seed and echoes the seed without changing its "
                     "start state.",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a pure Python kinematic stand-in for HumanoidWalkingEnv: it runs no Genesis scene, "
            "integrates no rigid-body contacts, gravity, actuator torque or sensor noise, and was never compared "
            "with the upstream simulator",
            "the fake uses 6 stand-in joints; the real environment sizes its action and observation spaces from "
            "robot.n_dofs after loading g1_29dof.urdf, so the real arrays are larger (the README describes a 35-DOF "
            "humanoid and the asset table lists 29 joint DOF for g1_29dof)",
            "the fake moves each joint by action * 0.1 and keeps the base at the spawn point; upstream drives "
            "Genesis position control and lets the base move, fall and terminate",
            "no wall-clock pacing: realtime_factor 0 and ticks advance simulated time by timestep_ms (50 ms) only; "
            "render() is a no-op and no Genesis viewer is modelled",
            "no snapshot and restore: the environment exposes no get_state/set_state",
            "the fake does not model the automatic grounding step: it keeps the spawn height instead of the height "
            "RobotGroundingCalculator computes (humanoid_env.py:112-120)",
            "no physical G1 or hardware is modelled and no result was validated against one",
        ],
    }
