"""OpenMHS driver for gh.unrealzoo/unrealzoo-gym: the UnrealMujoco-Go1-v0 environment.

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the contract from the
environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{values: [...]}`` bounded per
element by ``Box(low=-1.0, high=1.0)`` (12 elements for Go1), ``cap.world.reset.v1`` takes ``{seed}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a
machine and no operator-required limit.

The upstream environment is not a passive simulator: ``UnrealCvMujocoEnv`` connects an UnrealCV client to a running
Unreal Engine process and sends ``vset`` commands over a socket (gym_unrealcv/envs/base_env_mujoco.py:230-231).  Neither
the Unreal Engine binary nor the ``gym``/``unrealcv`` packages are available where the gate runs, and package code never
imports or runs the clone, so the ``fake`` backend is the package's own pure Python kinematic stand-in for the Go1
environment (fake.py).  The ``sim`` backend is served by ``gym.make(env_id)`` (GymnasiumDriver.open_native); that path
needs the upstream package, gym 0.10.9, unrealcv and a packaged UnrealZoo environment and was not run here.  The gate
never installs or imports the upstream package (driver-authoring.md, section 6).

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002): every
member of ``device.schema.json`` that applies to a simulator without a physical counterpart, and the gaps say what the
fake does not model.  Every fact cites a line of the clone at the pinned commit
85f4b72e0ecd3c77f17fab161c3c8bdfdd86cf7c.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

MUJOCO = "gym_unrealcv/envs/mujoco.py"
BASE = "gym_unrealcv/envs/base_env_mujoco.py"
INIT = "gym_unrealcv/__init__.py"


class UnrealMujocoGo1(GymnasiumDriver):
    device_id = "unrealzoo-go1"
    env_id = "UnrealMujoco-Go1-v0"
    native = "gym_unrealcv.envs.mujoco:UnrealCvMujocoEnv"
    backends = {"fake": ".fake:FakeUnrealCvMujoco"}
    action_space_ref = f"{MUJOCO}:129-134"
    display_name = "UnrealZoo UnrealMujoco Go1 (UnrealCV MuJoCo simulation)"
    vendor, model = "UnrealZoo", "UnrealMujoco-Go1-v0"
    tags = ["unrealzoo", "unrealcv", "mujoco", "go1", "robot", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("The Go1 entry of ROBOT_SPECS declares an observation dimension of 48 and an action dimension of 12",
             source="upstream_code", ref=f"{MUJOCO}:13-14"),
        Fact("The action space is a Box with low -1.0 and high 1.0 for every element, shape (action_dim,) and "
             "dtype float32", source="upstream_code", ref=f"{MUJOCO}:129-134"),
        Fact("The observation space is a Box with low -inf and high inf, shape (observation_dim,) and dtype "
             "float32", source="upstream_code", ref=f"{MUJOCO}:135-140"),
        Fact("A step sends the action to the UnrealCV server and returns (observation, 0.0, False, info): the "
             "reward is always 0.0 and the environment signals neither termination nor truncation",
             source="upstream_code", ref=f"{MUJOCO}:388-393"),
        Fact("A reset sets steps to 0, clears last_action, rebuilds the robot state and returns the first "
             "observation", source="upstream_code", ref=f"{MUJOCO}:334-339"),
        Fact("UnrealCvMujocoEnv.reset takes no seed and no options parameter", source="upstream_code",
             ref=f"{MUJOCO}:314"),
        Fact("UnrealMujoco-Go1-v0 registers the entry point gym_unrealcv.envs:UnrealCvMujocoEnv with the robot "
             "keyword go1", source="upstream_code", ref=f"{INIT}:10-19"),
        Fact("The Go1 MuJoCo defaults are timestep 0.005 s and control_decimation 4", source="upstream_code",
             ref=f"{BASE}:15-18"),
        Fact("The control period is the physics timestep multiplied by control_decimation", source="upstream_code",
             ref=f"{BASE}:142-145"),
        Fact("The environment connects an unrealcv.Client to (host, port); it does not open a hardware device",
             source="upstream_code", ref=f"{BASE}:230-231"),
        Fact("The package dependencies pin gym 0.10.9 and unrealcv 1.3.2", source="upstream_code",
             ref="pyproject.toml:10-15"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the last observation stays readable")
    fidelity_level = "F0"
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: determinism kind and lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "unrealzoo-gym:UnrealMujoco-Go1-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "a seed passed to cap.world.reset.v1 reseeds the fake's initial joint offsets and repeats the "
                     "trajectory for the same seed and actions; the upstream reset takes no seed (mujoco.py:314), so "
                     "on the sim backend a seed only reaches legacy gym.Env.seed() and the upstream server decides "
                     "the initial state",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no rigid-body dynamics, contacts, friction or actuator model: the fake advances 12 joint positions "
            "kinematically by action times the 0.005 s * 4 control period, and the action is the normalised Box "
            "value, not a torque or a target the upstream server would accept",
            "the 48-element observation layout returned by the UnrealCV server is not reconstructed: the fake "
            "publishes the 12 joint positions, the 12 applied action values and 24 zeros, and was never compared "
            "with the upstream environment",
            "no episode or task logic from a packaged UnrealZoo environment is modelled; the reward is always 0.0 "
            "and the environment never terminates, matching UnrealCvMujocoEnv.step (mujoco.py:388)",
            "no Unreal Engine process, UnrealCV server, camera or rendering is modelled; the sim backend "
            "(gym.make with the upstream package and a running UnrealCV server) was not run",
            "no validation against hardware or against the upstream environment: the model has never been "
            "compared with a real UnrealZoo run",
        ],
    }
