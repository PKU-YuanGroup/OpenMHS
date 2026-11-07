"""OpenMHS driver for gh.eric-ai-lab/vlmbench: the VLMbench Gymnasium environment (state mode).

A ``GymnasiumDriver`` is configuration only: ``env_id`` names the registered environment and the bridge derives the
contract from its spaces.  ``amsolver.gym`` registers every file under ``vlm/tasks`` as ``<task>-state-v0`` and
``<task>-vision-v0`` (amsolver/gym/__init__.py:10-26); this package serves the state environment of
``drop_pen_color`` and therefore the action space ``Box(-1, 1, (8,))`` (vlmbench_env.py:32-41, environment.py:41-47
and :188-207).  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{values: [8 floats]}``,
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.

The upstream environment is a CoppeliaSim/PyRep wrapper: ``VLMBenchEnv.__init__`` launches ``Environment`` headlessly
and gets a task (vlmbench_env.py:32-36), whose ``reset`` returns ``(descriptions, observation)`` and whose ``step``
returns ``(observation, reward, terminate)`` (task_environment.py:88-105 and :422-430).  The wrapper itself speaks the
legacy Gym API (reset returns a dict and step a 4-tuple, vlmbench_env.py:95-103), while the bridge uses the Gymnasium
5-tuple.  That difference and the state-vector composition are in the fidelity ``gaps``.

The upstream simulator needs CoppeliaSim 4.1.0 and PyRep (README.md:20) and was not run.  The ``fake`` backend is the
package's own pure-Python kinematic stand-in (fake.py).  A backend name that ``backends`` does not list (``sim``) would
be served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path additionally needs
``import amsolver.gym`` to register the task ids (amsolver/gym/__init__.py:10-26), which this package never does, so it
was not run.  This package is model-authored and unreviewed: it is checked on the fake backend only.

Every constant and rule cites a line of the clone at the pinned commit
(479bd17b7d80645002af74f142a29dfe8b428876).
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "amsolver/gym/vlmbench_env.py"
TASK_ENV = "amsolver/task_environment.py"
OBS = "amsolver/backend/observation.py"
SCENE = "amsolver/backend/scene.py"
ENVIRONMENT = "amsolver/environment.py"
REGISTRY = "amsolver/gym/__init__.py"
TASK_PATH = "amsolver/backend/task.py"


class VLMBench(GymnasiumDriver):
    device_id = "vlmbench"
    env_id = "drop_pen_color-state-v0"
    native = "amsolver.gym.vlmbench_env:VLMBenchEnv"
    backends = {"fake": ".fake:FakeVLMBenchEnv"}
    action_space_ref = f"{ENV}:40-41"
    display_name = "VLMbench DropPenColor (Gymnasium state mode)"
    vendor, model = "eric-ai-lab", "VLMbench drop_pen_color-state-v0"
    tags = ["vlmbench", "manipulation", "benchmark", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("VLMBenchEnv is a gymnasium.Env: the class is declared as `class VLMBenchEnv(gym.Env)`",
             source="upstream_code", ref=f"{ENV}:14"),
        Fact("VLMBenchEnv takes a task class and an observation_mode of 'state' or 'vision'; any other mode raises "
             "ValueError", source="upstream_code", ref=f"{ENV}:19-31"),
        Fact("The wrapper builds an amsolver Environment with ArmActionMode.ABS_JOINT_VELOCITY, launches it headlessly "
             "and gets the task from it", source="upstream_code", ref=f"{ENV}:32-36"),
        Fact("The action space is Box(low=-1.0, high=1.0, shape=(Environment.action_size,))",
             source="upstream_code", ref=f"{ENV}:40-41"),
        Fact("The supported-robot table gives the panda 7 arm joints", source="upstream_code",
             ref=f"{ENVIRONMENT}:41-47"),
        Fact("Action_size is the arm action size plus one gripper value, and for ABS_JOINT_VELOCITY the arm action "
             "size is the supported arm's joint count", source="upstream_code", ref=f"{ENVIRONMENT}:188-207"),
        Fact("The state observation space is Box(-inf, inf, shape=obs.get_low_dim_data().shape)",
             source="upstream_code", ref=f"{ENV}:43-45"),
        Fact("Vision mode is a Dict of the state plus left_shoulder_rgb, right_shoulder_rgb, wrist_rgb and front_rgb "
             "images", source="upstream_code", ref=f"{ENV}:46-59"),
        Fact("VLMBenchEnv.reset calls task.reset() and returns the extracted observation with the descriptions list "
             "added", source="upstream_code", ref=f"{ENV}:95-99"),
        Fact("VLMBenchEnv.step calls task.step(action) and returns (observation, reward, terminate, {})",
             source="upstream_code", ref=f"{ENV}:101-103"),
        Fact("TaskEnvironment.step treats the last action value as the gripper command and the rest as the arm "
             "action", source="upstream_code", ref=f"{TASK_ENV}:239-241"),
        Fact("The arm action length must equal the number of arm joints", source="upstream_code",
             ref=f"{TASK_ENV}:259-260"),
        Fact("The gripper command is open above 0.5 and closed below 0.5; exactly 0.5 keeps the current state",
             source="upstream_code", ref=f"{TASK_ENV}:251-254"),
        Fact("TaskEnvironment.step returns float(success) as the reward and the task's terminate flag, with 1.0 when "
             "a success occurred along a path and 0.5 for a grasp success", source="upstream_code",
             ref=f"{TASK_ENV}:422-430"),
        Fact("Observation.get_low_dim_data concatenates gripper_open first, then the non-None joint velocities, joint "
             "positions, joint forces, gripper pose, gripper joint positions, gripper touch forces and task "
             "low-dimensional state", source="upstream_code", ref=f"{OBS}:72-84"),
        Fact("The scene fills joint velocities, joint positions, gripper_open (1.0 when the gripper opening is above "
             "0.9), gripper_pose (the tip pose), gripper joint positions and the task state",
             source="upstream_code", ref=f"{SCENE}:287-314"),
        Fact("amsolver.gym registers every task file under vlm/tasks as <task>-state-v0 and <task>-vision-v0 with "
             "entry point amsolver.gym:VLMBenchEnv", source="upstream_code", ref=f"{REGISTRY}:10-26"),
        Fact("TASKS_PATH is ../../vlm/tasks relative to the amsolver/backend package, so the task classes are read "
             "from the clone tree", source="upstream_code", ref=f"{TASK_PATH}:25"),
        Fact("Environment.launch creates a PyRep and launches task_design.ttt headlessly",
             source="upstream_code", ref=f"{ENVIRONMENT}:136-138"),
        Fact("TaskEnvironment declares a module constant _DT = 0.05", source="upstream_code",
             ref=f"{TASK_ENV}:27"),
        Fact("The registration calls set no max_episode_steps, so a state environment has no truncation wrapper",
             source="upstream_code", ref=f"{REGISTRY}:13-26"),
        Fact("The documented Gymnasium example makes drop_pen_color-vision-v0, the vision id of the same task",
             source="vendor_doc", ref="examples/gym_test.py:42"),
        Fact("The AMSolver install instructions require CoppeliaSim 4.1.0 and PyRep", source="vendor_doc",
             ref="README.md:20"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).
    fidelity = {
        "engine": "gymnasium:drop_pen_color-state-v0 (AMSolver/CoppeliaSim)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake re-seeds its generator on reset(seed) and is deterministic after that; the upstream "
                     "VLMBenchEnv.reset() takes no seed and its task placement uses numpy's random generator, so a "
                     "seed is a bridge extension and was never compared with the upstream environment",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no dynamics: the fake integrates joint positions with position += 0.05 s * target velocity; it models "
            "no contacts, friction, gravity, actuator, sensor or noise",
            "the fake has no task scene, objects, language descriptions or success condition from the 32 task files "
            "under vlm/tasks: it stands in for the state-mode interface, not for a task",
            "the upstream wrapper returns only the observation from reset() and a 4-tuple from step() (the legacy "
            "Gym API); the fake follows the Gymnasium reset 2-tuple and step 5-tuple that the bridge reads, accepts "
            "the bridge's seed and options, and ignores options because the upstream reset() takes no arguments",
            "the fake's 29-element state is only the prefix of the real low-dimensional observation that the clone "
            "defines: gripper_open (1), joint velocities, joint positions and joint forces (7 each for the panda) "
            "and gripper pose (7); gripper joint positions, gripper touch forces and task_low_dim_state are "
            "omitted and the real length depends on the PyRep gripper and the task",
            "vision mode returns 1x1 RGB placeholders; the real camera default is 128x128 (observation_config.py:14) "
            "and no rendering was run",
            "the upstream simulation step is not stated in a text file: task_environment.py:27 declares _DT = 0.05 "
            "but no other line uses it, and the scene step is stored in the binary task_design.ttt; timestep_ms 50 "
            "describes the fake's own step",
            "no snapshot or restore is offered: neither the wrapper nor the fake exposes get_state/set_state",
            "the fake was never compared with the upstream environment: CoppeliaSim 4.1.0 and PyRep are required "
            "(README.md:20) and were not installed or run",
        ],
    }
