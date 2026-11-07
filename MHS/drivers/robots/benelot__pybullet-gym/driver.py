"""OpenMHS driver for gh.benelot/pybullet-gym: the InvertedPendulumPyBulletEnv-v0 environment.

A ``GymnasiumDriver`` is configuration only: ``env_id`` names the registered environment and the bridge derives the
``cap.world.*`` contract from the environment's spaces.  The card's first entry symbol,
``InvertedPendulumBulletEnv``, declares a one-element ``Box(-1, 1)`` action space and a five-element Box observation
space, so ``cap.world.step.v1`` takes ``{ticks, action: {values: [float]}}`` with ``values`` bounded per element by the
action space, and ``cap.world.reset.v1`` takes ``{seed, options}``.

The device is simulated (R0): there is no hardware backend, no path to a machine and no operator-required bound.  The
gate cannot import the clone (it needs pybullet, gym and numpy), so the ``fake`` backend is this package's own pure
Python InvertedPendulum stand-in (``fake.py``); a backend name that ``backends`` does not list (``sim``) would be served
by ``gym.make(env_id)`` after importing the clone, which was not run here.

This package is model-authored and unreviewed; it is checked on the fake backend only.  The upstream clone is read at
commit bc68201c8101c4e30dde95f425647a0709ee2f29 and never imported by the package.
"""

from mhs.driver import Fact, GymnasiumDriver

PENDULUM_ENV = "pybulletgym/envs/roboschool/envs/pendulum/inverted_pendulum_env.py"
PENDULUM_ROBOT = "pybulletgym/envs/roboschool/robots/pendula/interted_pendulum.py"
ROBOT_BASE = "pybulletgym/envs/roboschool/robots/robot_bases.py"
REGISTRY = "pybulletgym/envs/__init__.py"
SCENE_BASE = "pybulletgym/envs/roboschool/scenes/scene_bases.py"
PENDULUM_MODEL = "pybulletgym/envs/assets/mjcf/inverted_pendulum.xml"


class InvertedPendulum(GymnasiumDriver):
    device_id = "inverted-pendulum"
    env_id = "InvertedPendulumPyBulletEnv-v0"
    native = ("pybulletgym.envs.roboschool.envs.pendulum.inverted_pendulum_env:"
              "InvertedPendulumBulletEnv")
    backends = {"fake": ".fake:FakeInvertedPendulumEnv"}
    action_space_ref = 'pybulletgym/envs/roboschool/robots/robot_bases.py:24-25'
    display_name = "PyBullet Gymperium inverted pendulum (InvertedPendulumPyBulletEnv-v0)"
    vendor, model = "Benjamin Ellenberger (benelot)", "InvertedPendulumPyBulletEnv-v0"
    tags = ["inverted-pendulum", "roboschool", "reinforcement-learning", "simulation", "pybullet"]
    facts = [
        Fact("InvertedPendulumPyBulletEnv-v0 is registered with entry point "
             "pybulletgym.envs.roboschool.envs.pendulum.inverted_pendulum_env:InvertedPendulumBulletEnv",
             source="upstream_code", ref=f"{REGISTRY}:5-10"),
        Fact("The InvertedPendulumPyBulletEnv-v0 registration sets max_episode_steps to 1000",
             source="upstream_code", ref=f"{REGISTRY}:8"),
        Fact("The inverted pendulum robot declares action_dim=1 and obs_dim=5",
             source="upstream_code", ref=f"{PENDULUM_ROBOT}:9"),
        Fact("The action space is a one-element Box with both bounds from np.ones([action_dim]), that is -1 and 1",
             source="upstream_code", ref=f"{ROBOT_BASE}:24-25"),
        Fact("The observation space is a Box of obs_dim elements with bounds from -np.inf to np.inf",
             source="upstream_code", ref=f"{ROBOT_BASE}:26-27"),
        Fact("The observation vector is [cart position, cart velocity, cos(theta), sin(theta), theta angular "
             "velocity]", source="upstream_code", ref=f"{PENDULUM_ROBOT}:48-51"),
        Fact("apply_action sets the slider motor torque to 100 times the action clipped to -1 to 1",
             source="upstream_code", ref=f"{PENDULUM_ROBOT}:25"),
        Fact("The reset draws the pole angle uniformly from -0.1 to 0.1 (the swing-up reset adds 3.1415) and sets the "
             "motor torque to 0", source="upstream_code", ref=f"{PENDULUM_ROBOT}:16-18"),
        Fact("The non-swing-up episode terminates when abs(theta) is greater than 0.2 and each step pays reward 1.0",
             source="upstream_code", ref=f"{PENDULUM_ENV}:34-39"),
        Fact("The environment creates a scene with gravity 9.8, timestep 0.0165 s and frame_skip 1",
             source="upstream_code", ref=f"{PENDULUM_ENV}:13-14"),
        Fact("The scene stores timestep and frame_skip and computes dt as timestep times frame_skip",
             source="upstream_code", ref=f"{SCENE_BASE}:14-17"),
        Fact("The MJCF model gives the cart a slide joint named slider on the x axis with range -1 to 1 and the pole "
             "an unlimited hinge", source="upstream_code", ref=f"{PENDULUM_MODEL}:15-18"),
        Fact("The documented gym environment methods are reset(self), which returns the observation, and "
             "step(self, action), which returns observation, reward, done and info",
             source="vendor_doc", ref="README.md:67-68"),
        Fact("The environments are reimplemented with the pybullet wrapper of Bullet Physics",
             source="vendor_doc", ref="README.md:6"),
    ]
    safe_state = ("the simulated world stops advancing: after an e-stop every step and reset is refused and the last "
                  "observation stays readable until the runtime's safety reset clears the latch")
    #: The fidelity contract of the model as deployed.  The bridge derives engine, determinism, timestep, clock and
    #: reset; they are written out here so the whole contract is in one place (timestep from the scene's
    #: timestep 0.0165 s times frame_skip 1, inverted_pendulum_env.py:14).
    fidelity = {
        "engine": "pybullet-gym:InvertedPendulumPyBulletEnv-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the upstream environment seeds gym.utils.seeding.np_random and shares that generator with the "
                     "robot, and the fake seeds Python's random.Random with the reset seed; the two generators are "
                     "different, so one seed does not give the same trajectory on both implementations",
        },
        "timestep_ms": 16.5,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "Bullet rigid-body simulation of the cart, slider joint and pole hinge: the fake integrates a simplified "
            "cart-pole model with placeholder masses and arm length, not Bullet's joints, contacts, solver or "
            "integrator, so trajectories differ",
            "the fake draws the initial pole angle with Python's random.Random; upstream draws it from numpy's "
            "generator through gym.utils.seeding",
            "the fake applies the registered 1000-step limit itself and returns a five-tuple; upstream step() returns "
            "a four-tuple and gym.make adds the TimeLimit wrapper",
            "no rendering, camera adjustment or HUD is modelled",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
