"""OpenMHS driver for gh.gongxudong/fly-craft: the FlyCraft-v0 Gymnasium environment.

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the contract from
the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{values}`` of the
three-element Box of the default ``guidance_law_mode`` configuration, ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required limit.

The gate never imports or runs the clone.  Upstream FlyCraft needs platform-specific compiled ``*.so``/``*.dll``
libraries and is documented as Linux/Windows only (README.md:74), so the ``fake`` backend is this package's own
pure Python stand-in (fake.py).  A backend name that ``backends`` does not list (``sim``) is served by
``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path needs the upstream package installed and was
not run here.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002).  It is F0: the
fake models the spaces and the reset/step/reward/termination protocol, not the F16 flight dynamics.  This package
is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "flycraft/env.py"
TASK = "flycraft/tasks/velocity_vector_control_task.py"
PLANE = "flycraft/planes/f16_plane.py"
TERMINATION = "flycraft/terminations/termination_base.py"
TIMEOUT = "flycraft/terminations/timeout_termination.py"
CONFIG = "flycraft/configs/NMR.json"


class FlyCraft(GymnasiumDriver):
    device_id = "flycraft"
    env_id = "FlyCraft-v0"
    native = "flycraft.env:FlyCraftEnv"
    backends = {"fake": ".fake:FakeFlyCraftEnv"}
    action_space_ref = f"{PLANE}:161-172"
    display_name = "FlyCraft-v0 (fixed-wing UAV velocity vector control)"
    vendor, model = "Xudong Gong", "FlyCraft-v0"
    tags = ["fixed-wing", "uav", "velocity-vector-control", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("FlyCraft is a goal-conditioned reinforcement learning environment for fixed-wing UAV velocity vector "
             "control based on Gymnasium", source="vendor_doc", ref="README.md:3"),
        Fact("FlyCraft-v0 is registered with entry point flycraft.env:FlyCraftEnv", source="upstream_code",
             ref="flycraft/__init__.py:8-10"),
        Fact("FlyCraft-Level-Turn-v0 is registered with entry point flycraft.env_level_turn:FlyCraftLevelTurnEnv",
             source="upstream_code", ref="flycraft/__init__.py:13-15"),
        Fact("FlyCraftEnv is a gymnasium.Env subclass", source="upstream_code", ref=f"{ENV}:20"),
        Fact("The observation space is a Dict of three Boxes named observation, desired_goal and achieved_goal",
             source="upstream_code", ref=f"{ENV}:34-40"),
        Fact("The observation vector is ordered phi, theta, psi, v, mu, chi, p, h", source="upstream_code",
             ref=f"{ENV}:36"),
        Fact("The observation lower bounds are phi -180, theta -90, psi -180, v 0, mu -90, chi -180, p -300 and h 0",
             source="upstream_code", ref=f"{TASK}:454"),
        Fact("The observation upper bounds are phi 180, theta 90, psi 180, v 1000, mu 90, chi 180, p 300 and h 20000",
             source="upstream_code", ref=f"{TASK}:464"),
        Fact("The desired and achieved goal vector is [v, mu, chi] with bounds v 0 to 1000, mu -90 to 90 and chi "
             "-180 to 180", source="upstream_code", ref=f"{TASK}:467-474"),
        Fact("The action space is a Box built from F16Plane.get_action_lower_bounds and get_action_higher_bounds "
             "for the configured control mode", source="upstream_code", ref=f"{ENV}:54-59"),
        Fact("In guidance_law_mode the action is [p, nz, pla] with bounds p -180 to 180, nz -4 to 9 and pla 0 to 1",
             source="upstream_code", ref=f"{PLANE}:161-172"),
        Fact("In end_to_end_mode the action is [ail, ele, rud, pla] with bounds ail -21.5 to 21.5, ele -25 to 25, "
             "rud -30 to 30 and pla 0 to 1", source="upstream_code", ref=f"{PLANE}:163-174"),
        Fact("The plane's step time is 1/step_frequence seconds", source="upstream_code",
             ref=f"{PLANE}:144-145"),
        Fact("The default NMR configuration sets step_frequence to 10", source="upstream_code",
             ref=f"{CONFIG}:8"),
        Fact("reset(seed, options) reseeds the task and goal sampler when a seed is given, resets the plane and the "
             "task, and returns (observation, info)", source="upstream_code", ref=f"{ENV}:91-107"),
        Fact("step(action) returns (observation, reward, terminated, truncated, info)", source="upstream_code",
             ref=f"{ENV}:234"),
        Fact("The timeout termination reports terminated and truncated when step_cnt >= max_episode_steps - 1",
             source="upstream_code", ref=f"{TIMEOUT}:22-26"),
        Fact("max_episode_steps is max_simulate_time times step_frequence", source="upstream_code",
             ref=f"{TERMINATION}:106-107"),
        Fact("Upstream needs dynamic *.so/*.dll libraries and documents Linux or Windows only",
             source="vendor_doc", ref="README.md:74"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the
    #: engine, determinism and lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "flycraft:analytic-stand-in (F16 flight model absent)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake draws the goal from Python's random.Random(seed) and its state update is "
                     "deterministic, so one seed plus one action sequence repeats a trajectory on this fake; "
                     "upstream draws from numpy's Generator through its goal sampler, so a seed gives different "
                     "trajectories on the two implementations",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "F0: the F16 flight dynamics, control law and aerodynamic model are not modelled by the fake; its "
            "observation update is a kinematic placeholder and makes no claim about forces, motion or contacts",
            "the reward and termination rules of the fake are simplified: upstream combines the dense reward with "
            "reach-target, crash, extreme-state, timeout, continuously-move-away, continuously-roll and "
            "negative-overload/big-phi terminations; the fake models only the timeout truncation",
            "the fake draws a uniform goal with Python's random.Random; upstream uses numpy's Generator and the "
            "configured goal sampler (fixed goal, random range or the available-goals file) with optional noise",
            "timestep_ms 100 is the default NMR.json step_frequence of 10 Hz; a custom_config or config_file can "
            "change step_frequence, and the contract does not follow it",
            "the fake serves the default guidance_law_mode action [p, nz, pla]; an end_to_end_mode configuration "
            "(the four values ail, ele, rud, pla) is not modelled",
            "the upstream environment needs platform-specific compiled libraries and is documented as Linux or "
            "Windows only; it was never imported or run here, so the fake was not compared with it and returns "
            "Python lists where upstream returns float32 numpy arrays",
            "snapshot and restore are not offered: FlyCraftEnv exposes no get_state/set_state",
        ],
    }
