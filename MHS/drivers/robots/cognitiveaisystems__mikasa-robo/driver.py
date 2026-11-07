"""OpenMHS driver for gh.cognitiveaisystems/mikasa-robo: the BunchOfColors3-v0 environment (Gymnasium family).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the contract from the
environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the documented Panda ``pd_ee_delta_pose``
action (seven normalized values in ``[-1, 1]``), ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend and no e-stop path to a
machine.

The upstream class inherits ManiSkill's ``BaseEnv`` and imports ``sapien``, ``torch`` and ``mani_skill``
(bunch_of_colors.py:4-15); those packages are not importable where the gate runs (pyproject.toml:10, :26-32), and
package code never imports the clone.  The ``fake`` backend is therefore the package's own pure Python kinematic
stand-in (fake.py).  A backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)``
(GymnasiumDriver.open_native); that path needs the upstream stack and was not run here.

``env_kwargs`` selects the documented ``pd_ee_delta_pose`` action and the ``state`` observation mode so the contract
the bridge derives is the one documented in docs/source/observation_space.rst.  The ``fidelity`` attribute is the
complete fidelity contract of the model as deployed (spec 05-fidelity FID-002): the fake is kinematic/analytic (F0),
with no rigid-body dynamics, robot, scene, sensors or task rewards.  Every constant and rule cites a line of the clone
at the pinned commit (509b875f3d207c287497c0a897661062de928bb0).  This package is model-authored and unreviewed: it is
checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "mikasa_robo_suite/rl/memory_envs/bunch_of_colors.py"
DOC = "docs/source/observation_space.rst"


class BunchOfColors3(GymnasiumDriver):
    device_id = "mikasa-bunch-of-colors-3"
    env_id = "BunchOfColors3-v0"
    native = "mikasa_robo_suite.rl.memory_envs.bunch_of_colors:BunchOfColors3Env"
    backends = {"fake": ".fake:FakeBunchOfColors3Env"}
    env_kwargs = {"control_mode": "pd_ee_delta_pose", "obs_mode": "state"}
    display_name = "MIKASA-Robo BunchOfColors3-v0 (memory manipulation simulation)"
    vendor, model = "CognitiveAISystems", "mikasa-robo-suite 1.0.0"
    tags = ["mikasa-robo", "memory-task", "manipulation", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("BunchOfColors3-v0 is registered by @register_env with max_episode_steps=120",
             source="upstream_code", ref=f"{ENV}:381"),
        Fact("The abstract BunchOfColorsEnv defaults SEQUENCE_LENGTH to 5", source="upstream_code",
             ref=f"{ENV}:25"),
        Fact("BunchOfColors3Env sets SEQUENCE_LENGTH = 3", source="upstream_code", ref=f"{ENV}:383"),
        Fact("The environment supports the panda and panda_wristcam robots and defines nine colors",
             source="upstream_code", ref=f"{ENV}:19-20"),
        Fact("An episode draws SEQUENCE_LENGTH unique colors from the nine with the episode RNG",
             source="upstream_code", ref=f"{ENV}:102-105"),
        Fact("The robot qpos is a nine-element vector and its last two entries are handled as the gripper",
             source="upstream_code", ref=f"{ENV}:184-188"),
        Fact("In state mode the observation extras are tcp_pose, obj_to_goal_pos, oracle_info and, for each cube in "
             "the scene, its pose and its touch/sequence/next-target flags", source="upstream_code",
             ref=f"{ENV}:324-336"),
        Fact("The environment's step delegates to BaseEnv.step and returns its five values unchanged",
             source="upstream_code", ref=f"{ENV}:339-342"),
        Fact("The dense reward combines reaching, 0.5*static, correct-touch and wrong-touch terms, is scaled by "
             "active_phase and set to 100 on success", source="upstream_code", ref=f"{ENV}:346-361"),
        Fact("compute_normalized_dense_reward divides the dense reward by 100", source="upstream_code",
             ref=f"{ENV}:376-378"),
        Fact("The default sensors are a 128x128 base_camera and a 512x512 render_camera", source="upstream_code",
             ref=f"{ENV}:61-69"),
        Fact("The environment's SimConfig sets only GPU memory capacities, not a physics or control timestep",
             source="upstream_code", ref=f"{ENV}:53-59"),
        Fact("ManiSkill's BaseEnv is imported from mani_skill.envs.sapien_env, so reset, the spaces and close are "
             "inherited outside the clone", source="upstream_code", ref=f"{ENV}:6"),
        Fact("The clone documents the Panda pd_ee_delta_pose action as seven values, each in [-1, 1]: xyz, rpy and "
             "the gripper command", source="vendor_doc", ref=f"{DOC}:147-172"),
        Fact("The documented proprioception is seven values: absolute TCP xyz with no finite clamp, roll/pitch/yaw "
             "and the gripper opening in [0.0, 0.08] m", source="vendor_doc", ref=f"{DOC}:107-131"),
        Fact("The clone pins gymnasium 0.29.1, mani_skill 3.0.0b15, numpy 1.23.5 and torch 2.2.1 and requires "
             "Python >=3.9,<3.12", source="upstream_code", ref="pyproject.toml:10-32"),
    ]
    safe_state = ("the simulation stops advancing: cap.world.step.v1 and cap.world.reset.v1 are refused after an "
                  "e-stop until mhs.safety.reset clears the latch, and the recorded world state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The fake is analytic: it
    #: integrates the documented action mapping but models no rigid body, robot, scene, sensor or reward.
    fidelity = {
        "engine": "gymnasium:BunchOfColors3-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) seeds the fake's Python random stream for the initial pose jitter and the kinematic "
                     "integration is deterministic, so one seed repeats a trajectory of this fake; upstream draws "
                     "from ManiSkill's episode RNG, so a seed does not give the same trajectory on the two",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no rigid-body dynamics, contacts, friction, actuator, sensor or noise model: the fake integrates the "
            "seven documented action values by a fixed toy kinematic mapping and makes no physics claim",
            "the Panda robot, the nine cubes, the table scene, the camera sensors and the ManiSkill task and reward "
            "logic are not modelled; the fake returns reward 0.0 and never terminates an episode, it only truncates "
            "at the registered 120-step limit",
            "the real observation is ManiSkill's state tensor plus the extra keys of bunch_of_colors.py:324-336; its "
            "exact size depends on the robot and sensors and is not stated in the clone.  The fake returns a "
            "seven-value proprio-like stand-in (absolute xyz, rpy and gripper opening), not that array",
            "timestep_ms is 0: the clone states no physics or control timestep (SimConfig at bunch_of_colors.py:53-59 "
            "sets only GPU memory capacities), so the fake advances one step per tick and makes no wall-clock claim",
            "the fake's initial pose and joint jitter are marked placeholder test data and were never compared with "
            "the upstream environment; the upstream stack (mani_skill 3.0.0b15, torch 2.2.1) is not importable where "
            "the gate runs (pyproject.toml:10, :26-32)",
        ],
    }
