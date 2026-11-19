"""OpenMHS driver for gh.ll7/robot_sf_ll7: the Robot SF single-robot Gymnasium environment.

Robot SF is a social-navigation simulation and benchmarking package.  ``RobotEnv`` is its Gymnasium environment
facade: a differential-drive robot takes commanded linear and angular accelerations in a crowd, and ``reset`` /
``step`` return the fused sensor observation and the Gymnasium five-tuple.  A ``GymnasiumDriver`` is configuration
only: ``env_id`` names the upstream environment and the bridge derives the ``cap.world.*`` contract from the
environment's spaces.  Here the action space is the robot's ``Box`` of two acceleration commands and the step action
is ``{"values": [linear_acceleration, angular_acceleration]}``; ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.

The device is simulated (R0): there is no hardware backend, no physical stop path and no operator-required limit.
The ``fake`` backend is the package's own kinematic stand-in.  A backend name that ``backends`` does not list would
be served by ``gymnasium.make(env_id)``, but the id ``robot`` is only an entry of Robot SF's own catalog
(``robot_sf/gym_env/env_registry.py:165-174``).  ``register_env`` writes that catalog's ``_REGISTRY``
(``env_registry.py:94-116``) and the module never calls ``gymnasium.register``, so ``gymnasium.make('robot')`` raises
``NameNotFound``.  The ``sim`` backend is ``_build_sim_env``, which calls the catalog's factory
``make_robot_env`` (``env_registry.py:169``) and returns the ``RobotEnv`` that factory builds
(``environment_factory.py:262-268``, ``:672-688``).  The import stays inside the factory, so the fake backend never
loads the clone.  The sim entry is a callable, so the lock's string entry (``fake`` only) is still what G2 compares.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every fact cites a line of the clone at commit 53721be3248600e08641a9816d094b605e3c93e4.  This package is
model-authored and unreviewed: this workspace checks the fake backend, and the orchestrator's ``--backend sim``
run is the evidence for the real ``RobotEnv``.
"""

from mhs.driver import Fact, GymnasiumDriver

REGISTRY = "robot_sf/gym_env/env_registry.py"
ROBOT_ENV = "robot_sf/gym_env/robot_env.py"
ENV_UTIL = "robot_sf/gym_env/env_util.py"
SENSOR_FUSION = "robot_sf/sensor/sensor_fusion.py"
RANGE_SENSOR = "robot_sf/sensor/range_sensor.py"
DRIVE = "robot_sf/robot/differential_drive.py"
ROBOT_STATE = "robot_sf/robot/robot_state.py"
SIM_CONFIG = "robot_sf/sim/sim_config.py"
FACTORY = "robot_sf/gym_env/environment_factory.py"


def _build_sim_env(**_options):
    """Build the real upstream ``RobotEnv`` for the ``sim`` backend.

    The import is inside the factory so the fake backend never imports Robot SF.  The id ``robot`` is a catalog
    entry (``env_registry.py:165-174``), and ``register_env`` stores it on the module ``_REGISTRY``
    (``env_registry.py:94-116``).  That module does not call ``gymnasium.register``, so ``gymnasium.make('robot')``
    raises ``NameNotFound``.  The catalog names ``make_robot_env`` as the factory (``env_registry.py:169``).  Called
    with no arguments it keeps ``debug`` false (``environment_factory.py:529``), so ``BaseEnv`` does not construct a
    ``SimulationView`` (``base_env.py:249-250``).  ``create_robot_env`` selects ``RobotEnv`` when image observations
    are off (``environment_factory.py:262-268``) and ``make_robot_env`` returns that instance
    (``environment_factory.py:672-688``).  The returned object is not wrapped, patched or replaced.
    """
    from robot_sf.gym_env.environment_factory import make_robot_env

    return make_robot_env()


class RobotSF(GymnasiumDriver):
    device_id = "robot_sf"
    env_id = "robot"
    native = "robot_sf.gym_env.robot_env:RobotEnv"
    #: ``fake`` is this package's stand-in.  ``sim`` calls ``make_robot_env`` (environment_factory.py:672-688),
    #: which returns the real ``RobotEnv``.  The sim entry is a callable, so the lock's string entry (``fake``
    #: only) still describes the package's declared string backend and G2 compares a lock only when every entry
    #: is a string.
    backends = {"fake": ".fake:FakeRobotEnv", "sim": _build_sim_env}
    display_name = "Robot SF social navigation simulation (RobotEnv)"
    vendor, model = "ll7", "Robot SF"
    tags = ["social-navigation", "robot", "pedestrian", "gymnasium", "simulation"]
    risk = "R0"
    fidelity_level = "F0"
    facts = [
        Fact("Robot SF registers the single-robot environment under the env id \"robot\" with RobotEnv as its "
             "class, and calls it the primary supported training/evaluation environment", source="upstream_code",
             ref=f"{REGISTRY}:165-174"),
        Fact("register_env stores the catalog entry on the module-level _REGISTRY and does not call "
             "gymnasium.register", source="upstream_code", ref=f"{REGISTRY}:94-116"),
        Fact("The catalog names make_robot_env as the factory for the env id robot", source="upstream_code",
             ref=f"{REGISTRY}:169"),
        Fact("make_robot_env defaults debug to false", source="upstream_code", ref=f"{FACTORY}:529"),
        Fact("create_robot_env selects RobotEnv when image observations are off and returns that instance",
             source="upstream_code", ref=f"{FACTORY}:262-268"),
        Fact("make_robot_env builds the environment with EnvironmentFactory.create_robot_env and returns that "
             "instance", source="upstream_code", ref=f"{FACTORY}:672-688"),
        Fact("BaseEnv constructs a SimulationView only when debug or record_video is set", source="upstream_code",
             ref="robot_sf/gym_env/base_env.py:249-250"),
        Fact("RobotEnv is the Gymnasium environment facade and the public environment API for simulation episodes",
             source="upstream_code", ref=f"{ROBOT_ENV}:526-531"),
        Fact("The default DifferentialDriveSettings sets max_linear_speed 2.0, max_angular_speed 1.0, "
             "max_linear_accel 1.0 and max_angular_accel 1.0", source="upstream_code", ref=f"{DRIVE}:29-44"),
        Fact("The linear speed is clipped to min_linear_speed, which is 0.0 when allow_backwards is false",
             source="upstream_code", ref=f"{DRIVE}:103-108"),
        Fact("The action space is a Box over commanded linear and angular accelerations, with "
             "low [-max_linear_decel, -max_angular_accel] and high [max_linear_accel, max_angular_accel]",
             source="upstream_code", ref=f"{DRIVE}:335-343"),
        Fact("The robot observation space is a Box with low [min_linear_speed, -max_angular_speed] and "
             "high [max_linear_speed, max_angular_speed]: the linear and angular speed", source="upstream_code",
             ref=f"{DRIVE}:315-323"),
        Fact("Commanded accelerations are clipped to the acceleration bounds, integrated over the timestep, and "
             "the resulting speeds are clipped to min_linear_speed..max_linear_speed and "
             "-max_angular_speed..max_angular_speed", source="upstream_code", ref=f"{DRIVE}:181-193"),
        Fact("The default simulation timestep is time_per_step_in_secs 0.1 s and the default simulation duration "
             "is sim_time_in_secs 200.0 s", source="upstream_code", ref=f"{SIM_CONFIG}:257-261"),
        Fact("max_sim_steps is the ceiling of sim_time_limit divided by the timestep", source="upstream_code",
             ref=f"{ROBOT_STATE}:63-68"),
        Fact("A simulation step increments the timestep, adds the timestep to the elapsed time and sets is_timeout "
             "at max_sim_steps", source="upstream_code", ref=f"{ROBOT_STATE}:120-130"),
        Fact("is_terminal is true when the route is complete, the time limit expired or the robot collided with a "
             "pedestrian, obstacle or robot", source="upstream_code", ref=f"{ROBOT_STATE}:70-82"),
        Fact("RobotEnv.step returns (observation, reward, terminated, truncated, info) and always reports "
             "truncated False", source="upstream_code", ref=f"{ROBOT_ENV}:1264-1270"),
        Fact("RobotEnv.reset applies the seed through global_reset_seed and _apply_reset_seed and forwards seed "
             "and options to gymnasium Env.reset", source="upstream_code", ref=f"{ROBOT_ENV}:1272-1284"),
        Fact("The environment action space is the robot factory's action space, and its observation space is "
             "fused_sensor_space of the robot observation, a target sensor and a LiDAR sensor",
             source="upstream_code", ref=f"{ENV_UTIL}:363-378"),
        Fact("The default LiDAR scanner has max_scan_dist 10.0 and num_rays 272", source="upstream_code",
             ref=f"{RANGE_SENSOR}:146-148"),
        Fact("The fused observation space is a Dict of drive_state and rays Box members", source="upstream_code",
             ref=f"{SENSOR_FUSION}:71-89"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the
    #: engine, the determinism kind and the lockstep clock; they are written out so the whole contract reads in one
    #: place.
    fidelity = {
        "engine": "robot_sf:RobotEnv-kinematic",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the initial pose and the kinematics are deterministic, "
                     "so one implementation repeats a trajectory for the same seed and actions; this package's fake "
                     "draws the pose with Python's random.Random, while upstream seeds Python and numpy through "
                     "global_reset_seed (robot_sf/gym_env/env_util.py:63-84) and rebuilds the crowd from the seed "
                     "(robot_sf/gym_env/robot_env.py:695-705), so a seed gives different trajectories on the two",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic unicycle model only: no social-force pedestrians, no obstacles, no contacts and no collision "
            "or route-completion terminal condition; the reward is 0 and only the simulated time limit terminates "
            "an episode",
            "the observation is a reduced standing of the fused space: drive_state carries the two robot speeds "
            "and a target vector, and rays carries 8 constant ranges, while the real environment returns a Dict "
            "with 272 LiDAR rays by default (robot_sf/sensor/range_sensor.py:148) and a stacked target vector",
            "the pose is integrated with a simple unicycle Euler step, not the wheel-speed odometry of "
            "DifferentialDriveMotion.move",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "no rendering, recording, telemetry, planner, sensor noise or snapshot/restore; no physical device is "
            "modelled and the model was never validated against one",
            "the fake backend was never compared with the upstream environment (Robot SF was not importable where "
            "the gate ran), so trajectories can differ from upstream's numpy and PySocialForce streams",
        ],
    }
