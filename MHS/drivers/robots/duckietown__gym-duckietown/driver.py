"""OpenMHS driver for gh.duckietown/gym-duckietown: the MultiMap-v0 simulator (a Gymnasium family driver).

The card's entry symbols are ``gym_duckietown.envs:MultiMapEnv`` and ``gym_duckietown.envs:DuckiebotEnv``.
This package serves the simulator, ``MultiMapEnv``: it builds one ``DuckietownEnv`` for each of two map files and
advances to the next environment on every reset (multimap_env.py:17-26, :44-49).  ``DuckiebotEnv`` is the ZMQ client
of a real Duckiebot and is not served here; it is a hardware path that needs the robot (duckiebot_env.py:46-73).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the whole contract
from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{values: [vel,
angle]}``, a velocity and a steering angle that ``DuckietownEnv.step`` converts to the two wheel commands
(duckietown_env.py:36-63), bounded by ``Box(low=[-1, -1], high=[1, 1])`` (duckietown_env.py:19); ``cap.world.reset.v1``
takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The simulator is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required bound.

The gate cannot import the clone (the upstream package needs gym, numpy<=1.20, pyglet, OpenGL and Duckietown's world
packages), so the ``fake`` backend is the package's own pure Python stand-in.  A backend name that ``backends`` does
not list (``sim``) would be served by ``gym.make("MultiMap-v0")`` (GymnasiumDriver.open_native); that path needs the
upstream packages and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
every member of ``device.schema.json`` that applies to a simulator without a physical counterpart.  Every constant,
rule and gap cites a line of the clone at the pinned commit (c76a7fec7f739db4f624f40ca83ce99383665558).  This package
is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

MULTIMAP = "src/gym_duckietown/envs/multimap_env.py"
DUCKIETOWN = "src/gym_duckietown/envs/duckietown_env.py"
SIMULATOR = "src/gym_duckietown/simulator.py"
DUCKIEBOT = "src/gym_duckietown/envs/duckiebot_env.py"
PACKAGE = "src/gym_duckietown/__init__.py"


class MultiMap(GymnasiumDriver):
    device_id = "duckietown-multimap"
    env_id = "MultiMap-v0"
    native = "gym_duckietown.envs:MultiMapEnv"
    backends = {"fake": ".fake:FakeMultiMapEnv"}
    action_space_ref = f"{DUCKIETOWN}:19"
    display_name = "Gym-Duckietown MultiMap-v0 (two-map camera simulator)"
    vendor, model = "Duckietown", "MultiMap-v0"
    tags = ["duckietown", "multimap", "camera", "differential-drive", "simulation", "gym"]
    facts = [
        Fact("MultiMapEnv builds one DuckietownEnv for each of the two maps loop_only_duckies and "
             "small_loop_only_duckies", source="upstream_code", ref=f"{MULTIMAP}:17-20"),
        Fact("MultiMapEnv copies the action space, observation space and reward range of the DuckietownEnv it built",
             source="upstream_code", ref=f"{MULTIMAP}:22-24"),
        Fact("Every reset advances cur_env_idx to the next environment and resets that environment",
             source="upstream_code", ref=f"{MULTIMAP}:44-49"),
        Fact("step delegates to the current environment, adds the reward and the step count to the totals, and "
             "clears the totals when the episode is done", source="upstream_code", ref=f"{MULTIMAP}:51-65"),
        Fact("seed seeds every environment and the environment's np_random, and returns [seed]",
             source="upstream_code", ref=f"{MULTIMAP}:34-42"),
        Fact("The step_count property returns the step count of the current environment",
             source="upstream_code", ref=f"{MULTIMAP}:88-90"),
        Fact("DuckietownEnv is a wrapper that controls the simulator with a velocity and a steering angle instead of "
             "differential drive motor velocities", source="upstream_code", ref=f"{DUCKIETOWN}:9-13"),
        Fact("DuckietownEnv sets the action space to Box(low=[-1, -1], high=[1, 1], dtype=float32)",
             source="upstream_code", ref=f"{DUCKIETOWN}:19"),
        Fact("DuckietownEnv.step reads the action as vel and angle, computes the two motor rotation rates from them "
             "and the wheel distance, converts those to duty cycles limited to [-limit, limit] and passes "
             "[left, right] to Simulator.step", source="upstream_code", ref=f"{DUCKIETOWN}:36-63"),
        Fact("The observation space is Box(low=0, high=255, shape=(camera_height, camera_width, 3), dtype=uint8): "
             "an RGB camera image", source="upstream_code", ref=f"{SIMULATOR}:315-320"),
        Fact("The default camera size is 640 by 480 pixels", source="upstream_code", ref=f"{SIMULATOR}:103-105"),
        Fact("The observation is the image rendered from the agent's camera", source="upstream_code",
             ref=f"{SIMULATOR}:1953-1960"),
        Fact("The simulator's default frame rate is 30", source="upstream_code", ref=f"{SIMULATOR}:165"),
        Fact("delta_time is 1.0 / frame_rate", source="upstream_code", ref=f"{SIMULATOR}:299-300"),
        Fact("The reward range is -1000 to 1000", source="upstream_code", ref=f"{SIMULATOR}:322"),
        Fact("The default max_steps is 1500", source="upstream_code", ref=f"{SIMULATOR}:167"),
        Fact("Simulator.step clips its action to [-1, 1] before applying it", source="upstream_code",
             ref=f"{SIMULATOR}:1670"),
        Fact("update_physics increments step_count and advances timestamp by delta_time", source="upstream_code",
             ref=f"{SIMULATOR}:1561-1562"),
        Fact("An in-progress reward is speed * dot_dir - 10 * abs(lane distance) + 40 * collision penalty",
             source="upstream_code", ref=f"{SIMULATOR}:1666"),
        Fact("An invalid pose terminates the episode and returns REWARD_INVALID_POSE",
             source="upstream_code", ref=f"{SIMULATOR}:1687-1692"),
        Fact("REWARD_INVALID_POSE is -1000", source="upstream_code", ref=f"{SIMULATOR}:175"),
        Fact("Reaching max_steps terminates the episode with reward 0", source="upstream_code",
             ref=f"{SIMULATOR}:1694-1699"),
        Fact("MultiMap-v0 is registered with entry point gym_duckietown.envs:MultiMapEnv and reward_threshold 400",
             source="upstream_code", ref=f"{PACKAGE}:48"),
        Fact("Duckiebot-v0 is registered with entry point gym_duckietown.envs:DuckiebotEnv", source="upstream_code",
             ref=f"{PACKAGE}:50"),
        Fact("DuckiebotEnv is the environment that is the actual real robot", source="upstream_code",
             ref=f"{DUCKIEBOT}:46-47"),
        Fact("DuckiebotEnv connects a ZMQ PAIR socket to the bridge node at serverAddr:serverPort",
             source="upstream_code", ref=f"{DUCKIEBOT}:73-78"),
        Fact("DuckiebotEnv sends each action over that socket as a JSON command", source="upstream_code",
             ref=f"{DUCKIEBOT}:132-133"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the simulator state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gym-duckietown:MultiMap-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "a reset seed fixes the initial pose and the domain-randomization draws, and the pose update is "
                     "deterministic, so one implementation repeats a trajectory for the same seed and actions; the "
                     "fake draws with Python's random.Random and upstream with numpy's RandomState, so a seed gives "
                     "different trajectories on the two",
        },
        "timestep_ms": 1000.0 / 30.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic differential-drive pose integration with geometric collision checks only: no force, "
            "tire-slip, actuator, sensor or noise dynamics; a collision terminates the episode instead of "
            "producing contact forces",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "the deployed observation is a rendered 480 x 640 x 3 OpenGL camera image; the fake returns one "
            "3-value RGB pixel sample while its observation space still declares the real shape",
            "the fake uses a straight placeholder lane and synthetic RGB values, not the geometry, textures, "
            "distortion or domain randomization of the two map files",
            "the fake converts the velocity and the steering angle to the two wheel commands as DuckietownEnv.step "
            "does, with its default constants and the nominal wheel distance that upstream randomizes at every "
            "reset, and moves its pose from those commands with a placeholder speed and turn rate instead of the "
            "upstream dynamics",
            "the fake draws with Python's random.Random and was not compared with the upstream OpenGL simulator "
            "or its numpy RandomState",
            "snapshot and restore are not offered: MultiMapEnv exposes no get_state or set_state",
        ],
    }
