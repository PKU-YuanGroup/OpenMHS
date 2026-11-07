"""OpenMHS driver for gh.farama-foundation/metaworld: the assembly-v3 Sawyer task (a Gymnasium family driver).

A ``GymnasiumDriver`` is configuration only: ``env_id`` names a registered environment and the bridge derives the
contract from the environment's spaces.  This package serves one Meta-World task, ``assembly-v3``
(``SawyerNutAssemblyEnvV3``), through the single-environment registration ``Meta-World/goal_observable``
(metaworld/__init__.py:696-706); the environment is built with ``env_kwargs`` naming the task and its construction
seed.  The bridge publishes ``cap.world.step.v1`` (a 4-element Box action in ``{-1, 1}``), ``cap.world.reset.v1``
and ``cap.world.seed.v1``.  The device is simulated (R0): no hardware backend exists and no operator-required bound is
declared.

The gate does not install metaworld, MuJoCo or numpy (metaworld/pyproject.toml), and package code never imports the
clone.  The ``fake`` backend is therefore a pure-Python stand-in for the upstream class (see fake.py); a backend
name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id, **env_kwargs)`` through
``GymnasiumDriver.open_native``.  That path needs the upstream package and a registered Meta-World install and was
not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
every member of ``device.schema.json`` that applies to a simulator without a physical counterpart.  Every constant
and rule cites a line of the clone at the pinned commit (c0dafaf1557f31cad3b96ba2b62462f45638f5a5).  This package
is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "metaworld/envs/sawyer_assembly_peg_v3.py"
BASE = "metaworld/sawyer_xyz_env.py"
SCENE = "metaworld/assets/scene/basic_scene.xml"
INIT = "metaworld/__init__.py"
DICT = "metaworld/env_dict.py"


class MetaWorldAssembly(GymnasiumDriver):
    device_id = "metaworld-assembly-v3"
    env_id = "Meta-World/goal_observable"
    env_kwargs = {"env_name": "assembly-v3", "seed": 0}
    seed = 0
    native = "metaworld.envs.sawyer_assembly_peg_v3:SawyerNutAssemblyEnvV3"
    backends = {"fake": ".fake:FakeSawyerNutAssemblyEnvV3"}
    action_space_ref = f"{BASE}:239-243"
    display_name = "Meta-World assembly-v3 (Sawyer nut assembly, simulated)"
    vendor, model = "Farama Foundation", "Meta-World assembly-v3"
    tags = ["metaworld", "assembly-v3", "sawyer", "robotics", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The action space is a 4-element Box with each element from -1 to +1", source="upstream_code",
             ref=f"{BASE}:239-243"),
        Fact("step() requires a 4-element action, applies its first three elements through set_xyz_action and the "
             "last element through do_simulation", source="upstream_code", ref=f"{BASE}:580-596"),
        Fact("set_xyz_action clips every axis to [-1, 1] and multiplies it by action_scale before moving the mocap "
             "body", source="upstream_code", ref=f"{BASE}:320-336"),
        Fact("action_scale is 1.0 / 100 by default", source="upstream_code", ref=f"{BASE}:175-183"),
        Fact("The observation is one flat 39-element array that concatenates the current state, the previous state "
             "and the goal position", source="upstream_code", ref=f"{BASE}:513-527"),
        Fact("The 18-element current state is the hand position (3), the gripper distance clipped to 0..1 and 14 "
             "padded object values", source="upstream_code", ref=f"{BASE}:475-511"),
        Fact("step() returns (observation, reward, terminated, truncated, info), terminated is always False and "
             "truncated becomes True at curr_path_length == max_path_length", source="upstream_code",
             ref=f"{BASE}:631-642"),
        Fact("max_path_length is 500 steps by default", source="upstream_code", ref=f"{BASE}:153-154"),
        Fact("frame_skip is 5 by default", source="upstream_code", ref=f"{BASE}:175-183"),
        Fact("step() advances self.frame_skip MuJoCo frames per environment step", source="upstream_code",
             ref=f"{BASE}:591-596"),
        Fact("The MuJoCo scene physics timestep is 0.0025 s", source="upstream_code", ref=f"{SCENE}:2"),
        Fact("SawyerXYZEnv.reset(seed, options) ignores both arguments and resets curr_path_length to 0",
             source="upstream_code", ref=f"{BASE}:664-682"),
        Fact("seed(seed) seeds np_random and the action, observation and goal spaces", source="upstream_code",
             ref=f"{BASE}:275-290"),
        Fact("Meta-World/goal_observable is registered with an entry_point that selects the observable-goal class "
             "for env_name and passes seed=seed", source="upstream_code", ref=f"{INIT}:696-706"),
        Fact("assembly-v3 maps to SawyerNutAssemblyEnvV3", source="upstream_code", ref=f"{DICT}:26-27"),
        Fact("The goal_observable constructor seeds numpy before construction and calls env.seed(seed) after the "
             "first reset when a seed is given", source="upstream_code", ref=f"{DICT}:184-199"),
        Fact("reward_function_version is v2 by default", source="upstream_code", ref=f"{ENV}:19-24"),
        Fact("A successful assembly scores a reward of 10.0", source="upstream_code", ref=f"{ENV}:196-228"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "mujoco:metaworld/SawyerNutAssemblyEnvV3",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "assembly-v3 is seeded at construction: Meta-World/goal_observable passes env_kwargs seed 0 "
                     "into the wrapper, which seeds numpy before the scene is built and calls env.seed(seed) "
                     "(metaworld/env_dict.py:184-199).  SawyerXYZEnv.reset ignores its seed argument "
                     "(metaworld/sawyer_xyz_env.py:664-682), so cap.world.seed and the seed of cap.world.reset are "
                     "recorded by the bridge but cannot reseed the upstream environment.  The fake is a fixed, "
                     "deterministic stand-in and does not reseed either.",
        },
        "timestep_ms": 2.5,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the F1 claim is the MuJoCo rigid-body scene of the task; there is no validated actuator, sensor or "
            "noise model and no hardware counterpart was measured",
            "the physics timestep is 2.5 ms (basic_scene.xml:2) but step() advances frame_skip=5 frames, so one "
            "cap.world.step.v1 tick is a 12.5 ms control period; timestep_ms names the physics timestep (FID-015)",
            "no wall-clock pacing: realtime_factor 0, only commands advance simulated time",
            "the fake backend is a pure-Python kinematics stand-in: it has no contacts, rigid-body dynamics, "
            "gripper or object motion, and was not compared with the upstream environment (metaworld, MuJoCo and "
            "numpy are not installed where the gate runs); it returns the declared 39-element observation",
            "reset() ignores its seed argument upstream, so the bridge's seed control does not reseed the "
            "environment (see determinism.notes)",
            "snapshot_restore is false: the environment has get_env_state/set_env_state, not the get_state/"
            "set_state pair the Gymnasium bridge snapshots",
        ],
    }
