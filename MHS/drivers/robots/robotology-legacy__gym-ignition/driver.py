"""OpenMHS driver for gh.robotology-legacy/gym-ignition: the CartPoleDiscreteBalancing-Gazebo-v0 environment.

The upstream package registers its environments as legacy OpenAI Gym environments through
``gym.envs.registration.register``; every one of them has the same entry point,
``gym_ignition.runtimes.gazebo_runtime:GazeboRuntime``, and passes a different task class.  This package serves the
discrete cartpole member, ``CartPoleDiscreteBalancing-Gazebo-v0``: the card's ``GymnasiumDriver`` helper can express
it because the bridge accepts the legacy four-value ``step`` and the bare ``reset`` that the runtime returns.  The
other three registered identifiers are not served by this driver.

The upstream environment needs Ignition Gazebo, ScenARIO and ``gym_ignition_models``.  The gate cannot install or
import them, so the ``fake`` backend is the package's own analytic stand-in (``fake.py``); the ``sim`` backend, which
would call ``gym.make(env_id)``, was not run.  The driver is model-authored and unreviewed and has been checked on
the fake backend only.  Every Fact cites a file and line of the clone at commit
4bc8e0465eed68911434485ba0b9c0a6740d516e.
"""

from mhs.driver import Fact, GymnasiumDriver

REGISTRATION = "python/gym_ignition_environments/__init__.py"
README = "README.md"
BASE_RUNTIME = "python/gym_ignition/base/runtime.py"
BASE_TASK = "python/gym_ignition/base/task.py"
RUNTIME = "python/gym_ignition/runtimes/gazebo_runtime.py"
TASK = "python/gym_ignition_environments/tasks/cartpole_discrete_balancing.py"


class CartPoleDiscrete(GymnasiumDriver):
    device_id = "cartpole-discrete-gazebo"
    device_kind = "world.sim"
    env_id = "CartPoleDiscreteBalancing-Gazebo-v0"
    native = "gym_ignition.runtimes.gazebo_runtime:GazeboRuntime"
    backends = {"fake": ".fake:FakeCartPoleDiscrete"}
    display_name = "gym-ignition CartPoleDiscreteBalancing-Gazebo-v0"
    vendor, model = "robotology-legacy", "CartPoleDiscreteBalancing-Gazebo-v0"
    tags = ["cartpole", "gazebo", "ignition-gazebo", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("The package registers four legacy OpenAI Gym environments through gym.envs.registration.register "
             "(Pendulum-Gazebo-v0, CartPoleDiscreteBalancing-Gazebo-v0, CartPoleContinuousBalancing-Gazebo-v0 and "
             "CartPoleContinuousSwingup-Gazebo-v0) with the GazeboRuntime entry point and max_episode_steps=5000",
             source="upstream_code", ref=f"{REGISTRATION}:6-58"),
        Fact("CartPoleDiscreteBalancing-Gazebo-v0 is registered with task_cls CartPoleDiscreteBalancing, agent_rate "
             "1000, physics_rate 1000 and real_time_factor float32 max", source="upstream_code",
             ref=f"{REGISTRATION}:24-34"),
        Fact("The environments are built on the Ignition Gazebo simulator through the ScenARIO project",
             source="vendor_doc", ref=f"{README}:61"),
        Fact("The runtime is a gym.Env: class Runtime(gym.Env, abc.ABC)", source="upstream_code",
             ref=f"{BASE_RUNTIME}:11"),
        Fact("The runtime step sets the task action, runs Gazebo and returns observation, reward, done and info",
             source="upstream_code", ref=f"{RUNTIME}:103-132"),
        Fact("The runtime reset resets the task, runs a paused Gazebo step and returns the observation",
             source="upstream_code", ref=f"{RUNTIME}:134-152"),
        Fact("The runtime seed method delegates to the task and returns the list of seeds", source="upstream_code",
             ref=f"{RUNTIME}:173-183"),
        Fact("The task seeds its numpy RandomState with gym.utils.seeding.np_random(seed)", source="upstream_code",
             ref=f"{BASE_TASK}:234-239"),
        Fact("A cartpole reset draws x, dx, q and dq uniformly from -0.05 to 0.05", source="upstream_code",
             ref=f"{TASK}:144"),
        Fact("The action space is Discrete(2)", source="upstream_code", ref=f"{TASK}:49"),
        Fact("The cartpole force magnitude is 20.0", source="upstream_code", ref=f"{TASK}:37"),
        Fact("Action 1 commands +force_mag and any other action -force_mag as the linear joint's generalized force "
             "target", source="upstream_code", ref=f"{TASK}:75-79"),
        Fact("The cart limits are x 2.4 m, dx 20.0 m/s, q 12 degrees and dq 3*360 degrees per second",
             source="upstream_code", ref=f"{TASK}:41-44"),
        Fact("The observation is [x, dx, q, dq] taken from the linear and pivot joint positions and velocities",
             source="upstream_code", ref=f"{TASK}:89-94"),
        Fact("The observation space is the reset box scaled by 1.2", source="upstream_code", ref=f"{TASK}:61-68"),
        Fact("The episode is done when the observation leaves the reset box", source="upstream_code",
             ref=f"{TASK}:123-124"),
        Fact("The reward is 1.0 when not done and 0.0 when done, minus 0.10|x|, minus 0.10|dx| and minus 10.0 "
             "when x >= 0.9*2.4", source="upstream_code", ref=f"{TASK}:102-113"),
        Fact("One environment step runs physics_rate/agent_rate simulation iterations of 1.0/physics_rate seconds",
             source="upstream_code", ref=f"{RUNTIME}:196-208"),
        Fact("Gym-ignition does not provide out-of-the-box environments; the environments package holds canonical "
             "examples", source="vendor_doc", ref=f"{README}:72-75"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    fidelity_level = "F0"
    #: The complete fidelity contract of the model as deployed on this package's fake backend (spec 05-fidelity
    #: FID-002).  Upstream the model is an Ignition Gazebo rigid-body simulation; that path was not run, so the
    #: level below is deliberately the lower one that the analytic stand-in supports.
    fidelity = {
        "engine": "gazebo",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the runtime seeds the task's numpy RandomState through gym.utils.seeding.np_random "
                     "(base/task.py:234-239) and a reset draws from it; the fake backend implements the same "
                     "protocol with Python's random.Random, so a seed repeats a trajectory within one "
                     "implementation but not across the fake and the upstream environment",
        },
        "timestep_ms": 1.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is analytic: it moves the cart and pole positions directly and applies a fixed "
            "force; it models no rigid-body dynamics, contacts, friction, inertia or actuator, and the upstream "
            "Ignition Gazebo model was not run here",
            "no wall-clock pacing: realtime_factor is 0 and the fake advances only when a step is requested "
            "(upstream registers real_time_factor as float32 max)",
            "the fake draws the initial state with Python's random.Random while upstream draws it from numpy's "
            "RandomState, so one seed gives different trajectories on the two",
            "observation values are Python floats in a list; upstream returns a numpy float32 array",
            "the fake was never compared with an Ignition Gazebo run, and no physical device is modelled",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state",
        ],
    }
