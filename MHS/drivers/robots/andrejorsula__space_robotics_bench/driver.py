"""OpenMHS driver for gh.andrejorsula/space_robotics_bench: the ``_manipulation`` Gymnasium template.

Space Robotics Bench registers its environments with Gymnasium under the ``srb`` namespace
(``srb/utils/registry.py:21-27``); the barebones fixed-base manipulation template is registered from
``srb/tasks/manipulation/_manipulation/__init__.py:6-17`` with ``Task`` as its entry point, and the docs list it as
``_manipulation`` (``docs/src/getting_started/basic_usage.md:108``, used by the CLI at
``docs/src/config/robot.md:80``).  This driver names the registered id ``srb/_manipulation`` and the template class
``srb.tasks.manipulation._manipulation.task:Task`` (``srb/tasks/manipulation/_manipulation/task.py:53``).

A GymnasiumDriver is configuration only: the bridge derives the whole ``cap.world.*`` contract from the environment's
spaces.  The upstream action space is a Box with low -1.0 and high 1.0 per element
(``srb/core/env/common/base/direct/impl.py:353-357``); the observation is a Dict with the groups ``state``,
``state_dyn``, ``proprio`` and ``proprio_dyn`` (``srb/tasks/manipulation/_manipulation/task.py:235-253``).
``cap.world.step.v1`` takes ``{ticks, action: {values: [...]}}``, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is simulated R0: no hardware backend, no e-stop path to a machine and no
operator-required limit.

The upstream simulation needs Python 3.11, NVIDIA Omniverse and Isaac Sim (``srb/__main__.py:37-40``,
``docs/src/README.md:7``) and is not installed where the gate runs, and package code never imports the clone.  The
``fake`` backend is therefore this package's pure Python kinematic stand-in (fake.py); no backend named ``sim`` is
listed, so only the fake is exercised here.  The ``fidelity`` contract describes that deployed fake as F0 and does not
claim the upstream Isaac Sim/PhysX fidelity.

The package is model-authored and unreviewed: it is checked on the fake backend only, and no simulator or hardware run
is claimed.  Every Fact cites the clone at the pinned commit 7528ff81f1ac0b34ba259b1ae150fdb4f6a90b5e.
"""

from mhs.driver import Fact, GymnasiumDriver

TASK = "srb/tasks/manipulation/_manipulation/task.py"
DIRECT = "srb/core/env/common/base/direct/impl.py"
MANIPULATION_ENV = "srb/core/env/manipulation/env.py"
ENV_CFG = "srb/core/env/common/base/env_cfg.py"
FRANKA = "srb/assets/robot/manipulation/franka.py"


class SpaceRoboticsBenchManipulation(GymnasiumDriver):
    device_id = "srb-manipulation"
    env_id = "srb/_manipulation"
    native = "srb.tasks.manipulation._manipulation.task:Task"
    backends = {"fake": ".fake:FakeSpaceRoboticsBenchEnv"}
    action_space_ref = f"{DIRECT}:353-357"
    display_name = "Space Robotics Bench _manipulation template (Isaac Sim Gymnasium environment)"
    vendor, model = "Andrej Orsula", "Space Robotics Bench _manipulation template"
    tags = ["space-robotics", "isaac-sim", "isaac-lab", "gymnasium", "manipulation", "simulation",
            "reinforcement-learning"]
    facts = [
        Fact("Space Robotics Bench is a collection of environments and tasks for robotics research in space, "
             "providing a unified framework", source="vendor_doc", ref="README.md:16"),
        Fact("The simulation runs on NVIDIA Isaac Sim", source="vendor_doc", ref="docs/src/README.md:7"),
        Fact("The CLI refuses to run without the omni module, requiring an environment with NVIDIA Omniverse and "
             "Isaac Sim installed", source="upstream_code", ref="srb/__main__.py:37-40"),
        Fact("The CLI creates an environment with gymnasium.make(id=env_id, cfg=env_cfg, render_mode=...)",
             source="upstream_code", ref="srb/__main__.py:208-210"),
        Fact("register_srb_tasks registers each task with gymnasium.register under the default namespace srb as "
             "f'{namespace}/{id}'", source="upstream_code", ref="srb/utils/registry.py:21-27"),
        Fact("The manipulation template registers its package name and a _visual variant with Task as "
             "default_entry_point and TaskCfg as default_task_cfg", source="upstream_code",
             ref="srb/tasks/manipulation/_manipulation/__init__.py:6-17"),
        Fact("The docs list _manipulation as a barebones template whose entry point is Task(ManipulationEnv) and "
             "whose config is TaskCfg(ManipulationEnvCfg)", source="vendor_doc",
             ref="docs/src/getting_started/basic_usage.md:108"),
        Fact("The docs invoke the template with 'srb agent rand -e _manipulation ...'", source="vendor_doc",
             ref="docs/src/config/robot.md:80"),
        Fact("The template environment class is Task(ManipulationEnv), constructed from a TaskCfg",
             source="upstream_code", ref=f"{TASK}:53-57"),
        Fact("TaskCfg sets episode_length_s to 10.0 and is_finite_horizon to False", source="upstream_code",
             ref=f"{TASK}:41-42"),
        Fact("truncate_episodes defaults to True", source="upstream_code", ref=f"{ENV_CFG}:132"),
        Fact("The manipulation env runs physics at env_rate 1/150 s and the agent at agent_rate 1/50 s",
             source="upstream_code", ref=f"{MANIPULATION_ENV}:79-80"),
        Fact("The cfg sets decimation to floor(agent_rate / env_rate) and sim.dt to env_rate",
             source="upstream_code", ref=f"{ENV_CFG}:172-173"),
        Fact("The default robot of ManipulationEnvCfg is Franka", source="upstream_code",
             ref=f"{MANIPULATION_ENV}:68"),
        Fact("The default Franka action group is a differential inverse-kinematics relative pose command with "
             "command_type pose, use_relative_mode True and scale 0.1", source="upstream_code",
             ref=f"{FRANKA}:91-106"),
        Fact("The default Franka action addresses joints panda_joint1 through panda_joint7", source="upstream_code",
             ref=f"{FRANKA}:95"),
        Fact("The action space is a Box with low -1.0 and high 1.0 per element, shaped by "
             "action_manager.total_action_dim", source="upstream_code", ref=f"{DIRECT}:353-357"),
        Fact("The observation is a Dict with the groups state, state_dyn, proprio and proprio_dyn",
             source="upstream_code", ref=f"{TASK}:235-253"),
        Fact("The proprio group carries the end-effector position and its 6D rotation, and proprio_dyn carries the "
             "normalized robot and end-effector joint positions", source="upstream_code", ref=f"{TASK}:245-252"),
        Fact("The end-effector rotation is converted to a 6D representation with rotmat_to_rot6d",
             source="upstream_code", ref=f"{TASK}:173-174"),
        Fact("The reward sums four penalty terms: action rate, joint torque, joint acceleration and undesired robot "
             "contacts", source="upstream_code", ref=f"{TASK}:189-221"),
        Fact("The action-rate penalty is -0.5 times the mean squared difference between the current and previous "
             "action", source="upstream_code", ref=f"{TASK}:192-196"),
        Fact("There is no termination condition; the episode is truncated when the episode length reaches "
             "max_episode_length if truncate_episodes is true", source="upstream_code", ref=f"{TASK}:226-233"),
        Fact("The reset randomizes the robot joints with a uniform position offset of +-5 degrees and a zero "
             "velocity range", source="upstream_code", ref=f"{MANIPULATION_ENV}:54-61"),
        Fact("DirectEnv imports DirectRLEnv from isaaclab.envs, so the Gymnasium reset and step implementations "
             "come from outside the clone", source="upstream_code", ref=f"{DIRECT}:7"),
        Fact("DirectEnv.close deletes the action manager and closes the Isaac Lab environment",
             source="upstream_code", ref=f"{DIRECT}:136-141"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  It describes this package's
    #: kinematic fake, not Isaac Sim's PhysX: F0 claims no dynamics, and every gap names what is missing.
    fidelity = {
        "engine": "isaac:srb/_manipulation (kinematic fake stand-in)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake reseeds Python's random.Random from reset(seed) or cap.world.seed.v1 and its "
                     "kinematic update is deterministic, so one seed repeats a trajectory; the upstream seed is a "
                     "scenario seed consumed by Isaac Sim, and the fake was not compared with it",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic F0 stand-in with no rigid-body dynamics, contacts, friction, actuator, sensor or noise model; "
            "only the action-rate reward term is reproduced, so its trajectories are not Isaac Sim's",
            "the upstream simulation path (gymnasium.make('srb/_manipulation')) needs Python 3.11, NVIDIA Omniverse "
            "and Isaac Sim (srb/__main__.py:37-40) and was never opened here; only the package fake backend is "
            "exercised",
            "the fake returns only the proprio and proprio_dyn observation groups, each one vector of its members in "
            "sorted name order as the upstream concatenates them (srb/core/env/common/base/direct/impl.py:543-556): "
            "a constant 3D position and a constant 6D rotation, and a two-joint hand vector before a seven-joint arm "
            "vector; the upstream observation also has the state and state_dyn contact-force groups, and all fake "
            "observation values are placeholder test data",
            "the fake action Box has the seven elements of action_manager.total_action_dim in the default "
            "configuration (the Franka's six relative pose values and its hand's binary gripper value), while another "
            "robot, tool or action group changes the upstream width at run time; the fake adds the pose values to its "
            "arm joints without inverse kinematics and sets the hand joints to the gripper's close or open command at "
            "once, without the hand's actuator",
            "the fake truncates at 500 agent steps (10 s at 50 Hz), an approximation of the max_episode_length Isaac "
            "Lab computes from the cfg; no termination condition is modelled",
            "no wall-clock pacing: realtime_factor 0 and clock lockstep, so ticks advance simulated time by "
            "timestep_ms only",
            "snapshots and restore are not offered: the environment exposes no get_state/set_state",
            "the fake was never compared with an Isaac Sim run, and no simulator or hardware evidence exists",
        ],
    }
