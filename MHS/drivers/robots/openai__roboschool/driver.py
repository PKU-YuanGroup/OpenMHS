"""OpenMHS driver for gh.openai/roboschool: the RoboschoolInvertedPendulum-v1 environment.

The upstream package registers a legacy ``gym`` environment (``gym.envs.registration.register``,
``roboschool/__init__.py:11-17``) whose class is ``roboschool:RoboschoolInvertedPendulum``
(``roboschool/gym_pendulums.py:69``).  A ``GymnasiumDriver`` is configuration only: the bridge derives the
``cap.world.step.v1`` action schema and limits from the environment's action space and serves
``cap.world.reset.v1`` and ``cap.world.seed.v1``.  The device is a simulator (R0), so every mode, risk and
safety rule is the runtime's software latch: the simulation stops advancing after an e-stop and the state stays
readable.

The gate cannot import the upstream package (it needs ``gym``, ``numpy`` and the compiled Bullet scene), so the
``fake`` backend is the package's own pure Python stand-in in ``fake.py``.  A backend name that ``backends`` does
not list (``sim``) would be served by ``gym.make(env_id)`` through the bridge; that path needs the upstream
installation and was not run here.  This package is model-authored and unreviewed: it is checked on the fake
backend only and claims no MHS-Device level.
"""

from mhs.driver import Fact, GymnasiumDriver

PENDULUMS = "roboschool/gym_pendulums.py"
BASE_ENV = "roboschool/gym_mujoco_xml_env.py"
REGISTRATION = "roboschool/__init__.py"


class RoboschoolInvertedPendulum(GymnasiumDriver):
    device_id = "roboschool-inverted-pendulum"
    env_id = "RoboschoolInvertedPendulum-v1"
    native = "roboschool:RoboschoolInvertedPendulum"
    backends = {"fake": ".fake:FakeInvertedPendulum"}
    display_name = "Roboschool InvertedPendulum-v1 (OpenAI Roboschool)"
    vendor, model = "OpenAI", "RoboschoolInvertedPendulum-v1"
    tags = ["inverted-pendulum", "cartpole", "continuous-control", "reinforcement-learning", "roboschool",
            "simulation"]
    facts = [
        Fact("RoboschoolInvertedPendulum-v1 is registered with entry point roboschool:RoboschoolInvertedPendulum, "
             "max_episode_steps 1000 and reward_threshold 950.0", source="upstream_code",
             ref=f"{REGISTRATION}:11-17"),
        Fact("RoboschoolInvertedPendulum is a continuous-control inverted pendulum: keep a pole upright by moving "
             "the 1-D cart", source="upstream_code", ref=f"{PENDULUMS}:69-74"),
        Fact("The class is constructed with action_dim 1 and obs_dim 5", source="upstream_code",
             ref=f"{PENDULUMS}:78"),
        Fact("The action space is Box(-high, high) with high = np.ones([action_dim]), so with action_dim 1 it is "
             "bounded by -1 and 1; the observation space is Box(-inf*ones([obs_dim]), inf*ones([obs_dim]))",
             source="upstream_code", ref=f"{BASE_ENV}:26-29"),
        Fact("The scene uses gravity 9.8, timestep 0.0165 s and frame_skip 1", source="upstream_code",
             ref=f"{PENDULUMS}:81"),
        Fact("The pole hinge angle is drawn uniformly from -0.1 to 0.1 radians before each episode",
             source="upstream_code", ref=f"{PENDULUMS}:87-88"),
        Fact("Each step applies a motor torque of 100 times the action clipped to -1..1", source="upstream_code",
             ref=f"{PENDULUMS}:91-93"),
        Fact("The observation is [cart position, cart velocity, cos(theta), sin(theta), theta angular velocity]",
             source="upstream_code", ref=f"{PENDULUMS}:95-102"),
        Fact("A non-swingup step rewards 1.0 and terminates when the absolute pole angle exceeds 0.2 radians",
             source="upstream_code", ref=f"{PENDULUMS}:104-120"),
        Fact("RoboschoolInvertedPendulum.step is the legacy Gym API: it returns the four-tuple (state, reward, "
             "done, info)", source="upstream_code", ref=f"{PENDULUMS}:120"),
        Fact("The base environment seeds its numpy generator with gym.utils.seeding.np_random(seed) and returns "
             "[seed]", source="upstream_code", ref=f"{BASE_ENV}:35-37"),
        Fact("The base reset recreates the scene, resets the robot and returns the initial observation",
             source="upstream_code", ref=f"{BASE_ENV}:39-78"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the
    #: engine, the seeded determinism and the lockstep clock; they are written out so the contract reads in one
    #: place.
    fidelity = {
        "engine": "roboschool:RoboschoolInvertedPendulum-v1",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) fixes the pole angle and the dynamics are deterministic, so the package fake "
                     "repeats a trajectory for one seed and actions; upstream draws the angle from its numpy "
                     "generator, so a seed gives different trajectories on the fake and the upstream scene, and "
                     "nothing here was compared with a real run",
        },
        "timestep_ms": 16.5,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a pure Python cart-pole stand-in for the interface; its masses, inertia, contacts, "
            "damping and motor model are not the Bullet scene of roboschool/mujoco_assets/inverted_pendulum.xml "
            "and it was not compared with the upstream environment",
            "the fake reports truncation at the registered 1000 steps to mirror the TimeLimit wrapper that "
            "gym.make adds; the bare upstream class step returns a four-tuple and never truncates",
            "reset options are accepted by the family bridge but ignored: the upstream reset takes no options",
            "no rendering: the upstream camera_adjust and HUD paths are not modelled",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "no physical device is modelled and the model was never validated against one",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
