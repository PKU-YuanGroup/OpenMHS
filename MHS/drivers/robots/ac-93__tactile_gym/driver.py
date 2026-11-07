"""OpenMHS driver for gh.ac-93/tactile_gym: the edge_follow-v0 PyBullet environment.

A ``GymnasiumDriver`` is configuration only: ``env_id`` names the registered environment and the bridge derives
``cap.world.step.v1`` (``{ticks, action}`` with ``action.values`` bounded by the environment's action space),
``cap.world.reset.v1`` (``{seed, options}``) and ``cap.world.seed.v1`` (``{seed}``) from the environment's spaces
and methods.  The class is a legacy ``gym`` environment (``base_tactile_env.py:12``): ``reset`` takes no
seed/options and returns the observation, and ``step`` returns the four-tuple
``(observation, reward, done, info)`` (``base_tactile_env.py:166-185``); the bridge handles both the legacy
``seed``/``reset`` fallback and the four-tuple.  The card's helper expresses the interface; this is not a deviation.

The device is simulated (``mode = "simulated"``, R1: the capability advances a simulated robot arm, which the safety
spec classifies as simulation stepping, MHS-004 section 2.1).  There is no hardware backend, no serial port and no
robot API in the clone path used here, so the package has one backend, the package fake in ``fake.py``.  The fake is
a pure Python kinematic stand-in because the upstream environment needs PyBullet, OpenCV, numpy and
``tactile_gym.rl_envs`` to be imported for the registration, none of which the gate installs or imports; the package
never imports the clone.  A backend name outside ``backends`` (``sim``) would be served by ``gym.make(env_id)``
(``GymnasiumDriver.open_native``); in addition to the upstream dependencies that path needs ``tactile_gym.rl_envs``
imported so ``edge_follow-v0`` is registered, and it was not run here.

``env_kwargs`` supplies the deployment configuration: the class's own ``env_modes_default`` (``edge_follow_env.py:13-20``)
plus the ``tactile_sensor_name`` key the class reads at ``edge_follow_env.py:59`` but its default dict does not contain
(the demo sets it at ``examples/demo_edge_env.py:23``).  This is configuration, not a Fact or a Limit.

Every Fact cites a line of the clone at commit 28417ebaf52ac325200c4fbd351cd13c6a466f7d.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "tactile_gym/rl_envs/exploration/edge_follow/edge_follow_env.py"
BASE = "tactile_gym/rl_envs/base_tactile_env.py"
INIT = "tactile_gym/rl_envs/__init__.py"


class TactileEdgeFollow(GymnasiumDriver):
    device_id = "tactile_edge_follow"
    env_id = "edge_follow-v0"
    native = "tactile_gym.rl_envs.exploration.edge_follow.edge_follow_env:EdgeFollowEnv"
    backends = {"fake": ".fake:FakeEdgeFollowEnv"}
    action_space_ref = f"{ENV}:140"
    risk = "R1"
    display_name = "tactile_gym edge_follow-v0 (PyBullet simulation)"
    vendor, model = "ac-93", "tactile_gym edge_follow-v0"
    tags = ["tactile", "edge-follow", "pybullet", "robot-arm", "exploration", "reinforcement-learning",
            "simulation", "gymnasium"]
    env_kwargs = {
        "env_modes": {
            "movement_mode": "xy",
            "control_mode": "TCP_velocity_control",
            "noise_mode": "fixed_height",
            "observation_mode": "oracle",
            "reward_mode": "dense",
            "arm_type": "mg400",
            "tactile_sensor_name": "tactip",
        },
    }
    facts = [
        Fact("edge_follow-v0 is registered with entry point "
             "tactile_gym.rl_envs.exploration.edge_follow.edge_follow_env:EdgeFollowEnv",
             source="upstream_code", ref=f"{INIT}:3-6"),
        Fact("EdgeFollowEnv computes a simulation time step of 1/240 s, a control rate of 1/10 s and a velocity "
             "action repeat of floor(control_rate / sim_time_step)", source="upstream_code", ref=f"{ENV}:32-37"),
        Fact("The EdgeFollowEnv constructor's default max_steps is 250", source="upstream_code", ref=f"{ENV}:25"),
        Fact("The termination distance to the goal is 0.01 m", source="upstream_code", ref=f"{ENV}:67"),
        Fact("The mg400 branch sets the TCP limits x -0.150 to +0.150, y -0.11 to +0.11, z -0.1 to +0.1, roll and "
             "pitch 0 to 0 and yaw -pi to +pi", source="upstream_code", ref=f"{ENV}:71-79"),
        Fact("min_action and max_action are -0.25 and 0.25", source="upstream_code", ref=f"{ENV}:140"),
        Fact("The action space is a Box with low=min_action, high=max_action and shape (act_dim,)",
             source="upstream_code", ref=f"{ENV}:168-174"),
        Fact("get_act_dim returns 2 when movement_mode is xy", source="upstream_code", ref=f"{ENV}:478-480"),
        Fact("The oracle observation concatenates the TCP position, the TCP linear velocity, the goal position and "
             "the edge angle", source="upstream_code", ref=f"{ENV}:454-475"),
        Fact("The dense reward is -((1.0 * goal_dist) + (10.0 * edge_dist) + (1.0 * yaw_dist)) with yaw_dist 0",
             source="upstream_code", ref=f"{ENV}:440-451"),
        Fact("The edge angle is drawn uniformly from -pi to pi on every reset", source="upstream_code",
             ref=f"{ENV}:237-240"),
        Fact("The edge length is 0.105 for mg400/magician and 0.175 for the other arms, and the edge height is "
             "0.035", source="upstream_code", ref=f"{ENV}:208-216"),
        Fact("reset returns the starting observation", source="upstream_code", ref=f"{ENV}:333-336"),
        Fact("The observation space for observation_mode oracle is a Dict with one Box from -inf to +inf whose "
             "shape is the oracle observation shape", source="upstream_code", ref=f"{BASE}:76-91"),
        Fact("step returns (observation, reward, done, {}) - the legacy Gym API four-tuple, not the Gymnasium "
             "five-tuple", source="upstream_code", ref=f"{BASE}:166-185"),
        Fact("seed sets the environment RNG through gym.utils.seeding.np_random", source="upstream_code",
             ref=f"{BASE}:61-64"),
        Fact("close disconnects PyBullet and destroys the OpenCV windows", source="upstream_code", ref=f"{BASE}:69-74"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The contract of the backend as deployed.  The upstream environment is a PyBullet rigid-body simulation (F1),
    #: but the delivered fake is an analytic kinematic stand-in with no dynamics, so the package declares F0 and
    #: discloses the difference in the gaps.
    fidelity = {
        "engine": "analytic:tactile_gym/edge_follow-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed=...) or cap.world.seed.v1 fixes the fake's edge angle and start state through "
                     "Python's random.Random; upstream draws them with numpy's gym seeding generator, so one seed "
                     "does not give the same trajectory on the two implementations",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a pure Python 2-D kinematic stand-in for the PyBullet environment: it mirrors the "
            "public reset/seed/step/close surface and the two spaces, integrates the TCP at the control rate and "
            "computes the upstream dense reward from the goal and edge distances; it runs no rigid-body dynamics, "
            "contacts, robot arm IK or PyBullet physics",
            "the fake draws the edge angle and initial state with Python's random.Random; upstream draws them with "
            "numpy's generator, so a seed does not repeat the same trajectory on the two implementations",
            "the observation is the 10-value oracle vector only; the tactile image, visual image and extended "
            "feature observation modes are not modelled, and no tactile sensor is simulated",
            "the upstream environment is PyBullet rigid-body dynamics (F1); this package declares F0 because the "
            "fake integrates no dynamics and was never compared with the upstream environment",
            "no wall-clock pacing: realtime_factor 0, one bridge tick advances one control interval of 0.1 s, which "
            "upstream splits into 24 physics steps of 1/240 s",
            "the sim backend (gym.make('edge_follow-v0')) needs PyBullet, OpenCV, numpy and an import of "
            "tactile_gym.rl_envs so the id is registered; it was not run here",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state pair",
            "no physical robot arm or tactile sensor is modelled and nothing was validated against hardware",
        ],
    }
