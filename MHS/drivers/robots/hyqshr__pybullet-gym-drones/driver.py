"""OpenMHS driver for gh.hyqshr/pybullet-gym-drones: the DroneNavigation-v0 environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
contract from its spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with a 3-element ``action.values`` bounded
by the Box action space ``[-0.1, 0.1]`` on each axis, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The upstream class is an old-style ``gym.Env``: ``reset()`` returns the
observation, ``step(action)`` returns a 4-tuple ``(observation, reward, done, info)`` and ``seed(seed)`` reseeds the
environment; the Gymnasium bridge has explicit fallbacks for both shapes (mhs/bridge/gymnasium.py).  The device is
simulated (R0), so it has no hardware backend, no e-stop path to a machine and no operator-required limit.

The gate cannot import the upstream environment: the clone imports ``gym``, ``pybullet``, ``numpy``,
``matplotlib`` and the clone's own modules (drone_envs/envs/drone_env_v0.py:1-11), and package code never imports or
runs the clone.  The declared ``fake`` backend is therefore the package's own pure Python kinematic stand-in
(fake.py).  A backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)``
(GymnasiumDriver.open_native); that path needs gym and pybullet and was not run here.

This package covers DroneNavigation-v0 only.  The second registered environment, DroneNavigation-v1
(drone_envs/__init__.py:7-10), adds a 16 x 16 camera and 30 obstacle cubes and is not covered.

The ``fidelity`` attribute is the fidelity contract of the model as deployed on the checked fake backend (spec
05-fidelity FID-002): analytic, level F0, seeded, 1/30 s timestep, lockstep clock, full reset, no snapshot.  Every
Fact cites a line of the clone at the pinned commit 19a318c92914402d57a4dc9d1cb28cb72db268b3.  The package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

V0 = "drone_envs/envs/drone_env_v0.py"
CONFIG = "drone_envs/config.py"
DRONE = "drone_envs/resources/drone.py"
URDF = "drone_envs/resources/drone.urdf"
REGISTER = "drone_envs/__init__.py"


class DroneNavigationV0(GymnasiumDriver):
    device_id = "drone-navigation-v0"
    env_id = "DroneNavigation-v0"
    native = "drone_envs.envs:DroneNavigationV0"
    backends = {"fake": ".fake:FakeDroneNavigationV0"}
    display_name = "Pybullet-Gym-Drone DroneNavigation-v0"
    vendor, model = "hyqshr", "DroneNavigation-v0"
    tags = ["drone", "navigation", "reinforcement-learning", "simulation", "pybullet", "gym"]
    facts = [
        Fact("DroneNavigation-v0 is registered with id 'DroneNavigation-v0' and entry point "
             "'drone_envs.envs:DroneNavigationV0'", source="upstream_code", ref=f"{REGISTER}:2-5"),
        Fact("The action space is a 3-element Box with low [-0.1, -0.1, -0.1] and high [0.1, 0.1, 0.1]",
             source="upstream_code", ref=f"{V0}:24-27"),
        Fact("The observation space is 9 elements: drone x and y in [-12, 12], z in [0, 12], each velocity in "
             "[-3, 3], goal x and y in [-9, 9] and goal z in [0, 9]", source="upstream_code",
             ref=f"{CONFIG}:14-33"),
        Fact("A step applies the action, advances the pybullet simulation, reads the drone observation and returns "
             "the observation concatenated with the goal, the reward, done and reach_target", source="upstream_code",
             ref=f"{V0}:64-76"),
        Fact("The simulation timestep is set to 1/30 s", source="upstream_code", ref=f"{V0}:51-53"),
        Fact("Each thrust component is clipped to [-0.1, 0.1] and applied as an external force to link 4 in the "
             "link frame", source="upstream_code", ref=f"{DRONE}:19-35"),
        Fact("The drone is loaded at base position [0, 0, 0.1]", source="upstream_code", ref=f"{DRONE}:10-14"),
        Fact("The drone base link mass is 0.027 kg", source="upstream_code", ref=f"{URDF}:11"),
        Fact("The drone observation is the base position followed by the base linear velocity", source="upstream_code",
             ref=f"{DRONE}:38-49"),
        Fact("A reset resets the simulation, reloads the plane and drone, draws a new goal and returns the initial "
             "observation", source="upstream_code", ref=f"{V0}:82-97"),
        Fact("The goal is drawn with x and y uniform in [5, 9] or [-9, -5] and z uniform in [5, 9]",
             source="upstream_code", ref=f"{V0}:135-142"),
        Fact("The reward is the decrease in distance to the goal; leaving x or y at +-12 or z at or below 0 or at or "
             "above 12 subtracts 1 and ends the episode, and a distance below 2 adds 50 and sets reach_target",
             source="upstream_code", ref=f"{V0}:148-168"),
        Fact("seed() reseeds the environment random generator from gym.utils.seeding.np_random and returns the seed",
             source="upstream_code", ref=f"{V0}:78-80"),
        Fact("The upstream run script creates the environment with gym.make(env_name)", source="upstream_code",
             ref="run.py:87-92"),
        Fact("The project is a PyBullet and OpenAI Gym environment", source="vendor_doc", ref="README.md:3"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    fidelity = {
        "engine": "analytic",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the goal draw comes from the environment generator seeded by seed(); the kinematic update has "
                     "no randomness, so one seed and one action sequence give the same observations in this package's "
                     "fake, while the upstream pybullet model is not modelled and was not compared",
        },
        "timestep_ms": 1000.0 / 30.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the checked fake is a kinematic point-mass stand-in: no rigid-body orientation, gravity, contacts, drag, "
            "actuator, sensor or noise model; it does not reproduce the upstream pybullet model (README.md:3)",
            "the fake advances velocity and position with dt = 1/30 s from the base link mass 0.027 kg and ignores the "
            "plane, the goal body and collisions, so its trajectories differ from the upstream simulator and were "
            "never compared with it",
            "no wall-clock pacing: realtime_factor 0 and only cap.world.step.v1 advances simulated time",
            "DroneNavigation-v1 (the 16 x 16 camera and the 30 obstacle cubes) and rendering are not modelled; this "
            "package covers DroneNavigation-v0 only",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state",
        ],
    }
