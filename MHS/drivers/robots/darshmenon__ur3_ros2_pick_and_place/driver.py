"""OpenMHS Gymnasium driver for the UR reach environment of gh.darshmenon/ur3_ros2_pick_and_place.

DEVIATION FROM THE CARD: the card names RosDriver (family ros), but the card's
confirmed entry symbols are Gymnasium environment classes, not a ROS topic or
service surface.  The repository also contains ROS policy nodes, yet the
selected entry point ``mujoco_ur_rl_ros2.envs.ur_reach_env:URReachEnv`` is a
``gymnasium.Env`` driven through ``reset`` and ``step``.  A Gymnasium
environment does not become a ROS transport driver because the repository
contains ROS code, so this package uses ``GymnasiumDriver`` and serves the
catalogue's ``cap.world.step.v1``, ``cap.world.reset.v1`` and
``cap.world.seed.v1`` classes.

The upstream environment builds its scene from MuJoCo Menagerie files under
``$MUJOCO_MENAGERIE_PATH`` or ``~/mujoco_menagerie`` (ur_reach_env.py:11-23),
and neither MuJoCo nor that checkout is installed for this package.  The gate
therefore runs the package's own analytic stand-in, not the upstream
simulator; the fake is F0 contract evidence only.

Every Fact cites the pinned clone at e58ea6178d8d8195beb92387ba365227840a96a9.
No hardware was attached, no ROS graph was started and no MuJoCo simulation
was run while writing this package.
"""

from mhs.driver import Fact, GymnasiumDriver


class URReach(GymnasiumDriver):
    """The UR5e reach Gymnasium environment behind the ``cap.world.*`` classes."""

    device_id = "ur-reach"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    native = "mujoco_ur_rl_ros2.envs.ur_reach_env:URReachEnv"
    backends = {"fake": ".fake:FakeURReachEnv", "sim": ".sim:make_env"}
    # Pinned step integrates exactly five times; reset uses mj_resetData and
    # mj_forward without mj_step. The deployment must have no external stepper.
    timing_by_backend = {
        "sim": {
            "mode": "physics_ticks_v1",
            "control_decimation": 5,
            "physics_timestep_attr": "model.opt.timestep",
            "physics_clock_attr": "data.time",
            "native_autoreset": False,
            "reset_advances_physics": False,
            "source_refs": [
                "mujoco_ur_rl_ros2/envs/ur_reach_env.py:81-98",
                "mujoco_ur_rl_ros2/envs/ur_reach_env.py:100-119",
            ],
        }
    }

    tags = ["gymnasium", "mujoco", "simulation", "ur5e", "reach", "rl"]
    display_name = "UR5e reach Gymnasium environment"
    vendor = "darshmenon"
    model = "UR5e"

    # The fake copies the upstream action-space bounds; cite the line that
    # writes -1.0 and 1.0 (the shape is six from ur_reach_env.py:55).
    action_space_ref = "mujoco_ur_rl_ros2/envs/ur_reach_env.py:65"

    facts = [
        Fact(
            "URReachEnv is a Gymnasium environment (a gym.Env subclass) for a UR5e reach task.",
            source="upstream_code",
            ref="mujoco_ur_rl_ros2/envs/ur_reach_env.py:26-27",
        ),
        Fact(
            "URReachEnv resolves MuJoCo Menagerie models from $MUJOCO_MENAGERIE_PATH or "
            "~/mujoco_menagerie and raises FileNotFoundError when that directory is absent.",
            source="upstream_code",
            ref="mujoco_ur_rl_ros2/envs/ur_reach_env.py:11-23",
        ),
        Fact(
            "URReachEnv models six UR5e joints and composes a 15-number observation from six joint "
            "positions, six joint velocities and three target coordinates.",
            source="upstream_code",
            ref="mujoco_ur_rl_ros2/envs/ur_reach_env.py:55-61",
        ),
        Fact(
            "The normalized joint-velocity action space is a six-element Box with low -1.0 and high 1.0.",
            source="upstream_code",
            ref="mujoco_ur_rl_ros2/envs/ur_reach_env.py:55-66",
        ),
        Fact(
            "Each upstream action is scaled by 0.5 to rad/s and advances the MuJoCo model with five "
            "mj_step calls.",
            source="upstream_code",
            ref="mujoco_ur_rl_ros2/envs/ur_reach_env.py:100-104",
        ),
        Fact(
            "URReachEnv stores the model timestep multiplied by five as its _dt attribute.",
            source="upstream_code",
            ref="mujoco_ur_rl_ros2/envs/ur_reach_env.py:56",
        ),
        Fact(
            "On reset the environment restores the MuJoCo data and samples the target radius from 0.2 to "
            "0.55, the azimuth from -pi/2 to pi/2 and the elevation from 0.1 to pi/2.",
            source="upstream_code",
            ref="mujoco_ur_rl_ros2/envs/ur_reach_env.py:81-93",
        ),
        Fact(
            "The step reward is the negative end-effector-to-target distance plus 1.0 when that distance "
            "is below 0.05.",
            source="upstream_code",
            ref="mujoco_ur_rl_ros2/envs/ur_reach_env.py:106-111",
        ),
        Fact(
            "The episode terminates when the end-effector-to-target distance is below 0.02 and truncates "
            "after the simulated time exceeds 10.0 s.",
            source="upstream_code",
            ref="mujoco_ur_rl_ros2/envs/ur_reach_env.py:113-114",
        ),
        Fact(
            "render() lazily launches a passive MuJoCo viewer when render_mode is human, and close() closes that viewer.",
            source="upstream_code",
            ref="mujoco_ur_rl_ros2/envs/ur_reach_env.py:121-129",
        ),
    ]

    safe_state = (
        "The software latch refuses subsequent world steps; it does not reset the episode or resample the target. "
        "An in-flight native step is not a physical stop; the simulated environment has no hardware output."
    )

    # The deployed package fake is a deterministic, analytic stand-in.  It is
    # not the upstream MuJoCo simulator, so its timestep is zero and the
    # physics gaps below are part of the contract rather than an implicit claim.
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:package stand-in (no MuJoCo physics)",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "seeded",
                "seed_control": "parameter",
                "notes": "the fake seeds a Python random.Random from reset(seed); it exposes no state snapshot",
            },
            "timestep_ms": 0,
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": False,
            "gaps": [
                "the fake is a package stand-in: it does not run MuJoCo, load the universal_robots_ur5e/ur5e.xml "
                "and robotiq_2f85/2f85.xml Menagerie models, or model contacts, a gripper or rigid-body dynamics",
                "the upstream environment needs MuJoCo and a mujoco_menagerie checkout at $MUJOCO_MENAGERIE_PATH "
                "or ~/mujoco_menagerie (ur_reach_env.py:11-23); neither is installed here and the gate never runs "
                "upstream code",
                "the fake returns a 15-number observation (six placeholder joint positions, six placeholder joint "
                "velocities, three placeholder target coordinates) matching the upstream size, but the values are "
                "test data and do not reproduce MuJoCo state",
                "the fake does not model the upstream reward, termination or truncation criteria; it reports a "
                "placeholder distance reward and returns terminated and truncated as false",
                "the fake has no physics timestep, contacts, rendering or viewer and no wall-clock pacing; upstream _dt is the model "
                "timestep times five (ur_reach_env.py:56)",
                "the fake exposes no get_state/set_state, so the bridge cannot take exact snapshots and declares "
                "seeded rather than exact determinism",
            ],
        },
        "sim": {
            "engine": "mujoco:envs.ur_reach_env.URReachEnv",
            "fidelity_level": "F1",
            "determinism": {
                "kind": "seeded", "seed_control": "parameter",
                "notes": "upstream reset seeds Gymnasium; cross-version reproducibility is not validated",
            },
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": False,
            "gaps": [
                "MuJoCo deployment requires the pinned source, compatible numpy/gymnasium/mujoco/stable_baselines3 "
                "and external Menagerie assets; no upstream simulator or real device has been run in this review",
                "physics_ticks_v1 requests physics ticks in multiples of five; one native control call integrates "
                "five physics steps (ur_reach_env.py:56,100-104). The SDK reads model.opt.timestep and data.time; "
                "independent clock advancement and hidden native autoreset are unsupported. This declaration and "
                "synthetic clock tests do not establish actual MuJoCo deployment compatibility",
                "contact, gripper and actuator fidelity depend on external Menagerie models whose versions are not "
                "pinned by this repository; no calibration or hardware validation is claimed",
                "no wall-clock pacing; human rendering is optional, rgb_array is not implemented by the selected "
                "upstream render method, and state snapshots are not supported",
            ],
        },
    }
