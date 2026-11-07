"""OpenMHS driver for gh.ianyangchina/pybullet_multigoal_gym: the KukaBlockStack environment (a Gymnasium family
driver for a legacy Gym simulation).

The upstream package is a PyBullet implementation of the OpenAI Gym multi-goal robotics environment, built around a
Kuka iiwa14 7DoF arm with a robotiq85 or a parallel jaw gripper (README.md:9-11).  ``make_env(task='block_stack')``
registers and returns ``KukaBlockStackParallelGripSparseReward-v0``, whose entry class is
``KukaBlockStackEnv`` (__init__.py:33-35, :56-83, :178).  One package serves one task and one deployed
configuration: the default parallel-jaw, sparse-reward, non-image, non-joint-control BlockStack environment with
five blocks.

A GymnasiumDriver is configuration only.  The bridge derives ``cap.world.step.v1`` (``{ticks, action}`` with the
action ``{values}`` bounded element by element by the environment's ``Box(-1, 1)``), ``cap.world.reset.v1``
(``{seed, options}``) and ``cap.world.seed.v1`` (``{seed}``) from the environment.  The device is simulated and has
no hardware backend.  The risk is R1, not R0, because every step advances a simulated robot arm (simulation
stepping, MHS/spec/04-safety.md section 2.1), and there is no physical effect outside the process; no independent
hardware e-stop exists or is claimed.

The gate cannot import the clone (it needs gym, pybullet, numpy, numba and numpy-quaternion, requirements.txt:1-6),
and package code never imports the clone.  The ``fake`` backend is therefore the package's pure Python stand-in
(fake.py), which models the public surface and the registered 50-step horizon but no rigid-body dynamics.  A backend
name that ``backends`` does not list (``sim``) would be served by ``gym.make(env_id)`` (GymnasiumDriver.open_native);
that needs the upstream package, and the id is registered only when ``make_env`` is called, so it was not run here.

Every Fact cites a line of the clone at the pinned commit (54b50b8de3d2d58f88f8d4036aafc0858ed3d1e5).  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

INIT = "pybullet_multigoal_gym/__init__.py"
BASE = "pybullet_multigoal_gym/envs/base_envs/base_env.py"
MULTI = "pybullet_multigoal_gym/envs/task_envs/kuka_multi_step_envs.py"
MULTI_BASE = "pybullet_multigoal_gym/envs/base_envs/kuka_multi_step_base_env.py"
KUKA = "pybullet_multigoal_gym/robots/kuka.py"
README = "README.md"
REQUIREMENTS = "requirements.txt"


class KukaBlockStack(GymnasiumDriver):
    device_id = "kuka-block-stack"
    env_id = "KukaBlockStackParallelGripSparseReward-v0"
    native = "pybullet_multigoal_gym.envs.task_envs.kuka_multi_step_envs:KukaBlockStackEnv"
    backends = {"fake": ".fake:FakeKukaBlockStackEnv"}
    action_space_ref = f"{KUKA}:113"
    display_name = "pybullet_multigoal_gym KukaBlockStack (parallel jaw, sparse reward)"
    vendor, model = "Xintong Yang", "KukaBlockStackParallelGripSparseReward-v0"
    device_kind = "world.sim"
    risk = "R1"
    tags = ["kuka", "iiwa14", "block-stack", "manipulation", "pybullet", "reinforcement-learning", "simulation",
            "gym"]
    facts = [
        Fact("The package is a PyBullet implementation of the OpenAI Gym multi-goal robotics environment and uses "
             "a Kuka iiwa14 7DoF arm with a robotiq85 or a parallel jaw gripper", source="vendor_doc",
             ref=f"{README}:9-11"),
        Fact("Observation is a dictionary containing the state, desired goal, achieved goal and other sensory "
             "data", source="vendor_doc", ref=f"{README}:60"),
        Fact("The documented way to create an environment is the make_env(...) method", source="vendor_doc",
             ref=f"{README}:62"),
        Fact("make_env maps task 'block_stack' to the entry point "
             "pybullet_multigoal_gym.envs.task_envs.kuka_multi_step_envs:KukaBlockStackEnv", source="upstream_code",
             ref=f"{INIT}:33-35"),
        Fact("make_env builds the environment id from the task tag, gripper, render, reward, joint-control and "
             "image flags and appends -v0", source="upstream_code", ref=f"{INIT}:56-83"),
        Fact("make_env registers the multi-block tasks with the task constructor kwargs and the caller's "
             "max_episode_steps", source="upstream_code", ref=f"{INIT}:107-131"),
        Fact("make_env returns gym.make(env_id)", source="upstream_code", ref=f"{INIT}:178"),
        Fact("make_env defaults max_episode_steps to 50", source="upstream_code", ref=f"{INIT}:6"),
        Fact("KukaBlockStackEnv defaults distance_threshold to 0.05 and num_block to 5", source="upstream_code",
             ref=f"{MULTI}:7-10"),
        Fact("KukaBlockStackEnv passes grasping=True, joint_control=False, end_effector_start_on_table=False, "
             "obj_range=0.15 and target_range=0.15 to its multi-block base class", source="upstream_code",
             ref=f"{MULTI}:23-32"),
        Fact("BaseBulletMGEnv is a gym.Env", source="upstream_code", ref=f"{BASE}:10"),
        Fact("The base environment's constructor defaults are seed 0, gravity 9.81, timestep 0.002 s and "
             "frame_skip 20, and it seeds itself with seed 0", source="upstream_code", ref=f"{BASE}:15-24"),
        Fact("dt is timestep * frame_skip; the comment gives 0.002 * 20 = 0.04 seconds at the defaults",
             source="upstream_code", ref=f"{BASE}:112-118"),
        Fact("seed delegates to gym.utils.seeding.np_random and returns [seed]", source="upstream_code",
             ref=f"{BASE}:120-122"),
        Fact("reset(test=False) resets the robot and the task and returns the observation", source="upstream_code",
             ref=f"{BASE}:124-128"),
        Fact("step applies the action, computes the reward from the achieved and desired goals, and returns "
             "(obs, reward, False, info) with info['goal_achieved']", source="upstream_code", ref=f"{BASE}:130-138"),
        Fact("The environment owns an in-process PyBullet BulletClient (DIRECT by default, GUI when render=True) "
             "and sets gravity, fixedTimeStep = timestep * frame_skip, solver iterations and substeps; real-time "
             "simulation is off", source="upstream_code", ref=f"{BASE}:203-220"),
        Fact("The action space is the robot's action space", source="upstream_code", ref=f"{BASE}:84-85"),
        Fact("For non-image observations the observation space is a Dict of four Box(-inf, inf) float32 members "
             "named state, policy_state, achieved_goal and desired_goal", source="upstream_code",
             ref=f"{BASE}:86-92"),
        Fact("With grasping True, joint_control False and no primitive or end-effector rotation control, "
             "Kuka.action_space is Box(-1, 1) with 4 elements", source="upstream_code", ref=f"{KUKA}:108-113"),
        Fact("Each block contributes world position, relative position to the gripper, world euler orientation, "
             "and relative linear and angular velocities to the state, and its relative position to the policy "
             "state", source="upstream_code", ref=f"{MULTI_BASE}:264-280"),
        Fact("state is the gripper xyz, finger closeness, gripper velocity and finger velocity followed by the "
             "block states; policy_state is the gripper xyz, finger closeness and the relative block positions",
             source="upstream_code", ref=f"{MULTI_BASE}:282-283"),
        Fact("state and policy_state are clipped to [-5, 5]", source="upstream_code", ref=f"{MULTI_BASE}:306-307"),
        Fact("The observation dict has keys observation, policy_state, achieved_goal and desired_goal",
             source="upstream_code", ref=f"{MULTI_BASE}:317-320"),
        Fact("The sparse reward is -not_achieved and the dense reward is -distance, where distance is the "
             "Euclidean norm of the achieved minus desired goal and not_achieved is distance > distance_threshold",
             source="upstream_code", ref=f"{MULTI_BASE}:338-345"),
        Fact("The runtime dependencies are setuptools, pybullet~=3.0.6, gym~=0.17.3, numpy~=1.19.4, numba and "
             "numpy-quaternion", source="upstream_code", ref=f"{REQUIREMENTS}:1-6"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The only served backend is the
    #: package fake, so the package claims F0: placeholder kinematic transitions with no PyBullet, contacts,
    #: actuators or sensors.  The upstream environment would be an F1 PyBullet model, but it is not installed or
    #: run in this package.
    fidelity = {
        "engine": "pybullet:KukaBlockStackParallelGripSparseReward-v0 (kinematic fake stand-in)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) reaches the legacy env.seed() path and cap.world.seed.v1 sets the seed of the next "
                     "reset; the fake draws its placeholder block positions with Python's random.Random while "
                     "upstream seeds gym.utils.seeding.np_random, so one seed repeats on the fake but gives "
                     "different numbers than upstream, and no trajectory of the two was compared",
        },
        "timestep_ms": 40.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no dynamics: the fake moves the end effector by a fixed placeholder displacement and has no PyBullet, "
            "rigid-body, inverse-kinematics, contact, friction, actuator, sensor or noise model; the upstream "
            "environment would be an F1 PyBullet model, not this",
            "only the default non-image BlockStack configuration is modelled (parallel jaw or robotiq85, no joint "
            "control, no task decomposition, no curriculum, no grip-informed goal); image observations, goal "
            "images, depth and point clouds are refused by the fake",
            "observations are placeholder Python float lists; upstream returns float32 numpy arrays, and the "
            "reported lengths are the upstream composition for five blocks (83 state, 19 policy, 15 achieved and "
            "15 desired values), not measured runs",
            "the fake applies the 50-step time limit that make_env registers through max_episode_steps; the "
            "upstream task's own step() always returns done False and the limit comes from gym's TimeLimit wrapper",
            "the fake draws the initial state with Python's random.Random and upstream with numpy's generator, so "
            "one seed gives different numbers on the two",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state pair",
            "the upstream id is registered only when make_env is called, so the sim path (gym.make of the id) was "
            "not run; the fake is the only declared backend",
            "no physical device is modelled and the simulator was never validated against one",
        ],
    }
