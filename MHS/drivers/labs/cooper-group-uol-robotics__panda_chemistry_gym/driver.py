"""OpenMHS driver for gh.cooper-group-uol-robotics/panda_chemistry_gym: the Capping-v1 environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
whole contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action
``{values}`` bounded by ``Box(-1, 1)`` with four elements (three end-effector displacements and the gripper),
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated
(R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The gate never imports PyBullet, gym, gym_robotics or numpy (the upstream needs Python 3.8 and those packages,
README.md "Installation Requirements"), so the ``fake`` backend is the package's own pure Python kinematic stand-in.
A backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)``
(GymnasiumDriver.open_native); that path needs the upstream package, the ``custom_envs`` registration, PyBullet and
the mesh files, and was not run here (README.md).

The upstream class is the old Gym API: ``RobotTaskEnv.reset(seed)`` returns an observation, not a
``(observation, info)`` pair, and ``step`` returns a four-tuple ``(observation, reward, done, info)`` with ``done``
always False (``core.py:269-298``).  The bridge accepts both shapes; the fake applies the registration's 100-step
limit through ``done``, so the bridge reports the time-limit step as ``terminated``.  The ``fidelity`` attribute is
the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).  Every fact cites a line of the
clone at the pinned commit 10e82317010f662f5f8f0602e068447d170d9bb0.  This package is model-authored and
unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

CAPPING = "custom_envs/envs/Insertion_PandaTasks/Capping/Capping_PandaTask.py"
TASK = "custom_envs/envs/Insertion_Tasks/Capping/Capping_Task.py"
PANDA = "custom_envs/envs/robots/panda.py"
CORE = "panda_chemistry_gym/core.py"
PYBULLET = "panda_chemistry_gym/pybullet.py"
REGISTRY = "custom_envs/__init__.py"


class Capping(GymnasiumDriver):
    device_id = "panda-chemistry-capping"
    env_id = "Capping-v1"
    native = "custom_envs.envs:Capping_Env"
    backends = {"fake": ".fake:FakeCappingEnv"}
    display_name = "panda_chemistry_gym Capping-v1 (PyBullet Franka Panda)"
    vendor, model = "Cooper Group UoL Robotics", "Capping-v1"
    tags = ["panda", "pybullet", "capping", "insertion", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("Capping_Env builds a PyBullet simulation and a Panda robot with the gripper enabled, base position "
             "[-0.6, 0, 0], ee control and the Capping task", source="upstream_code", ref=f"{CAPPING}:15-19"),
        Fact("Capping_Env is registered as Capping{}{}-v1 in both control and reward variants, with "
             "max_episode_steps=100; the ee/sparse instance is Capping-v1", source="upstream_code",
             ref=f"{REGISTRY}:8-19"),
        Fact("In ee control the Panda action space is Box(-1.0, 1.0) with four values: three displacement values "
             "and one gripper value (3 + 1 because the gripper is not blocked)", source="upstream_code",
             ref=f"{PANDA}:22-24"),
        Fact("Panda.set_action clips the action to the action space low and high before using it",
             source="upstream_code", ref=f"{PANDA}:44-46"),
        Fact("In ee control the first three action values are an end-effector displacement scaled by 0.05",
             source="upstream_code", ref=f"{PANDA}:64-68"),
        Fact("The gripper action value is scaled by 0.2 and added to the current finger width",
             source="upstream_code", ref=f"{PANDA}:56-59"),
        Fact("The Panda observation is seven values: end-effector position (3), end-effector velocity (3) and "
             "finger width (1)", source="upstream_code", ref=f"{PANDA}:83-93"),
        Fact("The Capping task observation is nine values: cap base position (3), rotation (3) and velocity (3)",
             source="upstream_code", ref=f"{TASK}:152-159"),
        Fact("RobotTaskEnv._get_obs concatenates the robot and task observations and returns a dict with the keys "
             "observation, achieved_goal and desired_goal", source="upstream_code", ref=f"{CORE}:258-267"),
        Fact("The observation space is a Dict of three float32 Boxes bounded -200.0 to 200.0, for observation, "
             "desired_goal and achieved_goal; the action space is a Box(-1.0, 1.0) with the robot action shape",
             source="upstream_code", ref=f"{CORE}:245-253"),
        Fact("The achieved goal is six values: cap position (3) and end-effector position (3)",
             source="upstream_code", ref=f"{TASK}:162-166"),
        Fact("The desired goal is six values: cap target position (3) and vial end-effector position (3)",
             source="upstream_code", ref=f"{TASK}:191-195"),
        Fact("Capping.reset adds random xy offsets in [0, 0.05) to the cap and cap holder, to the vial and vial "
             "holder, and twice to the goal", source="upstream_code", ref=f"{TASK}:169-188"),
        Fact("The Capping task draws those placement offsets from Python's global random module, not from a seeded "
             "numpy generator", source="upstream_code", ref=f"{TASK}:172-173"),
        Fact("RobotTaskEnv.reset(seed) seeds the task's np_random generator, resets the robot and task, and returns "
             "the observation instead of an (observation, info) pair", source="upstream_code", ref=f"{CORE}:269-274"),
        Fact("The Capping task distance_threshold defaults to 0.015", source="upstream_code", ref=f"{TASK}:21"),
        Fact("is_success returns True when distance(achieved_goal, desired_goal) is below the task's "
             "distance_threshold", source="upstream_code", ref=f"{TASK}:198-201"),
        Fact("The reward is -1.2 while the cap touches the cap holder, otherwise -distance to the goal, and 1.0 "
             "when the task is already successful", source="upstream_code", ref=f"{TASK}:204-222"),
        Fact("RobotTaskEnv.step applies the robot action, advances the simulation, and returns (observation, "
             "reward, done, info) with done always False; success is only info['is_success']",
             source="upstream_code", ref=f"{CORE}:289-298"),
        Fact("The PyBullet wrapper defaults to 50 substeps, sets a 1/500 s physics timestep, gravity -9.81 m/s^2, "
             "and runs one physics step per substep", source="upstream_code", ref=f"{PYBULLET}:25-54"),
        Fact("One PyBullet.step() therefore advances 50 * (1/500) = 0.1 s of simulated time, the control interval",
             source="upstream_code", ref=f"{PYBULLET}:46-54"),
        Fact("The environment is simulated only: close() disconnects the PyBullet client and no hardware transport "
             "exists", source="upstream_code", ref=f"{PYBULLET}:56-58"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "pybullet:panda_chemistry_gym/Capping-v1",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the package's fake seeds random.Random from reset(seed) or cap.world.seed.v1, so one seed "
                     "and one action sequence give the same state hashes on the fake; upstream reset(seed) seeds "
                     "the task's np_random generator but Capping.reset draws its offsets from Python's global "
                     "random (Capping_Task.py:172-173), so the upstream path is not reproducible from the seed "
                     "alone; neither path was compared with the other",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a kinematic stand-in: it moves the end-effector and finger width and keeps the cap "
            "fixed, without PyBullet contact dynamics, collision response, mass, friction or the mesh scene, so it "
            "cannot reproduce the cap-holder contact reward or a physical insertion; the cap and goal are "
            "placeholders",
            "the upstream physics timestep is 2 ms and one environment step runs 50 substeps (a 100 ms control "
            "interval, pybullet.py:25-54); the fake advances one placeholder kinematic step per tick and does not "
            "integrate physics, so it does not model that interval",
            "the fake follows the old Gym API of the upstream class (reset returns an observation, step a "
            "four-tuple with done always False) and applies the registration's 100-step limit through done, so the "
            "bridge reports the 100th tick as terminated rather than truncated",
            "no wall-clock pacing (realtime_factor 0); the fake was not compared with the upstream PyBullet "
            "environment, and the model was never validated against a physical Panda or a laboratory task",
            "snapshot and restore are not offered: the environment exposes save_state/restore_state over PyBullet "
            "but no get_state/set_state that the bridge requires, so cap.world.snapshot.v1 is not bound",
            "rendering (human or rgb_array at 720 x 480, core.py:303-343) is not exposed by the cap.world.* classes",
        ],
    }
