"""OpenMHS driver for gh.mingfeisun/deepmimic_mujoco: the HumanoidDeepMimic-v0 gym environment.

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the contract from
the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{values}`` of the
three chest motors bounded by the model's control range, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path
to a machine and no operator-required limit.

The upstream package is a legacy ``gym`` / mujoco-py environment.  Its constructor hard-codes the asset path of one
host (``humanoid_deepmimic_env.py:7``), the ``envs`` package imports a module that does not exist
(``envs/__init__.py:2``), and the extrahard module that import names defines only a stub ``FooEnv``
(``humanoid_deepmimic_extrahard_env.py:5``).
Nothing in the clone was installed, imported or run.  The ``fake`` backend is the package's own reduced stand-in
(fake.py); the ``sim`` backend would need gymnasium, mujoco-py and the unreachable asset path, and was not run.

The ``fidelity`` attribute is the fidelity contract of the model as deployed (spec 05-fidelity FID-002): every member
of ``device.schema.json`` that applies to a simulator without a physical counterpart.  This package is model-authored
and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "src/mujoco/humanoid_deepmimic/envs/humanoid_deepmimic_env.py"
MODEL = "src/mujoco/humanoid_deepmimic/envs/asset/humanoid_deepmimic.xml"
INIT = "src/mujoco/humanoid_deepmimic/__init__.py"
ENVS_INIT = "src/mujoco/humanoid_deepmimic/envs/__init__.py"
EXTRA = "src/mujoco/humanoid_deepmimic/envs/humanoid_deepmimic_extrahard_env.py"


class HumanoidDeepMimic(GymnasiumDriver):
    device_id = "humanoid_deepmimic"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    env_id = "HumanoidDeepMimic-v0"
    native = "humanoid_deepmimic.envs:HumanoidDeepMimicEnv"
    backends = {"fake": ".fake:FakeHumanoidDeepMimicEnv"}
    display_name = "DeepMimic humanoid MuJoCo environment (reduced fake)"
    vendor, model = "Mingfei Sun", "HumanoidDeepMimic-v0"
    tags = ["deepmimic", "humanoid", "mujoco", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("HumanoidDeepMimic-v0 is registered with entry point "
             "humanoid_deepmimic.envs:HumanoidDeepMimicEnv", source="upstream_code", ref=f"{INIT}:3-6"),
        Fact("The environment class HumanoidDeepMimicEnv subclasses the legacy gym MujocoEnv and utils.EzPickle",
             source="upstream_code", ref=f"{ENV}:5"),
        Fact("The constructor loads asset/humanoid_deepmimic.xml through the legacy MuJoCo base with frame_skip 5, "
             "using the host-specific absolute path /home/mingfei/Documents/DeepMimic/mujoco/humanoid_deepmimic/"
             "envs/asset/humanoid_deepmimic.xml", source="upstream_code", ref=f"{ENV}:7"),
        Fact("One environment step computes forward reward from the root body's x displacement divided by dt, "
             "subtracts a 0.5*sum(a^2) control cost and a contact cost, and adds a survive reward of 1.0",
             source="upstream_code", ref=f"{ENV}:14-19"),
        Fact("The episode is not done while the state is finite and state[2] is between 0.2 and 1.0",
             source="upstream_code", ref=f"{ENV}:21-23"),
        Fact("The observation concatenates qpos[2:], qvel and cfrc_ext clipped to [-1, 1]",
             source="upstream_code", ref=f"{ENV}:31-36"),
        Fact("The reset model adds uniform(-0.1, 0.1) noise to the initial qpos and normal(0, 0.1) noise to the "
             "initial qvel", source="upstream_code", ref=f"{ENV}:38-42"),
        Fact("The model's simulator timestep is 0.003 s", source="upstream_code", ref=f"{MODEL}:9"),
        Fact("The model declares three chest motors, chest_x, chest_y and chest_z, on the chest ball joint",
             source="upstream_code", ref=f"{MODEL}:123-125"),
        Fact("The model's default motor control range is -0.3 to 0.3", source="upstream_code", ref=f"{MODEL}:7"),
        Fact("The model's root free joint is commented out, so the model has no free root position in qpos",
             source="upstream_code", ref=f"{MODEL}:28-30"),
        Fact("The envs package imports HumanoidDeepMimicExtraHardEnv from the module "
             "humanoid_deepmimic_extrahard_env.envs.humanoid_deepmimic_extrahard_env, which does not exist in the "
             "clone", source="upstream_code", ref=f"{ENVS_INIT}:2"),
        Fact("The extrahard module defines only FooEnv, whose step, reset and render methods do nothing",
             source="upstream_code", ref=f"{EXTRA}:5-15"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the last observation and tick stay readable")
    #: The fidelity contract of the reduced fake as deployed (spec 05-fidelity section 2).
    fidelity = {
        "engine": "gymnasium:HumanoidDeepMimic-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake draws its reset state from Python's random.Random(seed) and its dynamics are "
                     "deterministic, so one seed repeats a fake trajectory; the upstream MuJoCo environment was not "
                     "run and a fake seed does not reproduce it",
        },
        "timestep_ms": 15.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the upstream environment is a legacy gym/mujoco-py environment whose constructor hard-codes one host's "
            "absolute asset path (humanoid_deepmimic_env.py:7) and whose envs package imports a module that does not "
            "exist (envs/__init__.py:2); it was not installed, imported or run",
            "the card's second entry point, HumanoidDeepMimicExtraHardEnv, is not defined: the extrahard module "
            "contains only a stub FooEnv (humanoid_deepmimic_extrahard_env.py:5-15)",
            "the fake is a reduced scalar stand-in, not MuJoCo: no rigid-body dynamics, contacts, qpos/qvel "
            "integration or cfrc_ext; it returns a 9-number observation while the model's own observation "
            "concatenates qpos[2:] (16), qvel (17) and cfrc_ext (48) = 81 numbers (its step state_vector is "
            "18 qpos + 17 qvel = 35)",
            "the fake's action bound is the model's stated motor control range (-0.3 to 0.3) for the three chest "
            "motors, not the legacy gym action space: it refuses actions outside that range instead of simulating a "
            "clamp",
            "the fake terminates only when its reduced height leaves the 0.2 to 1.0 band; it has no MuJoCo contact, "
            "joint-range or non-finite-state failure model, and the upstream step itself truncates nothing",
            "the root free joint is commented out of the model, so the upstream state[2] used by the done check is "
            "not a torso height; the fake's height gate is a surrogate for that check",
            "no snapshot and restore: the environment exposes no get_state/set_state pair",
            "no rendering, viewer, reward from a motion capture clip or video output is offered by the fake",
        ],
    }
