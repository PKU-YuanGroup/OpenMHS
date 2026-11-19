"""OpenMHS driver for gh.gensim2/gensim2: the GenSim2 SAPIEN task environment (a Gymnasium family driver).

``gensim2.env.create_task.create_gensim`` builds a ``SapienEnv``, instantiates the requested task class and returns
``gensim2.env.wrappers.GenSimTaskWrapper``.  The wrapper exposes the legacy Gym API (``reset(random)`` returns the
observation; ``step(action)`` returns ``obs, reward, done, info``) over an eight-value action and a fifteen-value
state observation.  This package serves that step interface as ``cap.world.step.v1`` / ``cap.world.reset.v1`` /
``cap.world.seed.v1``.  It is a simulation (R0): there is no hardware backend and no physical e-stop path.

Two backends are declared.  ``fake`` is the package's pure-Python kinematic stand-in (``fake.py``), which the gate
exercises.  ``sim`` is the real environment factory (``fake.py:make_env``), which imports the installed upstream package and
needs ``gym``, ``sapien==2.2.2``, a CUDA-capable SAPIEN renderer and the asset tree; it was not run here and the gate
never calls it. The live path is blocked pending a lifecycle adapter: upstream wrapper.close calls task.close,
which the shipped task/base classes do not implement, and construction/reset print to stdout. The fidelity
contract describes the fake backend as deployed (F0, kinematic); the
``sim`` entry of ``fidelity_by_backend`` describes the SAPIEN environment (F1).

This package is model-authored and unreviewed.  It is checked on the fake backend only; no hardware was attached and
no real ROS, SAPIEN or device run is claimed.
"""

from mhs.driver import Fact, GymnasiumDriver

WRAPPER = "gensim2/env/wrappers.py"
BASE = "gensim2/env/base/base_env.py"
SIM = "gensim2/env/sapien/sim.py"
CREATE = "gensim2/env/create_task.py"


class GenSim2Env(GymnasiumDriver):
    device_id = "gensim2"
    env_id = None
    native = "gensim2.env.wrappers:GenSimTaskWrapper"
    backends = {"fake": ".fake:FakeGenSimTaskEnv", "sim": ".fake:make_env"}
    action_space_ref = f"{BASE}:329"
    display_name = "GenSim2 SAPIEN task environment"
    vendor, model = "GenSim2 authors", "GenSim2 / SAPIEN"
    tags = ["gensim2", "sapien", "manipulation", "simulation", "gymnasium", "reinforcement-learning"]
    facts = [
        Fact("create_gensim builds a SapienEnv with create_sapien", source="upstream_code", ref=f"{CREATE}:10"),
        Fact("create_gensim instantiates the named task class and returns GenSimTaskWrapper", source="upstream_code",
             ref=f"{CREATE}:20-21"),
        Fact("The factory's __main__ example calls create_gensim with TurnOnFaucet and a second argument Sapien", source="upstream_code",
             ref=f"{CREATE}:24-25"),
        Fact("GenSimTaskWrapper delegates reset(random) to task.reset(random)", source="upstream_code",
             ref=f"{WRAPPER}:112-113"),
        Fact("GenSimTaskWrapper.step calls task.env.step and returns obs, reward, done, info (the legacy four-value "
             "Gym tuple)", source="upstream_code", ref=f"{WRAPPER}:66-110"),
        Fact("The reward is task.get_reward(); an exception in that call is replaced by reward 0",
             source="upstream_code", ref=f"{WRAPPER}:69-72"),
        Fact("The wrapper sets done when the task reports success (unless whole_eps) and calls reset_internal when "
             "done", source="upstream_code", ref=f"{WRAPPER}:79-94"),
        Fact("The environment step calls step_action, sim_step, get_observation, is_done and get_info and returns "
             "obs, done, info", source="upstream_code", ref=f"{BASE}:244-276"),
        Fact("is_done is current_step >= horizon", source="upstream_code", ref=f"{BASE}:101-102"),
        Fact("horizon is 50 control steps and action_dim is 8", source="upstream_code", ref=f"{BASE}:111-117"),
        Fact("The action space is Box(low=-1, high=1, shape=(action_dim,))", source="upstream_code",
             ref=f"{BASE}:327-329"),
        Fact("The simulator sets _sim_freq=100, _sim_steps_per_control=80 and dt=_sim_steps_per_control/_sim_freq",
             source="upstream_code", ref=f"{SIM}:80-84"),
        Fact("sim_step executes _sim_steps_per_control scene steps and increments current_step once",
             source="upstream_code", ref=f"{SIM}:221-226"),
        Fact("The state observation is 15 float32 values: end-effector position (3), end-effector quaternion (4) and "
             "the first 8 joint positions", source="upstream_code", ref=f"{BASE}:304-319"),
        Fact("The action's first three values are the target end-effector position, elements 3:7 are the quaternion "
             "for an eight-value action, and the last value is the gripper command", source="upstream_code",
             ref=f"{BASE}:209-220"),
        Fact("Seeding replaces the environment's np_random generator and returns [seed]", source="upstream_code",
             ref=f"{BASE}:76-78"),
        Fact("The wrapper's seed delegates to task.env.seed", source="upstream_code", ref=f"{WRAPPER}:130-131"),
        Fact("The wrapper's close delegates to task.close", source="upstream_code", ref=f"{WRAPPER}:127-128"),
        Fact("GenSimBaseEnv subclasses gym.Env", source="upstream_code",
             ref=f"{BASE}:21"),
        Fact("set_gripper writes int(openness) * 0.04 as the target of each of the last two active joints",
             source="upstream_code", ref="gensim2/env/sapien/env.py:424-435"),
        Fact("GenSimBaseTask.reset_objects prints the selected Asset ID", source="upstream_code",
             ref="gensim2/env/base/base_task.py:108"),
    ]
    safe_state = ("the software latch refuses further step, reset and seed calls until mhs.safety.reset; "
                  "cached world state stays readable and latch reset advances nothing; the latch does not "
                  "interrupt an in-flight SAPIEN planner or certify a native stop; no hardware path is served")
    #: The deployed fake is an analytic kinematic stand-in (F0): it is not the SAPIEN physics simulation, and its
    #: initial pose, target pose and joint values are placeholders.  The sim backend's entry describes the upstream
    #: environment; it needs the upstream install and was not run here.
    fidelity_by_backend = {
        "fake": {
            "engine": "gensim2:analytic-fake",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "seeded",
                "seed_control": "parameter",
                "notes": "the standalone fake seed() controls its placeholder generator, but native reset accepts "
                         "only random=False. The bridge's legacy fallback calls seed(seed), then reset() and "
                         "discards options; protocol resets use the default placeholder pose. This is not a "
                         "claim of reproducible randomized resets in the upstream tasks",
            },
            "timestep_ms": 800.0,
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": False,
            "gaps": [
                "kinematic stand-in: the end-effector moves a fixed fraction toward the commanded pose and no "
                "forces, contacts, planning, collisions or dynamics are simulated",
                "the start pose, target pose, joint values and move fraction are placeholders, not values read from "
                "an upstream task or asset",
                "no camera, point cloud, depth, renderer or image observation is produced; the state observation is "
                "the only observation mode",
                "the task progress, reward and all_done flags are a one-stage reach model, not the multi-stage "
                "success criteria of the upstream tasks",
                "the upstream planner's per-control path can execute additional physics steps, so one upstream "
                "control step is not exactly the declared 800 ms; the fake advances one fixed 800 ms control step",
                "the fake reset signature matches wrappers.py:112: options['random'] is ignored by the bridge's "
                "legacy fallback; the earlier fake-only seeded random-reset behavior was not an upstream behavior",
                "fake close only marks the stand-in closed; the real wrapper calls task.close (wrappers.py:127-128), "
                "which the shipped task/base classes do not implement. A lifecycle adapter is required before "
                "the declared sim backend can be accepted",
            ],
        },
        "sim": {
            "engine": "gensim2:sapien",
            "fidelity_level": "F1",
            "determinism": {
                "kind": "seeded",
                "seed_control": "parameter",
                "notes": "env.seed sets np_random, but the task's random pose and openness sampling uses the global "
                         "numpy generator (gensim2/env/utils/pose.py:294 and :335), so cap.world.seed.v1 does not make a random reset "
                         "reproducible; the physics engine and planner are not claimed bit-reproducible",
            },
            "timestep_ms": 800.0,
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": False,
            "gaps": [
                "the upstream SAPIEN environment was not constructed or run in this package; it needs gym, "
                "sapien==2.2.2, a CUDA-capable renderer and the asset tree",
                "the declared sim backend is blocked: GenSimTaskWrapper.close calls task.close, absent from the "
                "shipped tasks and GenSimBaseTask. Construction and resets also print to stdout (sim.py:21-26, "
                "base_task.py:108), which needs isolation from an MHS stdio stream",
                "the legacy wrapper accepts reset(random=False), not seed/options; the bridge seeds separately "
                "and discards options. A random option does not reach the upstream task",
                "move_to_pose returns False on a planning exception or non-Success status (base_env.py:224-232), "
                "but step_action/step continue and the wrapper replaces reward errors with zero. A completed "
                "world step does not prove the requested end-effector pose was reached",
                "the software latch cannot interrupt a planner call already running; a compatible lifecycle/stop "
                "adapter must be reviewed before live use",
                "the separate panda_py/libfranka hardware initialization in gensim2/agent/utils/init_panda.py "
                "is outside create_gensim and is not served by this simulation package",
                "the planner may add physics steps inside one control call; 800 ms is the declared control period, "
                "not a measured duration",
                "contact, friction, actuator and sensor fidelity are the SAPIEN engine's; no contact or actuator "
                "parameters were validated against a physical robot",
                "no validation against a physical device is claimed",
            ],
        },
    }
