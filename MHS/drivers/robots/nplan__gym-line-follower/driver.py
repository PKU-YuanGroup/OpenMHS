"""OpenMHS driver for gh.nplan/gym-line-follower: the LineFollower-v0 environment (a Gymnasium family driver).

The upstream package is a PyBullet line-following simulator registered as ``LineFollower-v0``
(``gym_line_follower/__init__.py:4-6``) and built from ``gym_line_follower.envs:LineFollowerEnv``
(``gym_line_follower/envs/line_follower_env.py:26``).  A GymnasiumDriver is configuration only: ``env_id``
names the environment and the bridge derives the ``cap.world.*`` contract from its spaces.  ``cap.world.step.v1``
takes ``{ticks, action}`` with the action ``{values: [left, right]}`` bounded by the two-element action space
(``line_follower_env.py:80``), ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1``
``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no
operator-required bound.

The gate cannot import the upstream package (it needs ``gym``, ``pybullet``, ``opencv-python``, ``shapely``
and ``numpy``, ``setup.py:5-7``), and package code never imports the clone.  The ``fake`` backend is therefore
the package's own pure Python kinematic line follower (``fake.py``); the upstream simulator (a backend name
``backends`` does not list) would be served by ``gym.make(env_id)`` only after ``gym_line_follower`` was
imported, and that path was not run here (README notes).

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity
FID-002).  The fake is kinematic, so the level is F0.  Every fact cites a line of the clone at the pinned
commit (11b3dd8fe791c02bc36cbbf91c686825776b3025).  This package is model-authored and unreviewed: it is
checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "gym_line_follower/envs/line_follower_env.py"
README = "README.md"


class LineFollower(GymnasiumDriver):
    device_id = "gym-line-follower"
    env_id = "LineFollower-v0"
    native = "gym_line_follower.envs:LineFollowerEnv"
    backends = {"fake": ".fake:FakeLineFollowerEnv"}
    display_name = "Gym line follower (PyBullet line-following simulator)"
    vendor, model = "Nejc Planinsek", "LineFollower-v0"
    tags = ["line-follower", "differential-drive", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("The package registers LineFollower-v0 (entry point gym_line_follower.envs:LineFollowerEnv) and "
             "LineFollowerCamera-v0 (entry point gym_line_follower.envs:LineFollowerCameraEnv)",
             source="upstream_code", ref="gym_line_follower/__init__.py:3-12"),
        Fact("The action space is a Box of two motor-power values with low -1.0 and high 1.0",
             source="upstream_code", ref=f"{ENV}:80"),
        Fact("The constructor defaults are gui=True, nb_cam_pts=8, sub_steps=10, sim_time_step=1/250 s, "
             "max_track_err=0.3, power_limit=0.4 and max_time=60 s",
             source="upstream_code", ref=f"{ENV}:31-33"),
        Fact("The default observation type is points_latch", source="upstream_code", ref=f"{ENV}:31-32"),
        Fact("The points_latch observation space is 2*nb_cam_pts values, with x in [0.0, 0.3] and y in "
             "[-0.2, 0.2] for each point", source="upstream_code", ref=f"{ENV}:89-92"),
        Fact("A step scales every action by self.speed_limit before applying it",
             source="upstream_code", ref=f"{ENV}:171-172"),
        Fact("self.speed_limit is the power_limit constructor argument", source="upstream_code", ref=f"{ENV}:71"),
        Fact("One environment step runs sub_steps simulation steps and then reads the follower bot position",
             source="upstream_code", ref=f"{ENV}:179-184"),
        Fact("With the constructor defaults sub_steps=10 and sim_time_step=1/250 s, one environment step "
             "advances 0.04 s of simulated time", source="upstream_code", ref=f"{ENV}:31-32"),
        Fact("A reset generates a track and, when randomize is true, adds a start-yaw offset drawn uniformly "
             "from (-0.2, 0.2) rad", source="upstream_code", ref=f"{ENV}:142-147"),
        Fact("The reward is -0.2 per step plus 1000/nb_checkpoints * (1 - track_err/max_track_err)^2 for every "
             "checkpoint reached", source="upstream_code", ref=f"{ENV}:211-218"),
        Fact("The episode ends when the track is done, the progress deviates by more than 0.5, the track error "
             "exceeds max_track_err, or the step counter exceeds max_steps; a failed episode gets reward -100",
             source="upstream_code", ref=f"{ENV}:220-234"),
        Fact("seed() uses gym.utils.seeding.np_random and returns the seed as a one-element list",
             source="upstream_code", ref=f"{ENV}:323-325"),
        Fact("LineFollowerCameraEnv subclasses LineFollowerEnv and forces obsv_type='camera'",
             source="upstream_code", ref=f"{ENV}:342-345"),
        Fact("The camera observation space is a 240 x 320 x 3 uint8 image", source="upstream_code",
             ref=f"{ENV}:101-102"),
        Fact("The observation is 8 line points as x, y pairs in the robot's coordinate frame, with x in "
             "(0, 0.3) and y in (-0.2, 0.2)", source="vendor_doc", ref=f"{README}:74-77"),
        Fact("The follower starts at the beginning of a closed-loop track and the episode ends when the loop "
             "is complete or the follower leaves the line", source="vendor_doc", ref=f"{README}:63-67"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    fidelity_level = "F0"
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the
    #: engine, determinism kind and clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "analytic:line-follower-kinematics",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's initial lateral and yaw offsets and the "
                     "dynamics are deterministic, so one implementation repeats a trajectory for the same seed "
                     "and actions; upstream draws the track and the start pose from numpy/gym's generator, so a "
                     "seed gives different trajectories on the two implementations",
        },
        "timestep_ms": 40.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic/analytic unicycle on a fixed circular track: no rigid-body dynamics, contacts, wheel "
            "slip, motor torque, sensor or noise model; the upstream environment is a PyBullet simulation of "
            "a differential-drive URDF",
            "the fake track is a fixed circle, not the randomised Bezier loop the upstream reset generates "
            "(line_follower_env.py:142-143)",
            "the fake observations are an analytic lookahead along the circle, not the upstream camera-window "
            "intersection of line points (line_follower_bot.py:155-190)",
            "the fake uses Python's random.Random, upstream uses numpy and gym.utils.seeding "
            "(line_follower_env.py:323-325), so a seed does not give the same trajectory on both",
            "the fake does not render, does not produce the 240 x 320 x 3 camera observation of "
            "LineFollowerCamera-v0, and offers no snapshot or restore",
            "the fake was not compared with the upstream environment; the upstream package was not installed "
            "where the gate ran (it needs gym, pybullet, opencv-python, shapely and numpy, setup.py:5-7)",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
