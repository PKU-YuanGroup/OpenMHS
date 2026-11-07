"""OpenMHS driver for gh.stepjam/rlbench: the RLBench Gymnasium wrapper, on the state-observation reach_target task.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
whole contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}``; the default RLBench
action mode makes ``action`` a Box of 8 values (seven delta arm joint positions and one absolute gripper value), so
the bridge serves ``action.values`` with its per-element limits.  ``cap.world.reset.v1`` takes ``{seed, options}``,
``cap.world.seed.v1`` ``{seed}``, and the device is simulated (R0): there is no hardware backend, no path to a
machine and no operator-required limit.

The gate never imports the clone.  RLBench needs CoppeliaSim v4.1.0 and PyRep (README.md:64) and its Gymnasium ids
exist only after the package registration side effect (rlbench/__init__.py:36-48), so the checked ``fake`` backend
is this package's kinematic stand-in for ``RLBenchEnv`` (fake.py).  A backend name that ``backends`` does not list
(``sim``) is passed to ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path additionally needs
RLBench and CoppeliaSim installed and the ``rlbench`` package imported to register the id, and it was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every constant and rule cites a line of the clone at commit 02720bba4c73fe02eb75df946b8791b806028a9d.  This package
is model-authored and unreviewed; it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

GYM = "rlbench/gym.py"
ACTION_MODE = "rlbench/action_modes/action_mode.py"
GRIPPER_MODE = "rlbench/action_modes/gripper_action_modes.py"


class RLBenchReachTarget(GymnasiumDriver):
    device_id = "rlbench-reach-target"
    env_id = "rlbench/reach_target-state-v0"
    native = "rlbench.gym:RLBenchEnv"
    backends = {"fake": ".fake:FakeRLBenchEnv"}
    action_space_ref = f"{ACTION_MODE}:77-79"
    display_name = "RLBench reach_target (state observations)"
    vendor, model = "Stephen James", "RLBench 1.2.0 reach_target-state-v0"
    tags = ["rlbench", "robot-manipulation", "reach-target", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("RLBenchEnv is a Gymnasium environment: class RLBenchEnv(gym.Env)",
             source="upstream_code", ref=f"{GYM}:20"),
        Fact("The state observation mode disables all high-dimensional observations and enables all low-dimensional "
             "ones", source="upstream_code", ref=f"{GYM}:31-33"),
        Fact("The wrapper constructs the RLBench Environment headless, launches it and gets the requested task "
             "environment from it", source="upstream_code", ref=f"{GYM}:44-50"),
        Fact("The observation space is a Dict built from the first observation: an rgb member is a Box bounded 0 to "
             "255 and every other member a Box bounded -inf to inf, with the observation's shape and dtype",
             source="upstream_code", ref=f"{GYM}:61-70"),
        Fact("The action space is a Box of action_mode.action_bounds() with the shape of Environment.action_shape",
             source="upstream_code", ref=f"{GYM}:72-74"),
        Fact("The extracted state observation keeps joint_velocities, joint_positions, joint_forces, gripper_open, "
             "gripper_pose, gripper_joint_positions, gripper_touch_forces and task_low_dim_state, and wraps a scalar "
             "in an array of one", source="upstream_code", ref=f"{GYM}:76-93"),
        Fact("reset seeds numpy's global generator, reads options['reset_to_demo'] when present, resets the task "
             "environment and returns the extracted observation with the text descriptions",
             source="upstream_code", ref=f"{GYM}:101-114"),
        Fact("step delegates to the task environment and returns (observation, reward, terminated, False, {})",
             source="upstream_code", ref=f"{GYM}:116-118"),
        Fact("The default action mode is JointPositionActionMode, which uses JointPosition(False) delta joint "
             "positions for the arm and absolute GripperJointPosition(True) for the gripper",
             source="upstream_code", ref=f"{ACTION_MODE}:59-61"),
        Fact("The default action mode applies the arm and gripper targets, steps the scene once and then re-applies "
             "the post-step targets", source="upstream_code", ref=f"{ACTION_MODE}:63-71"),
        Fact("JointPositionActionMode.action_bounds returns 7 arm deltas in [-0.1, 0.1] and one gripper value in "
             "[0.0, 0.04]", source="upstream_code", ref=f"{ACTION_MODE}:77-79"),
        Fact("The Panda entry of SUPPORTED_ROBOTS has 7 joints", source="upstream_code",
             ref="rlbench/const.py:38-39"),
        Fact("GripperJointPosition repeats the single gripper action for both joints and uses it as the absolute "
             "target", source="upstream_code", ref=f"{GRIPPER_MODE}:128-136"),
        Fact("TaskEnvironment.step returns the scene observation, float(success) as the reward and the task's "
             "terminate flag", source="upstream_code", ref="rlbench/task_environment.py:100-109"),
        Fact("ReachTarget's task_low_dim_state is the 3-element target position", source="upstream_code",
             ref="rlbench/tasks/reach_target.py:46-48"),
        Fact("The Gymnasium ids are built at import time as rlbench/{task_name}-{obs_mode}-v0 with entry point "
             "rlbench.gym:RLBenchEnv and nondeterministic=True", source="upstream_code",
             ref="rlbench/__init__.py:36-48"),
        Fact("Scene.step calls the PyRep simulator step and then the task step", source="upstream_code",
             ref="rlbench/backend/scene.py:314-316"),
        Fact("RLBench is built around CoppeliaSim v4.1.0 and PyRep", source="vendor_doc", ref="README.md:64"),
        Fact("The optional gym extra installs gymnasium==1.0.0a2", source="upstream_code", ref="setup.py:44-46"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock from the environment; they are written out so the whole contract
    #: reads in one place.  The fake is kinematic, hence F0: it has no dynamics, contacts or sensors to claim.
    fidelity = {
        "engine": "rlbench:reach_target-state-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's initial joint positions and target, and its "
                     "kinematic update is deterministic; upstream seeds numpy in reset (gym.py:104) but registers "
                     "every id nondeterministic=True (__init__.py:47) and was not run here, so the seed does not "
                     "select the same trajectory on the two implementations",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the package fake is kinematic: a tick adds the commanded arm delta to the joint positions and sets the "
            "gripper joints to the commanded absolute value; it models no contacts, collisions, dynamics, forces or "
            "physics engine, while upstream steps the CoppeliaSim scene (rlbench/backend/scene.py:314-316)",
            "the fake was never compared with a real RLBench run: RLBench needs CoppeliaSim v4.1.0 and PyRep "
            "(README.md:64) and was not installed or imported here; the observation keys follow the upstream extract "
            "list (rlbench/gym.py:78) but every value is synthetic",
            "no fixed physics timestep is published in the clone and the environment exposes no dt attribute, so "
            "timestep_ms is 0: one tick is one kinematic update, not a declared interval of simulated time",
            "vision observations and rendering are not served: the driver binds the state observation mode and "
            "cap.world.render.v1 is not bound; render() of the fake returns one placeholder pixel",
            "snapshot and restore are not offered: RLBenchEnv exposes no get_state/set_state pair",
        ],
    }
