"""OpenMHS driver for gh.ian-chuang/manipulator-mujoco: the Aubo i5 + AG95 Gymnasium environment.

The card lists two Gymnasium entry symbols (``manipulator_mujoco.envs:AuboI5Env`` and
``manipulator_mujoco.envs:UR5eEnv``).  This package serves the first, ``AuboI5Env``, because the card's model
entries are the AG95 assets and this environment is the one that composes the Aubo i5 arm with the AG95 gripper
(``manipulator_mujoco/envs/aubo_i5_env.py:44-51``).  ``UR5eEnv`` is named in ``facts.md`` and was not implemented
(one device per package).

A ``GymnasiumDriver`` is configuration only: ``env_id`` names the registered environment and the bridge derives
``cap.world.step.v1`` (``{ticks, action}`` with ``action.values`` bounded by the environment's action space),
``cap.world.reset.v1`` (``{seed, options}``) and ``cap.world.seed.v1`` (``{seed}``) from the environment's spaces
and methods.  The device is a simulation (``mode = "simulated"``); it has no hardware backend and no native stop,
so the runtime's software e-stop latch is the only stop path.  The risk is R1, not R0: the capability advances a
simulated robot, which the safety spec lists as simulation stepping (MHS-004 section 2.1).

The upstream environment imports ``mujoco``, ``dm_control``, ``numpy`` and ``gymnasium``
(``requirements.txt:1-4``); ``mujoco``, ``dm_control`` and ``gymnasium`` are not installed where the acceptance gate
runs, the gate never installs the upstream package, and package code never imports the clone.  The ``fake`` backend
is therefore this package's pure Python stand-in (``fake.py``) for the upstream class: it mirrors the public
``reset``, ``step``, ``render`` and ``close`` methods and the two spaces, keeps a tick counter and returns the same
all-zero observation that ``_get_obs`` returns.  It integrates no rigid-body, contact, tendon or actuator dynamics,
so its fidelity contract is F0, not the F1 the upstream MuJoCo model would justify.  The ``sim`` backend
(``gymnasium.make(env_id)``, opened by ``GymnasiumDriver.open_native``) needs the upstream package and was not run.

Every Fact cites a line of the clone at commit f2d7d776a74034387e825dec6a13a91b1e1f493e.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "manipulator_mujoco/envs/aubo_i5_env.py"
INIT = "manipulator_mujoco/__init__.py"
ARENA = "manipulator_mujoco/arenas/standard.py"
AUBO = "manipulator_mujoco/assets/robots/aubo_i5/aubo_i5.xml"
AG95 = "manipulator_mujoco/assets/robots/ag95/ag95.xml"
AG95_SCENE = "manipulator_mujoco/assets/robots/ag95/scene.xml"
OSC = "manipulator_mujoco/controllers/operational_space_controller.py"
EFFORT = "manipulator_mujoco/controllers/joint_effort_controller.py"


class AuboI5(GymnasiumDriver):
    device_id = "aubo_i5"
    env_id = "manipulator_mujoco/AuboI5Env-v0"
    native = "manipulator_mujoco.envs:AuboI5Env"
    backends = {"fake": ".fake:FakeAuboI5Env"}
    risk = "R1"
    display_name = "manipulator-mujoco Aubo i5 + AG95 (Gymnasium)"
    vendor, model = "ian-chuang", "Aubo i5 with AG95 gripper in MuJoCo"
    tags = ["aubo-i5", "ag95", "manipulation", "mujoco", "gymnasium", "simulation", "reinforcement-learning"]
    facts = [
        Fact("AuboI5Env is declared as a gymnasium.Env subclass", source="upstream_code", ref=f"{ENV}:13"),
        Fact("AuboI5Env is registered as manipulator_mujoco/AuboI5Env-v0 with entry point "
             "manipulator_mujoco.envs:AuboI5Env", source="upstream_code", ref=f"{INIT}:4-10"),
        Fact("The second environment of the package is registered as manipulator_mujoco/UR5eEnv-v0 with entry "
             "point manipulator_mujoco.envs:UR5eEnv", source="upstream_code", ref=f"{INIT}:12-18"),
        Fact("The observation space is a Box of shape (6,) with -inf and +inf float64 bounds", source="upstream_code",
             ref=f"{ENV}:22-24"),
        Fact("The action space is a Box of shape (6,) with every element bounded by -0.1 and 0.1 (float64)",
             source="upstream_code", ref=f"{ENV}:27-29"),
        Fact("The environment builds a StandardArena, a mocap Target, an AuboI5 arm, an AG95 gripper attached to the "
             "arm and a box with 0.02 m half-extents attached as a free body, then creates the physics",
             source="upstream_code", ref=f"{ENV}:39-67"),
        Fact("AuboI5Env hands the OSC min_effort -150.0, max_effort 150.0, kp 300, ko 300, kv 30, vmax_xyz 1.0 and "
             "vmax_abg 2.0", source="upstream_code", ref=f"{ENV}:70-81"),
        Fact("The operational-space controller computes the task-space command and adds gravity compensation before "
             "passing the joint effort to the effort controller", source="upstream_code", ref=f"{OSC}:91-103"),
        Fact("The joint effort controller clips every commanded effort to [min_effort, max_effort] and writes it to "
             "the joints' qfrc_applied", source="upstream_code", ref=f"{EFFORT}:28-32"),
        Fact("The arena sets the physics timestep to 0.002 s on the MJCF option", source="upstream_code",
             ref=f"{ARENA}:7"),
        Fact("The environment stores the physics model's opt.timestep as its own step interval", source="upstream_code",
             ref=f"{ENV}:84"),
        Fact("The Aubo i5 model bounds each of its six joints to -3.04 to 3.04 rad", source="upstream_code",
             ref=f"{AUBO}:60-101"),
        Fact("The AG95 model gives its joints and the fingers actuator a joint range and ctrlrange of 0 to 0.943 and "
             "a forcerange of -5 to 5", source="upstream_code", ref=f"{AG95}:6-13"),
        Fact("The AG95 fingers_actuator is a general actuator driven by the split tendon of the two outer knuckle "
             "joints", source="upstream_code", ref=f"{AG95}:132-148"),
        Fact("The ag95/scene.xml file includes ag95.xml and adds a free box with 0.015 m half-extents tied to an "
             "anchor by a spatial tendon limited to 0 to 0.02 m", source="upstream_code",
             ref=f"{AG95_SCENE}:6-40"),
        Fact("reset(seed, options) calls super().reset(seed=seed), sets the six arm joints to the qpos "
             "[0, 0, 1.5707, 0, 1.5707, 0], places the mocap target at [0.5, 0, 0.04] with quaternion [0, 0, 0, 1] "
             "and returns the observation and the info dict from _get_info()", source="upstream_code",
             ref=f"{ENV}:96-109"),
        Fact("_get_obs returns np.zeros(6) and _get_info returns an empty dict", source="upstream_code",
             ref=f"{ENV}:88-94"),
        Fact("step(action) does not read its action argument: it takes the current mocap target pose, runs the OSC "
             "toward it and steps the physics once", source="upstream_code", ref=f"{ENV}:111-121"),
        Fact("step returns the observation, reward 0, terminated False, truncated False and the info dict",
             source="upstream_code", ref=f"{ENV}:127-133"),
        Fact("Neither registered environment id sets max_episode_steps; the two register calls pass only id and "
             "entry_point and both max_episode_steps lines are commented out", source="upstream_code",
             ref=f"{INIT}:4-18"),
        Fact("render returns physics.render() when render_mode is rgb_array, and close closes the viewer if one was "
             "launched", source="upstream_code", ref=f"{ENV}:135-178"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the backend as deployed (spec 05-fidelity section 2).  The upstream model would be
    #: F1 with MuJoCo rigid-body dynamics, but the delivered fake is a kinematic stand-in with no dynamics, so the
    #: package declares F0 and discloses the difference in the gaps.
    fidelity = {
        "engine": "gymnasium:manipulator_mujoco/AuboI5Env-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed=...) and cap.world.seed.v1 accept a non-negative seed and the bridge records it; "
                     "the fake is deterministic (the observation is the constant zeros(6) the upstream _get_obs "
                     "returns) and no random draw changes it, so two runs with the same seed and commands repeat",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a pure Python stand-in for the MuJoCo environment: it mirrors the public env API "
            "and the two spaces, keeps a tick counter and returns the observation the upstream _get_obs returns; "
            "it integrates no rigid-body, contact, tendon or actuator dynamics and does not run the OSC",
            "the upstream step ignores its action argument, so the published action space changes no modelled "
            "state in this build; the bridge still enforces every action bound before calling the environment",
            "the observation is the constant zeros(6) of _get_obs, so joint positions, velocities, contacts, "
            "render frames and the mocap pose are not published; the observation space is unbounded (-inf/+inf)",
            "no wall-clock pacing: realtime_factor 0, the 2 ms timestep is the upstream arena setting and the fake "
            "does not integrate simulated time, only the bridge tick count advances",
            "no rendering: the upstream rgb_array path calls physics.render(), the fake renders nothing",
            "MuJoCo, dm_control and the upstream package were not installed where the gate ran, so the fake was "
            "never compared with the upstream environment; the sim backend (gymnasium.make) was not run",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state pair",
            "no physical Aubo i5 or AG95 is modelled and nothing was validated against hardware",
        ],
    }
