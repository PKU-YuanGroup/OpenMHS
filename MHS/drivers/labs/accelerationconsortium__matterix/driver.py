"""OpenMHS driver for gh.accelerationconsortium/matterix: the registered Beakers Gymnasium environment.

Matterix is an Isaac Sim/Isaac Lab simulation framework for chemistry-lab digital twins (README.md:13), not a hardware
transport.  The card is a Gymnasium family card and the entry symbol is ``matterix.envs:MatterixBaseEnv``
(matterix_base_env.py:48): the class is a Gymnasium environment, so a :class:`GymnasiumDriver` is the right shape.  It
is configuration only: ``cap.world.step.v1`` takes ``{ticks, action}`` with the action derived from the environment's
Box action space, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.

This package serves ``Matterix-Test-Beakers-Franka-v1`` (test_dev_tasks/__init__.py:15-22), the first of the four test
tasks the card names.  The upstream environment needs Isaac Sim 5.0, Isaac Lab 3.0 and a config object; the project
always builds that config with ``parse_env_cfg`` before ``gym.make(task, cfg=...)`` (scripts/random_agent.py:60-64).
The gate cannot import any of that, so the ``fake`` backend is this package's pure Python kinematic stand-in
(fake.py), and the ``sim`` backend path (GymnasiumDriver.open_native) was not run.  The device is simulated at R0:
there is no hardware backend, no native stop and no operator-required limit.

The ``fidelity`` attribute is the complete contract of the model as deployed (spec 05-fidelity FID-002): engine,
level, determinism, timestep, pacing, reset and gaps.  Every constant and rule cites a line of the clone at the pinned
commit 687e2cef294f00e86dbb32173fefd93b50e5107f.  This package is model-authored and unreviewed: it is checked on the
fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "source/matterix/matterix/envs/matterix_base_env.py"
CFG = "source/matterix/matterix/envs/matterix_base_env_cfg.py"
TASKS = "source/matterix_tasks/matterix_tasks/test_dev_tasks/__init__.py"
BEAKERS = "source/matterix_tasks/matterix_tasks/test_dev_tasks/test_franka_beakers.py"
OBSERVATIONS = "source/matterix/matterix/envs/mdp/observations.py"


class MatterixBeakers(GymnasiumDriver):
    device_id = "matterix-beakers"
    env_id = "Matterix-Test-Beakers-Franka-v1"
    native = "matterix.envs:MatterixBaseEnv"
    backends = {"fake": ".fake:FakeMatterixEnv"}
    display_name = "Matterix Test Beakers Franka (Isaac Lab simulation)"
    vendor, model = "The Matterix Project Developers", "Matterix-Test-Beakers-Franka-v1"
    tags = ["matterix", "isaac-lab", "isaac-sim", "robotics", "chemistry", "simulation", "gymnasium"]
    facts = [
        Fact("Matterix describes itself as a multi-scale, GPU-accelerated robotic simulation framework for digital "
             "twins of chemistry labs", source="vendor_doc", ref="README.md:13"),
        Fact("The documented setup installs isaaclab[isaacsim,all]==3.0.0b2.post1, so Isaac Sim and Isaac Lab are "
             "external dependencies of the simulator stack", source="vendor_doc", ref="README.md:39"),
        Fact("The project builds the environment configuration with parse_env_cfg and then calls "
             "gym.make(task, cfg=env_cfg), so a bare gym.make(env_id) has no cfg", source="upstream_code",
             ref="scripts/random_agent.py:60-64"),
        Fact("MatterixBaseEnv derives from ManagerBasedEnv and gym.Env", source="upstream_code", ref=f"{ENV}:48"),
        Fact("The environment is vectorized: is_vector_env is True", source="upstream_code", ref=f"{ENV}:78"),
        Fact("step applies the action, advances cfg.decimation physics steps, updates the semantic manager, computes "
             "terminations and rewards, resets terminated environments and returns observations, rewards, terminated, "
             "truncated and extras", source="upstream_code", ref=f"{ENV}:215-317"),
        Fact("reset accepts seed, env_ids and options, sets the seed when given, resets the requested environments "
             "and returns the observations and extras", source="upstream_code", ref=f"{ENV}:501-556"),
        Fact("The observation space is a gym.spaces.Dict of Box spaces with infinite bounds built from the observation "
             "terms, the action space is Box(low=-inf, high=inf, shape=(action_dim,)), and both are batched for "
             "num_envs", source="upstream_code", ref=f"{ENV}:415-441"),
        Fact("The maximum episode length is ceil(episode_length_s / step_dt) environment steps", source="upstream_code",
             ref=f"{ENV}:161-163"),
        Fact("The default control decimation is 5 action updates per policy step", source="upstream_code",
             ref=f"{CFG}:95-96"),
        Fact("The default physics timestep is 1/60 s", source="upstream_code", ref=f"{CFG}:244"),
        Fact("The default episode_length_s is 30.0 s", source="upstream_code", ref=f"{CFG}:165"),
        Fact("Matterix-Test-Beakers-Franka-v1 is registered with entry point matterix.envs:MatterixBaseEnv",
             source="upstream_code", ref=f"{TASKS}:15-22"),
        Fact("The Beakers test task declares a non-concatenated policy observation group with the terms ee_pos_robot "
             "and ee_pos_robot2, both computed by mdp.ee_env_pos", source="upstream_code", ref=f"{BEAKERS}:29-34"),
        Fact("ee_env_pos returns the end-effector position in the environment frame as three coordinates",
             source="upstream_code", ref=f"{OBSERVATIONS}:49-53"),
        Fact("The Beakers test task configures two Franka arms, robot (joint position control) and robot2 "
             "(differential IK control)", source="upstream_code", ref=f"{BEAKERS}:57-62"),
    ]
    safe_state = ("the simulation stops advancing: the runtime latches the e-stop and no step or reset is accepted "
                  "until mhs.safety.reset clears it; the last observation and tick stay readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: determinism, clock and reset defaults from the fake; they are written out so the whole contract reads in one
    #: place.  The upstream model is F1: PhysX rigid-body dynamics with contacts, without a validated device.
    fidelity = {
        "engine": "matterix:isaaclab",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) sets the Isaac Lab seed before the scene reset (matterix_base_env.py:531-533), so "
                     "a seeded run repeats on the same installation; the fake uses Python's random.Random and was "
                     "never compared with the upstream environment, and no exact bit-for-bit claim is made",
        },
        "timestep_ms": 1000.0 / 60.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a kinematic stand-in: it integrates a placeholder joint offset from the action and "
            "reports the two 3-vector end-effector positions; it loads no Isaac Sim or Isaac Lab, no PhysX scene, no "
            "Franka asset, beaker or table, and models no contacts, friction, gravity, actuators or sensors",
            "one cap.world.step.v1 tick is one Matterix env.step (one control update), not one physics step: the "
            "default decimation is 5 and the default physics timestep is 1/60 s, so a tick advances 5/60 s = 83.33 ms "
            "while timestep_ms names the 1/60 s physics step (spec FID-015)",
            "no wall-clock pacing: realtime_factor 0, the simulation advances only when step or reset is called",
            "no physical device is modelled and nothing was validated against one; the README's real-world "
            "deployment claim has no hardware transport in this repository",
            "the environment is vectorized upstream (num_envs defaults to 1); the fake serves one environment and "
            "its two spaces carry the batch dimension of one",
            "the upstream environment needs Isaac Sim 5.0, Isaac Lab 3.0 and a cfg built by parse_env_cfg "
            "(README.md:39, scripts/random_agent.py:60-64); it could not be imported where the gate ran, so the fake "
            "was never compared with it",
            "seeded determinism is claimed for the fake only; the upstream RNG and PhysX were not run and no "
            "trajectory comparison was made",
            "snapshot and restore are not offered: MatterixBaseEnv defines no get_state or set_state method",
        ],
    }
