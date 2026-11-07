"""OpenMHS driver for gh.liruiw/fleet-tools: the Franka Panda tool-use simulation environments.

The package is a legacy Gym API benchmark over Drake (README.md:5, env/basedrakeenv.py:23), so the card's
GymnasiumDriver family fits: the bridge derives ``cap.world.step.v1`` from the environment's action space,
``cap.world.reset.v1`` calls ``reset``/``seed`` and ``cap.world.seed.v1`` stores the seed of the next reset.

The environments are not Gymnasium environments and they are not registered as importable package entry points
from this driver: constructing one needs a Hydra ``task_config``, pydrake, torch and the bundled assets.  The
``fake`` backend is therefore the package's own small deterministic stand-in (fake.py) for FrankaDrakeEnv in the
Hammer teleop configuration; the upstream simulator itself (backend ``sim``) is not served by this package and
was never run.  The action bounds the bridge publishes come from that configuration's action_scale (0.04, 0.4);
the default DrakeBaseConfig uses (0.08, 0.6), so a deployment that changes the task config also changes the
envelope (fake.py cites the configuration, RESULT.json notes the restriction).

The device is simulated (R0): it has no hardware backend, no independent stop and no operator-required limit.
This package is model-authored and unreviewed; it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "env/frankadrakeenv.py"
BASE = "env/basedrakeenv.py"
SPACE = "core/utils/utils.py"
CONFIG = "experiments/config/task/DrakeBaseConfig.yaml"
HAMMER = "experiments/config/task/FrankaDrakeHammerEnvTeleop.yaml"


class FleetToolsFranka(GymnasiumDriver):
    device_id = "fleet-tools-franka"
    env_id = "FrankaDrakeEnv-v0"
    native = "env.frankadrakeenv:FrankaDrakeEnv"
    backends = {"fake": ".fake:FakeFrankaDrakeEnv"}
    display_name = "Fleet-Tools Franka Drake simulation"
    vendor, model = "Lirui Wang", "Fleet-Tools FrankaDrakeEnv"
    tags = ["fleet-tools", "franka", "panda", "drake", "manipulation", "simulation", "gym"]
    facts = [
        Fact("The project is a simulation environment benchmark built with the Gym API and Drake simulations "
             "for a Franka Panda", source="upstream_code", ref="README.md:5"),
        Fact("BaseDrakeRobotEnv derives from gym.Env, so every Fleet-Tools environment uses the legacy Gym API",
             source="upstream_code", ref=f"{BASE}:23"),
        Fact("FrankaDrakeEnv derives from BaseDrakeRobotEnv and is constructed from a task_config",
             source="upstream_code", ref=f"{ENV}:24-25"),
        Fact("The action space is PandaTaskSpace6D(task_config.env.action_scale), a 6-element end-effector delta",
             source="upstream_code", ref=f"{ENV}:134"),
        Fact("PandaTaskSpace6D returns a Box of shape [6] with the first three bounds +-trans_scale and the last "
             "three +-rotation_scale", source="upstream_code", ref=f"{SPACE}:372-396"),
        Fact("The Hammer teleop task configuration sets action_scale [0.04, 0.4] and numObservations [9]",
             source="upstream_code", ref=f"{HAMMER}:26-29"),
        Fact("The observation space is Box(low=-1.0, high=1.0) with shape numObservations",
             source="upstream_code", ref=f"{ENV}:139"),
        Fact("DrakeBaseConfig sets numActions to 6 and numObservations to [10, 240, 320]",
             source="upstream_code", ref=f"{CONFIG}:79-80"),
        Fact("DrakeBaseConfig sets the simulation dt to 0.004 s and substep_num to 40",
             source="upstream_code", ref=f"{CONFIG}:63-64"),
        Fact("The environment control period env_dt is sim_dt multiplied by substep_num",
             source="upstream_code", ref=f"{ENV}:71"),
        Fact("step computes the reward with _get_reward and returns the legacy four-tuple obs, reward, done, info",
             source="upstream_code", ref=f"{ENV}:247-250"),
        Fact("The base FrankaDrakeEnv reward is 0", source="upstream_code", ref=f"{ENV}:415-416"),
        Fact("step sets done to sim_done, so the base environment has no separate time limit in step",
             source="upstream_code", ref=f"{ENV}:248"),
        Fact("reset returns the legacy four-tuple obs, reward, done, info", source="upstream_code", ref=f"{ENV}:380"),
        Fact("seed uses gym.utils.seeding.np_random and Drake's RandomGenerator and returns [seed]",
             source="upstream_code", ref=f"{ENV}:141-144"),
        Fact("The environment is registered under the id FrankaDrakeEnv-v0", source="upstream_code",
             ref="env/__init__.py:11"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge would derive
    #: engine, determinism and the clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:FrankaDrakeEnv-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake draws its initial observation from random.Random(seed) and is otherwise "
                     "deterministic; upstream seeds gym's np_random and Drake's RandomGenerator, so one seed does "
                     "not give the same trajectory on the two",
        },
        "timestep_ms": 160.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a deterministic 9-value observation and 6-value action stand-in, not the Drake contact "
            "simulation: no rigid-body dynamics, contacts, friction, controller, rendering or sensors are modelled",
            "the upstream default DrakeBaseConfig uses a [10, 240, 320] image observation; the package fake uses "
            "the Hammer teleop configuration's 9-value keypoint observation instead, because the standard bridge "
            "carries only JSON values",
            "the base reward is 0; the knife, spatula, hammer and wrench task rewards are not modelled",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "the upstream environment was never opened here (it needs a Hydra task_config, pydrake, torch and the "
            "bundled assets) and no upstream trajectory was compared with the fake",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
