"""OpenMHS driver for gh.abmorobotics/rlroverlab: the AAU Rover navigation task (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id = "AAURoverEnv-v0"`` names the registered environment and the
bridge derives the contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with
``action.values`` (a two-element ``Box``), ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend and no
operator-required limit.

The README names Isaac Sim 6.0.1 and Isaac Lab (README.md:4-5, :11); both are outside the pinned clone and not
installed where the gate runs, so the ``fake`` backend is the package's own analytic kinematic stand-in (fake.py).
A backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make("AAURoverEnv-v0")``
(GymnasiumDriver.open_native); that path needs the upstream installation and was not run here.  The clone does not
state numeric action bounds (the Isaac Lab base outside the repository owns the space), so the fake publishes an
unbounded Box and the bridge derives no action-value limit (see the fidelity gaps).

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every constant and rule cites a line of the clone at the pinned commit 578906ad5c3383087aeec038be82b87e05d4ee2c.
This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENTRY = "rover_envs/envs/navigation/entrypoints/rover_env.py"
REGISTER = "rover_envs/envs/navigation/robots/aau_rover/__init__.py"
CFG = "rover_envs/envs/navigation/rover_env_cfg.py"
OBS = "rover_envs/envs/navigation/mdp/observations.py"
ACTION = "rover_envs/mdp/actions/ackermann_actions.py"
TERRAIN = "rover_envs/envs/navigation/utils/terrains/terrain_importer.py"
TERMINATION = "rover_envs/envs/navigation/mdp/terminations.py"


class RLRoverLab(GymnasiumDriver):
    device_id = "rlroverlab"
    env_id = "AAURoverEnv-v0"
    native = "rover_envs.envs.navigation.entrypoints:RoverEnv"
    backends = {"fake": ".fake:FakeAAURoverEnv"}
    display_name = "RLRoverLab AAU Rover navigation (Isaac Lab)"
    vendor, model = "abmoRobotics", "AAURoverEnv-v0"
    tags = ["aau-rover", "navigation", "reinforcement-learning", "isaac-lab", "simulation", "gymnasium"]
    facts = [
        Fact("AAURoverEnv-v0 is registered with entry_point 'rover_envs.envs.navigation.entrypoints:RoverEnv' and "
             "disable_env_checker=True", source="upstream_code", ref=f"{REGISTER}:7-10"),
        Fact("RoverEnv extends Isaac Lab's ManagerBasedRLEnv", source="upstream_code", ref=f"{ENTRY}:12"),
        Fact("RoverEnv.step delegates to ManagerBasedRLEnv.step", source="upstream_code", ref=f"{ENTRY}:47-49"),
        Fact("The navigation task is configured with sim.dt 1/30 s, decimation 6 and episode_length_s 150",
             source="upstream_code", ref=f"{CFG}:352-356"),
        Fact("The action term has action_dim 2, commented as a linear velocity and an angular velocity",
             source="upstream_code", ref=f"{ACTION}:70-72"),
        Fact("AckermannAction.process_actions computes the processed action as raw action times scale plus offset",
             source="upstream_code", ref=f"{ACTION}:86-89"),
        Fact("The AAU rover task sets wheelbase_length 0.849, middle_wheel_distance 0.894, "
             "rear_and_front_wheel_distance 0.77, wheel_radius 0.1, min_steering_radius 0.8 and offset -0.0135",
             source="upstream_code", ref=f"rover_envs/envs/navigation/robots/aau_rover/env_cfg.py:24-34"),
        Fact("The observation group concatenates the last action, distance to target (scale 0.11), heading "
             "(scale 1/pi), angle difference (scale 1/pi) and the height scan (scale 1)",
             source="upstream_code", ref=f"{CFG}:171-190"),
        Fact("The height scanner uses GridPatternCfg(resolution=0.05, size=[5.0, 5.0]) with max_distance=100.0",
             source="upstream_code", ref=f"{CFG}:106-114"),
        Fact("The height scan is the sensor height minus the ray hit height minus 0.26878, the distance between "
             "the sensor and the rover's base", source="upstream_code", ref=f"{OBS}:35-45"),
        Fact("The terrain importer sets target_distance 9.0", source="upstream_code", ref=f"{TERRAIN}:167"),
        Fact("Targets are sampled on a circle of that radius around the environment origin with a uniformly random "
             "angle", source="upstream_code", ref=f"{TERRAIN}:198-214"),
        Fact("The position command resamples every 150.0 s and its heading command is uniform in (-pi, pi)",
             source="upstream_code", ref=f"{CFG}:269-276"),
        Fact("The task terminates on timeout, on success with a distance threshold of 0.18 and a contact force "
             "threshold of 1.0", source="upstream_code", ref=f"{CFG}:244-261"),
        Fact("The success test requires the distance to be below the configured threshold and the absolute heading "
             "error to be below 0.1 rad", source="upstream_code", ref=f"{TERMINATION}:14-31"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:AAURoverEnv-v0 (analytic fake)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) fixes the target and the next episode; the analytic dynamics are deterministic. "
                     "The fake draws its targets with Python's random.Random and the upstream target sampler uses "
                     "torch.rand (terrain_importer.py:208), so a seed gives different trajectories on the two.",
        },
        "timestep_ms": 200.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "F0 analytic model: simulated positions are integrated directly from the two action values; there is "
            "no rigid-body dynamics, no contact, friction, actuator or sensor model, and the wheel-level "
            "Ackermann mapping of ackermann_actions.py:91-96 is not applied",
            "the height-scan observation (a 5.0 m by 5.0 m grid at 0.05 m resolution, rover_env_cfg.py:106-114) is "
            "not modelled: the fake publishes the last action and the three target terms and omits the scan array",
            "the eight reward terms (rover_env_cfg.py:199-241) and the timeout, success, far-from-target and "
            "collision terminations (rover_env_cfg.py:244-261) are not modelled; the fake returns reward 0 and "
            "never reports terminated or truncated",
            "the clone states no numeric action bounds (the Isaac Lab base outside the repository owns the space); "
            "the fake publishes an unbounded Box and the bridge derives no action-value limit",
            "the terrain, the spawn-location sampling, the random spawn yaw and the reset options are not modelled: "
            "the fake starts at the origin with yaw 0",
            "the fake was not compared with the upstream Isaac Sim environment, which was not run (it needs Isaac "
            "Sim/Isaac Lab and a GPU); observations, rewards and random streams differ",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
