"""OpenMHS driver for gh.clvrai/furniture-bench: the FurnitureSim-v0 environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only.  ``env_id`` names the registered environment and the bridge derives the
whole contract from the environment's spaces: ``cap.world.step.v1`` takes ``{ticks, action}`` with the action
``{values}`` bounded by the 8-element ``Box(-1, 1)`` of the ``quat`` action representation, ``cap.world.reset.v1``
takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): a physics simulator
has no hardware backend, no native stop and no operator-supplied bound.

The upstream ``FurnitureSim-v0`` needs Isaac Gym (CUDA, Linux) and ``gym==0.21.0`` on Python < 3.9.  Neither is
installed where the gate runs and package code never imports the clone, so the ``fake`` backend is the package's
own pure Python kinematic stand-in for ``FurnitureSimEnv``.  A backend name that ``backends`` does not list
(``sim``) is served by ``gym.make(env_id, **env_kwargs)`` (GymnasiumDriver.open_native); that path needs the
upstream package, Isaac Gym and a GPU, and it was not run here.

The ``fidelity`` attribute describes the model as deployed by this package: the fake is kinematic (F0) and not
the Isaac Gym PhysX simulator (F1), which the gaps state.  Every constant and rule cites a line of the clone at the
pinned commit (a87960a2490a7a19c86ea16a5ef371718b2baa70).  This package is model-authored and unreviewed; it is
checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

SIM = "furniture_bench/envs/furniture_sim_env.py"
REG = "furniture_bench/__init__.py"
OBS = "furniture_bench/envs/observation.py"
CONFIG = "furniture_bench/config.py"
SIM_CONFIG = "furniture_bench/sim_config.py"
ROBOT_STATE = "furniture_bench/robot/robot_state.py"


class FurnitureSim(GymnasiumDriver):
    device_id = "furniture_bench_sim"
    env_id = "FurnitureSim-v0"
    env_kwargs = {"furniture": "square_table", "headless": True}
    native = "furniture_bench.envs.furniture_sim_env:FurnitureSimEnv"
    backends = {"fake": ".fake:FakeFurnitureSimEnv"}
    action_space_ref = f"{SIM}:660-666"
    display_name = "FurnitureBench FurnitureSim-v0 (Isaac Gym)"
    vendor, model = "CLVR @ KAIST", "FurnitureSim-v0"
    tags = ["furniture-assembly", "manipulation", "isaac-gym", "reinforcement-learning", "simulation",
            "gymnasium"]
    mode = "simulated"
    risk = "R0"
    facts = [
        Fact("FurnitureSim-v0 is registered with entry point "
             "furniture_bench.envs.furniture_sim_env:FurnitureSimEnv", source="upstream_code",
             ref=f"{REG}:33-36"),
        Fact("FurnitureSimEnv is the gym.Env subclass of the simulator", source="upstream_code",
             ref=f"{SIM}:48"),
        Fact("The default visual observation lists ee_pos, ee_quat, ee_pos_vel, ee_ori_vel, gripper_width, "
             "color_image1 and color_image2", source="upstream_code", ref=f"{OBS}:19-27"),
        Fact("For the quat rotation representation the action is an end-effector delta of 8 numbers "
             "[x, y, z, qx, qy, qz, qw, gripper]; rot_6d uses 10 numbers and axis uses 7", source="upstream_code",
             ref=f"{SIM}:707-714"),
        Fact("The action space is a Box with every element from -1 to 1 and shape (num_envs, pose_dim + 1)",
             source="upstream_code", ref=f"{SIM}:660-666"),
        Fact("pose_dim is 7 for quat, 9 for rot_6d and 6 for axis", source="upstream_code",
             ref=f"{SIM}:653-658"),
        Fact("step clips the action to the bounds of the action space before applying it", source="upstream_code",
             ref=f"{SIM}:720-723"),
        Fact("The default maximum number of environment steps is 3000", source="upstream_code",
             ref=f"{SIM}:70"),
        Fact("An environment is done when its step count exceeds the furniture's max_env_steps", source="upstream_code",
             ref=f"{SIM}:1009-1016"),
        Fact("The observation space is a Dict with a nested robot_state Dict (unless concat_robot_state is True) and "
             "one Box per colour image", source="upstream_code", ref=f"{SIM}:673-703"),
        Fact("The robot-state dimensions are ee_pos 3, ee_quat 4, ee_pos_vel 3, ee_ori_vel 3, joint_positions 7, "
             "joint_velocities 7, joint_torques 7 and gripper_width 1", source="upstream_code",
             ref=f"{ROBOT_STATE}:17-26"),
        Fact("The resized camera image is (224, 224) pixels", source="upstream_code", ref=f"{CONFIG}:79"),
        Fact("The full-resolution camera image is (1280, 720) pixels", source="upstream_code", ref=f"{CONFIG}:77"),
        Fact("step returns a four-tuple (observation, reward, done, info)", source="upstream_code",
             ref=f"{SIM}:822-827"),
        Fact("reset returns the observation", source="upstream_code", ref=f"{SIM}:1152-1175"),
        Fact("The reward is computed from the furniture assembly state", source="upstream_code",
             ref=f"{SIM}:829-846"),
        Fact("The robot control frequency is 10 Hz", source="upstream_code", ref=f"{CONFIG}:21"),
        Fact("The Isaac Gym simulation timestep is 1/60 s with 2 substeps", source="upstream_code",
             ref=f"{SIM_CONFIG}:23-24"),
        Fact("step derives the number of simulator refreshes from the control frequency, the timestep and the "
             "substeps", source="upstream_code", ref=f"{SIM}:725-731"),
        Fact("A positive gripper action closes the gripper and a negative one opens it to max_gripper_width",
             source="upstream_code", ref=f"{SIM}:762-774"),
        Fact("max_gripper_width is 0.065 for the square_table furniture", source="upstream_code",
             ref=f"{CONFIG}:35-36"),
        Fact("squeeze_batch_dim defaults to False, so observations keep the leading environment dimension",
             source="upstream_code", ref=f"{SIM}:184-185"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The fake backend is a
    #: kinematic stand-in (F0); the upstream Isaac Gym simulator is F1 and is not modelled here.
    fidelity = {
        "engine": "furniture_bench:FurnitureSim-v0 (fake kinematic stand-in)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) repeats the fake's initial pose jitter and every transition; the fake uses "
                     "Python's random.Random while the upstream engine uses Isaac Gym PhysX with GPU physics, so a "
                     "seed does not give the same trajectory on the two",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no dynamics: the fake moves the end effector kinematically and has no rigid-body physics, contacts, "
            "friction, gravity, actuator, joint or sensor model; the upstream simulator is Isaac Gym PhysX (F1), "
            "not this F0 model",
            "the image observations are placeholder 2 x 2 x 3 arrays; the configured real sizes are 224 x 224 when "
            "resize_img is True and 1280 x 720 at full resolution, and the fake models no camera, lighting or depth",
            "rotation is not modelled (the ee_quat stays the identity and the quaternion part of the action has no "
            "effect) and the assembly check and parts_poses reward are not modelled; the reward is always 0",
            "one environment per instance: num_envs > 1 is not modelled and the action space always has shape "
            "(1, 8)",
            "the fake returns one observation per environment (no batch dimension), while the upstream environment "
            "keeps a leading dimension because squeeze_batch_dim defaults to False",
            "no rendering, viewer, video recording or GPU simulation",
            "the fake was not compared with the upstream Isaac Gym environment: Isaac Gym is not installed and "
            "needs a Linux GPU machine, so the sim backend was not run",
            "reset initial-pose randomization ranges are not modelled; the fake adds a small placeholder jitter to "
            "a fixed kinematic pose",
        ],
    }
