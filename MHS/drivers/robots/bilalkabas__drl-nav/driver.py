"""OpenMHS driver for gh.bilalkabas/drl-nav: the AirSimDroneEnv corridor environment (a Gymnasium family driver).

The upstream class is a legacy ``gym.Env`` (``gym==0.21.0``) over a separately downloaded Windows
Unreal/AirSim scene.  It has no simulator inside the clone and the card's install command does not include
the AirSim runtime, so the package is checked on the fake backend only: ``fake.py`` is a pure Python
stand-in for the environment's interface (``scripts/airsim_env.py:11``), and it is not imported from the
clone.  A backend name that ``backends`` does not list (``sim``) is served by
``gymnasium.make(env_id, **env_kwargs)`` (``GymnasiumDriver.open_native``); that path needs the legacy gym
package and the Unreal scene, and was not run.

A GymnasiumDriver is configuration only: ``env_id`` names the upstream registration and the bridge derives
the contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action
``{values: [vy, vz]}`` bounded by ``Box(low=-0.6, high=0.6, shape=(2,))`` (``scripts/airsim_env.py:28-29``),
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is
simulated (R0): it has no hardware backend, no e-stop path to a machine and no operator-required limit.

The ``fidelity`` attribute describes the model as deployed (spec 05-fidelity FID-002): a kinematic corridor
stand-in, level F0, with every known omission in ``gaps``.  Every fact cites a line of the clone at the
pinned commit a996f5461c90adfe765ca3274d4da7c8499891c3.  This package is model-authored and unreviewed.
"""

from mhs.driver import Fact, GymnasiumDriver

AIRSIM_ENV = "scripts/airsim_env.py"
AIRSIM_CLIENT = "scripts/airsim/client.py"


class DrlNavAirSim(GymnasiumDriver):
    device_id = "drl-nav"
    env_id = "airsim-env-v0"
    # The bridge starts a new episode when a step follows a terminal state; AirSimDroneEnv itself expects
    # the caller to call reset() (scripts/airsim_env.py:42-45).
    autoreset = True
    native = "scripts.airsim_env:AirSimDroneEnv"
    backends = {"fake": ".fake:FakeAirSimDroneEnv"}
    action_space_ref = f"{AIRSIM_ENV}:28-29"
    display_name = "DRL-Nav AirSim corridor (legacy Gym environment)"
    vendor, model = "Bilal Kabas", "DRL-Nav"
    tags = ["drone", "uav", "navigation", "reinforcement-learning", "simulation", "airsim", "legacy-gym",
            "corridor"]
    facts = [
        Fact("AirSimDroneEnv is a gym.Env subclass; its constructor takes ip_address, image_shape, env_config "
             "and input_mode and connects an airsim.MultirotorClient to ip_address", source="upstream_code",
             ref=f"{AIRSIM_ENV}:11-17"),
        Fact("The action space is a two-element Box with low -0.6, high 0.6 and dtype float32", source="upstream_code",
             ref=f"{AIRSIM_ENV}:28-29"),
        Fact("The observation space is Box(0, 255) with dtype uint8; for multi_rgb its shape is "
             "(image_shape[0], image_shape[1]*3, 1), otherwise image_shape", source="upstream_code",
             ref=f"{AIRSIM_ENV}:19-26"),
        Fact("The environment is registered as airsim-env-v0 with entry point scripts:AirSimDroneEnv",
             source="upstream_code", ref="scripts/__init__.py:5-8"),
        Fact("step calls do_action, get_obs and compute_reward and returns the legacy four values obs, reward, "
             "done, info", source="upstream_code", ref=f"{AIRSIM_ENV}:36-40"),
        Fact("do_action sends moveByVelocityBodyFrameAsync(0.4, action[0], action[1], duration=1) and then "
             "moveByVelocityAsync(0, 0, 0, duration=1)", source="upstream_code", ref=f"{AIRSIM_ENV}:87-91"),
        Fact("The AirSim duration argument is in seconds", source="upstream_code", ref=f"{AIRSIM_CLIENT}:1027"),
        Fact("setup_flight resets the drone, enables API control, arms it, commands moveToZAsync(-1, 1), stores "
             "the collision timestamp, chooses a random section, and sets the pose with y_pos and z_pos from "
             "((np.random.rand(1,2)-0.5)*2)", source="upstream_code", ref=f"{AIRSIM_ENV}:50-76"),
        Fact("The alignment reward is exp(-target_dist_curr_3d)*30; a collision or a lost hole gives -100 and "
             "done, and travelling more than 3.7 gives done", source="upstream_code", ref=f"{AIRSIM_ENV}:122-148"),
        Fact("is_collision compares the current simGetCollisionInfo().time_stamp with the timestamp stored at "
             "setup", source="upstream_code", ref=f"{AIRSIM_ENV}:152-154"),
        Fact("get_obs for depth requests a DepthPerspective image, clips values above 3.4 and scales the clipped "
             "value by 255/3.4", source="upstream_code", ref=f"{AIRSIM_ENV}:111-113"),
        Fact("The README gives the input sizes as 50 x 50 x 1 for depth, 50 x 50 x 3 for single RGB and "
             "50 x 150 x 1 for stacked gray", source="vendor_doc", ref="README.md:30-32"),
        Fact("The README says the project currently runs only on Windows because the Unreal environments are "
             "packaged for Windows", source="vendor_doc", ref="README.md:8"),
        Fact("The README says the training scene is a separately downloaded TrainEnv.zip and its executable "
             "must be opened before training", source="vendor_doc", ref="README.md:165-171"),
        Fact("The pinned requirements use gym==0.21.0", source="upstream_code", ref="requirements.txt:11"),
        Fact("config.yml sets train_mode and test_mode to multi_rgb", source="upstream_code", ref="config.yml:1-3"),
        Fact("train.py builds image_shape (50,50,1) for depth and (50,50,3) otherwise and calls "
             "gym.make('scripts:airsim-env-v0', ip_address='127.0.0.1', image_shape=..., env_config=..., "
             "input_mode=...)", source="upstream_code", ref="train.py:21-33"),
        Fact("The README's settings.json configures a 50 x 50 camera with FOV_Degrees 120 and ClockSpeed 40",
             source="vendor_doc", ref="README.md:119-158"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The model as deployed on the fake backend (spec 05-fidelity section 2).  The fake is a kinematic
    #: corridor stand-in, not the Unreal/AirSim rigid-body model, so it claims F0 and says what it omits.
    fidelity = {
        "engine": "analytic:drl-nav-corridor",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake draws its initial y and z from random.Random(seed) and its transitions are "
                     "deterministic, so reset(seed) or cap.world.seed.v1 repeats a trajectory on the fake; the "
                     "upstream reset takes no seed and the external AirSim scene was not run",
        },
        "timestep_ms": 1000.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a kinematic corridor stand-in: positions advance by the commanded body-frame velocity "
            "for the 1 s command period, with no Unreal renderer, no AirSim physics, no contacts and no "
            "actuator, sensor or noise model",
            "the upstream environment runs only on Windows and needs the separately downloaded TrainEnv.zip "
            "Unreal/AirSim executable (README.md:8 and :165-171); the sim backend was not run and the fake was "
            "never compared with the upstream scene",
            "the observation is the configured 50 x 50 x 1 depth array (train.py:22-24), but the fake paints a "
            "synthetic depth grid with a target marker instead of rendering the Unreal camera",
            "the AirSim physics timestep is not in the clone; one tick is one 1 s velocity command "
            "(scripts/airsim_env.py:87-88), so timestep_ms describes the fake's command period only",
            "no snapshot or restore: AirSimDroneEnv exposes no get_state or set_state",
            "the fake accepts reset options start, target and sections for deterministic tests; "
            "AirSimDroneEnv.reset takes no options (scripts/airsim_env.py:42-45)",
            "the bridge is configured autoreset=True, so a step after a terminal state starts a new episode; "
            "AirSimDroneEnv itself expects the caller to call reset()",
        ],
    }
