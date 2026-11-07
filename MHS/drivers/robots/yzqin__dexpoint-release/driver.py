"""OpenMHS driver for gh.yzqin/dexpoint-release: the DexPoint Allegro relocation simulation.

``AllegroRelocateRLEnv`` is a legacy ``gym.Env`` built in-process on SAPIEN: it has no transport, no serial port
and no vendor SDK, so the card's ``family-config`` / ``GymnasiumDriver`` shape is the right one.  The class
attributes only configure the family; the ``cap.world.step/reset/seed`` contract is derived from the environment's
spaces by the gymnasium bridge.

The upstream simulator needs SAPIEN 2.1.0, a display/renderer and data files the clone does not carry (``day.ktx``
and the ShapeNet/EGAD assets are download links in ``README.md``), and package code never imports or runs the clone.
The ``fake`` backend is therefore this package's own pure-Python kinematic stand-in (``fake.py``); no ``sim`` or
``hardware`` backend is declared.  The fidelity contract describes that model as deployed: level F0 (a kinematic
stand-in, no dynamics), seeded reset draws, one control step per tick.

Every Fact cites a line of the clone at the pinned commit (17f1e238bb120d92baabe8207494d48476fea289).  This package
is model-authored and unreviewed; it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

RELOCATE = "dexpoint/env/rl_env/relocate_env.py"
RL_BASE = "dexpoint/env/rl_env/base.py"
SIM_RELOCATE = "dexpoint/env/sim_env/relocate_env.py"
SIM_BASE = "dexpoint/env/sim_env/base.py"


class DexPointAllegroRelocate(GymnasiumDriver):
    device_id = "dexpoint_allegro_relocate"
    native = "dexpoint.env.rl_env.relocate_env:AllegroRelocateRLEnv"
    backends = {"fake": ".fake:FakeAllegroRelocateRLEnv"}
    action_space_ref = f"{RL_BASE}:401-402"
    display_name = "DexPoint Allegro relocation (SAPIEN manipulation simulation)"
    vendor, model = "Yuzhe Qin et al.", "DexPoint 0.4.0"
    tags = ["dexpoint", "dexterous-manipulation", "allegro", "sapien", "simulation", "reinforcement-learning",
            "point-cloud"]
    facts = [
        Fact("The repository contains the simulated environment and training code for DexPoint",
             source="vendor_doc", ref="README.md:11-12"),
        Fact("The environment is constructed in-process from its Python class with keyword arguments, with no "
             "transport setup", source="upstream_code", ref="example/example_use_state_only_env.py:14-22"),
        Fact("AllegroRelocateRLEnv is the concrete environment; LabRelocateEnv and BaseRLEnv are its parents",
             source="upstream_code", ref=f"{RELOCATE}:16"),
        Fact("The constructor defaults the robot to allegro_hand_xarm6_wrist_mounted_face_front, the object "
             "category to YCB and the object to tomato_soup_can", source="upstream_code", ref=f"{RELOCATE}:17-19"),
        Fact("The default robot's configuration declares hand_dof 16 and arm_dof 6",
             source="upstream_code", ref="dexpoint/utils/common_robot_utils.py:53-56"),
        Fact("The action space is Box(low=-1, high=1) with shape (action_dim,)", source="upstream_code",
             ref=f"{RL_BASE}:400-402"),
        Fact("action_dim returns the robot's degree-of-freedom count", source="upstream_code", ref=f"{RL_BASE}:78-80"),
        Fact("The oracle state concatenates robot qpos (dof), palm position (3), object pose (7), object-to-tip "
             "offsets (12), contact flags (5), target offset (3), target quaternion (4) and target "
             "angle (1)", source="upstream_code", ref=f"{RELOCATE}:87-91"),
        Fact("For a state-only environment obs_dim is the length of the oracle state", source="upstream_code",
             ref=f"{RL_BASE}:314-319"),
        Fact("The observation space is a Box from -infinity to +infinity with obs_dim elements",
             source="upstream_code", ref=f"{RL_BASE}:404-408"),
        Fact("The SAPIEN scene timestep is 0.005 s", source="upstream_code", ref=f"{SIM_RELOCATE}:28-29"),
        Fact("One control step advances frame_skip simulation steps: control_time_step is the scene timestep times "
             "frame_skip", source="upstream_code", ref=f"{RL_BASE}:111-113"),
        Fact("The horizon is 200 control steps", source="upstream_code", ref=f"{RELOCATE}:155-157"),
        Fact("OBJECT_LIFT_LOWER_LIMIT is -0.03", source="upstream_code", ref=f"{RELOCATE}:13"),
        Fact("An episode is done when object_lift is below OBJECT_LIFT_LOWER_LIMIT",
             source="upstream_code", ref=f"{RELOCATE}:152-153"),
        Fact("step applies the action, updates the cached state and returns (observation, reward, done, info); at "
             "the horizon it sets done and info['TimeLimit.truncated']", source="upstream_code",
             ref=f"{RL_BASE}:204-217"),
        Fact("reset re-seeds when a seed is given, resets the internal state and returns the new observation",
             source="upstream_code", ref=f"{RELOCATE}:124-150"),
        Fact("The object start pose is drawn uniformly in x and y from (-0.1, 0.1) times randomness_scale at the "
             "object height", source="upstream_code", ref=f"{SIM_RELOCATE}:81-88"),
        Fact("The target pose is drawn uniformly in x and y from (-0.2, 0.2) times randomness_scale at height "
             "0.25", source="upstream_code", ref=f"{SIM_RELOCATE}:91-100"),
        Fact("seed installs the random generator and returns [seed]", source="upstream_code", ref=f"{SIM_BASE}:58-60"),
        Fact("The reward gives 0.5 on contact, 10 times the lift clipped to 0..0.2, a 1.0 bonus above 0.02 lift "
             "plus 1/(0.04 + target distance), and divides the total by 10", source="upstream_code",
             ref=f"{RELOCATE}:100-122"),
        Fact("The thumb's finger reward scale is 0.04 and the other three tips use 0.01", source="upstream_code",
             ref=f"{RELOCATE}:52-53"),
        Fact("The package requires numpy, transforms3d, gym 0.25.2, sapien 2.1.0, open3d, imageio and torch, and "
             "declares Python 3.8 or newer", source="upstream_code", ref="setup.py:18-27"),
        Fact("The installation instructions download day.ktx and place it at assets/misc/ktx/day.ktx",
             source="vendor_doc", ref="README.md:37-39"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the last observation and state stay readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The deployed backend is the
    #: pure-Python kinematic stand-in in fake.py, so the level is F0: it has no rigid-body dynamics or contacts.
    fidelity = {
        "engine": "analytic:dexpoint-allegro-relocate-stand-in",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the object and target draw, and the stand-in is "
                     "deterministic after that; the fake draws with Python's random module while upstream draws "
                     "with numpy's generator, so one seed gives different poses on the two",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no dynamics: the stand-in advances a step counter and integrates the first three action values into "
            "a palm position; it models no rigid-body motion, contact, friction, actuator or sensor, and the "
            "object and target stay at their reset poses",
            "the observation has the upstream layout but its fingertip offsets, contact flags, object height and "
            "quaternion are fixed placeholders that no collision engine computes, and only the first three action "
            "values move the palm; the hand values are recorded as qpos",
            "the initial object and target poses use Python's random module, upstream uses numpy's generator, so "
            "a seed gives different poses on the two",
            "timestep_ms 50.0 is the upstream control step (0.005 s scene timestep x the constructor default "
            "frame_skip 10 at dexpoint/env/rl_env/relocate_env.py:17); the stand-in only counts steps",
            "the stand-in was never compared with a SAPIEN run: sapien 2.1.0 is not installed where the gate runs "
            "and the clone does not carry the day.ktx or ShapeNet/EGAD assets its README downloads",
            "no rendering, visual observation, imagination buffers or passive environment checker is modelled",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
