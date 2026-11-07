"""OpenMHS driver for gh.boosterrobotics/booster_train: the Booster-T1-MotionTracking-v0 Gymnasium environment.

The repository is an Isaac Lab extension that *configures* one manager-based Gymnasium environment per registered
task; it does not define the environment class.  ``Booster-T1-MotionTracking-v0`` is registered with entry point
``isaaclab.envs:ManagerBasedRLEnv`` and ``env_cfg_entry_point`` ``RoughWoStateEstimationEnvCfg`` (the card's entry
symbol), a ``ManagerBasedRLEnvCfg`` subclass that sets the 23-DoF T1 robot, its joint-position action scale, the
motion anchor and the tracked bodies.  A GymnasiumDriver is configuration only: ``env_id`` names the registered task
and the bridge derives the whole ``cap.world.*`` contract from the environment's spaces.  ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  The T1 motion-tracking environment is a learned motion-tracking task over an Isaac Sim humanoid, not a device
that acts on the world; deployment to a real robot is delegated to the separate booster_deploy repository
(README.md:63).

The acceptance gate cannot import the upstream package (it needs Isaac Lab 2.3.2, Isaac Sim 5.1.0 and booster_assets,
README.md:5-7 and :19-21) and never imports the read-only clone.  The ``fake`` backend is therefore this package's
pure Python stand-in (fake.py): it reproduces the shape of the action and observation the bridge reads, a seeded reset
and the episode truncation derived from the configuration, but not Isaac Sim's physics.  A backend name that
``backends`` does not list (``sim``) is served by ``gymnasium.make("Booster-T1-MotionTracking-v0")``
(GymnasiumDriver.open_native); that path needs the Isaac Sim/Isaac Lab install, a configuration object and the T1
motion file, and was not run here.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002), not of the engine's
generic capabilities: the Isaac Sim rigid-body tracking task, its 5 ms physics step with decimation 4 (a 20 ms
control step), the seeded reset and the omissions that ``gaps`` lists.  This package is model-authored and
unreviewed; it is checked on the fake backend only and its evidence is ``contract_checked``, never an MHS-Device
level.
"""

from mhs.driver import Fact, GymnasiumDriver

T1 = "source/booster_train/booster_train/tasks/manager_based/beyond_mimic/robots/t1/motion_tracking"
TRACKING = f"{T1}/tracking_env_cfg.py"
ENV_CFG = f"{T1}/env_cfg.py"
COMMANDS = "source/booster_train/booster_train/tasks/manager_based/beyond_mimic/mdp/commands.py"
T1_ROBOT = "source/booster_train/booster_train/assets/robots/booster_t1.py"
JOINT_NAMES = "source/booster_train/booster_train/assets/robots/motion_joint_names.py"
TRAIN = "scripts/rsl_rl/train.py"


class BoosterT1MotionTracking(GymnasiumDriver):
    device_id = "booster-t1-motion-tracking"
    env_id = "Booster-T1-MotionTracking-v0"
    native = ("booster_train.tasks.manager_based.beyond_mimic.robots.t1.motion_tracking.env_cfg:"
              "RoughWoStateEstimationEnvCfg")
    backends = {"fake": ".fake:FakeT1TrackingEnv"}
    display_name = "Booster T1 MotionTracking-v0 (Isaac Lab manager-based environment)"
    vendor, model = "Booster Robotics", "Booster-T1-MotionTracking-v0"
    tags = ["booster", "t1", "humanoid", "motion-tracking", "beyondmimic", "isaac-lab", "isaac-sim",
            "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("Booster-T1-MotionTracking-v0 is registered with entry point isaaclab.envs:ManagerBasedRLEnv, "
             "env_cfg_entry_point env_cfg.RoughWoStateEstimationEnvCfg, rsl_rl_cfg_entry_point ppo_cfg.PPORunnerCfg "
             "and the environment checker disabled", source="upstream_code", ref=f"{T1}/__init__.py:13-21"),
        Fact("The registered T1 policy environment is RoughWoStateEstimationEnvCfg, which derives from "
             "FlatWoStateEstimationEnvCfg; that parent sets the policy motion_anchor_pos_b and base_lin_vel "
             "observation terms to None", source="upstream_code", ref=f"{ENV_CFG}:42-50"),
        Fact("FlatEnvCfg assigns the T1 robot configuration, the T1 action scale, the motion file t1_dance.npz, the "
             "trunk motion anchor and 18 tracked body names from the trunk to the ankles", source="upstream_code",
             ref=f"{ENV_CFG}:10-38"),
        Fact("The default T1 motion file is the bare relative name t1_dance.npz, not a path under booster_assets",
             source="upstream_code", ref=f"{ENV_CFG}:17"),
        Fact("TrackingEnvCfg is a ManagerBasedRLEnvCfg that groups the scene, observations, actions, commands, "
             "rewards, terminations, events and curriculum configuration", source="upstream_code",
             ref=f"{TRACKING}:307-320"),
        Fact("The environment uses decimation 4 over a 0.005 s simulation step and an episode length of 10.0 s, so "
             "one control step is 0.02 s and the time-out is 500 control steps", source="upstream_code",
             ref=f"{TRACKING}:325-328"),
        Fact("The sole action term is a joint-position action over every joint of the robot with the default joint "
             "positions as offset", source="upstream_code", ref=f"{TRACKING}:107"),
        Fact("The policy observation group concatenates the motion command, the motion anchor orientation matrix "
             "prefix, base angular velocity, joint position, joint velocity and the last action, in that order, with "
             "corruption enabled", source="upstream_code", ref=f"{TRACKING}:119-134"),
        Fact("The motion command is the concatenation of the reference joint positions and joint velocities loaded "
             "from the motion file", source="upstream_code", ref=f"{COMMANDS}:137-139"),
        Fact("MotionLoader asserts that the motion file exists, loads it with numpy and reads fps, joint positions, "
             "joint velocities, body positions, orientations and linear and angular velocities, selecting the "
             "tracked bodies and joints by name", source="upstream_code", ref=f"{COMMANDS}:30-65"),
        Fact("The T1 robot configuration spawns T1_23dof.urdf from the external booster_assets directory, so the "
             "23-DoF robot description is not part of this clone", source="upstream_code", ref=f"{T1_ROBOT}:22-25"),
        Fact("T1_CSV_JOINT_NAMES lists the 23 T1 joints in motion order: two head joints, four joints per arm, the "
             "waist yaw joint, four joints per leg and two ankle joints per leg", source="upstream_code",
             ref=f"{JOINT_NAMES}:28-52"),
        Fact("The T1 actuator groups cover the arms, waist, legs, feet and head, which are the joints the "
             "joint-position action term drives", source="upstream_code", ref=f"{T1_ROBOT}:58-125"),
        Fact("The repository targets Isaac Lab 2.3.2 and Isaac Sim 5.1.0 and supports the T2, T1 and K1 platforms",
             source="vendor_doc", ref="README.md:5-7"),
        Fact("booster_assets must be cloned and installed separately because it holds the Booster robot models and "
             "motion data", source="vendor_doc", ref="README.md:19-21"),
        Fact("The package is installed in editable mode with python -m pip install -e source/booster_train",
             source="vendor_doc", ref="README.md:27"),
        Fact("After training, deployment in MuJoCo or on real Booster robots is done in the separate booster_deploy "
             "repository", source="vendor_doc", ref="README.md:63"),
        Fact("The training script launches the Omniverse app through AppLauncher(parser) before the environment is "
             "created", source="upstream_code", ref=f"{TRAIN}:49"),
        Fact("The training script creates the registered task with gym.make(task, cfg=env_cfg), so the environment "
             "is driven through the Gymnasium make/step/reset interface", source="upstream_code", ref=f"{TRAIN}:155"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: determinism and lockstep clock; they are written out so the whole contract reads in one place.  The timestep
    #: is the control step the bridge's tick counts; the physics step and decimation are named in the gaps (FID-015).
    fidelity = {
        "engine": "isaaclab:Booster-T1-MotionTracking-v0",
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
            "the fake does not load the T1 URDF (downloaded with booster_assets, README.md:19-21, T1_23dof.urdf at "
            "booster_t1.py:25) or the t1_dance.npz motion file (a bare name at env_cfg.py:17): its 23-element "
            "action vector and 124-element flat observation are placeholder sizes, and the observation terms are "
            "zeros and an identity orientation rather than the configured MDP terms",
            "the upstream policy observation group has six active terms after the T1 rough configuration disables "
            "motion_anchor_pos_b and base_lin_vel (env_cfg.py:42-46, tracking_env_cfg.py:119-134); the fake returns "
            "one flat float vector, while the upstream environment returns its observation groups as tensors",
            "the fake models no reward term, no termination event and no time_out DoneTerm: it always returns a "
            "zero reward and terminated=False, and truncates at 500 control steps only because that follows from "
            "episode_length_s 10.0 and the 0.02 s control step",
            "the action space is unbounded in this package because the clone states no action bound (the action "
            "scale of booster_t1.py:128-168 maps a unitless action to a joint target); the fake applies a "
            "placeholder gain instead of that scale and enforces the array length only",
            "no physical robot is modelled and nothing was validated against hardware; the environment is trained "
            "in simulation and deployment is delegated to a separate repository (README.md:63)",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the declared step only",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "the upstream environment was never constructed here (Isaac Sim, Isaac Lab and booster_assets are "
            "absent) and the fake was never compared with an upstream run",
        ],
    }
