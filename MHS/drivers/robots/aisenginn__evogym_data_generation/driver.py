"""OpenMHS driver for gh.aisenginn/evogym_data_generation: the Walker-v0 Gymnasium environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
whole contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` where the action is
``{values}`` with one actuator target per actuator, bounded by the upstream ``Box(0.6, 1.6)`` (walk.py:36),
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0):
there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The gate cannot import the upstream package: evogym needs Python >=3.7,<3.11 and a compiled CMake extension
(pyproject.toml:40-49, setup.py:61-65), and package code never imports the clone.  The ``fake`` backend is this
package's pure Python analytic stand-in (fake.py).  No ``sim`` backend is declared: ``WalkingFlat.__init__`` requires
a robot ``body`` ndarray (walk.py:17-27), so ``gymnasium.make("Walker-v0")`` alone cannot construct it; a deployment
that installs evogym must supply a body, and that path was not run here.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002).  It describes the
analytic fake, not the upstream soft-body simulator, and states the gaps.  Every constant and rule cites a line of
the clone at commit 91c05ab7a793f86e099c21d377f183c95c9990cd.  This package is model-authored and unreviewed: it is
checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

WALK = "evogym/envs/walk.py"
BASE = "evogym/envs/base.py"
REGISTRY = "evogym/envs/__init__.py"
SIM = "evogym/simulator/SimulatorCPP/Sim.cpp"
ENVIRONMENT = "evogym/simulator/SimulatorCPP/Environment.cpp"
UTILS = "evogym/utils.py"


class EvogymWalker(GymnasiumDriver):
    device_id = "evogym_walker_v0"
    env_id = "Walker-v0"
    native = "evogym.envs.walk:WalkingFlat"
    backends = {"fake": ".fake:FakeWalkerEnv"}
    # The action width belongs to a placeholder body, not a configured upstream instance.  The bridge
    # therefore records these as fake-derived bounds; the upstream numeric range is documented as a Fact.
    fidelity_level = "F0"
    display_name = "Evogym Walker-v0 (soft-robot locomotion)"
    vendor, model = "Evogym", "Walker-v0"
    tags = ["evogym", "soft-robot", "walker", "locomotion", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("The repository is built on Evogym, a simulation environment for evolutionary robotics and soft "
             "robots", source="vendor_doc", ref="README.md:7"),
        Fact("The package requires Python >=3.7 and <3.11", source="upstream_code", ref="pyproject.toml:40"),
        Fact("The package depends on gymnasium and numpy<2.0.0", source="upstream_code",
             ref="pyproject.toml:46-49"),
        Fact("Installation builds the CMake extension evogym.simulator_cpp from evogym/simulator",
             source="upstream_code", ref="setup.py:61-65"),
        Fact("WalkingFlat is the concrete environment class of evogym.envs.walk", source="upstream_code",
             ref=f"{WALK}:15"),
        Fact("Walker-v0 is registered with entry point evogym.envs.walk:WalkingFlat and max_episode_steps=500",
             source="upstream_code", ref=f"{REGISTRY}:16-20"),
        Fact("WalkingFlat loads the Walker-v0 world and adds the robot body at position (1, 1)",
             source="upstream_code", ref=f"{WALK}:26-27"),
        Fact("The number of action values is the number of actuator indices of the robot",
             source="upstream_code", ref=f"{WALK}:33"),
        Fact("num_robot_points is the size of the robot's position array", source="upstream_code",
             ref=f"{WALK}:34"),
        Fact("The action space is Box(low=0.6, high=1.6, shape=(num_actuators,))", source="upstream_code",
             ref=f"{WALK}:36"),
        Fact("The observation space is Box(low=-100.0, high=100.0, shape=(2 + num_robot_points,))",
             source="upstream_code", ref=f"{WALK}:37"),
        Fact("The environment's step forwards the robot action to the base step as a one-entry robot dictionary",
             source="upstream_code", ref=f"{WALK}:45"),
        Fact("EvoGymBase.step clips every actuator value to [0.6, 1.6] before setting it", source="upstream_code",
             ref=f"{BASE}:54-57"),
        Fact("The observation concatenates the robot's centre-of-mass velocity with its relative point positions",
             source="upstream_code", ref=f"{WALK}:51-54"),
        Fact("get_relative_pos_obs subtracts the point centre and flattens the coordinate array",
             source="upstream_code", ref=f"{BASE}:260-262"),
        Fact("The reward is the change of the robot's centre-of-mass x between the previous and the new step",
             source="upstream_code", ref=f"{WALK}:56-59"),
        Fact("An unstable simulation subtracts 3.0 from the reward", source="upstream_code", ref=f"{WALK}:62-64"),
        Fact("The goal is met when the centre-of-mass x exceeds 99 voxel sizes and adds 1.0 to the reward",
             source="upstream_code", ref=f"{WALK}:67-69"),
        Fact("WalkingFlat.step returns five values and always reports truncated=False", source="upstream_code",
             ref=f"{WALK}:72"),
        Fact("WalkingFlat.reset calls the base reset and returns the observation with an empty info dict",
             source="upstream_code", ref=f"{WALK}:74-84"),
        Fact("EvoGymBase.reset ignores its seed and options arguments and resets the simulator",
             source="upstream_code", ref=f"{BASE}:65-69"),
        Fact("BenchmarkBase.VOXEL_SIZE is 0.1", source="upstream_code", ref=f"{BASE}:384"),
        Fact("The simulator runs physics_updates_per_step=30 updates per environment step", source="upstream_code",
             ref=f"{SIM}:23"),
        Fact("Each physics update integrates 0.0001 s with the RK4 integrator", source="upstream_code",
             ref=f"{ENVIRONMENT}:190"),
        Fact("The project's own test constructs an environment with gym.make(env_name, body=body)",
             source="upstream_code", ref="tests/screen_free/test_baseline_envs.py:29-30"),
        Fact("The Walker-v0 example supplies a body from sample_robot((5,5))", source="upstream_code",
             ref="examples/gym_test.py:8-9"),
        Fact("The voxel types define H_ACT as 3 and V_ACT as 4", source="upstream_code", ref=f"{UTILS}:8-15"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The contract of the analytic fake this package deploys, not of the upstream soft-body simulator.  The
    #: timestep is 30 RK4 updates of 0.0001 s (Sim.cpp:23, Environment.cpp:190); reset is full and no checkpoint
    #: method is exposed.
    fidelity = {
        "engine": "analytic:evogym Walker-v0 fake",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "the fake's transitions are deterministic and the upstream reset ignores seed and options "
                     "(base.py:65-69, walk.py:74-84), so a reset reproduces the same initial state with or without "
                     "a seed; the bridge still advertises cap.world.seed.v1 because the reset signature accepts "
                     "seed, but the value does not change the initial state or the fake trajectory",
        },
        "timestep_ms": 3.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no soft-body simulation: the C++ point-mass physics, actuator deformation, contacts, collisions, "
            "constraint solving and self-collision instability flag are not modelled",
            "the fake moves a single centre of mass at a placeholder gain from the mean clipped actuator value "
            "and holds four material points at fixed relative offsets; it is an F0 stand-in, not a re-implementation "
            "of the upstream dynamics",
            "the observation has 2 + 2*4 = 10 values (four placeholder material points); the upstream size is "
            "2 + num_robot_points (walk.py:34), where num_robot_points comes from the compiled simulator and the "
            "robot body, so the fake's array is a placeholder whose size is not the device's",
            "the fake's body is a placeholder 5x5 robot with one horizontal actuator; the upstream body is the "
            "required body argument of WalkingFlat.__init__ (walk.py:17-27) and may have any valid shape and "
            "actuator count, so the action width is a placeholder configuration, not a device property; the "
            "derived action bounds have fake provenance and no action_space_ref",
            "the fake applies the 500-step time limit that gymnasium.make adds to Walker-v0 (evogym/envs/"
            "__init__.py:19); WalkingFlat.step itself always returns truncated=False (walk.py:72)",
            "no sim backend is declared and the upstream environment was never run here: it needs Python <3.11, "
            "gymnasium, numpy<2.0.0 and the compiled evogym.simulator_cpp, and gym.make('Walker-v0') requires a "
            "robot body argument; package code never imports the clone",
            "the fake returns Python floats and lists; upstream returns NumPy arrays and declares its Box "
            "spaces with dtype=float (walk.py:36-37)",
            "no rendering and no snapshot or restore: the fake exposes no renderer or get_state/set_state",
            "no wall-clock pacing: realtime_factor is 0 and only ticks advance the 3 ms simulated timestep",
        ],
    }
