"""OpenMHS driver for gh.kjell-k/airgym: the AirSim quadrotor environment (a Gymnasium family driver).

``gym_airsim.envs.AirGym:AirSimEnv`` is a legacy OpenAI Gym environment: it defines ``_reset``/``_step`` over the old
Gym API, a ``Discrete(3)`` action space (straight, yaw right, yaw left) and a 30 x 100 depth observation
(AirGym.py:24-27).  The family bridge serves it as ``cap.world.step.v1`` (``{ticks, action}`` with ``action.index``
bounded to 0..2 from the action space), ``cap.world.reset.v1`` (``{seed, options}``) and ``cap.world.seed.v1``
(``{seed}``).  The device is simulated (R0): there is no hardware backend and no e-stop path to a machine.

The gate cannot import the clone (it needs AirSim, gym, numpy, cv2, eventlet and PIL) and package code never imports
it.  The ``fake`` backend is this package's pure Python kinematic stand-in (fake.py); it is the only backend that was
run.  The clone has no active Gym registration (gym_airsim/__init__.py:1-7), so no ``sim`` env_id is set: the ``sim``
backend would need a registered environment and the AirSim RPC server at 127.0.0.1:41451 (AirSimClient.py:426-430).

The ``fidelity`` attribute is the contract of the model as deployed: a kinematic, analytic environment with no
AirSim physics, collision or camera model.  Every constant and rule cites a line of the clone at the pinned commit
(818749ab1e93f41e1f1cf62a98f15ee9e4461568).  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

AIRGYM = "gym_airsim/envs/AirGym.py"
CLIENT = "gym_airsim/envs/myAirSimClient.py"
README = "README.md"


class AirGym(GymnasiumDriver):
    device_id = "airgym"
    native = "gym_airsim.envs.AirGym:AirSimEnv"
    backends = {"fake": ".fake:FakeAirSimEnv"}
    action_space_ref = f"{AIRGYM}:27"
    display_name = "AirGym AirSim quadrotor environment (simulated)"
    vendor, model = "Kjell Kersandt", "AirSimEnv"
    tags = ["airsim", "quadrotor", "depth-camera", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("AirSimEnv is the Gym environment class a user instantiates; it derives from gym.Env and uses gym "
             "spaces", source="upstream_code", ref=f"{AIRGYM}:18-27"),
        Fact("The observation space is a Box with low 0, high 255 and shape (30, 100); the state starts as uint8 "
             "zeros of the same shape", source="upstream_code", ref=f"{AIRGYM}:24-25"),
        Fact("The action space is Discrete(3)", source="upstream_code", ref=f"{AIRGYM}:27"),
        Fact("The flight goal is global xy (221.0, -9.0)", source="upstream_code", ref=f"{AIRGYM}:29"),
        Fact("The distance log starts at 221 and the track log at -2 for every episode", source="upstream_code",
             ref=f"{AIRGYM}:35-38"),
        Fact("The environment uses the legacy Gym methods _step and _reset, not the current Gymnasium reset/step API",
             source="upstream_code", ref=f"{AIRGYM}:75-127"),
        Fact("A step asserts the action is in the action space, forwards it to airgym.take_action, then reads "
             "getPosition and goal_direction", source="upstream_code", ref=f"{AIRGYM}:75-85"),
        Fact("The distance reward is -1 plus the distance closed since the previous step (distance_before - "
             "distance_now)", source="upstream_code", ref=f"{AIRGYM}:60-70"),
        Fact("A collision ends the episode with reward -100; the code also ends it with reward 0 when take_action "
             "returns 99", source="upstream_code", ref=f"{AIRGYM}:87-94"),
        Fact("Reaching within 3 of the goal ends the episode with reward 100", source="upstream_code",
             ref=f"{AIRGYM}:99-102"),
        Fact("A cumulative reward below -100 ends the episode", source="upstream_code", ref=f"{AIRGYM}:109-112"),
        Fact("A step returns the depth observation, reward, done and an info object with x_pos and y_pos",
             source="upstream_code", ref=f"{AIRGYM}:117-120"),
        Fact("A reset calls AirSim_reset, clears the logs and returns the depth observation", source="upstream_code",
             ref=f"{AIRGYM}:134-150"),
        Fact("The depth observation is 10 goal-direction rows on top of 20 depth rows, 100 columns wide, and the "
             "goal line is mapped from track over -180..180 onto 0..100", source="upstream_code",
             ref=f"{CLIENT}:137-153"),
        Fact("The depth image comes from AirSim's DepthPerspective camera, inverted and gamma-corrected with factor "
             "10 before resizing", source="upstream_code", ref=f"{CLIENT}:121-139"),
        Fact("Action 0 flies straight for 1 s at 4 m/s, action 1 yaws right for 0.8 s, action 2 yaws left for 1 s",
             source="upstream_code", ref=f"{CLIENT}:70-102"),
        Fact("straight moves along the current heading at the requested speed with moveByVelocityZ at z=-6",
             source="upstream_code", ref=f"{CLIENT}:31-39"),
        Fact("yaw_right commands 30 deg/s and yaw_left commands -30 deg/s", source="upstream_code",
             ref=f"{CLIENT}:41-49"),
        Fact("The README documents the three actions as straight 4 m/s for 1 s, right yaw 26 deg/s for 1 s and left "
             "yaw 30 deg/s for 1 s", source="vendor_doc", ref=f"{README}:34-38"),
        Fact("MultirotorClient defaults the AirSim address to 127.0.0.1 and passes port 41451 to AirSimClientBase",
             source="upstream_code", ref="AirSimClient.py:426-430"),
        Fact("AirSimClientBase opens a msgpackrpc Client to that address and port", source="upstream_code",
             ref="AirSimClient.py:148-150"),
        Fact("The README says the repository is not maintained anymore and new AirSim versions are very likely "
             "incompatible", source="vendor_doc", ref=f"{README}:1"),
        Fact("The Gym registration of AirSimEnv-v42 is commented out; the module only imports register",
             source="upstream_code", ref="gym_airsim/__init__.py:1-7"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime refuses every step and reset until "
                  "mhs.safety.reset clears the latch, and the last observation stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  One step is one action interval
    #: of 1 s (README.md:35-38); the fake integrates the action durations of myAirSimClient.py:70-102 and nothing else.
    fidelity = {
        "engine": "airsim-gym:AirSimEnv",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "on the fake backend, reset(seed) selects the placeholder depth texture, so one seed and action "
                     "sequence repeats a trajectory; the upstream AirGym._seed only initialises np_random "
                     "(AirGym.py:41-49) and no code reads it, so the real AirSim simulation is not driven by this "
                     "seed.  The fake is the only backend that was run",
        },
        "timestep_ms": 1000.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic/analytic stand-in only: it integrates straight motion at 4 m/s and yaw at 30 deg/s for the "
            "durations of myAirSimClient.py:70-102; it models no AirSim physics, no contact, no actuator, no sensor "
            "or noise model and no obstacle",
            "no collision: take_action never reports has_collided, while the upstream polls getCollisionInfo() "
            "during every action (myAirSimClient.py:74-99); collision termination is therefore not exercised",
            "the 30 x 100 observation is a placeholder image: 10 goal-direction rows over 20 synthetic depth rows "
            "(the shape of myAirSimClient.py:141-153), not AirSim's DepthPerspective camera image; the depth rows "
            "are a fixed per-episode texture and do not change as the drone moves, while only the goal-direction "
            "line follows the yaw",
            "the reset options object is accepted by the bridge and ignored, because AirSimEnv._reset takes no "
            "arguments (AirGym.py:127); only the seed affects the fake",
            "the seed only drives the fake's placeholder depth texture; the real AirSim simulation is external and "
            "was never started, so the upstream environment was not compared with this fake",
            "no wall-clock pacing: realtime_factor 0, and the fake does not reproduce the time.sleep and blocking "
            "waits of myAirSimClient.py:54-102 and :161-169",
            "snapshot and restore are not offered: AirSimEnv exposes no get_state/set_state",
        ],
    }
