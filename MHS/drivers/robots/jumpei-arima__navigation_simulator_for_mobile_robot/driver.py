"""OpenMHS driver for gh.jumpei-arima/navigation_simulator_for_mobile_robot: the Nsmr-v1 navigation simulator.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives
``cap.world.step.v1`` (``{ticks, action}`` with ``action.values`` bounded by the environment's Box action space),
``cap.world.reset.v1`` (``{seed, options}``) and ``cap.world.seed.v1`` (``{seed}``) from the environment object.
The device is simulated (R0): it has no hardware backend, no machine to stop and no operator-required limit.

The upstream package is a legacy ``gym`` environment (``gym>=0.10.5``, ``requirements.txt:1``) with numpy
(``requirements.txt:2``) and a Cython raycasting extension (``setup.py:13-15``).  The gate never installs or imports
the clone, so the ``fake`` backend is this package's pure Python stand-in for ``NsmrGymEnv``.  A backend name that
``backends`` does not list (``sim``) is served by ``gym.make(env_id)`` through GymnasiumBridge; that path was not run
and is not claimed here.

Every Fact and every fidelity constant cites a line of the clone at the pinned commit
(4727fa696f363e88d757c0896f1c3f0dacc83af3).  This package is model-authored and unreviewed and is checked on the
fake backend only (the upstream environment itself was never run).
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "nsmr/envs/NsmrGymEnv.py"
SIM = "nsmr/envs/nsmr.py"
ROBOT = "nsmr/robots/robot.json"


class NsmrGym(GymnasiumDriver):
    device_id = "nsmr-gym"
    env_id = "Nsmr-v1"
    native = "nsmr.envs.NsmrGymEnv:NsmrGymEnv"
    backends = {"fake": ".fake:FakeNsmrGymEnv"}
    action_space_ref = f"{ROBOT}:3-6"
    display_name = "NSMR Nsmr-v1 (2D mobile robot navigation simulator)"
    vendor, model = "Jumpei Arima", "Nsmr-v1"
    tags = ["navigation", "mobile-robot", "lidar", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("Nsmr-v1 is registered with entry_point nsmr.envs.NsmrGymEnv:NsmrGymEnv and max_episode_steps=500",
             source="upstream_code", ref="nsmr/envs/__init__.py:7-11"),
        Fact("The observation space is a Dict of a lidar Box with num_range elements from min_range to max_range "
             "and a target Box with bounds [0.0, -1.0, -1.0] to [100.0, 1.0, 1.0]", source="upstream_code",
             ref=f"{ENV}:119-127"),
        Fact("The action space is a Box of two values, linear velocity between min_linear_velocity and "
             "max_linear_velocity and angular velocity between min_angular_velocity and max_angular_velocity, both "
             "read from the robot configuration", source="upstream_code", ref=f"{ENV}:128-134"),
        Fact("The bundled robot configuration sets radius 0.3, linear velocity limits 0.0 and 1.0, and angular "
             "velocity limits -1.0 and 1.0", source="upstream_code", ref=f"{ROBOT}:2-6"),
        Fact("The bundled robot configuration sets linear acceleration 0.5 and angular acceleration 1.0",
             source="upstream_code", ref=f"{ROBOT}:7-8"),
        Fact("The bundled lidar configuration has 720 rays, range 0.1 to 30.0, max_angle 1.5707963267948966 and "
             "angle_increment 0.004363323129985824", source="upstream_code", ref=f"{ROBOT}:17-22"),
        Fact("NsmrGymEnv constructs NSMR with only robot and layout", source="upstream_code", ref=f"{ENV}:25"),
        Fact("NSMR's constructor default timestep is dt=0.1 s and it is stored as the simulator's DT",
             source="upstream_code", ref=f"{SIM}:12-18"),
        Fact("NSMR.update runs add_bias, stuck, check_action, state_transition and add_noise in that order",
             source="upstream_code", ref=f"{SIM}:71-77"),
        Fact("check_action limits the change of each velocity by max_linear_acceleration*DT or "
             "max_angular_acceleration*DT and then clamps both to the robot's velocity limits",
             source="upstream_code", ref=f"{SIM}:79-86"),
        Fact("state_transition integrates the unicycle pose in closed form and normalizes the heading",
             source="upstream_code", ref=f"{SIM}:88-98"),
        Fact("reset_pose draws a random pose until it is collision free and a random target",
             source="upstream_code", ref=f"{SIM}:48-59"),
        Fact("reset_noise_param draws the noise parameters from numpy's global random module",
             source="upstream_code", ref=f"{SIM}:61-69"),
        Fact("get_lidar returns num_range readings from the Raycasting map, with oversight and range noise",
             source="upstream_code", ref=f"{SIM}:139-152"),
        Fact("get_relative_target_position returns [distance, sin(theta), cos(theta)]",
             source="upstream_code", ref=f"{SIM}:154-162"),
        Fact("The reward is goal_reward when the distance is below the robot radius, -collision_penalty on a "
             "collision and otherwise alpha times the distance change; a stop_penalty is subtracted when there is "
             "no progress, and beta/(2*pi)*abs(theta) for the heading error", source="upstream_code",
             ref=f"{ENV}:83-98"),
        Fact("is_done is true at max_steps, on a collision or after the goal", source="upstream_code",
             ref=f"{ENV}:100-108"),
        Fact("reset returns only the observation and step returns the legacy 4-tuple (observation, reward, done, "
             "info)", source="upstream_code", ref=f"{ENV}:53-72"),
        Fact("NsmrGymEnv.seed assigns self.np_random and returns [seed]", source="upstream_code",
             ref=f"{ENV}:113-115"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model this package serves (spec 05-fidelity section 2).  The upstream model is
    #: kinematic: a unicycle pose integrated in closed form (nsmr.py:88-98) behind acceleration and velocity limits
    #: (nsmr.py:79-86); it has no rigid-body dynamics or contact forces, so the level is F0.
    fidelity = {
        "engine": "nsmr:2d-raycasting",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake draws its start pose and target from Python's random.Random(seed), so one seed "
                     "repeats its trajectory; the upstream NsmrGymEnv.seed only assigns self.np_random while NSMR "
                     "draws from numpy's global random module (nsmr.py:61-69, 107-108, 148-150, 168), so the "
                     "upstream simulator itself is not reproducible from the seed",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic 2D unicycle only: no rigid-body dynamics, contacts or collision forces; is_collision "
            "(nsmr.py:129-137) is an occupancy lookup and outside the map it returns false",
            "the fake does not raycast the 10 m x 10 m map (simple_map.json:2-3, 1000 cells at 0.01 m): it returns "
            "the real 720 lidar values (robot.json:18) as placeholder readings all at max_range, so its "
            "observations are not the upstream's",
            "the fake does not model the upstream sensor and actuator noise, the stuck state or the lidar "
            "oversight events (nsmr.py:100-124, 148-150); its trajectories are not compared with the upstream's",
            "no rendering: the fake's render returns None and the upstream Renderer is not reimplemented",
            "the reward follows the upstream default parameters, but the fake does not model collisions and "
            "detects a goal only from the distance",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "no wall-clock pacing: realtime_factor 0, only commands advance simulated time (100 ms per tick)",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
