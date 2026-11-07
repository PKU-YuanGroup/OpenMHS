"""OpenMHS driver for gh.kousheekc/isaac_drone_racer: the Isaac-Drone-Racer-v0 Gymnasium environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}``, ``cap.world.reset.v1``
takes ``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): it has no
hardware backend, no e-stop path to a machine and no operator-required limit.

The registered entry point is ``isaaclab.envs:ManagerBasedRLEnv`` (tasks/drone_racer/__init__.py:15), a class of
the external Isaac Lab package that is not part of this clone, and the card's entry symbol is the environment
configuration class ``DroneRacerEnvCfg``.  ``native`` therefore names that configuration class, as the card's
override requires, while ``env_id`` names the registration that ``gymnasium.make`` would resolve.  Gate G7 checks
the fake against the configuration class; the names of the Gymnasium environment interface (``reset``, ``step``,
``action_space``, ``observation_space``, ``close``) are reported as ``MAYBE_ABSENT`` warnings because the base
lies outside the clone (driver-authoring.md, G7).

The gate cannot open the upstream environment: it needs Isaac Sim 4.5.0 (README.md:7), Isaac Lab v2.1.0
(README.md:44-48) and a GPU, and package code never imports the clone.  The ``fake`` backend is therefore a small
pure Python stand-in for the environment (fake.py); it models the vertical thrust of the four rotor commands and
the episode limits of the configuration, and it says in the fidelity ``gaps`` what it does not model.  A backend
name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver
.open_native); that path was not run here.

Every constant and rule cites a line of the clone at the pinned commit
(d530f67768d53701454f406e4da967e0e9c30842).  This package is model-authored and unreviewed: it is checked on the
fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

INIT = "tasks/drone_racer/__init__.py"
CFG = "tasks/drone_racer/drone_racer_env_cfg.py"
ACTIONS = "tasks/drone_racer/mdp/actions.py"
DRONE = "assets/five_in_drone.py"


class DroneRacer(GymnasiumDriver):
    device_id = "isaac-drone-racer"
    env_id = "Isaac-Drone-Racer-v0"
    native = "tasks.drone_racer.drone_racer_env_cfg:DroneRacerEnvCfg"
    backends = {"fake": ".fake:FakeDroneRacerEnv"}
    display_name = "Isaac Drone Racer (Isaac Lab Gymnasium environment)"
    vendor, model = "Kousheek Chakraborty", "Isaac-Drone-Racer-v0"
    tags = ["drone", "racing", "quadrotor", "reinforcement-learning", "simulation", "isaaclab", "gymnasium"]
    facts = [
        Fact("The drone racing task is registered as a standard Gym environment with the ID Isaac-Drone-Racer-v0",
             source="vendor_doc", ref="README.md:62"),
        Fact("Isaac-Drone-Racer-v0 is registered with entry_point isaaclab.envs:ManagerBasedRLEnv, the environment "
             "configuration DroneRacerEnvCfg and the env checker disabled", source="upstream_code",
             ref=f"{INIT}:13-20"),
        Fact("Isaac-Drone-Racer-Play-v0 is registered the same way with the configuration DroneRacerEnvCfg_PLAY",
             source="upstream_code", ref=f"{INIT}:23-30"),
        Fact("The project is an open-source simulation framework for autonomous drone racing built on IsaacLab",
             source="vendor_doc", ref="README.md:12"),
        Fact("The Isaac Sim badge pins version 4.5.0", source="vendor_doc", ref="README.md:7"),
        Fact("The setup instructions require the IsaacLab v2.1.0 release tag", source="vendor_doc",
             ref="README.md:44-48"),
        Fact("The default scene spawns 4096 environments with env_spacing 0.0", source="upstream_code", ref=f"{CFG}:197"),
        Fact("The policy observation group concatenates the position, attitude, linear velocity, angular velocity, "
             "target position in the body frame and last action terms, with corruption disabled", source="upstream_code",
             ref=f"{CFG}:88-97"),
        Fact("The default configuration disables the critic observation group (observations.critic = None)",
             source="upstream_code", ref=f"{CFG}:215"),
        Fact("The environment uses decimation 4 and a simulation step of 1/400 s, so one environment step advances "
             "0.01 s of simulated time", source="upstream_code", ref=f"{CFG}:220-226"),
        Fact("The episode length is 20 s (episode_length_s = 20)", source="upstream_code", ref=f"{CFG}:221"),
        Fact("The episode terminates on a time out, when the drone is more than 20 m from the target gate, and on an "
             "illegal contact above threshold 0.01", source="upstream_code", ref=f"{CFG}:187-191"),
        Fact("The track configuration places seven gates; gate 1 is at (0.0, 0.0, 1.0) and gate 4 at "
             "(-5.0, -5.0, 2.5)", source="upstream_code", ref=f"{CFG}:39-49"),
        Fact("The reset pose range is x from -3.5 to -1.5, y from -0.5 to 0.5 and z written as (1.5, 0.5), with all "
             "linear and angular velocities zero", source="upstream_code", ref=f"{CFG}:128-139"),
        Fact("The default action configuration disables the motor model (use_motor_model=False)", source="upstream_code",
             ref=f"{CFG}:77"),
        Fact("The action term stores four raw actions per environment", source="upstream_code", ref=f"{ACTIONS}:44"),
        Fact("The raw action is clamped to [-1, 1] and mapped by (x + 1) / 2 to a motor speed up to omega_max",
             source="upstream_code", ref=f"{ACTIONS}:97-99"),
        Fact("The action configuration declares arm length 0.035 m, thrust coefficient 2.25e-7 and omega_max 5145 "
             "rad/s, the last computed from a 1950 KV motor on a 6S battery at 4.2 V per cell", source="upstream_code",
             ref=f"{ACTIONS}:144-155"),
        Fact("The processed action is applied as a body-z thrust and a three-axis body moment", source="upstream_code",
             ref=f"{ACTIONS}:106-109"),
        Fact("The drone is a simulated USD articulation spawned from assets/5_in_drone/5_in_drone.usd, not a "
             "hardware connection", source="upstream_code", ref=f"{DRONE}:28-31"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: determinism kind and lockstep clock; they are written out so the whole contract reads in one place.  The
    #: contract describes the upstream Isaac Lab environment; the fake backend is analytic and the gaps say so.
    fidelity = {
        "engine": "isaaclab:Isaac-Drone-Racer-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the state this package's fake starts from; the upstream "
                     "environment runs on Isaac Sim/PhysX and its determinism was not measured here, so no exact claim "
                     "is made",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend integrates only the total rotor thrust along the body z axis: the rigid-body flight "
            "dynamics, the body moments, aerodynamic drag, contacts and the USD drone asset of the upstream Isaac "
            "Sim scene are not modelled",
            "the observation layout is inferred from the six concatenated policy terms of the environment "
            "configuration (20 values) and was not read from a running Isaac Sim environment",
            "the fake action bounds of -1 to 1 per component mirror the clamp of the action term; the gym action "
            "space is created by isaaclab.envs.ManagerBasedRLEnv outside the clone and was not read",
            "the 20 s time limit and the 20 m flyaway termination are modelled; the collision termination, the "
            "gate-passing command logic and the reward terms are not (the fake reward is always 0.0)",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "the environment was never run: Isaac Sim 4.5.0, Isaac Lab v2.1.0 and a GPU are required, the fake was "
            "not compared with the upstream environment and nothing was validated against a physical device",
        ],
    }
