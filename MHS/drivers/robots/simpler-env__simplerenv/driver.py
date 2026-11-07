"""OpenMHS driver for gh.simpler-env/simplerenv: the GraspSingleCokeCanInScene-v0 environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
whole contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action
``{values: [7 numbers]}`` (the combined static Google-robot controller), ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required limit.

The upstream environment needs SAPIEN, gymnasium, the downloaded asset directory and a GPU-capable renderer, so the
``fake`` backend is the package's own pure Python stand-in (fake.py); the ``sim`` backend would be
``gymnasium.make(env_id)`` and was not run.  The package is model-authored and unreviewed and is checked on the fake
backend only.  Every fact cites a line of the clone at the pinned commit eddb5690749a1e34267807c0f7b5eede323918d7.
"""

from mhs.driver import Fact, GymnasiumDriver

SCENE = "ManiSkill2_real2sim/mani_skill2_real2sim/envs/custom_scenes/grasp_single_in_scene.py"
CUSTOM_BASE = "ManiSkill2_real2sim/mani_skill2_real2sim/envs/custom_scenes/base_env.py"
SAPIEN_ENV = "ManiSkill2_real2sim/mani_skill2_real2sim/envs/sapien_env.py"
GOOGLEROBOT = "ManiSkill2_real2sim/mani_skill2_real2sim/agents/robots/googlerobot.py"
DEFAULTS = "ManiSkill2_real2sim/mani_skill2_real2sim/agents/configs/google_robot/defaults.py"
PD_EE_POSE = "ManiSkill2_real2sim/mani_skill2_real2sim/agents/controllers/pd_ee_pose.py"
PD_JOINT_POS = "ManiSkill2_real2sim/mani_skill2_real2sim/agents/controllers/pd_joint_pos.py"
BASE_CONTROLLER = "ManiSkill2_real2sim/mani_skill2_real2sim/agents/base_controller.py"
BASE_AGENT = "ManiSkill2_real2sim/mani_skill2_real2sim/agents/base_agent.py"
COMMON = "ManiSkill2_real2sim/mani_skill2_real2sim/utils/common.py"
REGISTRATION = "ManiSkill2_real2sim/mani_skill2_real2sim/utils/registration.py"


class GraspSingleCokeCan(GymnasiumDriver):
    device_id = "grasp-single-coke-can"
    env_id = "GraspSingleCokeCanInScene-v0"
    native = ("ManiSkill2_real2sim.mani_skill2_real2sim.envs.custom_scenes.grasp_single_in_scene:"
              "GraspSingleCokeCanInSceneEnv")
    backends = {"fake": ".fake:FakeGraspSingleCokeCanEnv"}
    display_name = "simpler-env GraspSingleCokeCanInScene-v0 (static Google robot picks a coke can)"
    vendor, model = "simpler-env", "GraspSingleCokeCanInScene-v0"
    tags = ["grasp", "coke-can", "manipulation", "reinforcement-learning", "simulation", "simplerenv",
            "gymnasium"]
    facts = [
        Fact("GraspSingleCokeCanInScene-v0 is registered with max_episode_steps=80 and its constructor fixes "
             "model_ids to ['coke_can']", source="upstream_code", ref=f"{SCENE}:613-618"),
        Fact("The default robot is google_robot_static", source="upstream_code", ref=f"{CUSTOM_BASE}:51"),
        Fact("The static Google robot's default control mode is "
             "arm_pd_ee_delta_pose_align_interpolate_by_planner_gripper_pd_joint_target_delta_pos_interpolate_by_planner",
             source="upstream_code", ref=f"{GOOGLEROBOT}:210-211"),
        Fact("The arm controller takes a position lower bound of -1.0, a position upper bound of 1.0 and a rotation "
             "bound of pi/2", source="upstream_code", ref=f"{DEFAULTS}:168-176"),
        Fact("The arm action is a Box of three position and three rotation elements built from those bounds",
             source="upstream_code", ref=f"{PD_EE_POSE}:161-178"),
        Fact("A controller configured with normalize_action=True receives a Box with bounds -1 and 1",
             source="upstream_code", ref=f"{COMMON}:121-123"),
        Fact("The selected gripper controller has use_target=True and clip_target=True",
             source="upstream_code", ref=f"{DEFAULTS}:291-307"),
        Fact("The combined controller flattens the controllers' Box spaces into one Box action space",
             source="upstream_code", ref=f"{BASE_CONTROLLER}:253-260"),
        Fact("A controller with use_target reports its target_qpos as its controller state",
             source="upstream_code", ref=f"{PD_JOINT_POS}:163-166"),
        Fact("The default simulation frequency is 500 Hz and the default control frequency is 20 Hz",
             source="upstream_code", ref=f"{SAPIEN_ENV}:86-87"),
        Fact("The control timestep is the reciprocal of the control frequency, so 50 ms at the default 20 Hz",
             source="upstream_code", ref=f"{SAPIEN_ENV}:236-238"),
        Fact("step returns the observation, the reward, the terminated flag, a False truncation flag and info",
             source="upstream_code", ref=f"{SAPIEN_ENV}:547-555"),
        Fact("The default observation mode is state and get_obs flattens the state dict into one array",
             source="upstream_code", ref=f"{SAPIEN_ENV}:255-261"),
        Fact("The state observation puts the agent proprioception and the task extras under agent and extra",
             source="upstream_code", ref=f"{SAPIEN_ENV}:269-271"),
        Fact("The agent proprioception is qpos, qvel and the controller state",
             source="upstream_code", ref=f"{BASE_AGENT}:173-178"),
        Fact("A static Google robot has 11 qpos values", source="upstream_code", ref=f"{GOOGLEROBOT}:21-27"),
        Fact("The agent observation adds the robot base pose", source="upstream_code", ref=f"{CUSTOM_BASE}:344-347"),
        Fact("The task extras add the tcp pose, the object pose and the object-minus-tcp position",
             source="upstream_code", ref=f"{SCENE}:390-399"),
        Fact("The reward is 1.0 when info['success'] is true and 0.0 otherwise", source="upstream_code",
             ref=f"{CUSTOM_BASE}:401-406"),
        Fact("Success requires a grasp and lifting the object more than 0.01 above its settled height",
             source="upstream_code", ref=f"{SCENE}:434-440"),
        Fact("get_done returns info['success'], so the episode terminates when the object is lifted",
             source="upstream_code", ref=f"{SAPIEN_ENV}:579-580"),
        Fact("gym.make wraps the environment in a TimeLimit when max_episode_steps is set",
             source="upstream_code", ref=f"{REGISTRATION}:108-114"),
        Fact("A reset draws the object xy uniformly from [-0.35, -0.02] to [-0.12, 0.42] and drops it from 0.5 "
             "above the table height", source="upstream_code", ref=f"{SCENE}:268-277"),
        Fact("A reset draws the static Google base x from 0.30 to 0.40 and y from 0.0 to 0.2 unless the reset "
             "options give an initial xy", source="upstream_code", ref=f"{CUSTOM_BASE}:306-311"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "simplerenv:GraspSingleCokeCanInScene-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the initial state and the dynamics are deterministic, "
                     "so one implementation repeats a trajectory for the same seed and actions; upstream draws with "
                     "numpy RandomState and this package's fake with Python's random.Random, so a seed gives "
                     "different trajectories on the two",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a toy kinematic stand-in, not the SAPIEN physics of the upstream environment: no "
            "rigid-body dynamics, contact solving, gripper geometry, asset loading or camera rendering",
            "the observation has the 47-number layout of the default state mode, but its values are placeholders; "
            "image, state_dict and point-cloud observation modes are not served",
            "the fake draws with Python's random.Random and upstream with numpy RandomState, so one seed gives "
            "different trajectories on the two",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms (50 ms) only",
            "no physical device is modelled and the model was never validated against one",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
