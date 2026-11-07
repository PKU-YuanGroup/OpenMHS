"""OpenMHS driver for gh.andy-xiong6/bipedal_locomotion_isaaclab: the pointfoot blind-flat Isaac Lab task.

The repository registers Gymnasium simulation tasks for pointfoot and wheelfoot bipedal robots.  The card's entry
symbols are two environment-configuration classes; this package serves the pointfoot flat task
``Isaac-PF-Blind-Flat-v0``, whose config is ``PFBlindFlatEnvCfg``.  A ``GymnasiumDriver`` is configuration only:
``env_id`` names the registered task, ``native`` names the config class the card confirmed, and the bridge derives
the whole ``cap.world.*`` contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}``
with the action shaped by the action space (a six-value ``Box`` of raw joint-position offsets), ``cap.world.reset.v1``
takes ``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.

The upstream environment is the external ``omni.isaac.lab.envs:ManagerBasedRLEnv`` (``__init__.py:64-71``) and needs
Isaac Sim 4.2.0 and Isaac Lab 1.4.0 with a GPU (README.md:7-8); it is not importable where the gate runs, and package
code never imports or runs the clone.  The ``fake`` backend is therefore the package's own pure Python kinematic
stand-in (fake.py).  A backend name that ``backends`` does not list (``sim``) would be served by
``gymnasium.make("Isaac-PF-Blind-Flat-v0")`` through ``GymnasiumDriver.open_native``; that path needs the upstream
stack and the registration to be imported by the caller, and it was not run here.

The device is simulated (R0): there is no hardware backend, no physical stop and no operator-required limit.  The
``fidelity`` attribute is the contract of the model as deployed on the fake backend (spec 05-fidelity FID-002): a
kinematic stand-in (F0), not the Isaac Sim physics model, and its gaps say so.  Every fact cites a line of the clone
at commit 748f879e099aaa3d3d19437a7eed48c9a72b1e28.  This package is model-authored and unreviewed; it is checked on
the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

BASE = "exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/cfg/PF/base_env_cfg.py"
POINTFOOT = "exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/robots/pointfoot_env_cfg.py"
REGISTER = "exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/robots/__init__.py"
ASSET = "exts/bipedal_locomotion/bipedal_locomotion/assets/config/pointfoot_cfg.py"
OBSERVATIONS = "exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/mdp/observations.py"


class PointfootFlat(GymnasiumDriver):
    device_id = "pointfoot-flat"
    env_id = "Isaac-PF-Blind-Flat-v0"
    native = "bipedal_locomotion.tasks.locomotion.robots.pointfoot_env_cfg:PFBlindFlatEnvCfg"
    backends = {"fake": ".fake:FakePointfootEnv"}
    seed = 42
    display_name = "Pointfoot blind flat locomotion task (Isaac Lab / Isaac Sim)"
    vendor, model = "andy-xiong6", "bipedal_locomotion_isaaclab"
    tags = ["pointfoot", "bipedal", "locomotion", "blind-flat", "isaac-lab", "isaac-sim",
            "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("This repository is used to train and simulate bipedal robots such as the limxdynamics TRON1",
             source="vendor_doc", ref="README.md:17"),
        Fact("The project targets Isaac Sim 4.2.0 and Isaac Lab 1.4.0", source="vendor_doc", ref="README.md:7-8"),
        Fact("The extension is installed with python -m pip install -e exts/bipedal_locomotion using a Python "
             "interpreter that has Isaac Lab installed", source="vendor_doc", ref="README.md:42-45"),
        Fact("The training command selects the registered task Isaac-PF-Blind-Flat-v0", source="vendor_doc",
             ref="README.md:67"),
        Fact("Real-robot deployment is delegated to the external rl-deploy-with-python repository's mlp branch",
             source="vendor_doc", ref="README.md:109"),
        Fact("Isaac-PF-Blind-Flat-v0 is registered with the external entry point omni.isaac.lab.envs:"
             "ManagerBasedRLEnv and env_cfg_entry_point pointfoot_env_cfg.PFBlindFlatEnvCfg", source="upstream_code",
             ref=f"{REGISTER}:64-71"),
        Fact("The flat task inherits PFBaseEnvCfg and sets the height scanner, the policy and critic heights "
             "observations and the terrain-level curriculum to None", source="upstream_code",
             ref=f"{POINTFOOT}:72-80"),
        Fact("The pointfoot base environment sets the robot to POINTFOOT_CFG and the six leg joint initial "
             "positions to 0.0, 0.0, 0.0918, 0.0918, -0.057 and -0.057", source="upstream_code",
             ref=f"{POINTFOOT}:31-39"),
        Fact("POINTFOOT_CFG's initial state names the six leg joints plus foot_L_Joint and foot_R_Joint, eight "
             "joints in all", source="upstream_code", ref=f"{ASSET}:29-42"),
        Fact("The action term is a joint-position action over the six named leg joints with scale 0.25 and "
             "use_default_offset True", source="upstream_code", ref=f"{BASE}:112-117"),
        Fact("The base velocity command has heading_command True", source="upstream_code", ref=f"{BASE}:97"),
        Fact("The base velocity command ranges are lin_vel_x -1.0 to 1.0, lin_vel_y -0.5 to 0.5, ang_vel_z -1 to 1 "
             "and heading -pi to pi", source="upstream_code", ref=f"{BASE}:103-105"),
        Fact("The gait command ranges are frequency 1.5 to 2.5 Hz, offset 0.5 and duration 0.5, resampled every "
             "5.0 s", source="upstream_code", ref=f"{BASE}:85-93"),
        Fact("The policy observation terms in order are base angular velocity, projected gravity, joint positions, "
             "joint velocities, last action, velocity command, gait phase and gait command", source="upstream_code",
             ref=f"{BASE}:128-145"),
        Fact("The policy observation group concatenates its terms, enables corruption and uses history_length 5 "
             "with flatten_history_dim True", source="upstream_code", ref=f"{BASE}:150-154"),
        Fact("The simulation advances by sim.dt 0.005 s, the control decimation is 4, an episode is 20.0 s long "
             "and the configured seed is 42", source="upstream_code", ref=f"{BASE}:435-440"),
        Fact("The episode ends through the time_out term or an illegal contact of base_Link above a threshold of "
             "1.0", source="upstream_code", ref=f"{BASE}:395-402"),
        Fact("get_gait_phase returns the gait phase as [sin(phase), cos(phase)] with shape (num_envs, 2)",
             source="upstream_code", ref=f"{OBSERVATIONS}:117-124"),
        Fact("get_gait_command returns the gait command parameters [frequency, offset, duration] with shape "
             "(num_envs, 3)", source="upstream_code", ref=f"{OBSERVATIONS}:143-150"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The fake is kinematic, so the
    #: level is F0; the bridge derives the engine, clock and lockstep members and they are written out here.
    fidelity = {
        "engine": "gymnasium:Isaac-PF-Blind-Flat-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's command draws and the kinematic update is "
                     "deterministic, so one seed and action sequence repeat a trajectory; the upstream Isaac Lab "
                     "and PhysX random streams are not used and no trajectory was compared with the upstream "
                     "environment",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic model: no rigid-body dynamics, contacts, friction, actuators, sensors, terrain or noise "
            "model; the six joint targets are mapped to positions without a physics engine",
            "the policy observation is a 185-value stand-in built from the clone's eight observation terms, the "
            "eight named joints and history_length 5 (base_env_cfg.py:128-154); observation corruption, command "
            "resampling, the gait-phase computation and the real Isaac Lab observation space were not observed, "
            "and the joint positions, joint velocities, commands, gait values and reward are placeholders",
            "the real action-space bounds were not observed: the clone configures no action clip, and the bounds "
            "come from the external ManagerBasedRLEnv / JointPositionAction implementation, so the fake's action "
            "Box is unbounded",
            "the illegal base_contact termination, the reward terms and the PhysX sensor and actuator models are "
            "not modelled",
            "the upstream simulator needs Isaac Sim 4.2.0 and Isaac Lab 1.4.0 with a GPU (README.md:7-8) and was "
            "not installed or run; the sim backend and the registered task were not run",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "snapshot and restore are not offered: the fake exposes no get_state or set_state",
        ],
    }
