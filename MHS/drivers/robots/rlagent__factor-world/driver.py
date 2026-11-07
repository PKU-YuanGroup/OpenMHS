"""OpenMHS driver for gh.rlagent/factor-world: the Meta-World assembly-v2 task (simulated, R0).

DEVIATION FROM THE CARD: the card names ``family`` mujoco and ``helper`` MujocoDriver because the repository vendors
Meta-World MuJoCo assets, but the confirmed entry symbol is a Gym task class, not one raw MJCF model.  The assembly
environment exposes a four-element normalised action, a dictionary observation and the legacy ``gym.Env`` reset/step
pair (``envs/sawyer_xyz_env.py:164-167`` and ``:486-488``).  A ``MujocoDriver`` serves one MJCF model through
``model_path`` and writes ``data.ctrl`` per actuator: ``sawyer_assembly_peg.xml`` has only two gripper actuators
(``ctrlrange`` -1..1) and moves the hand through a weld to a mocap body (``:22-28``), so it cannot express the first
three action elements or the task observation, reward and episode.  The package is therefore a ``GymnasiumDriver``
over ``envs.tasks.sawyer_assembly_peg_v2:SawyerNutAssemblyEnvV2`` and binds the card's ``cap.world.step.v1`` and
``cap.world.reset.v1``; the bridge also serves ``cap.world.seed.v1``.  The card's other entry symbol,
``wrappers:make_wrapped_env``, is a factory, not a class: it selects the goal-hidden subclass and applies optional
factor wrappers (``wrappers.py:83-87``, ``envs/factors/utils.py:61-72``).  This package serves the task class with the
goal-hidden configuration (``envs/env_dict.py:348-355``); the factor wrappers are not served.

The upstream stack (MuJoCo 2.1, mujoco_py and gym) is not installed where the gate runs, and package code never imports
the clone.  The ``fake`` backend is this package's pure-Python kinematic stand-in (``fake.py``); no ``sim`` backend is
declared, so the upstream MuJoCo path was not run.  The device is simulated (R0): there is no hardware backend, no
e-stop path to a machine and no operator-required limit.  This package is model-authored and unreviewed: it is checked
on the fake backend only, and its evidence is ``contract_checked``, never an MHS-Device level.

Every Fact cites a line of the clone at commit 01df1f18f7e532afda0a38169356fa637d24e432.
"""

from mhs.driver import Fact, GymnasiumDriver

TASK = "envs/tasks/sawyer_assembly_peg_v2.py"
SAWYER = "envs/sawyer_xyz_env.py"
MUJOCO_ENV = "envs/mujoco_env.py"
ENV_DICT = "envs/env_dict.py"
WRAPPERS = "wrappers.py"
FACTORS = "envs/factors/utils.py"
README = "README.md"
CONDA = "conda_env.yml"
SCENE = "third_party/metaworld/metaworld/envs/assets_v2/scene/basic_scene.xml"
MODEL = "third_party/metaworld/metaworld/envs/assets_v2/sawyer_xyz/sawyer_assembly_peg.xml"


class FactorWorldAssembly(GymnasiumDriver):
    """The Factor-World assembly-v2 task, simulated on the package's kinematic fake."""

    device_id = "factor-world-assembly"
    device_kind = "world.sim"
    mode, risk = "simulated", "R0"
    native = "envs.tasks.sawyer_assembly_peg_v2:SawyerNutAssemblyEnvV2"
    backends = {"fake": ".fake:FakeSawyerNutAssemblyEnvV2"}
    action_space_ref = f"{SAWYER}:164-167"
    display_name = "Factor-World Sawyer nut assembly (Meta-World assembly-v2, simulated)"
    vendor, model = "rlagent", "factor-world assembly-v2"
    tags = ["factor-world", "metaworld", "assembly", "sawyer", "mujoco", "manipulation", "simulation", "gym"]
    facts = [
        Fact("The repository provides MetaWorld environments with factors of variation including arm position, "
             "camera position, floor texture, lighting, object position, object size, object texture, table "
             "position, table texture and distractor objects", source="vendor_doc", ref=f"{README}:15-25"),
        Fact("The make_wrapped_env factory selects the goal-hidden class for env_name unless observe_goal is true",
             source="upstream_code", ref=f"{WRAPPERS}:83-87"),
        Fact("The assembly-v2 environment name is registered to the SawyerNutAssemblyEnvV2 class",
             source="upstream_code", ref=f"{ENV_DICT}:75-76"),
        Fact("SawyerNutAssemblyEnvV2 uses the MJCF model sawyer_xyz/sawyer_assembly_peg.xml",
             source="upstream_code", ref=f"{TASK}:25-26"),
        Fact("The environment action space is a Box of four elements, each from -1 to +1", source="upstream_code",
             ref=f"{SAWYER}:164-167"),
        Fact("A step applies action[:3] as a mocap hand displacement through set_xyz_action and action[-1] as the "
             "two gripper actuator commands [action[-1], -action[-1]]", source="upstream_code",
             ref=f"{SAWYER}:486-488"),
        Fact("set_xyz_action clips the action to -1..1, scales it by action_scale and clips the mocap position to "
             "mocap_low..mocap_high", source="upstream_code", ref=f"{SAWYER}:206-217"),
        Fact("SawyerXYZEnv defaults frame_skip to 5", source="upstream_code", ref=f"{SAWYER}:111"),
        Fact("SawyerXYZEnv defaults action_scale to 1/100", source="upstream_code", ref=f"{SAWYER}:116"),
        Fact("MujocoEnv.dt is model.opt.timestep times frame_skip", source="upstream_code",
             ref=f"{MUJOCO_ENV}:118-120"),
        Fact("The MJCF basic scene sets the physics timestep to 0.0025 s", source="upstream_code",
             ref=f"{SCENE}:2"),
        Fact("The assembly model has two position actuators, r_close and l_close, with ctrlrange -1 to +1, and a "
             "weld equality attaches the mocap body to the hand", source="upstream_code", ref=f"{MODEL}:22-28"),
        Fact("MujocoEnv loads the model with mujoco_py.load_model_from_path and creates a mujoco_py.MjSim",
             source="upstream_code", ref=f"{MUJOCO_ENV}:58-59"),
        Fact("SawyerXYZEnv sets max_path_length to 500", source="upstream_code", ref=f"{SAWYER}:100"),
        Fact("A step ends the episode when info['success'] is true or curr_path_length reaches max_path_length",
             source="upstream_code", ref=f"{SAWYER}:522"),
        Fact("The step returns the observation dictionary, info['success'] as the reward, the done flag and the "
             "info dictionary", source="upstream_code", ref=f"{SAWYER}:520-523"),
        Fact("The v2 observation is a 39-element flat proprio array made of 18 current elements, 18 previous "
             "elements and a 3-element goal, and the image is None unless get_image_obs is set",
             source="upstream_code", ref=f"{SAWYER}:391-425"),
        Fact("The proprio observation is cast to np.float32", source="upstream_code", ref=f"{SAWYER}:422"),
        Fact("Without images the observation space is a Dict with a single proprio Box", source="upstream_code",
             ref=f"{SAWYER}:474-483"),
        Fact("SawyerXYZEnv.reset resets curr_path_length to 0 and calls the base reset", source="upstream_code",
             ref=f"{SAWYER}:540-542"),
        Fact("MujocoEnv.reset calls sim.reset and reset_model and returns the observation reset_model produced",
             source="upstream_code", ref=f"{MUJOCO_ENV}:99-108"),
        Fact("The assembly reset_model resets the hand, sets the target to the goal, places the object and the peg, "
             "and returns the observation", source="upstream_code", ref=f"{TASK}:100-117"),
        Fact("The goal-hidden class sets _set_task_called to True in its constructor, so the configured task does "
             "not need an external set_task before reset", source="upstream_code", ref=f"{ENV_DICT}:348-355"),
        Fact("The factor wrapper generates a model XML that includes factors/factors_train.xml or "
             "factors/factors_eval.xml, so factors change the model file", source="upstream_code",
             ref=f"{FACTORS}:61-72"),
        Fact("The project pins python 3.8, mujoco_py >=2.1,<2.2 and gym 0.25.1", source="vendor_doc",
             ref=f"{CONDA}:19-46"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the last observation stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "factor-world:assembly-v2/SawyerNutAssemblyEnvV2",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "The configured task has random_init false (envs/sawyer_xyz_env.py:107 and :135), so its "
                     "reset_model takes fixed start positions and does not draw from the RNG; the legacy seed() "
                     "is recorded by the bridge but does not select a different start.  The package's fake is "
                     "deterministic and repeats exactly for any seed.",
        },
        "timestep_ms": 12.5,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a kinematic stand-in for the MuJoCo task: it does not load the MJCF model, does not run "
            "mujoco_py, and resolves no contacts, mocap weld, gripper actuators, object physics, collision or "
            "assembly reward, so trajectories, success and grasp state are not modelled",
            "the fake returns the 39-element proprio list of Python floats with placeholder object, goal and "
            "previous-frame values; upstream returns a numpy float32 array whose values are MuJoCo site and body "
            "positions",
            "the fake does not render images: image is None, matching the class default get_image_obs false "
            "(envs/sawyer_xyz_env.py:108); the 84x84 camera path the factory requests by default is not served",
            "the factor wrappers for arm, camera, floor texture, lighting, object, table and distractor factors "
            "are not served: they generate a different MJCF XML from factors_train.xml or factors_eval.xml "
            "(envs/factors/utils.py:61-72), and this package serves the base assembly-v2 class",
            "the card's class entry symbol is SawyerNutAssemblyEnvV2; the factory builds a goal-hidden subclass "
            "that sets _set_task_called (envs/env_dict.py:348-355), and the fake models that configured task",
            "MuJoCo 2.1, mujoco_py and gym are not installed where the gate runs (conda_env.yml:19-46), so no "
            "trajectory or observation was compared with the upstream environment",
            "snapshot_restore is false: the class has set_state but no get_state pair, and the Gymnasium bridge "
            "offers snapshots only when both exist",
            "no wall-clock pacing: realtime_factor 0, and one tick advances the environment by 12.5 ms of "
            "simulated time only (0.0025 s timestep times frame_skip 5)",
            "the fake's action path does not clip the hand to the task's hand_low/hand_high; it applies the "
            "normalised first three elements at action_scale 1/100 without a collision or joint-limit model",
        ],
    }
