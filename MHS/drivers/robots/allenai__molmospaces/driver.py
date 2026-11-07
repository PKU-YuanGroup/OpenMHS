"""OpenMHS driver for gh.allenai/molmospaces: the MolmoSpaces GymEnv wrapper (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the
``cap.world.*`` contract from the environment.  MolmoSpaces is not an ordinary Gymnasium family member:
``GymEnv`` deliberately declares neither ``action_space`` nor ``observation_space`` (the upstream comments say
why), so the bridge publishes ``cap.world.step.v1`` with an open ``action`` object and leaves the action
semantics to the task behind ``env.task``.  A step action is a dict keyed by move group (``arm``, ``gripper``),
and the step result is the task's five-tuple.  The device is simulated (R0): there is no hardware backend, no
e-stop path to a machine and no operator-required limit.

The gate cannot install or import the clone (and package code never imports it), so the ``fake`` backend is the
package's own analytic stand-in for the wrapper.  It models the episode lifecycle (reset samples a seed, step
advances one control period, the task horizon truncates) and a reduced ``qpos`` observation; it does not run
MuJoCo and does not model rigid-body dynamics.  The fidelity ``gaps`` say so.

Every fact cites a file and line of the clone at commit 713fd12ab593c3bbb4abfaa76622e14249aa36b3.  This package
is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

GYM_ENV = "molmo_spaces/tasks/gym_env.py"
TASK = "molmo_spaces/tasks/task.py"
SAMPLER = "molmo_spaces/tasks/task_sampler.py"
SENSORS = "molmo_spaces/env/sensors.py"
ROBOT_CONFIGS = "molmo_spaces/configs/robot_configs.py"
PICK_CONFIG = "molmo_spaces/configs/base_pick_config.py"
CONFIG_REGISTRY = "molmo_spaces/data_generation/config/object_manipulation_datagen_configs.py"
GYM_DOC = "docs/gym_compatibility.md"


class MolmoSpaces(GymnasiumDriver):
    """The MolmoSpaces GymEnv for the Franka pick data-generation config, served as a simulated R0 device."""

    device_id = "molmospaces"
    env_id = "MolmoSpaces/FrankaPickDroidDataGenConfig-v0"
    native = "molmo_spaces.tasks.gym_env:GymEnv"
    backends = {"fake": ".fake:FakeGymEnv"}
    display_name = "MolmoSpaces GymEnv (Franka pick, simulated)"
    vendor, model = "Allen Institute for AI", "MolmoSpaces"
    tags = ["molmospaces", "gymnasium", "simulation", "reinforcement-learning", "franka", "mujoco"]
    facts = [
        Fact("GymEnv is the molmospaces gymnasium environment class; it subclasses gymnasium.Env",
             source="upstream_code", ref=f"{GYM_ENV}:48"),
        Fact("GymEnv wraps a MolmoSpaces task sampler and keeps the current episode's task on env.task",
             source="upstream_code", ref=f"{GYM_ENV}:49-53"),
        Fact("The env id namespace is MolmoSpaces", source="upstream_code", ref=f"{GYM_ENV}:42"),
        Fact("An environment id is NAMESPACE/<ConfigName>-v<version>", source="upstream_code",
             ref=f"{GYM_ENV}:210"),
        Fact("The upstream gym compatibility guide builds the Franka pick environment with the id "
             "MolmoSpaces/FrankaPickDroidDataGenConfig-v0", source="vendor_doc", ref=f"{GYM_DOC}:21"),
        Fact("FrankaPickDroidDataGenConfig is registered in the data generation config registry",
             source="upstream_code", ref=f"{CONFIG_REGISTRY}:71"),
        Fact("GymEnv deliberately declares no action_space: actions are dicts keyed by move group (arm, gripper, "
             "etc.)", source="upstream_code", ref=f"{GYM_ENV}:74-76"),
        Fact("GymEnv deliberately declares no observation_space: observations are list[dict], one per batch "
             "element", source="upstream_code", ref=f"{GYM_ENV}:76-78"),
        Fact("The gym compatibility guide states observations are list[dict], one per batch element, and the key "
             "set can change between resets", source="vendor_doc", ref=f"{GYM_DOC}:84-86"),
        Fact("Only n_batch == 1 is supported; a larger batch is refused", source="upstream_code",
             ref=f"{GYM_ENV}:165-171"),
        Fact("The only reset options are house_index and force_advance_scene", source="upstream_code",
             ref=f"{GYM_ENV}:44-45"),
        Fact("reset(seed, options) samples a new task and returns task.reset()", source="upstream_code",
             ref=f"{GYM_ENV}:144-178"),
        Fact("reset closes the previous task before sampling the next one", source="upstream_code",
             ref=f"{GYM_ENV}:155-161"),
        Fact("step delegates to the current task's step with the action dict", source="upstream_code",
             ref=f"{GYM_ENV}:181-184"),
        Fact("A reset with a seed calls task_sampler.seed_task_sampling(seed)", source="upstream_code",
             ref=f"{GYM_ENV}:144-146"),
        Fact("seed_task_sampling seeds random, numpy and torch globally", source="upstream_code",
             ref=f"{SAMPLER}:428-431"),
        Fact("The PickBaseConfig control timestep is 2.0 ms and its task horizon is 500 steps",
             source="upstream_code", ref=f"{PICK_CONFIG}:39-42"),
        Fact("A task is truncated when episode_step_count reaches the task horizon", source="upstream_code",
             ref=f"{TASK}:423-424"),
        Fact("A task step returns observation, reward, terminated, truncated and info", source="upstream_code",
             ref=f"{TASK}:379"),
        Fact("The task info carries cumulative_reward and num_steps_taken per batch element",
             source="upstream_code", ref=f"{TASK}:463-472"),
        Fact("RobotJointPositionSensor returns the robot joint positions as a dict keyed by move group",
             source="upstream_code", ref=f"{SENSORS}:344-361"),
        Fact("The pick task sensor suite registers the qpos sensor with uuid qpos and max_joints 9",
             source="upstream_code", ref=f"{SENSORS}:1017"),
        Fact("Franka's initial qpos has 7 arm joints and 2 gripper joints", source="upstream_code",
             ref=f"{ROBOT_CONFIGS}:150-153"),
        Fact("register_configs registers every config with entry point molmo_spaces.tasks.gym_env:GymEnv and "
             "max_episode_steps None", source="upstream_code", ref=f"{GYM_ENV}:227-233"),
        Fact("Registration passes order_enforce=False so gymnasium.make returns the GymEnv itself",
             source="upstream_code", ref=f"{GYM_ENV}:237-241"),
        Fact("render returns an RGB array and does not require render_mode to be set", source="upstream_code",
             ref=f"{GYM_ENV}:186-198"),
        Fact("close closes the current task and closes the sampler only when the env built it",
             source="upstream_code", ref=f"{GYM_ENV}:199-205"),
        Fact("A reset samples an episode and can load a scene and compile a MuJoCo model, which takes seconds",
             source="vendor_doc", ref=f"{GYM_DOC}:88-90"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: The fidelity contract of the model as deployed.  The fake backend is an analytic episode model, not MuJoCo:
    #: F0, one tick is one 2 ms control step of the selected config, and the gaps list what is not modelled.
    fidelity = {
        "engine": "molmo_spaces:GymEnv (fake backend: analytic episode model; upstream would be MuJoCo)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake's reset re-seeds its own random.Random from the reset seed, so one seed and one "
                     "action sequence repeat its trajectory; upstream seeds Python's random, numpy and torch "
                     "globally instead (task_sampler.py:428-431), so the two are not expected to agree",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic/analytic wrapper only: the fake samples an episode and advances one 2 ms control step per "
            "tick (PickBaseConfig ctrl_dt_ms, base_pick_config.py:39); it models no MuJoCo rigid-body dynamics, "
            "contacts, gripper geometry, actuators, sensors or noise",
            "the observation is reduced to the qpos sensor of one batch element: arm 7 joints and gripper 2 joints "
            "(robot_configs.py:150-153); upstream also returns qvel, robot_base_pose, env_states, task_info, "
            "camera frames, TCP pose, object poses and action sensors, and the key set can change between resets",
            "actions are accepted as an open dict keyed by move group; the fake applies arm and gripper joint "
            "positions but does not model the controller, contact or object interaction the real task uses",
            "no rendering: render() is not served by this package and no RGB frame is produced",
            "no wall-clock pacing: realtime_factor 0 and only commands advance simulated time, one control step "
            "per tick",
            "no snapshot or restore: GymEnv exposes no get_state/set_state, so determinism is seeded, not exact",
            "the fake was never compared with a real MuJoCo run, no physical device is modelled, and the model "
            "was not validated against one",
        ],
    }
