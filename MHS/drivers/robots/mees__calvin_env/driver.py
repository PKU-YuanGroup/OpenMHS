"""OpenMHS driver for gh.mees/calvin_env: the CALVIN PyBullet table-top environment (a Gymnasium family driver).

``PlayTableSimEnv`` is a legacy Gym environment: ``reset(scene_obs, robot_obs)`` returns one observation and
``step(action)`` returns the four-value ``(obs, reward, done, info)`` tuple, with ``reward`` always 0 and ``done``
always False (play_table_env.py:170-174 and :222-243).  The environment defines no ``action_space`` or
``observation_space``; an action is a dict such as ``{"type": "cartesian_rel", "action": [x, y, z, rx, ry, rz, gripper]}``
or one of the other three dict types of ``Robot.apply_action`` (robot.py:245-295).  A GymnasiumDriver is configuration
only, so this package narrows the reset contract to the seed the legacy ``seed()`` method supports, leaves the step
``action`` as the open object of ``cap.world.step.v1`` and passes the action through unchanged.

The device is a simulator (R0): there is no hardware backend, no physical stop and no operator-required bound.  The
``fake`` backend is the package's own pure Python kinematic stand-in for the class named by ``native``; the gate never
imports the clone and pybullet/EGL are not available where it runs.  The ``fidelity`` attribute is the contract of the
model as deployed, including the differences listed in its ``gaps``.  Every fact cites a line of the clone at the pinned
commit 797142c588c21e76717268b7b430958dbd13bf48.  This package is model-authored and unreviewed: it is checked on the
fake backend only, and no hardware or upstream run is claimed.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "calvin_env/envs/play_table_env.py"
ROBOT = "calvin_env/robot/robot.py"
SCENE = "calvin_env/scene/play_table_scene.py"
ENV_CONF = "conf/env/play_table_env.yaml"
PANDA_CONF = "conf/robot/panda.yaml"
STATIC_CAMERA_CONF = "conf/cameras/cameras/static.yaml"
GRIPPER_CAMERA_CONF = "conf/cameras/cameras/gripper.yaml"
TACTILE_CAMERA_CONF = "conf/cameras/cameras/tactile.yaml"


class CalvinPlayTable(GymnasiumDriver):
    device_id = "calvin_env"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    native = "calvin_env.envs.play_table_env:PlayTableSimEnv"
    backends = {"fake": ".fake:FakePlayTableSimEnv"}
    env_id = None
    display_name = "CALVIN PlayTableSimEnv (PyBullet table-top environment)"
    vendor, model = "Mees", "CALVIN PlayTableSimEnv"
    tags = ["calvin", "simulation", "pybullet", "gym", "manipulation", "reinforcement-learning", "world"]
    facts = [
        Fact("PlayTableSimEnv is a gym.Env subclass", source="upstream_code", ref=f"{ENV}:27"),
        Fact("The constructor takes bullet_time_step and control_freq (default 30) and sets action_repeat to "
             "int(bullet_time_step // control_freq)", source="upstream_code", ref=f"{ENV}:28-53"),
        Fact("The play_table_env configuration sets bullet_time_step 240.0 and control_freq 30",
             source="upstream_code", ref=f"{ENV_CONF}:5-12"),
        Fact("initialize_bullet sets the physics timestep to 1.0 / bullet_time_step", source="upstream_code",
             ref=f"{ENV}:126"),
        Fact("reset(scene_obs, robot_obs) resets the scene and robot, advances one physics step and returns get_obs()",
             source="upstream_code", ref=f"{ENV}:170-174"),
        Fact("seed(seed) sets np_random with gym.utils.seeding.np_random and returns [seed]", source="upstream_code",
             ref=f"{ENV}:176-179"),
        Fact("step(action) applies robot.apply_action(action), advances physics action_repeat times, steps the scene "
             "and returns obs, 0, False, info", source="upstream_code", ref=f"{ENV}:222-243"),
        Fact("get_camera_obs renders every camera to an rgb and a depth array", source="upstream_code",
             ref=f"{ENV}:181-189"),
        Fact("get_obs returns the camera observations and the robot and scene state observations", source="upstream_code",
             ref=f"{ENV}:191-196"),
        Fact("get_state_obs returns robot_obs from Robot.get_observation() and scene_obs from PlayTableScene.get_obs()",
             source="upstream_code", ref=f"{ENV}:198-213"),
        Fact("get_info returns robot_info and, when use_scene_info is set, scene_info", source="upstream_code",
             ref=f"{ENV}:215-220"),
        Fact("Robot.get_observation returns the tcp position, the tcp orientation, the gripper opening width, the "
             "seven arm joint states and the gripper action", source="upstream_code", ref=f"{ROBOT}:181-212"),
        Fact("Robot.apply_action accepts the dict types joint_rel, joint_abs, cartesian_rel and cartesian_abs, plus "
             "a raw relative action array", source="upstream_code", ref=f"{ROBOT}:245-291"),
        Fact("The relative action scales default to max_rel_pos 0.02 and max_rel_orn 0.05", source="upstream_code",
             ref=f"{ROBOT}:33-34"),
        Fact("relative_to_absolute multiplies the relative position by max_rel_pos and the relative orientation by "
             "max_rel_orn", source="upstream_code", ref=f"{ROBOT}:228-237"),
        Fact("The gripper action must be -1 or 1", source="upstream_code", ref=f"{ROBOT}:293-295"),
        Fact("The configured gripper joint limits are 0 to 0.04", source="upstream_code", ref=f"{PANDA_CONF}:12"),
        Fact("The panda configuration sets euler_obs true, so the tcp orientation is three Euler angles",
             source="upstream_code", ref=f"{PANDA_CONF}:22"),
        Fact("The static camera is configured at 200 by 200 pixels", source="upstream_code",
             ref=f"{STATIC_CAMERA_CONF}:7-8"),
        Fact("The gripper camera is configured at 84 by 84 pixels", source="upstream_code",
             ref=f"{GRIPPER_CAMERA_CONF}:7-8"),
        Fact("The tactile camera is configured at 120 by 160 pixels", source="upstream_code",
             ref=f"{TACTILE_CAMERA_CONF}:3-4"),
        Fact("PlayTableScene.get_obs concatenates door, button, switch, light and movable-object states",
             source="upstream_code", ref=f"{SCENE}:152-160"),
        Fact("get_env loads the dataset's merged Hydra configuration and instantiates the environment",
             source="upstream_code", ref=f"{ENV}:267-286"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: The upstream reset takes the initial scene and robot observations, not a seed or options.  The bridge's legacy
    #: path can apply a seed through seed(); options are not forwarded to a reset with this signature, so the contract
    #: advertises only the seed and refuses anything else instead of silently dropping it.
    _RESET_INPUTS = {
        "seed": {"type": "integer", "minimum": 0,
                 "description": "Seed applied through the legacy seed() before reset; it fixes the fake's scene draw"},
    }
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  timestep_ms is one control step:
    #: action_repeat 8 physics ticks at 1/240 s from the configuration (conf/env/play_table_env.yaml:5-12,
    #: play_table_env.py:53 and :126), i.e. 1/30 s.
    fidelity = {
        "engine": "pybullet:PlayTableSimEnv",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the upstream seed() feeds gym.utils.seeding.np_random and the fake seeds Python's random.Random; "
                     "one implementation repeats a scene draw for one seed, but the two generators differ, so a seed "
                     "does not give the same trajectory on the fake and on a pybullet run",
        },
        "timestep_ms": 1000.0 / 30.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no pybullet rigid-body dynamics, contacts, inverse kinematics, motors or sensors: the fake advances a "
            "kinematic tcp pose and a small scene state, so objects never move and contacts are not computed",
            "the camera arrays are 4x4 RGB and 4x4 depth placeholders; the configured static camera is 200x200 and "
            "the gripper camera 84x84 (conf/cameras/cameras/static.yaml:7-8 and gripper.yaml:7-8), so NOT COVERED: "
            "the full-resolution rgb and depth camera arrays",
            "the scene model is one door, one button, one switch, one light and three movable poses, not the configured "
            "CALVIN scene objects; scene_obs is a simplified flat list",
            "the upstream reset(scene_obs, robot_obs) inputs are not exposed by the bridge's legacy reset path: only a "
            "seed reaches the environment, and reset options are not forwarded",
            "the fake was never compared with a pybullet run: the upstream package needs pybullet, EGL and a dataset "
            "directory and was not installed or run where the gate ran",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
