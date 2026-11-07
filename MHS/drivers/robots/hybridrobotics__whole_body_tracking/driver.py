"""OpenMHS driver for gh.hybridrobotics/whole_body_tracking: the Tracking-Flat-G1-v0 Gymnasium environment.

The repository is an Isaac Lab extension that *configures* one manager-based Gymnasium environment per registered
task; it does not define the environment class.  ``Tracking-Flat-G1-v0`` is registered with entry point
``isaaclab.envs:ManagerBasedRLEnv`` and ``env_cfg_entry_point`` ``G1FlatEnvCfg`` (the card's entry symbol), a
``ManagerBasedRLEnvCfg`` subclass that sets the G1 robot, its joint-position action scale, the motion anchor and the
tracked bodies.  A GymnasiumDriver is configuration only: ``env_id`` names the registered task and the bridge derives
the whole ``cap.world.*`` contract from the environment's spaces.  ``cap.world.reset.v1`` takes ``{seed, options}``
and ``cap.world.seed.v1`` takes ``{seed}``.

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  The G1 tracking environment itself is a learned motion-tracking task over an Isaac Sim humanoid, not a device
that acts on the world.

The acceptance gate cannot import the upstream package (it needs Isaac Sim 4.5.0 and Isaac Lab 2.1.0 on Linux,
README.md:3-6) and never imports the read-only clone.  The ``fake`` backend is therefore this package's pure Python
stand-in (fake.py): it reproduces the shape of the action and observation the bridge reads, a seeded reset and the
episode truncation derived from the configuration, but not Isaac Sim's physics.  A backend name that ``backends``
does not list (``sim``) is served by ``gymnasium.make("Tracking-Flat-G1-v0")`` (GymnasiumDriver.open_native); that
path needs the Isaac Sim/Isaac Lab install, a configuration object and a motion file, and was not run here.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002), not of the engine's
generic capabilities: the Isaac Sim rigid-body tracking task, its 5 ms physics step with decimation 4 (a 20 ms
control step), the seeded reset and the omissions that ``gaps`` lists.  This package is model-authored and
unreviewed; it is checked on the fake backend only and its evidence is ``contract_checked``, never an MHS-Device
level.
"""

from mhs.driver import Fact, GymnasiumDriver

TRACKING = "source/whole_body_tracking/whole_body_tracking/tasks/tracking"
G1_CONFIG = f"{TRACKING}/config/g1"
G1_ROBOT = "source/whole_body_tracking/whole_body_tracking/robots/g1.py"
COMMANDS = f"{TRACKING}/mdp/commands.py"
TRAIN = "scripts/rsl_rl/train.py"


class G1FlatTracking(GymnasiumDriver):
    device_id = "g1-flat-tracking"
    env_id = "Tracking-Flat-G1-v0"
    native = "whole_body_tracking.tasks.tracking.config.g1.flat_env_cfg:G1FlatEnvCfg"
    backends = {"fake": ".fake:FakeTrackingEnv"}
    display_name = "BeyondMimic Tracking-Flat-G1-v0 (Isaac Lab manager-based environment)"
    vendor, model = "HybridRobotics", "Tracking-Flat-G1-v0"
    tags = ["beyondmimic", "g1", "humanoid", "motion-tracking", "isaac-lab", "isaac-sim",
            "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("Tracking-Flat-G1-v0 is registered with entry point isaaclab.envs:ManagerBasedRLEnv, "
             "env_cfg_entry_point flat_env_cfg.G1FlatEnvCfg and rsl_rl_cfg_entry_point G1FlatPPORunnerCfg, with the "
             "environment checker disabled", source="upstream_code", ref=f"{G1_CONFIG}/__init__.py:9-17"),
        Fact("The repository targets Isaac Sim 4.5.0, Isaac Lab 2.1.0, Python 3.10 and Linux", source="vendor_doc",
             ref="README.md:3-6"),
        Fact("G1FlatEnvCfg subclasses TrackingEnvCfg and sets the G1 cylinder robot, the G1 joint action scale, the "
             "torso_link motion anchor and 14 tracked body names from pelvis to the wrists and ankles",
             source="upstream_code", ref=f"{G1_CONFIG}/flat_env_cfg.py:8-31"),
        Fact("TrackingEnvCfg is a ManagerBasedRLEnvCfg that groups the scene, observations, actions, commands, "
             "rewards, terminations, events and curriculum configuration", source="upstream_code",
             ref=f"{TRACKING}/tracking_env_cfg.py:293-307"),
        Fact("The environment uses decimation 4 over a 0.005 s simulation step and an episode length of 10.0 s, so "
             "one control step is 0.02 s and the time-out is 500 control steps", source="upstream_code",
             ref=f"{TRACKING}/tracking_env_cfg.py:309-316"),
        Fact("The sole action term is a joint-position action over every joint of the robot with the default joint "
             "positions as offset", source="upstream_code", ref=f"{TRACKING}/tracking_env_cfg.py:102-106"),
        Fact("G1_ACTION_SCALE maps every actuator joint expression to 0.25 * effort_limit_sim / stiffness",
             source="upstream_code", ref=f"{G1_ROBOT}:184-195"),
        Fact("The policy observation group concatenates command, motion anchor position, motion anchor orientation, "
             "base linear velocity, base angular velocity, joint position, joint velocity and the last action, in "
             "that order, with corruption enabled", source="upstream_code",
             ref=f"{TRACKING}/tracking_env_cfg.py:113-133"),
        Fact("The motion command is the concatenation of the reference joint positions and joint velocities loaded "
             "from the motion file", source="upstream_code", ref=f"{COMMANDS}:100-110"),
        Fact("MotionLoader asserts that the motion file exists and loads fps, joint_pos, joint_vel and body pose, "
             "quaternion and velocity arrays from a numpy NPZ file", source="upstream_code", ref=f"{COMMANDS}:30-42"),
        Fact("MotionCommandCfg.motion_file is MISSING, so a reset cannot run until a motion file is supplied to the "
             "command term by the caller", source="upstream_code", ref=f"{COMMANDS}:357-361"),
        Fact("The termination terms cut an episode when the anchor-z error exceeds 0.25, the projected-gravity "
             "error of the anchor exceeds 0.8, or a tracked end-effector body's z error exceeds 0.25, and time_out "
             "ends it at the episode length", source="upstream_code",
             ref=f"{TRACKING}/tracking_env_cfg.py:257-278"),
        Fact("The command configuration sets the reset pose ranges, the velocity range and a joint position range of "
             "-0.1 to 0.1", source="upstream_code", ref=f"{TRACKING}/tracking_env_cfg.py:85-99"),
        Fact("The robot description is not part of the clone: the README downloads unitree_description.tar.gz from "
             "GCS into the package assets directory before the G1 URDF can be spawned", source="vendor_doc",
             ref="README.md:46-55"),
        Fact("Reference motions are stored in and loaded from the WandB registry, and the reference motion must be "
             "retargeted to the robot and use generalized coordinates", source="vendor_doc", ref="README.md:67-69"),
        Fact("The training script creates the environment with gym.make(task, cfg=env_cfg), so the registered "
             "environment is driven through the Gymnasium make/step/reset interface", source="upstream_code",
             ref=f"{TRAIN}:113-114"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: determinism and lockstep clock; they are written out so the whole contract reads in one place.  The timestep is
    #: the control step the bridge's tick counts; the physics step and decimation are named in the gaps (FID-015).
    fidelity = {
        "engine": "isaaclab:Tracking-Flat-G1-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the upstream environment draws its initial pose, velocity and joint-position randomization "
                     "from the seeded simulator and the motion command term, and the motion file is fixed, so one "
                     "seed and one action sequence are intended to repeat a trajectory on the same engine; this "
                     "package's fake draws its reset state from Python's random.Random, so the same seed gives a "
                     "different trajectory on the fake and upstream, and no upstream run was made",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the deployed model is Isaac Sim/PhysX rigid-body dynamics with contacts (F1), but the fake backend is a "
            "pure Python analytic stand-in: it models no contacts, actuator forces, joint limits, sensors or "
            "contact or observation noise, and its numeric constants are placeholders, not the model's",
            "one cap.world.step tick is one control step of 20 ms (the configuration's decimation 4 over the "
            "0.005 s physics step); the physics step itself is 5 ms, and a client that needs it reads this note "
            "rather than timestep_ms, which names the step the bridge counts",
            "the fake does not load the G1 URDF (downloaded from GCS, README.md:46-55) or a motion NPZ (assigned to "
            "the command term by the caller, commands.py:30-42 and 357-361): its 29-element action vector and "
            "160-element flat observation are placeholder sizes, and the observation terms are zeros and an "
            "identity orientation rather than the configured MDP terms",
            "the upstream policy observation group has eight terms (tracking_env_cfg.py:113-133) whose command width "
            "comes from the motion NPZ; the fake returns one flat float vector, while the upstream environment "
            "returns its observation groups as tensors",
            "the fake models no reward term, no termination event and no time_out DoneTerm: it always returns a "
            "zero reward and terminated=False, and truncates at 500 control steps only because that follows from "
            "episode_length_s 10.0 and the 0.02 s control step",
            "the action space is unbounded in this package because the clone states no action bound (the action "
            "scale of g1.py:184-195 maps a unitless action to a joint target); the fake applies a placeholder gain "
            "instead of that scale and enforces the array length only",
            "no physical robot is modelled and nothing was validated against hardware; the environment is trained "
            "in simulation and deployment is delegated to a separate repository (README.md:23-24)",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the declared step only",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "the upstream environment was never constructed here (Isaac Sim and Isaac Lab are absent) and the fake "
            "was never compared with an upstream run",
        ],
    }
