"""OpenMHS Gymnasium driver for gh.cursedrock17/gazebo_gymnasium (``GazeboCartPole-v0``).

DEVIATION FROM THE CARD: the card says ``family: ros`` with ``helper: RosDriver``
and ``reason_code: family:ros``.  The confirmed entry symbol,
``gazebo_gymnasium_bridge.gazebo_gymnasium_bridge.envs.gym_env:GazeboEnv``
(gym_env.py:49), is a standard ``gymnasium.Env``: it builds one in-process
``InProcessHarnessVecEnv`` from an ``AgentSpec`` and steps it through the
Gymnasium API.  The repository's ROS 2 packages supply the message types and
launch files around that environment; the environment itself is not a ROS
topic/service transport.  A Gymnasium environment therefore uses
``GymnasiumDriver`` (driver-authoring.md, "Choosing the shape"), not
``RosDriver``.  No ROS endpoint, type or action is invented here.

The served environment is the shipped ``GazeboCartPole-v0`` registration, which
wraps the default ``cartpole`` spec: a discrete two-force slider action, a
four-value joint observation, a constant reward of 1.0, termination at the
pole-angle or cart-position threshold, and truncation at the spec's
500-transition limit.  The real backend needs Linux, ROS 2 Jazzy, Gazebo
Harmonic and the native ``gz.sim8`` bindings (README.md:61-63, 71-78;
inprocess_vec_env.py:476-480); none of them is available where this package is
checked, so only the package's analytic fake (``.fake:FakeGazeboCartPole``) is
declared and exercised.  This package is model-authored and unreviewed.
"""

from mhs.driver import Fact, GymnasiumDriver

GYM_ENV = "gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/gym_env.py"
AGENT_SPEC = "gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/agent_spec.py"
INPROCESS = "gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/envs/inprocess_vec_env.py"
HARNESS = "gazebo_gymnasium_bridge/gazebo_gymnasium_bridge/harness/harness_core.py"
CARTPOLE_SDF = ("gazebo_gymnasium_examples/gazebo_gymnasium_resources/models/"
                "cartpole_bare/model.sdf")


class GazeboCartPole(GymnasiumDriver):
    """The ``GazeboCartPole-v0`` single-agent Gymnasium environment."""

    device_id = "gazebo-cartpole"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    env_id = "GazeboCartPole-v0"
    native = "gazebo_gymnasium_bridge.gazebo_gymnasium_bridge.envs.gym_env:GazeboEnv"
    backends = {"fake": ".fake:FakeGazeboCartPole"}
    #: agent_spec.py:773 defines ``action_space=spaces.Discrete(2)``, the space the fake copies.
    action_space_ref = f"{AGENT_SPEC}:773"
    display_name = "Gazebo Gymnasium CartPole-v0"
    vendor, model = "Lucas Wendland / CursedRock17", "GazeboCartPole-v0"
    tags = ["gymnasium", "gazebo", "gz-sim", "cartpole", "reinforcement-learning", "simulation"]

    facts = [
        Fact("gazebo_gymnasium_bridge documents reinforcement-learning agents training in Gazebo through the "
             "standard Gymnasium API.", source="vendor_doc", ref="README.md:3-4"),
        Fact("The clone targets Linux x86-64 only and its locked environment provides ROS 2 Jazzy and Gazebo "
             "Harmonic.", source="vendor_doc", ref="README.md:61-63"),
        Fact("The Pixi environment supplies Gazebo Harmonic with its gz.sim Python bindings.", source="vendor_doc",
             ref="README.md:71-72"),
        Fact("The registered env ids map GazeboCartPole-v0 to the cartpole agent spec; GazeboCartPoleContinuous-v0 "
             "is a separate registration.", source="upstream_code", ref=f"{GYM_ENV}:37-46"),
        Fact("register_envs registers each id with entry point "
             "gazebo_gymnasium_bridge.envs.gym_env:GazeboEnv and kwargs {'agent': agent}.",
             source="upstream_code", ref=f"{GYM_ENV}:92-99"),
        Fact("GazeboEnv.__init__ takes agent='cartpole' by default, reads its spaces from get_spec(agent), and "
             "builds InProcessHarnessVecEnv with n_agents=1 and autoreset=False.",
             source="upstream_code", ref=f"{GYM_ENV}:54-64"),
        Fact("GazeboEnv.reset calls gym.Env.reset(seed=seed), seeds the vector environment only when a seed is "
             "given, calls its reset(), and returns the first observation with an empty info dictionary.",
             source="upstream_code", ref=f"{GYM_ENV}:66-71"),
        Fact("GazeboEnv.step sends one action through step_async/step_wait, pops TimeLimit.truncated from info, "
             "reports terminated only when done and not truncated, and returns the five-value Gymnasium tuple.",
             source="upstream_code", ref=f"{GYM_ENV}:73-79"),
        Fact("_cartpole_action_to_commands rounds the action to an integer and commands a slider_to_cart force of "
             "+_CART_FORCE (10.0) for action 1 and -10.0 for any other action.", source="upstream_code",
             ref=f"{AGENT_SPEC}:740-749"),
        Fact("The cartpole spec declares action_space=spaces.Discrete(2).", source="upstream_code",
             ref=f"{AGENT_SPEC}:773"),
        Fact("The cartpole observation space is Box with low [-4.8, -inf, -0.41887903, -inf], high "
             "[4.8, inf, 0.41887903, inf] and shape (4,), in float32.", source="upstream_code",
             ref=f"{AGENT_SPEC}:762-767"),
        Fact("The observation order is cart position, cart velocity, pole angle and pole angular velocity from the "
             "slider_to_cart and cart_to_pole joints.", source="upstream_code", ref=f"{AGENT_SPEC}:774-775"),
        Fact("Cartpole reset puts the cart at zero position and velocity and draws the pole angle uniformly from "
             "-0.05 to 0.05 with zero angular velocity.", source="upstream_code", ref=f"{AGENT_SPEC}:752-758"),
        Fact("The cartpole pole-angle threshold is 0.20944 and the cart-position threshold is 2.4.",
             source="upstream_code", ref=f"{AGENT_SPEC}:730-731"),
        Fact("The cartpole terminated_fn returns true when the absolute pole angle or the absolute cart position "
             "exceeds its threshold.", source="upstream_code", ref=f"{AGENT_SPEC}:776-779"),
        Fact("The cartpole reward function always returns 1.0.", source="upstream_code", ref=f"{AGENT_SPEC}:776"),
        Fact("AgentSpec defaults frame_skip to 5 physics ticks per environment step and max_episode_steps to 500.",
             source="upstream_code", ref=f"{AGENT_SPEC}:221-222"),
        Fact("The in-process world sets a 0.01 s maximum physics step and real_time_factor 0.",
             source="upstream_code", ref=f"{INPROCESS}:56-59"),
        Fact("step_wait calls _step_server(self.frame_skip) in both its image and its non-image branch.",
             source="upstream_code", ref=f"{INPROCESS}:1115-1121"),
        Fact("_step_server calls self._server.run(True, ticks, False) and does not use its return value.",
             source="upstream_code", ref=f"{INPROCESS}:810-814"),
        Fact("InProcessHarnessVecEnv truncates at max_episode_steps and sets info['TimeLimit.truncated'] only when "
             "the episode truncated without terminating.", source="upstream_code",
             ref=f"{INPROCESS}:1168-1181"),
        Fact("InProcessHarnessVecEnv.seed replaces its generator with numpy.random.default_rng(seed).",
             source="upstream_code", ref=f"{INPROCESS}:1225-1227"),
        Fact("The reset path passes that generator into Core.reset_agent for each reset agent.",
             source="upstream_code", ref=f"{INPROCESS}:816-823"),
        Fact("Core.reset_agent calls reset_joint_state(rng) and applies every returned joint position and velocity.",
             source="upstream_code", ref=f"{HARNESS}:317-324"),
        Fact("InProcessHarnessVecEnv imports the native gz.sim8 bindings in its constructor.",
             source="upstream_code", ref=f"{INPROCESS}:476-480"),
        Fact("The constructor writes the generated world SDF to a tempfile.mkstemp file, hosts it in "
             "gz_sim.TestFixture with pre- and post-update callbacks, and steps the server once.",
             source="upstream_code", ref=f"{INPROCESS}:769-779"),
        Fact("The constructor prints a ready line naming the agent, n_agents and frame_skip.",
             source="upstream_code", ref=f"{INPROCESS}:802-806"),
        Fact("close() unsubscribes the camera topics in image mode and removes the temporary world file; it calls "
             "no method of the TestFixture or its server.", source="upstream_code", ref=f"{INPROCESS}:1190-1207"),
        Fact("The cartpole_bare model is an SDF with a prismatic slider_to_cart joint limited to -4..4, a "
             "revolute cart_to_pole joint with effort 1000 and velocity 8, and mass-1 slider, cart and pole links.",
             source="upstream_code", ref=f"{CARTPOLE_SDF}:9-46"),
    ]

    safe_state = ("simulation advancement stops: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the last observation and world state stay readable")
    fidelity = {
        "engine": "analytic:package fake for gymnasium:GazeboCartPole-v0 (upstream engine is Gazebo Harmonic)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "one seed repeats the fake's pole-angle draw and its integration, but the fake uses Python's "
                     "random.Random whereas the upstream vector environment uses numpy.random.default_rng, so the "
                     "same seed does not reproduce an upstream Gazebo trajectory",
        },
        # agent_spec.py:221 frame_skip 5 * inprocess_vec_env.py:57 max_step_size 0.01 s.
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an analytic cartpole integrator with placeholder dynamics; it does not run Gazebo "
            "Harmonic or DART and models no contacts, friction, solver, joint effort/velocity limit or SDF inertia",
            "the fake's gravity, mass and pole-length constants are test data, not calibrated model parameters; "
            "no trajectory was compared with an upstream Gazebo run",
            "the fake draws the reset pole angle with Python's random.Random while the upstream environment uses "
            "numpy.random.default_rng, so one seed gives different angles on the two",
            "the fake returns Python float lists; the upstream environment returns numpy float32 arrays of the "
            "same four values",
            "no rendering is served; GazeboEnv metadata declares no render modes and the fake has no renderer",
            "only GazeboCartPole-v0 is covered; the other seven registered ids, the vector and multi-agent "
            "environments and the camera-based line follower are outside this package",
            "the real environment requires Linux, ROS 2 Jazzy, Gazebo Harmonic with gz.sim8, gymnasium and "
            "stable-baselines3; none is installed here and no Gazebo or ROS graph was opened",
            "the fake does not model the world-fixed slider joint or the 0.60 m spawn height; cart position is "
            "the slider joint coordinate only",
            "the upstream reset applies the drawn joint state in the pre-update callback and steps the server one "
            "0.01 s tick before reading the observation; the fake returns the drawn state without that tick",
            "the upstream step ignores the boolean return of server.run, so a server that does not run scores the "
            "transition on the previous observation; the fake cannot model that swallowed failure",
            "fake-only contract: no sim backend is declared; live construction (never run here) would host gz-sim "
            "inside the server process through gz.sim8.TestFixture, write a temporary world SDF, print a ready "
            "line to standard output (which corrupts an MHS server that speaks over stdio), and its close() "
            "removes only that file and leaves the TestFixture server alive",
        ],
    }
