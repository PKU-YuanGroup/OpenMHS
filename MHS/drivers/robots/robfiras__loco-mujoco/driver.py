"""OpenMHS driver for gh.robfiras/loco-mujoco: the registered Gymnasium environment ``LocoMujoco``.

``GymnasiumWrapper`` (the card's entry symbol) is a Gymnasium adapter around one of the LocoMuJoCo humanoid
environments.  It is registered as ``LocoMujoco`` and constructed with ``env_name`` plus keyword arguments that
reach the environment constructor through ``RLFactory.make``.  This driver binds the ``Atlas`` environment and pins
the physics configuration (``timestep=0.001`` s, ``n_substeps=10``) that ``LocoEnv`` documents as its defaults, so a
control step is 10 ms (``simulation_dt * n_intermediate_steps * n_substeps``).

A GymnasiumDriver is configuration only: the bridge derives ``cap.world.step.v1`` (``{ticks, action}`` with the
action ``{values: [...]}`` from the Box action space), ``cap.world.reset.v1`` (``{seed, options}``) and
``cap.world.seed.v1`` (``{seed}``) from the environment's spaces and from its ``dt``.  The action space of the
``Atlas`` environment is the 27-dimensional PD-control space normalized to -1..1; the observation space is the
wrapper's Box conversion of the inner environment's space (the 65 documented Atlas observations plus the 3-value
``GoalRandomRootVelocity`` goal that ``RLFactory`` uses by default).

The device is simulated (R0).  There is no hardware backend and no e-stop path to a machine; the safe state is the
runtime's software latch.  The ``fake`` backend is this package's own pure Python stand-in for ``GymnasiumWrapper``
(the upstream package, jax and the separate ``loco_mujoco_models`` model files are not importable where the gate
runs).  A backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make("LocoMujoco", ...)``
through the family driver; that path was not run here.  The package is model-authored and unreviewed: every check
ran on the fake backend only, and the fidelity ``gaps`` say what the fake does not model.
"""

from mhs.driver import Fact, GymnasiumDriver

WRAPPER = "loco_mujoco/core/wrappers/gymnasium.py"
REGISTRATION = "loco_mujoco/environments/humanoids/__init__.py"
ENVIRONMENTS = "loco_mujoco/environments/base.py"
MUJOCO_BASE = "loco_mujoco/core/mujoco_base.py"
CONTROL_BASE = "loco_mujoco/core/control_functions/base.py"
PD_CONTROL = "loco_mujoco/core/control_functions/pd.py"
ATLAS = "loco_mujoco/environments/humanoids/atlas.py"
GOALS = "loco_mujoco/core/observations/goals.py"


class LocoMujoco(GymnasiumDriver):
    device_id = "loco-mujoco"
    env_id = "LocoMujoco"
    #: ``Atlas`` is a registered RL environment (humanoids/__init__.py:26); the two numbers are the constructor
    #: defaults of ``LocoEnv`` (environments/base.py:51-52), pinned here so the control step is 10 ms.
    env_kwargs = {"env_name": "Atlas", "timestep": 0.001, "n_substeps": 10}
    native = "loco_mujoco.core.wrappers.gymnasium:GymnasiumWrapper"
    backends = {"fake": ".fake:FakeGymnasiumWrapper"}
    display_name = "LocoMuJoCo LocoMujoco (Atlas humanoid)"
    vendor, model = "robfiras", "LocoMujoco/Atlas"
    tags = ["loco-mujoco", "humanoid", "mujoco", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The gymnasium environment 'LocoMujoco' is registered with entry point "
             "loco_mujoco.core.wrappers.gymnasium:GymnasiumWrapper", source="upstream_code",
             ref=f"{REGISTRATION}:58-60"),
        Fact("GymnasiumWrapper's constructor takes env_name and builds the wrapped environment with "
             "RLFactory.make(env_name, **kwargs)", source="upstream_code", ref=f"{WRAPPER}:19-46"),
        Fact("GymnasiumWrapper.step calls the wrapped environment and returns its five values unchanged: "
             "observation, reward, absorbing, done, info", source="upstream_code", ref=f"{WRAPPER}:55-73"),
        Fact("GymnasiumWrapper.reset seeds numpy and jax from the seed when one is given and returns "
             "(observation, {})", source="upstream_code", ref=f"{WRAPPER}:75-94"),
        Fact("render_fps is 1.0 / the wrapped environment's dt", source="upstream_code", ref=f"{WRAPPER}:48"),
        Fact("GymnasiumWrapper.close stops the wrapped environment", source="upstream_code",
             ref=f"{WRAPPER}:107-112"),
        Fact("LocoEnv's constructor defaults are n_substeps=10 and timestep=0.001", source="upstream_code",
             ref=f"{ENVIRONMENTS}:51-52"),
        Fact("simulation_dt is the MuJoCo model's opt.timestep", source="upstream_code",
             ref=f"{MUJOCO_BASE}:1297-1304"),
        Fact("The effective dt is simulation_dt * n_intermediate_steps * n_substeps", source="upstream_code",
             ref=f"{MUJOCO_BASE}:1307-1314"),
        Fact("The inner environment starts with n_intermediate_steps set to 1", source="upstream_code",
             ref=f"{MUJOCO_BASE}:125"),
        Fact("The base control function does not run at the simulation frequency", source="upstream_code",
             ref=f"{CONTROL_BASE}:96-100"),
        Fact("The inner environment advances the MuJoCo model with mujoco.mj_step for n_substeps",
             source="upstream_code", ref=f"{MUJOCO_BASE}:260-262"),
        Fact("PDControl normalizes the agent's action space to [-1, 1]", source="upstream_code",
             ref=f"{PD_CONTROL}:31-32"),
        Fact("Atlas's default action specification is the actuator list from back_bkz_actuator through "
             "l_leg_akx_actuator", source="upstream_code", ref=f"{ATLAS}:387-394"),
        Fact("RLFactory.make defaults goal_type to GoalRandomRootVelocity", source="upstream_code",
             ref="loco_mujoco/task_factories/rl_factory.py:15-20"),
        Fact("The goal is appended to the observation specification", source="upstream_code",
             ref=f"{MUJOCO_BASE}:138"),
        Fact("GoalRandomRootVelocity has goal dimension 3", source="upstream_code", ref=f"{GOALS}:427-429"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch; the last state stays readable and nothing is actuated")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the
    #: determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "mujoco:loco-mujoco:LocoMujoco",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the seed is a reset parameter; upstream seeds numpy and jax from it, this package's fake "
                     "draws placeholder values from random.Random(seed), so a seed repeats a fake trajectory but "
                     "not the upstream one",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the upstream sim backend needs the upstream package plus its separate loco_mujoco_models model files "
            "and jax/numpy (install command pip install .), and was not run here; only the fake backend was checked",
            "the fake backend is a placeholder: it starts from random placeholder joint values, adds the action to "
            "the position, and has no MuJoCo contacts, actuators, sensors, reward function or termination; it was "
            "never compared with the upstream environment",
            "the fake returns 68 placeholder observation values (the 65 entries of Atlas's default observation "
            "specification plus the 3 GoalRandomRootVelocity goal values) and accepts 27 action values; these are "
            "test data, not the MuJoCo state",
            "the reset seeds numpy and jax global state in upstream (gymnasium.py:89-94); the fake uses "
            "random.Random(seed), so one seed gives a different trajectory on the two",
            "snapshot and restore are not offered: GymnasiumWrapper exposes no get_state or set_state",
            "the 10 ms control step holds only because this driver pins env_kwargs timestep 0.001 s and n_substeps "
            "10 (the upstream constructor defaults); another configuration or model file changes it",
        ],
    }
