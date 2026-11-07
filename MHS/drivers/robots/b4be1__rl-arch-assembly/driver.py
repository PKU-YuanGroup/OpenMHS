"""OpenMHS driver for gh.b4be1/rl-arch-assembly: the StackingTask assembly environment (Gymnasium family).

``StackingTask`` is a legacy Gym environment for a simulated UR10 assembly cell.  The task package builds a
``gym.spaces.Dict`` action space from its controllers and a ``gym.spaces.Dict`` observation space from its sensors
(``python/task/base_task.py:73-87``); the canonical configuration in ``python/algorithm/run_config/env/stacking.py``
uses two controllers and ten sensors.  The bridge serves ``cap.world.step.v1``, ``cap.world.reset.v1`` and
``cap.world.seed.v1``; the action is the controller dictionary and every continuous value is normalized to [-1, 1].

The upstream environment cannot be constructed by ``gym.make``: it has no registration id, its constructor requires
controllers, sensors, rewards, task data and aggregation properties (``python/task/stacking_task.py:31-41``), and the
``assembly-gym`` package it imports is an unpopulated git submodule (``.gitmodules:21-24``).  The ``fake`` backend is
therefore the package's own analytic model of the observed interface (fake.py), not the PyBullet environment.  The
simulated world is R1: every step advances a simulated robot arm, so a wrong action changes simulated state, but
nothing here has a hardware backend, a physical e-stop or an operator-required limit.  This package is model-authored
and unreviewed; it was checked on the fake backend only.

The ``fidelity`` attribute is the complete contract of the model as deployed (spec 05-fidelity FID-002): analytic
kinematics, no engine, no contacts and no validated dynamics.  Every Fact cites a line of the clone at the pinned
commit 187e460c79e41ae38e1b750d75e369f3473dd3eb.
"""

from mhs.driver import Fact, GymnasiumDriver


class StackingTask(GymnasiumDriver):
    device_id = "rl-arch-assembly"
    native = "task.stacking_task:StackingTask"
    backends = {"fake": ".fake:FakeStackingTask"}
    display_name = "rl-arch-assembly StackingTask (simulated UR10 placing)"
    vendor, model = "b4be1", "rl-arch-assembly StackingTask"
    tags = ["assembly", "gym", "placing", "reinforcement-learning", "robot-arm", "simulation", "stacking", "ur10"]
    risk = "R1"
    facts = [
        Fact("The project documentation says the task package defines the gym environment used to train the placing "
             "controller", source="vendor_doc", ref="README.md:55"),
        Fact("StackingTask is the task in which the robot stacks a given number of parts on an existing structure",
             source="upstream_code", ref="python/task/stacking_task.py:26-29"),
        Fact("BaseTask is the gym.Env base of the task classes", source="upstream_code",
             ref="python/task/base_task.py:25"),
        Fact("BaseTask.initialize builds observation_space and action_space as gym.spaces.Dict from the sensors and "
             "controllers", source="upstream_code", ref="python/task/base_task.py:73-87"),
        Fact("BaseTask.step returns the legacy four-value tuple observation, reward, done, info",
             source="upstream_code", ref="python/task/base_task.py:146"),
        Fact("BaseTask.reset takes no seed or options and returns only the initial observation",
             source="upstream_code", ref="python/task/base_task.py:160-181"),
        Fact("BaseTask.step ends the episode when the configured time_limit_steps is reached", source="upstream_code",
             ref="python/task/base_task.py:111-112"),
        Fact("Controller.initialize returns a normalized gym.spaces.Box action in [-1, 1] per joint",
             source="upstream_code", ref="python/task/controllers/controller.py:33-35"),
        Fact("ContinuousSensor normalizes every observation to [-1, 1] and clips only when clip=True",
             source="upstream_code", ref="python/task/sensors/continuous_sensor.py:18-22"),
        Fact("The controller interval of the canonical stacking configuration is 0.05 s and time_limit_steps is "
             "round(time_limit_s / controller_interval)", source="upstream_code",
             ref="python/algorithm/run_config/env/stacking.py:25-26"),
        Fact("The canonical stacking configuration uses a joint-velocity-difference arm controller and a "
             "joint-position gripper controller", source="upstream_code",
             ref="python/algorithm/run_config/env/stacking.py:33-38"),
        Fact("The canonical stacking configuration observes the arm joint sin/cos and velocity, the gripper joint "
             "angle and velocity, the end-effector pose and velocity, the current part's pose, velocity and target "
             "pose, and the time", source="upstream_code",
             ref="python/algorithm/run_config/env/stacking.py:41-43"),
        Fact("The controller Dict key is '<name_prefix>_controller_<robot_name>_<component>'", source="upstream_code",
             ref="python/task/controllers/robot_component_controller.py:22-23"),
        Fact("StackingTask requires controllers, sensors, rewards, a task path, aggregation properties, spawn "
             "position and orientation limits and a target position; it has no zero-argument constructor",
             source="upstream_code", ref="python/task/stacking_task.py:31-41"),
        Fact("The episode ends when the last part is released from the gripper, or when the optional target-reached "
             "condition is enabled and met", source="upstream_code", ref="python/task/stacking_task.py:142-154"),
        Fact("assembly-gym is declared as the git submodule at submodule/assembly-gym", source="upstream_code",
             ref=".gitmodules:21-24"),
    ]
    safe_state = ("the simulation stops advancing: an e-stop latches in the runtime and no step or reset is "
                  "accepted until mhs.safety.reset clears it; the last state stays readable")
    #: The contract of the model as deployed (spec 05-fidelity section 2).  The fake is analytic (F0): it mirrors
    #: the action and observation keys of the canonical configuration, not the PyBullet scene or its dynamics.
    fidelity = {
        "engine": "rl-arch-assembly:StackingTask (analytic fake)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake reseeds random.Random(seed) on reset(seed) and repeats a trajectory for the same seed "
                     "and actions; upstream BaseTask.reset takes no seed or options and uses process-global random "
                     "and numpy generators, so seed control is a property of the fake and was not verified upstream",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "analytic kinematics, not a physics engine: no PyBullet, no scene, meshes or task definitions, and no "
            "rigid-body dynamics, contacts, friction, gripper mechanics or assembly physics",
            "no UR10 inverse kinematics or controller loop: the fake integrates placeholder joint velocities and an "
            "end-effector position; the observation vectors are synthesized normalized state, not sensor readings",
            "the reward and the done condition are placeholders: upstream the reward is a sum of four reward terms "
            "and done depends on part release, optional target markers and time_limit_steps (stacking_task.py:142-154, "
            "base_task.py:111-112); the fake only stops at a placeholder episode-step count",
            "the observation keys follow the canonical get_env_config sensor set, but the values are not "
            "measurements of a simulation and were never compared with an upstream run",
            "the upstream task needs the assembly-gym submodule (.gitmodules:21-24), which is not present in the "
            "clone; the fake neither imports it nor the clone",
            "no seed/options contract upstream: BaseTask.reset takes no seed or options (base_task.py:160); the fake "
            "accepts a seed for the bridge and ignores reset options",
            "no rendering, snapshot/restore, DIGIT tactile sensors, task data, aggregation properties or wrappers",
            "no wall-clock pacing: realtime_factor 0; one tick advances the fake by 50 ms, while time_step is a "
            "constructor argument upstream and the canonical configuration passes 0.05 s",
            "the sim backend is not offered: the clone registers no gym id and StackingTask cannot be built without "
            "the missing submodule and task data; only the fake backend was checked",
        ],
    }
