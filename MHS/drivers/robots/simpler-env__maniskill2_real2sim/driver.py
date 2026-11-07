"""Full seven-axis GraspSingleCokeCanInScene control with a package-owned fake.

The selected upstream arm disables action normalization: translation bounds are
[-1, 1], rotation bounds are [-pi/2, pi/2], and the gripper alone is normalized.
The Python fake is F0, with one logical 50 ms control step per native call, no
SAPIEN physics and no hardware. Its explicit JSON checkpoint includes its RNG
and episode state. It is not a native checkpoint.

The live ``sim`` backend (sim.py, not run) builds the registered task with a
package-owned physics tick counter. Its physics_ticks_v1 timing accounts 25
physics ticks per control call and measures the settling ticks the native reset
integrates (reported in the reset receipt, never as episode ticks). Native
get_state omits task/controller/RNG/TimeLimit state, so the sim backend opts out
of protocol snapshots explicitly.
"""

from mhs.driver import Fact, GymnasiumDriver

BASE_ENV = "mani_skill2_real2sim/envs/custom_scenes/base_env.py"
GRASP = "mani_skill2_real2sim/envs/custom_scenes/grasp_single_in_scene.py"
SAPIEN_ENV = "mani_skill2_real2sim/envs/sapien_env.py"
ROBOT = "mani_skill2_real2sim/agents/robots/googlerobot.py"
AGENT = "mani_skill2_real2sim/agents/base_agent.py"
CONTROLLER = "mani_skill2_real2sim/agents/base_controller.py"
POSE_CTRL = "mani_skill2_real2sim/agents/controllers/pd_ee_pose.py"
ROBOT_DEFAULTS = "mani_skill2_real2sim/agents/configs/google_robot/defaults.py"
COMMON = "mani_skill2_real2sim/utils/common.py"
SAPIEN_UTILS = "mani_skill2_real2sim/utils/sapien_utils.py"
REGISTRATION = "mani_skill2_real2sim/utils/registration.py"


class ManiSkill2Real2Sim(GymnasiumDriver):
    device_id = "maniskill2-real2sim-grasp-coke-can"
    env_id = "GraspSingleCokeCanInScene-v0"
    native = "mani_skill2_real2sim.envs.custom_scenes.grasp_single_in_scene:GraspSingleCokeCanInSceneEnv"
    backends = {"fake": ".fake:FakeGraspSingleCokeCanEnv", "sim": ".sim:connect"}
    checkpoint_by_backend = {
        "fake": {"profile": "json_state_v1", "getter": "get_state", "setter": "set_state", "max_bytes": 65536},
        "sim": {"profile": "none",
                "reason": ("native get_state returns actor/articulation simulation state only "
                           "(sapien_env.py:653-680); task, controller, RNG and TimeLimit state are missing")},
    }
    #: Live physics accounting through the package-owned counter of sim.py (not the fake: it is logical 50 ms ticks).
    timing_by_backend = {
        "sim": {
            "mode": "physics_ticks_v1",
            "control_decimation": 25,
            "physics_timestep_attr": "sim_timestep",
            "physics_clock_attr": "mhs_physics_clock_s",
            "native_autoreset": False,
            "reset_advances_physics": True,
            "reset_clock": "continue",
            "max_reset_ticks": 1250,
            "source_refs": [f"{SAPIEN_ENV}:137-143", f"{SAPIEN_ENV}:569-573", f"{SAPIEN_ENV}:233-234",
                            "mani_skill2_real2sim/envs/custom_scenes/base_env.py:220-224", f"{GRASP}:302-316"],
        }
    }
    display_name = "SimplerEnv ManiSkill2 real2sim (GraspSingleCokeCanInScene-v0)"
    vendor, model = "simpler-env", "ManiSkill2 real2sim GraspSingleCokeCanInScene-v0"
    tags = ["maniskill2", "real2sim", "simplerenv", "grasping", "simulation", "gymnasium"]
    #: The upstream default: BaseEnv seeds its main RNG with 2022 before it constructs the environment.
    seed = 2022
    facts = [
        Fact("The default robot is google_robot_static", source="upstream_code",
             ref=f"{BASE_ENV}:49-51"),
        Fact("The static Google robot's default control mode is arm_pd_ee_delta_pose_align_interpolate_by_planner_"
             "gripper_pd_joint_target_delta_pos_interpolate_by_planner", source="upstream_code",
             ref=f"{ROBOT}:207-211"),
        Fact("The arm pose controller builds a six-element Box: three position deltas and three rotation deltas",
             source="upstream_code", ref=f"{POSE_CTRL}:161-178"),
        Fact("The arm controller config passes pos_lower -1.0, pos_upper 1.0 and rot_bound np.pi / 2",
             source="upstream_code", ref=f"{ROBOT_DEFAULTS}:168-176"),
        Fact("The selected arm explicitly disables action normalization, retaining its rotation Box bounds",
             source="upstream_code", ref=f"{ROBOT_DEFAULTS}:177-201"),
        Fact("The controller normalizes its action space when normalize_action is true", source="upstream_code",
             ref=f"{CONTROLLER}:51-54"),
        Fact("The action normalizer is Box(-1, 1) with the original shape and dtype", source="upstream_code",
             ref=f"{COMMON}:121-123"),
        Fact("The gripper uses PDJointPosMimicControllerConfig with normalize_action=True", source="upstream_code",
             ref=f"{ROBOT_DEFAULTS}:291-307"),
        Fact("CombinedController flattens the arm and gripper spaces into one Box", source="upstream_code",
             ref=f"{CONTROLLER}:253-260"),
        Fact("GraspSingleCokeCanInScene-v0 is registered with max_episode_steps=80 and the model_ids list ['coke_can']",
             source="upstream_code", ref=f"{GRASP}:613-617"),
        Fact("register_env notes that gym.make wraps the environment with a TimeLimit to limit the maximum number "
             "of steps", source="upstream_code", ref=f"{REGISTRATION}:127-130"),
        Fact("The supported observation modes are state, state_dict, none and image", source="upstream_code",
             ref=f"{SAPIEN_ENV}:65"),
        Fact("The default obs_mode is the first supported mode", source="upstream_code",
             ref=f"{SAPIEN_ENV}:146-147"),
        Fact("For obs_mode state, get_obs flattens the observation dict into one array", source="upstream_code",
             ref=f"{SAPIEN_ENV}:255-261"),
        Fact("The agent proprioception is qpos, qvel and the controller state", source="upstream_code",
             ref=f"{AGENT}:173-178"),
        Fact("The static Google robot qpos is 11-dimensional", source="upstream_code", ref=f"{ROBOT}:21"),
        Fact("The observation adds the robot base pose to the agent proprioception", source="upstream_code",
             ref=f"{BASE_ENV}:344-346"),
        Fact("The task adds tcp_pose, obj_pose and tcp_to_obj_pos to the state observation", source="upstream_code",
             ref=f"{GRASP}:390-398"),
        Fact("A serialized pose is its position followed by its quaternion, seven numbers", source="upstream_code",
             ref=f"{SAPIEN_UTILS}:21-22"),
        Fact("The reward is 0.0, or 1.0 when the episode info has success", source="upstream_code",
             ref=f"{BASE_ENV}:401-406"),
        Fact("The episode terminates when info['success'] is true", source="upstream_code",
             ref=f"{SAPIEN_ENV}:579-580"),
        Fact("reset(seed, options) reseeds the main and episode RNGs and initializes the episode", source="upstream_code",
             ref=f"{SAPIEN_ENV}:465-486"),
        Fact("The scene timestep is 1 / sim_freq", source="upstream_code", ref=f"{SAPIEN_ENV}:620"),
        Fact("sim_freq defaults to 500 Hz and control_freq to 20 Hz", source="upstream_code",
             ref=f"{SAPIEN_ENV}:86-87"),
        Fact("BaseEnv get_state returns actor/articulation simulation state and requires task-specific overrides",
             source="upstream_code", ref=f"{SAPIEN_ENV}:653-680"),
        Fact("Task success depends on consecutive grasp, lifted state and episode statistics",
             source="upstream_code", ref=f"{GRASP}:401-452"),
        Fact("Reset settles actors by integrating the scene", source="upstream_code", ref=f"{GRASP}:302-319"),
        Fact("The native control loop calls scene.step once per configured simulation substep", source="upstream_code",
             ref=f"{SAPIEN_ENV}:569-573"),
        Fact("The substep count is sim_freq // control_freq; the separately cited 500 Hz and 20 Hz defaults give 25",
             source="upstream_code", ref=f"{SAPIEN_ENV}:137-143"),
        Fact("BaseEnv provides get_state and set_state for the simulation state", source="upstream_code",
             ref=f"{SAPIEN_ENV}:674-680"),
        Fact("BaseEnv seeds its main RNG with 2022 before it constructs the environment", source="upstream_code",
             ref=f"{SAPIEN_ENV}:185-188"),
        Fact("step_action calls scene.step and then _after_simulation_step once per simulation substep",
             source="upstream_code", ref=f"{SAPIEN_ENV}:569-573"),
        Fact("The sim_timestep property is 1.0 / _sim_freq", source="upstream_code", ref=f"{SAPIEN_ENV}:233-234"),
        Fact("_settle steps the scene int(sim_freq * t) times", source="upstream_code",
             ref="mani_skill2_real2sim/envs/custom_scenes/base_env.py:220-224"),
        Fact("The object settles with _settle(0.5) twice and _settle(1.5) once more when it is still moving",
             source="upstream_code", ref=f"{GRASP}:302-316"),
        Fact("EnvSpec.make passes the registered default keyword arguments to the environment class",
             source="upstream_code", ref=f"{REGISTRATION}:31-34"),
    ]
    safe_state = ("No new step or reset is accepted after an e-stop until mhs.safety.reset clears the latch. A native "
                  "step or reset already running is not interrupted: it completes (a multi-step command stops at the "
                  "next control call), and the e-stop reports the safe state only after it ended, waiting at most "
                  "the e-stop budget and otherwise retrying in the background. The world state stays readable.")
    fidelity = {
        "determinism": {"kind": "seeded", "seed_control": "parameter",
                        "notes": "The fake Python RNG and native NumPy RNG differ; no cross-backend trajectory "
                                 "or exact native determinism is claimed."},
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
    }
    fidelity_by_backend = {
        "fake": {
            "engine": "python:openmhs-simplerenv-grasp-fake",
            "fidelity_level": "F0",
            "timestep_ms": 50.0,
            "snapshot_restore": True,
            "gaps": [
                "Package-owned 48-number state stand-in; values are test data, not native observations.",
                "No SAPIEN, contacts, PD drives, rendered scene, asset loading or physical device is simulated.",
                "One fake tick is a logical 50 ms control interval. No physical substeps are integrated.",
                "The selected live defaults use 500 Hz physics and 20 Hz control, or 25 substeps per control call.",
                "The fake models the 80-control-step TimeLimit; the raw native task terminates on success.",
                "JSON snapshots capture the fake's state and Python RNG, not native SAPIEN or NumPy state.",
                "Only the default state observation and seven-axis control are exposed; no image observations.",
                "No wall-clock pacing or comparison against the native simulator or hardware.",
            ],
        },
        "sim": {
            "engine": "sapien:ManiSkill2-real2sim",
            "fidelity_level": "F1",
            "timestep_ms": 2.0,
            "snapshot_restore": False,
            "gaps": [
                "Not run: SAPIEN, the asset tree and the upstream package were not installed; the live route is a "
                "source-reviewed contract, not a validated deployment, and no native trajectory was tested.",
                "Physics ticks come from a package-owned counter of completed scene.step() calls at the two "
                "integration sites (control substeps and reset settling); it is not a SAPIEN clock.",
                "Reset settling (up to 1,250 ticks at the 500 Hz default) is measured per reset; options or "
                "distractors that settle longer exceed the declared bound and fault the timing.",
                "Contact, actuator and controller fidelity are those of SAPIEN and the PD controllers; neither is "
                "validated against the physical robot; no native camera output or wall-clock pacing.",
            ],
        },
    }
