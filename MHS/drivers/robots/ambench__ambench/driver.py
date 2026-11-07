"""OpenMHS driver for gh.ambench/ambench: the PressButton-Am-EE-Abs-PID-Direct-v0 environment.

A GymnasiumDriver is configuration: ``env_id`` names the registered task and the bridge derives the contract from
the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{values}`` derived from
the environment's Box, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The
device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

AM-Bench is an Isaac Lab suite: the upstream environment needs Isaac Sim 5.1, a Linux host, an NVIDIA GPU and
Python 3.11 (README.md:42-43), so nothing from the clone is imported or run by this package and the ``fake`` backend
is the package's own pure Python kinematic stand-in for ``ambench.tasks.press_button.press_button_env:PressButton``.
A backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)``
(GymnasiumDriver.open_native); that path needs Isaac Sim and Isaac Lab and was not run here.

The environment's actual Gym spaces are built by Isaac Lab, outside the clone: the clone declares the action
dimension (``action_space: int``, base_env_cfg.py:47) and the observation-space members (base_env_cfg.py:28-39 and
press_button_env_cfg.py:175-180), so the fake publishes a Box of eight unbounded values and a Dict with those eleven
members.  The ``fidelity`` attribute is the complete fidelity contract of the model (spec 05-fidelity FID-002); every
fact cites a line of the clone at the pinned commit 60bf5b73041df4eab571f7d9f0a297aeecbf2e0d.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

BASE_ENV = "source/ambench/ambench/tasks/base/base_env.py"
BASE_CFG = "source/ambench/ambench/tasks/base/base_env_cfg.py"
PRESS = "source/ambench/ambench/tasks/press_button/press_button_env.py"
PRESS_CFG = "source/ambench/ambench/tasks/press_button/press_button_env_cfg.py"
PRESS_INIT = "source/ambench/ambench/tasks/press_button/__init__.py"
REGISTRY = "source/ambench/ambench/tasks/_registration.py"
PIPELINE = "source/ambench/ambench/controllers/control_pipeline.py"
ROBOT_IO = "source/ambench/ambench/robots/robot_io.py"
EEF = "source/ambench/ambench/robots/eef.py"
WALL = "source/ambench/ambench/scenes/wall.py"


class PressButtonEE(GymnasiumDriver):
    device_id = "ambench-press-button"
    env_id = "PressButton-Am-EE-Abs-PID-Direct-v0"
    native = "ambench.tasks.press_button.press_button_env:PressButton"
    backends = {"fake": ".fake:FakePressButtonEnv"}
    display_name = "AM-Bench PressButton (free end-effector, absolute PID pose)"
    vendor, model = "The AM-Bench Contributors", "PressButton-Am-EE-Abs-PID-Direct-v0"
    tags = ["aerial-manipulation", "isaac-lab", "isaac-sim", "press-button", "reinforcement-learning",
            "simulation", "gymnasium"]
    facts = [
        Fact("BaseEnv is a DirectRLEnv subclass and holds the shared simulation lifecycle around one robot profile "
             "and control pipeline", source="upstream_code", ref=f"{BASE_ENV}:29-30"),
        Fact("PressButton extends BaseEnv", source="upstream_code", ref=f"{PRESS}:17"),
        Fact("PressButton-Am-EE-Abs-PID-Direct-v0 is registered with entry_point "
             "press_button_env:PressButton and env_cfg_entry_point press_button_env_cfg:PressButtonEnvEEAbsPIDCfg",
             source="upstream_code", ref=f"{PRESS_INIT}:11-16"),
        Fact("register_env calls gym.register(id=task_id, entry_point=entry_point, disable_env_checker=True, ...)",
             source="upstream_code", ref=f"{REGISTRY}:19-26"),
        Fact("For ABSOLUTE_EE_POSE the control pipeline's action_dim returns 8", source="upstream_code",
             ref=f"{PIPELINE}:49-53"),
        Fact("The pipeline reads the action position from action[:, :3] and the quaternion from action[:, 3:7], and "
             "adds the scene env origins to the position", source="upstream_code", ref=f"{PIPELINE}:93-95"),
        Fact("The end-effector pipeline passes action[:, -1] to compute_gripper_targets",
             source="upstream_code", ref=f"{PIPELINE}:150-153"),
        Fact("The gripper command is clamped to -1..1 and mapped as -1 closed and +1 open onto the ordered gripper "
             "joint targets", source="upstream_code", ref=f"{ROBOT_IO}:133-151"),
        Fact("The observation for one environment is ee_pos (3), ee_quat (4), ee_lin_vel (3), ee_ang_vel (3), "
             "base_pos (3), base_quat (4), base_lin_vel (3), base_ang_vel (3), gripper_width (1), button_pressed (1) "
             "and goal_pos (3)", source="upstream_code", ref=f"{PRESS}:81-97"),
        Fact("The observation is returned wrapped as {'policy': [one dict per environment]}; arm_joint_pos and "
             "arm_joint_vel are added only when the robot profile has arm joints", source="upstream_code",
             ref=f"{PRESS}:99-106"),
        Fact("The base observation space is a gymnasium Dict of float32 Boxes: positions and velocities are "
             "unbounded, quaternions are bounded to -1..1 and gripper_width is 0..inf", source="upstream_code",
             ref=f"{BASE_CFG}:28-39"),
        Fact("The PressButton observation space adds button_pressed as a 0..1 Box of one element and goal_pos as an "
             "unbounded three-element Box", source="upstream_code", ref=f"{PRESS_CFG}:175-180"),
        Fact("The task succeeds when the button plunger joint position is at least button_pressed_threshold",
             source="upstream_code", ref=f"{PRESS}:36-39"),
        Fact("The plunger slide joint travel is 0.0 (unpressed) to 0.01 (fully pressed) and success uses the 0.004 "
             "threshold", source="upstream_code", ref=f"{PRESS_CFG}:167-170"),
        Fact("The PressButton reward is always zeros, whatever the state", source="upstream_code",
             ref=f"{PRESS}:108-110"),
        Fact("The episode is truncated when episode_length_buf reaches max_episode_length - 1",
             source="upstream_code", ref=f"{BASE_ENV}:122"),
        Fact("The task's episode_length_s is 20", source="upstream_code", ref=f"{PRESS_CFG}:104"),
        Fact("The simulation timestep is 1/120 s and decimation is 1", source="upstream_code",
             ref=f"{BASE_CFG}:46-52"),
        Fact("BaseEnv sets self.dt = cfg.sim.dt * cfg.decimation", source="upstream_code", ref=f"{BASE_ENV}:39"),
        Fact("The free end-effector robot starts at position (0.0, 0.0, 1.0) with the identity quaternion and its "
             "two finger joints at 0.001 each", source="upstream_code", ref=f"{EEF}:29-35"),
        Fact("The free end-effector profile names ee_link as its control body, base body and end-effector "
             "body", source="upstream_code", ref=f"{EEF}:63-65"),
        Fact("The wall is at (2.0, 0.0, 1.0)", source="upstream_code", ref=f"{PRESS_CFG}:109"),
        Fact("The wall default size is (0.1, 2.0, 2.0)", source="upstream_code", ref=f"{WALL}:18"),
        Fact("The button is placed on the wall surface, offset by half the wall thickness in front of the wall",
             source="upstream_code", ref=f"{PRESS_CFG}:120-127"),
        Fact("Each reset randomizes the wall x and y by -0.2..0.2 and its pitch by -0.2..0.2 rad, and the button "
             "position on the wall by -0.3..0.3 in y and z", source="upstream_code", ref=f"{PRESS_CFG}:43-68"),
        Fact("AM-Bench requires a native Linux host, a discrete NVIDIA GPU and Isaac Sim 5.1 with Python 3.11",
             source="vendor_doc", ref="README.md:42-43"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "isaaclab:PressButton-Am-EE-Abs-PID-Direct-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the upstream reset reseeds the environment's event RNG and the physics is stepped in "
                     "lockstep; the package's fake seeds Python's random.Random from reset(seed) or "
                     "cap.world.seed.v1, so one seed and one action sequence repeat its state hashes.  The fake was "
                     "not compared with the Isaac Lab environment, and GPU physics determinism was not exercised",
        },
        "timestep_ms": 8.333333333333334,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is kinematic: it moves the end effector toward the commanded absolute pose and models "
            "the button press geometrically; it has no rigid-body dynamics, contacts, collision response, actuator, "
            "sensor or noise model, so it is an F0 stand-in for an F1 environment and was not compared with Isaac Lab",
            "the action-space bounds are not declared in the clone: the config declares only the dimension "
            "(base_env_cfg.py:47) and Isaac Lab builds the Gym Box outside the clone; the fake publishes an "
            "unbounded Box of eight values, so the runtime has no per-element action bound",
            "no wall-clock pacing: realtime_factor 0, one tick is one 1/120 s physics step (decimation 1), and the "
            "episode truncates after the 20 s episode_length_s expressed in those steps",
            "the fake returns the per-environment observation dictionary directly, while PressButton._get_observations "
            "wraps it in {'policy': [dict]} (press_button_env.py:99-106); the bridge therefore publishes the eleven "
            "fields without the policy wrapper",
            "the fake randomizes only the button position; the upstream reset also randomizes the wall pose and the "
            "button scale through Isaac Lab event terms (press_button_env_cfg.py:43-98), whose RNG and GPU "
            "determinism were not run",
            "no physical device is modelled and the model was never validated against hardware; snapshot and restore "
            "are not offered because the environment exposes no get_state/set_state",
        ],
    }
