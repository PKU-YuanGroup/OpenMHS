"""OpenMHS Gymnasium driver for gh.leekwoon/nav-gym (the NavGym-v0 environment).

DEVIATION FROM THE CARD: the card names helper ``RosDriver`` (family ``ros``),
but the pinned upstream's primary interface is a Gymnasium environment, not a
ROS transport.  ``nav_gym_env/__init__.py:5`` registers the self-configuring
environment ``NavGym-v0`` whose entry point is ``nav_gym_env.env:NavGymEnv``
(``nav_gym_env/__init__.py:39``); ``gym.make("NavGym-v0")`` supplies every
constructor argument from the registration kwargs.  The repository's ROS nodes
(``nav_gym/src/nav_gym_ros/``) are a separate, unselected interface, and an
environment does not become a ROS driver merely because the repository also
contains ROS code.  This package therefore serves the environment through
``GymnasiumDriver`` and the ``cap.world.step.v1`` / ``cap.world.reset.v1`` /
``cap.world.seed.v1`` classes.

The checked backend is the package's own analytic stand-in (fake.py), because
the upstream class imports torch, OpenCV, pyastar2d, range_libc, CMap2D and
pose2d (``nav_gym/src/nav_gym_env/env.py:1-28``) and loads a Torch policy file
in its constructor (``nav_gym/src/nav_gym_env/env.py:111-119``).  Package code
never imports or runs the clone, so the fake does not reproduce the upstream
crowd simulation and its trajectories were never compared with it.

Every fact cites the clone at the pinned commit
92aa9ce66074cc51d5aa598205b52443976d8af7.  The package is model-authored and
unreviewed (``driver.lock.json`` keeps ``reviewed_by: null``); only the fake
backend is validated here and no simulator, ROS graph or hardware was run.
"""

from mhs.driver import Fact, GymnasiumDriver

_ENV = "nav_gym/src/nav_gym_env/env.py"
_INIT = "nav_gym/src/nav_gym_env/__init__.py"
_ROBOT = "nav_gym/src/nav_gym_env/keti_robot.py"


class NavGym(GymnasiumDriver):
    device_id = "nav-gym"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    env_id = "NavGym-v0"
    native = "nav_gym_env.env:NavGymEnv"
    backends = {"fake": ".fake:FakeNavGymEnv"}
    display_name = "nav-gym NavGym-v0 navigation simulator"
    vendor, model = "leekwoon", "NavGym-v0"
    tags = ["navigation", "reinforcement-learning", "simulation", "gym", "crowd"]
    #: The Box action space is built from the registration's linvel_range and
    #: rotvel_range (env.py:133-137); those two lines are the only place the
    #: bound numbers are written.
    action_space_ref = f"{_INIT}:12-13"
    safe_state = ("the simulated world stops advancing: after an e-stop the runtime refuses step and "
                  "reset until mhs.safety.reset clears the latch; the environment has no native stop "
                  "method and the readable state is kept")
    facts = [
        Fact("NavGym-v0 is registered with id 'NavGym-v0'", source="upstream_code", ref=f"{_INIT}:5"),
        Fact("NavGym-v0's entry point is 'nav_gym_env.env:NavGymEnv'", source="upstream_code",
             ref=f"{_INIT}:39"),
        Fact("The registration supplies the constructor kwargs, including time_step 0.2 s, "
             "distance_threshold 0.5 m and num_scan_stack 1", source="upstream_code",
             ref=f"{_INIT}:8-11"),
        Fact("The registration sets the linear velocity range to [0, 0.5] and the rotational velocity "
             "range to [-0.64, 0.64]", source="upstream_code", ref=f"{_INIT}:12-13"),
        Fact("The action space is a two-element Box: low [linvel_range[0], rotvel_range[0]] and high "
             "[linvel_range[1], rotvel_range[1]], dtype float32", source="upstream_code",
             ref=f"{_ENV}:133-137"),
        Fact("The observation space is a Dict of the scan-plus-pose observation "
             "(num_scan_stack * robot.n_angles + 7), a two-element achieved_goal and a two-element "
             "desired_goal; all are unbounded float32 Boxes", source="upstream_code",
             ref=f"{_ENV}:138-142"),
        Fact("KetiRobot reports 512 lidar angles, angle_min -3.141592, angle_max 3.141592, "
             "angle_increment 0.0122718463 and range_max 25 m", source="upstream_code",
             ref=f"{_ROBOT}:44-48"),
        Fact("KetiRobot.set_vel applies the [linear, rotational] velocity for time_step with a 0.14474 m "
             "rotation-centre offset and wraps theta modulo 2*pi", source="upstream_code",
             ref=f"{_ROBOT}:65-93"),
        Fact("A step applies the action with robot.set_vel, computes the reward, done and info, and "
             "returns (observation, reward, done, info)", source="upstream_code",
             ref=f"{_ENV}:664-728"),
        Fact("step prints a message when the linear or rotational velocity is outside its registered range "
             "but applies the action unclipped (the np.clip lines are commented out); the rotational "
             "upper-bound check compares action[0]", source="upstream_code", ref=f"{_ENV}:606-613"),
        Fact("The terminal flag is the logical OR of success (goal distance below distance_threshold) "
             "and crash (any scan range below scan_threshold)", source="upstream_code",
             ref=f"{_ENV}:508-512"),
        Fact("The reward adds the factors reward_success, reward_crash, reward_progress, reward_forward, "
             "reward_rotation and reward_discomfort, each scaled by reward_scale", source="upstream_code",
             ref=f"{_ENV}:557-578"),
        Fact("The registration sets reward_scale 15 and the success, crash, progress, forward, rotation "
             "and discomfort factors to 1, 1, 0.001, 0.0, 0.005 and 0.01", source="upstream_code",
             ref=f"{_INIT}:19-25"),
        Fact("A reset samples the environment parameters and map, creates the robot and humans, and "
             "returns the initial observation without taking a reset argument", source="upstream_code",
             ref=f"{_ENV}:730-831"),
        Fact("The upstream package declares matplotlib, pandas, rospkg, netifaces, gym 0.10.5, "
             "opencv-python, PyQt5, torch, pyastar2d, pymap2d, pyrangelibc and pyrvo2 as install "
             "requirements", source="upstream_code", ref="nav_gym/setup.py:13-27"),
        Fact("The project is an OpenAI-gym compatible navigation simulator that can be integrated into "
             "ROS", source="vendor_doc", ref="README.md:3"),
    ]
    fidelity = {
        "engine": "analytic: open-space kinematic stand-in for NavGym-v0 (no crowd or map model)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": ("the checked fake starts every episode from the same fixed pose and has no random "
                      "draws, so a reset reproduces its observation; the bridge records a reset seed, but "
                      "the upstream reset() takes no seed argument and NavGymEnv exposes no seed() method, "
                      "so the seed does not vary the upstream scene or the fake"),
        },
        "timestep_ms": 200.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the checked fake is an open-space kinematic stand-in: it has no generated indoor/outdoor "
            "map, crowd, human policy, lidar ray casting, collision, discomfort or scan noise, and its "
            "trajectories were never compared with the upstream simulator",
            "the scan is a constant maximum-range return and the crash terminal is therefore never "
            "reached in the fake; only the goal-distance success terminal is exercised",
            "the fake keeps the upstream step and reset shapes, the 512-angle scan length, the 200 ms "
            "timestep and the two-element velocity action, but it is not the upstream crowd simulation",
            "the upstream constructor needs torch, OpenCV, pyastar2d, range_libc, CMap2D, pose2d and the "
            "human_policy.pth policy; none of them is installed where the gate runs, and package code "
            "never imports or runs the clone",
            "no wall-clock pacing: realtime_factor 0 and only cap.world.step.v1 advances simulated time",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state and "
            "the bridge has no checkpoint profile for this package",
            "the upstream registers NavGym-v0 with gym 0.10.5 (gym.envs.registration, __init__.py:1), not "
            "Gymnasium, and its reward indexes with the np.bool alias (env.py:557-565) that current NumPy "
            "releases no longer define; no live gymnasium.make('NavGym-v0'), reset or step was run, and a "
            "live backend would need the upstream's old dependency set",
            "the upstream step applies out-of-range actions unclipped (env.py:606-613); the bridge refuses "
            "any action outside the Box, so it is stricter than the upstream",
        ],
    }
