"""OpenMHS driver for gh.louislelay/kinova_isaaclab_sim2real: the Gen3-Reach-v0 Isaac Lab reach task.

The clone registers ``Gen3-Reach-v0`` with ``gymnasium.register`` and names ``isaaclab.envs:ManagerBasedRLEnv`` as
the entry point (source/gen3/gen3/tasks/manager_based/gen3_reach/__init__.py:15-24).  The card's entry symbol is the
environment configuration that registration points to, ``Gen3ReachEnvCfg``
(source/gen3/gen3/tasks/manager_based/gen3_reach/joint_pos_env_cfg.py:25); it is what this package names as
``native`` and what G7 reads, while the served environment is the registered task.  ``GymnasiumDriver`` derives
``cap.world.step.v1`` (``{ticks, action}``) and the reset/seed classes from the environment's spaces: the action is a
joint-position target for the seven Kinova Gen3 joints, scaled by 0.5 on top of the default offsets
(pretrained_models/reach/env.yaml:339-350, joint_pos_env_cfg.py:39-41), and a policy step is 1/30 s
(env.yaml:21 and :76).  The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and
no operator-required limit.

The gate cannot install or import Isaac Sim, Isaac Lab, PhysX, torch or a GPU (pre-trained task config
env.yaml:20 and :78; README.md:25), so the ``fake`` backend is this package's own pure-Python kinematic stand-in
(fake.py).  A backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)``
(GymnasiumDriver.open_native); that path needs the upstream installation and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every constant and rule in the facts and the fidelity gaps cites a line of the clone at the pinned commit
d97c80ed8f532de5ab2609366f12e9d4c62e1ea3.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

TASK_INIT = "source/gen3/gen3/tasks/manager_based/gen3_reach/__init__.py"
TASK_CFG = "source/gen3/gen3/tasks/manager_based/gen3_reach/joint_pos_env_cfg.py"
ENV_YAML = "pretrained_models/reach/env.yaml"
AGENT_YAML = "pretrained_models/reach/agent.yaml"
EXTENSION = "source/gen3/config/extension.toml"
SETUP = "source/gen3/setup.py"


class KinovaGen3Reach(GymnasiumDriver):
    device_id = "gen3-reach"
    env_id = "Gen3-Reach-v0"
    native = "gen3.tasks.manager_based.gen3_reach.joint_pos_env_cfg:Gen3ReachEnvCfg"
    backends = {"fake": ".fake:FakeGen3ReachEnv"}
    mode = "simulated"
    risk = "R0"
    seed = 42
    display_name = "Kinova Gen3 Reach in Isaac Lab (Gen3-Reach-v0)"
    vendor, model = "louislelay", "kinova_isaaclab_sim2real"
    tags = ["kinova", "gen3", "reach", "isaac-sim", "isaac-lab", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("The repository is a standalone Isaac Lab extension for training reinforcement-learning agents on the "
             "Kinova Gen3 and deploying them in Isaac Sim or on the real robot via ROS2", source="vendor_doc",
             ref="README.md:5-7"),
        Fact("Isaac Lab is installed first, and the Python package is installed with python -m pip install -e "
             "source/gen3", source="vendor_doc", ref="README.md:25-30"),
        Fact("The Sim2Real pipeline runs with ROS2 and does not require Isaac Lab or Isaac Sim to be installed",
             source="vendor_doc", ref="README.md:10"),
        Fact("The task package imports gymnasium and registers Gen3-Reach-v0 with gym.register; its entry point is "
             "isaaclab.envs:ManagerBasedRLEnv, its environment configuration is "
             "joint_pos_env_cfg:Gen3ReachEnvCfg and the environment checker is disabled", source="upstream_code",
             ref=f"{TASK_INIT}:6-24"),
        Fact("Gen3ReachEnvCfg subclasses ReachEnvCfg and sets the scene robot to KINOVA_GEN3_N7_CFG at the prim path "
             "{ENV_REGEX_NS}/Robot", source="upstream_code", ref=f"{TASK_CFG}:25-31"),
        Fact("The reset event reset_robot_joints uses the position range (0.75, 1.25)", source="upstream_code",
             ref=f"{TASK_CFG}:32-33"),
        Fact("The action is a JointPositionActionCfg over joint_names ['.*'] with scale 0.5 and "
             "use_default_offset=True", source="upstream_code", ref=f"{TASK_CFG}:39-41"),
        Fact("The end-effector command targets the body end_effector_link and fixes the pitch range at pi/2",
             source="upstream_code", ref=f"{TASK_CFG}:43-45"),
        Fact("The simulation timestep is 0.016666666666666666 s", source="upstream_code", ref=f"{ENV_YAML}:21"),
        Fact("The decimation is 2, so one policy step advances two simulation timesteps", source="upstream_code",
             ref=f"{ENV_YAML}:76"),
        Fact("The scene robot's initial joint positions are joint_1 0.0, joint_2 0.65, joint_3 0.0, joint_4 1.89, "
             "joint_5 0.0, joint_6 0.6 and joint_7 -1.57", source="upstream_code",
             ref=f"{ENV_YAML}:144-151"),
        Fact("The sim2real mapping treats a simulation joint angle as radians and converts it to degrees with "
             "np.rad2deg", source="upstream_code", ref="scripts/sim2real/run_task_reach.py:130-141"),
        Fact("The scene robot is the Kinova Gen3 N7, loaded from gen3n7_instanceable.usd", source="upstream_code",
             ref=f"{ENV_YAML}:124"),
        Fact("The arm actuators have effort limits of 39.0 for joint_1 to joint_4 and 9.0 for joint_5 to joint_7 and "
             "a velocity limit of 100.0", source="upstream_code", ref=f"{ENV_YAML}:157-165"),
        Fact("The reset event reset_joints_by_scale scales the default joint positions by a factor from 0.75 to 1.25 "
             "and sets the joint velocities from the range 0.0 to 0.0", source="upstream_code",
             ref=f"{ENV_YAML}:352-360"),
        Fact("The policy observation group concatenates the joint_pos_rel, joint_vel_rel, ee_pose command and "
             "last_action terms, with corruption enabled", source="upstream_code", ref=f"{ENV_YAML}:288-338"),
        Fact("The joint position and joint velocity observations add uniform noise from -0.01 to 0.01",
             source="upstream_code", ref=f"{ENV_YAML}:294-315"),
        Fact("The ee_pose command is a UniformPoseCommand for end_effector_link resampled every 4.0 s, with position "
             "ranges x 0.35 to 0.65, y -0.2 to 0.2 and z 0.15 to 0.5, roll 0.0, pitch 1.5707963267948966 and yaw "
             "-3.14 to 3.14", source="upstream_code", ref=f"{ENV_YAML}:508-535"),
        Fact("An episode lasts 12.0 s", source="upstream_code", ref=f"{ENV_YAML}:369"),
        Fact("The only termination is the time-out term", source="upstream_code", ref=f"{ENV_YAML}:490-494"),
        Fact("The joint-position action term is not clipped (clip: null)", source="upstream_code",
             ref=f"{ENV_YAML}:344"),
        Fact("The recorded environment configuration seeds the run with 42", source="upstream_code",
             ref=f"{ENV_YAML}:75"),
        Fact("The training configuration leaves clip_actions null", source="upstream_code", ref=f"{AGENT_YAML}:34"),
        Fact("The extension declares isaaclab, isaaclab_assets, isaaclab_mimic, isaaclab_rl and isaaclab_tasks as "
             "dependencies", source="upstream_code", ref=f"{EXTENSION}:17-22"),
        Fact("The package requires Python 3.10 or newer", source="upstream_code", ref=f"{SETUP}:37"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The checked backend is the
    #: package's kinematic stand-in, so the claim is F0 and makes no determinism claim about Isaac Sim.
    fidelity = {
        "engine": "gymnasium:Gen3-Reach-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake reseeds Python's random.Random from reset(seed), so one seed repeats the fake's own "
                     "trajectory; Isaac Lab draws the joint scales, the pose command and the observation noise from "
                     "numpy/torch generators, so the same seed is not claimed to reproduce an Isaac Sim trajectory",
        },
        "timestep_ms": 33.33333333333333,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a kinematic stand-in (F0): no rigid-body dynamics, contacts, friction, actuator effort or "
            "velocity limits (env.yaml:157-165), sensor or rendering model; the joint positions are set directly to "
            "the scaled action and were never compared with an Isaac Sim run",
            "the action space is published as an unbounded seven-value Box because the clone records the "
            "joint-position action, its scale 0.5 and clip: null but no numeric action bound (env.yaml:339-350); "
            "the real Isaac Lab Box bounds were not observed",
            "the policy observation group is modelled with four seven-value terms (joint_pos, joint_vel, "
            "pose_command, actions); the clone's joint_pos_rel and joint_vel_rel are computed by Isaac Lab term "
            "functions and the command width is the pose command's position plus quaternion, so torch-level dtype, "
            "layout and corruption details were not observed",
            "the reward is a constant 0.0 placeholder, not the configured sum of end-effector tracking, action-rate "
            "and joint-velocity terms (env.yaml:370-488), because the forward kinematics and command error are "
            "external Isaac Lab functions",
            "only the 12.0 s time-out truncates an episode (env.yaml:369, :490-494); the tracking reward terms and "
            "PhysX contacts are not modelled",
            "the reset event scales the default joint positions by a factor in (0.75, 1.25) (env.yaml:352-360) and "
            "the command is resampled every 4.0 s (env.yaml:508-513), but the fake draws both from Python's "
            "random.Random, not numpy/torch, so a seed does not reproduce an Isaac Sim episode",
            "the sim backend (gymnasium.make('Gen3-Reach-v0')) was not run: it needs Isaac Sim, Isaac Lab, PhysX, "
            "torch and a GPU (env.yaml:20 and :78; README.md:25)",
            "no wall-clock pacing: realtime_factor 0 and one tick advances simulated time by 33.33 ms only",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state pair in the clone",
        ],
    }
