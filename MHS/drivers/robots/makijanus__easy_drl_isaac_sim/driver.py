"""OpenMHS driver for gh.makijanus/easy_drl_isaac_sim: the ``Isaac_envs`` Isaac Sim environment.

The upstream is a Gymnasium-style simulation environment: ``Isaac_envs`` is a ``gym.Env`` that starts the proprietary
Isaac Sim 2021.2.1 ``SimulationApp`` in its constructor and steps a Jetbot through a fixed ``random_walk`` obstacle
scene (``DRL_Isaac_lib/env.py:15-42``; ``README.md:70-74``).  The card's family is ``gymnasium``, so this is a
:class:`GymnasiumDriver`: ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{index}`` bounded by the
environment's ``Discrete(3)`` space, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1``
``{seed}``.  The device is simulated (R0): there is no hardware backend and no physical stop path.

The upstream class is old Gym API: ``reset()`` takes no arguments and returns an observation, and ``step(action)``
returns a four-tuple ``(observation, reward, done, info)`` (``env.py:126-213``).  The bridge accepts both shapes and
applies the seed through the class's ``seed()`` method (``env.py:249-252``).  The constructor hardcodes
``env_name='random_walk'``, ``robot_name='jetbot'`` and ``action_type='discrete'`` (``env.py:40-42``); those are the
variant this package serves.

The gate cannot import Isaac Sim (or the upstream's ``gym`` import), so the ``fake`` backend is this package's pure
Python kinematic stand-in (``fake.py``); it was written from the pinned source, never run against Isaac Sim.  There is
no registered Gymnasium id and no listed simulator backend: the upstream is installed only by copying it into an Isaac
Sim 2021.2.1 installation (``README.md:70-74``), so the fake is the only backend this package can serve here.

The ``fidelity`` attribute is the complete contract of the model as deployed (spec 05-fidelity FID-002).  Every
constant and rule cites a line of the clone at the pinned commit aa7fcf6d8a8c707ca3d94a8db7dad0de13a45245.  This
package is model-authored and unreviewed: it is checked on the fake backend only, and nothing here was validated
against Isaac Sim or a physical robot.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "DRL_Isaac_lib/env.py"
ROBOTS = "DRL_Isaac_lib/isaac_robots.py"
ENVS = "DRL_Isaac_lib/isaac_envs.py"


class EasyDRLIsaacSim(GymnasiumDriver):
    device_id = "easy-drl-isaac-sim"
    env_id = None                       # not registered with Gymnasium; the package serves the fake backend only
    native = "DRL_Isaac_lib.env:Isaac_envs"
    backends = {"fake": ".fake:FakeIsaacEnv"}
    action_space_ref = f"{ROBOTS}:313"
    display_name = "Easy DRL Isaac Sim (random_walk, Jetbot, discrete)"
    vendor, model = "makijanus", "easy_drl_isaac_sim"
    tags = ["isaac-sim", "jetbot", "reinforcement-learning", "simulation", "gymnasium", "random-walk"]
    facts = [
        Fact("The README requires Isaac Sim 2021.2.1 and installs the library by copying DRL_Isaac_lib into the "
             "Isaac Sim package directory", source="vendor_doc", ref="README.md:70-74"),
        Fact("Isaac_envs is a gym.Env whose metadata declares render.modes human", source="upstream_code",
             ref=f"{ENV}:15-16"),
        Fact("The constructor defaults are skip_frame 1, physics_dt 1/60 s, rendering_dt 1/60 s, max_episode_length "
             "3000, seed 0 and headless True", source="upstream_code", ref=f"{ENV}:18-25"),
        Fact("The step interval is stored as physics_dt * skip_frame and the reset offset as int(rendering_dt / "
             "physics_dt)", source="upstream_code", ref=f"{ENV}:31-34"),
        Fact("The constructor hardcodes env_name random_walk, robot_name jetbot and action_type discrete",
             source="upstream_code", ref=f"{ENV}:40-42"),
        Fact("For random_walk the constructor builds the fixed vertical path map with random=False, then draws a "
             "random robot pose and target", source="upstream_code", ref=f"{ENV}:53-57"),
        Fact("get_action_space returns spaces.Discrete(3) for the discrete action type", source="upstream_code",
             ref=f"{ROBOTS}:312-313"),
        Fact("The observation space is a Dict of three Boxes: IR_raleted shape (1,12) in [0,1], pos_raleted shape "
             "(2,) low [0,-pi] high [8,pi], and vel_raleted shape (2,) low [0,-pi/4] high [10,pi/4]",
             source="upstream_code", ref=f"{ENV}:96-120"),
        Fact("The Jetbot's three discrete movements are [15, 0.785], [25, 0] and [15, -0.785], each a [linear, yaw] "
             "pair", source="upstream_code", ref=f"{ROBOTS}:317-320"),
        Fact("The differential controller uses wheel radius 3.25 and wheel base 11.25 for the Jetbot and computes "
             "the two wheel joint velocities from the [linear, yaw] command", source="upstream_code",
             ref=f"{ROBOTS}:142-163"),
        Fact("step applies the selected movement for each skip frame, calls differential_controller for a "
             "differential robot, advances the world with world.step(render=False), and returns "
             "(observations, reward, done, info)", source="upstream_code", ref=f"{ENV}:126-193"),
        Fact("The observation is the lidar ranges, the goal distance and angular difference, and the base "
             "linear and angular velocity", source="upstream_code", ref=f"{ENV}:220-237"),
        Fact("The lidar interface resizes its depth array to (1, number_lasers)", source="upstream_code",
             ref=f"{ENVS}:235-243"),
        Fact("distance_to measures the 3D Euclidean distance and angular_difference_to computes theta from the "
             "quaternion components and returns a wrapped theta-alpha angle", source="upstream_code",
             ref=f"{ROBOTS}:222-260"),
        Fact("The episode ends when current_time_step_index - steps_after_reset reaches max_episode_length, when "
             "the minimum lidar range is <= 0.155, or when the goal distance is <= 0.5", source="upstream_code",
             ref=f"{ENV}:157-189"),
        Fact("The reward starts as distance_reward = -distance/100 and is scaled by 1 - index/max_episode_length "
             "only when distance_reward is positive, "
             "minus 10*(0.6 - minimum_lidar) on a lidar collision, and plus 10 + 90*(1 - index/max_episode_length) "
             "at the goal", source="upstream_code", ref=f"{ENV}:168-189"),
        Fact("reset calls world.reset() and, for random_walk, randomizes the goal position and then the robot pose; "
             "it returns only the observation", source="upstream_code", ref=f"{ENV}:195-213"),
        Fact("The seed method uses gym.utils.seeding.np_random(seed), calls np.random.seed(seed) and returns "
             "[seed]", source="upstream_code", ref=f"{ENV}:249-252"),
        Fact("The lidar is created with 12 lasers, a 360-degree horizontal FOV, a 30-degree vertical FOV, "
             "360/number_lasers horizontal resolution, rotation_rate 0 and yaw_offset 0", source="upstream_code",
             ref=f"{ENVS}:157-219"),
        Fact("For the Jetbot the lidar min_range is 0.15 and max_range is 1", source="upstream_code",
             ref=f"{ENVS}:166-171"),
        Fact("The random_walk map uses map_dist_unit 0.5 and height 0.2 for the Jetbot, a 5x5 grid, four outer "
             "walls and one cube for every grid cell", source="upstream_code", ref=f"{ENVS}:248-321"),
        Fact("The fixed map array is rotated counter-clockwise with np.rot90, and a cell is visible when its rotated "
             "value is 1", source="upstream_code", ref=f"{ENVS}:365-387"),
        Fact("The random reset draws the robot x as map_dist_unit * randint(map_dimension), its y as "
             "-1.5*map_dist_unit and its orientation quaternion as [0, 0, sin(a), cos(a)] with a = rand()*pi; the "
             "goal x is drawn the same way with y = 5.5*map_dist_unit and z = 0.25", source="upstream_code",
             ref=f"{ENVS}:409-430"),
        Fact("get_observations acquires depth camera data but does not use it; the returned dictionary contains "
             "only IR_raleted, pos_raleted and vel_raleted", source="upstream_code", ref=f"{ENV}:215-240"),
        Fact("render returns without drawing and close closes the SimulationApp", source="upstream_code",
             ref=f"{ENV}:242-247"),
    ]
    safe_state = ("the served fake stops advancing: the latch refuses step and world-reset commands until "
                  "mhs.safety.reset clears it; the fake state stays readable. This package serves no Isaac Sim "
                  "backend and controls no external simulator timeline")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: determinism kind and lockstep clock; they are written out so the whole contract reads in one place.  The
    #: upstream is an Isaac Sim 2021.2.1 rigid-body simulation, but the deployed backend here is the package's
    #: analytic kinematic fake, which is F0 (no dynamics).
    fidelity = {
        "engine": "isaac-sim-2021.2.1 (analytic fake)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "cap.world.seed.v1 or cap.world.reset.v1(seed) seeds the fake's Python random.Random before the "
                     "reset; upstream seed() uses gym.utils.seeding.np_random and numpy's global generator "
                     "(env.py:249-252) while the fake draws with random.Random, so one seed does not reproduce "
                     "upstream trajectories; neither path was compared with the other",
        },
        "timestep_ms": 1000.0 / 60.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a kinematic stand-in: the commanded [linear, yaw] velocity is integrated directly "
            "at the default 1/60 s control period; there is no Isaac Sim/PhysX rigid-body dynamics, wheel-ground "
            "friction, actuator response, gravity, contact response or rendering, so the deployed model is F0 "
            "(absence of dynamics) even though the upstream uses Isaac Sim 2021.2.1 (README.md:70)",
            "the fake's linear command gain of 0.01 is a placeholder, not a verified centimetre-to-metre conversion; "
            "the controller at isaac_robots.py:142-163 states wheel geometry and wheel velocity formulas but no "
            "linear command unit",
            "the goal-angle calculation preserves isaac_robots.py:245-259: for the fake's planar quaternion "
            "[0, 0, sin(yaw/2), cos(yaw/2)], the pinned theta numerator is zero and theta is pi rather than yaw; "
            "the simulator's quaternion convention was not validated",
            "the 12-beam lidar is an analytic 2D raycast against the fixed random_walk obstacle boxes, capped at "
            "1 m and clamped to 0.15 m; the Isaac range sensor's exact beam phase, vertical FOV, 3D occlusion and "
            "miss behaviour are not modelled",
            "the RGB/depth camera data is acquired by get_observations (env.py:218) but is not part of the returned "
            "observation or the observation space (env.py:113-120); NOT COVERED: the RGB/depth camera arrays",
            "the random reset draws the robot x and yaw and the goal x with Python's random.Random from the same "
            "distributions as isaac_envs.py:409-430; upstream draws them from numpy's global generator seeded by "
            "seed() (env.py:249-252), so a seed gives different trajectories on the two, and observations are "
            "Python lists rather than numpy arrays",
            "the fake was never compared with the upstream environment: Isaac Sim 2021.2.1 is proprietary "
            "(README.md:70) and is not installed or importable where the gate runs; there is no SyntheticDataHelper "
            "and no rendering",
            "the environment is not registered with Gymnasium and no simulator backend is listed: the upstream is "
            "installed only by copying it into an Isaac Sim 2021.2.1 tree (README.md:70-74), so this package "
            "serves the fake backend only",
            "a live wrapper would need its own lifecycle and output handling: the upstream constructor starts "
            "SimulationApp and uses flat module imports (env.py:27-37), reset prints to stdout (env.py:207-210), "
            "the goal branch prints to stdout (env.py:185-189), and close closes SimulationApp (env.py:245-247); "
            "the fake latch supplies no stop for an independently running Isaac timeline",
            "snapshot and restore are not offered: Isaac_envs exposes no get_state/set_state method",
        ],
    }
