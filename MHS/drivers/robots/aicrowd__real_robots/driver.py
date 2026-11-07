"""OpenMHS driver for gh.aicrowd/real_robots: the REALRobot2020 Kuka tabletop simulation.

A GymnasiumDriver is configuration only: ``env_id`` names a registered
environment and the Gymnasium bridge derives the contract from the
environment's spaces.  The upstream class is ``real_robots.envs.env:REALRobotEnv``
(env.py:27), a legacy Gym environment whose ``action_type='joints'``
configuration exposes a ``Dict`` action space with a nine-element
``joint_command`` Box and a one-value ``render`` MultiBinary flag
(env.py:57-61).  ``cap.world.step.v1`` therefore takes
``{ticks, action}`` with ``action.joint_command`` as nine numbers in radians
and ``action.render`` as one 0/1 integer; ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is
simulated (R0): there is no hardware backend, no e-stop path to a machine and
no operator-required limit.

The gate cannot import ``gym``, ``pybullet`` or the clone, so the ``fake``
backend is the package's own pure Python stand-in (fake.py).  A backend name
that ``backends`` does not list is served by ``gym.make(env_id)`` through the
Gymnasium bridge; that path needs the upstream package with gym and pybullet
(setup.py:24-31) and was not run here (README.md).

The ``fidelity`` attribute describes the model as deployed (spec 05-fidelity
FID-002).  The fake is kinematic and its camera arrays are a smaller
stand-in, so the package claims F0 and lists every difference in ``gaps``.
This package is model-authored and unreviewed: it is checked on the fake
backend only, and no hardware was attached.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "real_robots/envs/env.py"
ROBOT = "real_robots/envs/robot.py"
README = "README.md"
ENVIRONMENT = "environment.md"
INIT = "real_robots/__init__.py"


class RealRobot(GymnasiumDriver):
    """The REALRobot2020 R1 (extended observations) joints environment as a simulated R0 device."""

    device_id = "real-robots"
    env_id = "REALRobot2020-R1J3-v0"
    env_kwargs = {"additional_obs": True, "objects": 3, "action_type": "joints"}
    native = "real_robots.envs.env:REALRobotEnv"
    backends = {"fake": ".fake:FakeREALRobotEnv"}
    display_name = "REALRobot2020 Kuka iiwa tabletop (PyBullet simulation)"
    vendor, model = "AIcrowd", "REALRobot2020"
    tags = ["kuka", "iiwa", "manipulation", "pybullet", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("The REALRobot environment is a standard gym environment with a 7DoF Kuka arm, a 2DoF gripper "
             "and a table with 3 objects", source="vendor_doc", ref=f"{README}:104-105"),
        Fact("The action is a vector of 9 joint positions in radians; the two gripper joints range from 0 to "
             "+pi/2 and are coupled so the second is at most twice the first", source="vendor_doc",
             ref=f"{ENVIRONMENT}:8-10"),
        Fact("The environment registers 18 REALRobot2020 ids and creates them through "
             "real_robots.envs:REALRobotEnv with additional_obs, objects and action_type keyword arguments",
             source="upstream_code", ref=f"{INIT}:16-28"),
        Fact("REALRobotEnv defaults to render=False, objects=3, action_type='joints' and additional_obs=True",
             source="upstream_code", ref=f"{ENV}:36-37"),
        Fact("With action_type='joints' the action space is a Dict with 'joint_command' (the 9-joint Box) and "
             "'render' (MultiBinary(1))", source="upstream_code", ref=f"{ENV}:57-61"),
        Fact("Kuka builds a 9-element Box action space from min_joints and max_joints; the two gripper joints "
             "are limited to 0 and pi/2", source="upstream_code", ref=f"{ROBOT}:58-71"),
        Fact("Each step clamps the change of a joint to at most 0.2 rad for joints 1 to 5, 0.3 rad for joints "
             "6 and 7 and 0.1 rad for the two gripper joints", source="upstream_code", ref=f"{ENV}:314-321"),
        Fact("step_joints applies the joint command, advances the Bullet scene and returns "
             "(observation, reward, done, info)", source="upstream_code", ref=f"{ENV}:326-356"),
        Fact("The default reward function returns 0 for every observation", source="upstream_code",
             ref=f"{ENV}:11-12"),
        Fact("The intrinsic phase ends after 15e6 steps and an extrinsic trial after 10e3 steps",
             source="upstream_code", ref=f"{ENV}:32-34"),
        Fact("step_joints sets done when the timestep reaches intrinsic_timesteps or extrinsic_timesteps",
             source="upstream_code", ref=f"{ENV}:345-352"),
        Fact("The observation dictionary carries joint_positions, touch_sensors, retina and goal, and the "
             "extended form adds depth, mask, object_positions, goal_mask and goal_positions",
             source="upstream_code", ref=f"{ENV}:277-310"),
        Fact("The top camera image and the goal image are 240x320x3 arrays", source="vendor_doc",
             ref=f"{ENVIRONMENT}:39-40"),
        Fact("Kuka has 9 joints, 4 touch sensors and a 320 by 240 eye camera", source="upstream_code",
             ref=f"{ROBOT}:26-31"),
        Fact("The observation space declares joint_positions, touch_sensors, retina, depth, goal and, with "
             "additional_obs, mask, object_positions, goal_mask and goal_positions with the Kuka dimensions",
             source="upstream_code", ref=f"{ROBOT}:81-99"),
        Fact("The Bullet scene uses gravity 9.81, a timestep of 0.005 s and frame_skip 1", source="upstream_code",
             ref=f"{ENV}:202-204"),
        Fact("reset resets the simulation, sets gravity to (0, 0, -9.81), resets the timestep to 0 and returns "
             "the observation", source="upstream_code", ref=f"{ENV}:206-219"),
        Fact("The installation requires gym, pybullet and numpy (plus Click, tqdm, aicrowd-api, pillow and "
             "pyinterval); it declares no serial, VISA or socket dependency", source="upstream_code",
             ref="setup.py:24-31"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the last observation stays readable")
    #: The complete fidelity contract of the model as deployed (spec 05-fidelity section 2).  The
    #: bridge derives the engine and timestep; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "pybullet:REALRobot2020",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake accepts reset(seed=...) and uses the seed for its synthetic tabletop object "
                     "positions; the upstream REALRobotEnv.reset() takes no seed (env.py:206) and the upstream "
                     "PyBullet path would not reproduce that seed, so only the fake is seeded",
        },
        "timestep_ms": 5.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic stand-in for the PyBullet model: no rigid-body dynamics, contacts, friction, object "
            "physics or rendered camera; joint positions follow the commanded targets with the upstream "
            "per-step clamp (env.py:314-321)",
            "the retina, depth, mask and goal arrays are 24x32 (three channels for images) instead of the "
            "device's 240x320x3 and 240x320 (robot.py:30-31,86-95); their values are synthetic test data, "
            "not camera or sensor readings",
            "the fake accepts reset(seed, options) and seeds its synthetic object positions; the upstream "
            "REALRobotEnv.reset() takes no seed (env.py:206), so the upstream PyBullet path does not reproduce "
            "the fake's seeded trajectories",
            "the fake returns zero goal_mask and goal_positions arrays; the upstream extended observation "
            "carries goal.mask and goal.final_state, which are None until a goal is set (env.py:97-98,307-309)",
            "no wall-clock pacing: realtime_factor 0, and ticks advance simulated time by timestep_ms only",
            "snapshot and restore are not offered: REALRobotEnv has no get_state/set_state",
            "no physical device is modelled and the model was never validated against one",
            "the fake was never compared with the upstream environment: gym and pybullet are not installed "
            "where the gate runs (setup.py:24-31)",
        ],
    }
