"""OpenMHS driver for gh.xarm-developer/uf-gym: the XArm6Reach-v3 environment (a Gymnasium family driver).

``uf_gym`` adds UFACTORY xArm6/xArm7 models to panda-gym and registers Gymnasium environment ids on import.  This
package serves one of them, ``XArm6Reach-v3``: the task card's first confirmed entry symbol
``uf_gym.envs.uf_tasks.xarm6_tasks:XArm6ReachEnv``.  A GymnasiumDriver is configuration only; the bridge derives
``cap.world.step.v1`` (``{ticks, action}`` with ``action.values`` from the environment's ``Box`` action space),
``cap.world.reset.v1`` (``{seed, options}``) and ``cap.world.seed.v1`` (``{seed}``) from the environment.

The device is simulated (R0): it has no hardware backend and no operator-required limit.  The gate cannot import
gymnasium, pybullet or panda-gym (the clone declares pybullet and panda-gym as external prerequisites,
README.md:11-12, and its scripts add a sibling panda-gym checkout to sys.path, test_xarm6_reach.py:3), so the
``fake`` backend is the package's own pure Python kinematic stand-in (fake.py).  A backend name that ``backends``
does not list (``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path needs the
upstream packages and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
The checked deployment is the kinematic fake, so the level is F0; the gaps state what the upstream PyBullet
simulation does that the fake does not reproduce.  This package is model-authored and unreviewed: it is checked on
the fake backend only.  The other entry symbols of the card (XArm6ReachEnv's siblings in ``xarm6_tasks.py`` and
``xarm7_tasks.py`` and the XArm6/XArm7 robot classes) are named in facts.md and are not served by this package.
"""

from mhs.driver import Fact, GymnasiumDriver

TASKS6 = "uf_gym/envs/uf_tasks/xarm6_tasks.py"
ROBOT6 = "uf_gym/envs/uf_robots/xarm6.py"
REGISTRATION = "uf_gym/__init__.py"


class XArm6Reach(GymnasiumDriver):
    device_id = "xarm6-reach"
    env_id = "XArm6Reach-v3"
    env_kwargs = {"reward_type": "sparse", "control_type": "ee"}
    native = "uf_gym.envs.uf_tasks.xarm6_tasks:XArm6ReachEnv"
    backends = {"fake": ".fake:FakeXArm6ReachEnv"}
    action_space_ref = f"{ROBOT6}:32-34"
    display_name = "UFACTORY xArm6 Reach (panda-gym / PyBullet)"
    vendor, model = "UFACTORY", "XArm6Reach-v3"
    tags = ["ufactory", "xarm6", "reach", "panda-gym", "pybullet", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("The repository adds UFACTORY robot model support to panda-gym training and simulation tools for "
             "reinforcement learning", source="vendor_doc", ref="README.md:3"),
        Fact("pybullet and panda-gym are prerequisites of the repository", source="vendor_doc",
             ref="README.md:11-12"),
        Fact("The scripts add a sibling ../panda-gym checkout to sys.path, so panda-gym is external to this "
             "repository", source="upstream_code", ref="test_xarm6_reach.py:3"),
        Fact("Only xArm6 and xArm7 (with gripper) are supported currently", source="vendor_doc",
             ref="README.md:27"),
        Fact("uf_gym registers each XArm6*-v3 id on import, with entry_point uf_gym.envs:XArm6{task}Env and "
             "max_episode_steps 50, or 100 for the Stack task", source="upstream_code",
             ref=f"{REGISTRATION}:13-20"),
        Fact("The same registration loop also creates the XArm7*-v3 ids, with entry_point "
             "uf_gym.envs:XArm7{task}Env and the same 50/100-step limit", source="upstream_code",
             ref=f"{REGISTRATION}:24-31"),
        Fact("XArm6Reach-v3 is registered on the sparse/ee iteration: the loop visits sparse before dense and ee "
             "before joints, and those two choices add no suffix to the id", source="upstream_code",
             ref=f"{REGISTRATION}:8-13"),
        Fact("XArm6ReachEnv is the entry class of XArm6Reach-v3", source="upstream_code", ref=f"{TASKS6}:167"),
        Fact("XArm6ReachEnv builds a PyBullet simulation, creates an XArm6 with block_gripper=True at base "
             "position [-0.5, 0.0, 0.0], and attaches a Reach task that uses the robot's end-effector position",
             source="upstream_code", ref=f"{TASKS6}:201-203"),
        Fact("With control_type 'ee' the XArm6 action has three arm dimensions, and the gripper adds one unless "
             "block_gripper is true; the action space is Box(-1.0, 1.0, shape=(n_action,), dtype=np.float32)",
             source="upstream_code", ref=f"{ROBOT6}:32-34"),
        Fact("set_action clips every action to the action space before using it", source="upstream_code",
             ref=f"{ROBOT6}:56"),
        Fact("An end-effector action is scaled by 0.05 m per unit before inverse kinematics", source="upstream_code",
             ref=f"{ROBOT6}:85"),
        Fact("The target end-effector height is clipped at z=0", source="upstream_code", ref=f"{ROBOT6}:90"),
        Fact("With the gripper blocked, the neutral pose is the six arm angles 0.0, -1.103210210442149, "
             "-0.5245520784266224, 0.0, 1.62760333106346, 0.0 rad and the end-effector is link 6",
             source="upstream_code", ref=f"{ROBOT6}:46-47"),
        Fact("XArm6.reset sets the arm to its neutral joint values", source="upstream_code",
             ref=f"{ROBOT6}:125-127"),
        Fact("get_obs returns the end-effector position and velocity, plus the finger width when the gripper is "
             "not blocked", source="upstream_code", ref=f"{ROBOT6}:113-123"),
        Fact("get_ee_position and get_ee_velocity return the link position and velocity of ee_link",
             source="upstream_code", ref=f"{ROBOT6}:138-143"),
        Fact("The test script creates XArm6Reach-v3 with gymnasium.make and drives it through reset, step, render "
             "and close", source="upstream_code", ref="test_xarm6_reach.py:24-40"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: determinism and lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:XArm6Reach-v3",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake samples its placeholder goal from random.Random(seed) and is otherwise deterministic, "
                     "so one seed and one action sequence repeat a state hash; the upstream environment's own "
                     "seeding and PyBullet determinism were not run or compared",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the checked fake backend is an analytic kinematic stand-in: it has no rigid-body dynamics, contacts, "
            "friction or actuator model; the upstream environment builds a PyBullet simulation "
            "(uf_gym/envs/uf_tasks/xarm6_tasks.py:201) whose dynamics the fake does not reproduce",
            "timestep_ms is 0: the fake advances one discrete transition per tick and neither the clone nor the fake "
            "declares the PyBullet physics timestep, so no simulated duration is claimed",
            "no wall-clock pacing: realtime_factor 0, so ticks are not wall-clock seconds and no timing model is "
            "claimed",
            "the observation is a flat placeholder vector (end-effector position, velocity and goal), not the "
            "upstream observation structure: the upstream class inherits its observation space from panda-gym's "
            "RobotTaskEnv, which is not in the clone and was not imported",
            "the reward, the goal range and the success radius are placeholders; the upstream Reach reward is "
            "computed by panda-gym, which is not in the clone, so no reward semantics are claimed",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "no physical xArm device is modelled and nothing in this package was validated against hardware",
        ],
    }
