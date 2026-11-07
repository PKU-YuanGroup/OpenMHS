"""OpenMHS driver for gh.tommasovandermeer/social-navigation-pyenvs: the SocialGym-v0 environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
runtime contract from the environment object.  The upstream class declares dummy ``Discrete(1)`` action and
observation spaces "just for registration" (``social_gym/social_nav_gym.py:55-57``); the steps that matter are the
robot action types ``ActionXY(vx, vy)`` and ``ActionRot(v, r)`` (``crowd_nav/utils/action.py:3-4``) and the list of
human ``ObservableState`` objects (``social_gym/social_nav_gym.py:100-105``).  The package's fake is therefore a
small, self-contained model of that interface: a two-number robot action box and a five-number observation for one
human.  The real environment still needs ``configure(config)`` and ``set_robot(robot)`` before ``reset``
(``social_nav_gym.py:59-98,125``); it is not served here because gymnasium, pygame, scipy and torch are not
importable in the gate's environment.

The device is simulated (R0): no hardware backend, no e-stop path to a machine, no operator-required bound.  The
``fidelity`` attribute records what the model does and does not reproduce.  Every Fact cites a line of the clone at
the pinned commit f9cd244d3e529247ca1031364de22954717b9493.  This package is model-authored and unreviewed: it is
checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

GYM = "social_gym/social_nav_gym.py"
SIM = "social_gym/social_nav_sim.py"
CONFIG = "crowd_nav/configs/env.config"


class SocialNavGym(GymnasiumDriver):
    device_id = "social-nav"
    env_id = "SocialGym-v0"
    native = "social_gym.social_nav_gym:SocialNavGym"
    backends = {"fake": ".fake:FakeSocialNavGym"}
    display_name = "Social Navigation Gym SocialGym-v0"
    vendor, model = "Tommaso Van Der Meer", "SocialGym-v0"
    tags = ["social-navigation", "crowd-simulation", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("SocialGym-v0 is registered with entry point social_gym.social_nav_gym:SocialNavGym",
             source="upstream_code", ref="social_gym/__init__.py:3-6"),
        Fact("SocialNavGym is both a gymnasium Env and a SocialNavSim", source="upstream_code", ref=f"{GYM}:14"),
        Fact("The action and observation spaces are dummy Discrete(1) spaces, declared just for registration",
             source="upstream_code", ref=f"{GYM}:55-57"),
        Fact("reset raises AttributeError when no robot has been set and accepts only the train, val and test "
             "phases", source="upstream_code", ref=f"{GYM}:125-126"),
        Fact("reset seeds numpy from the phase's case counter, not from a caller-supplied seed",
             source="upstream_code", ref=f"{GYM}:137"),
        Fact("reset puts the robot at the configured start pose, resets the simulator and installs both time steps",
             source="upstream_code", ref=f"{GYM}:213-217"),
        Fact("One environment step applies the same action for robot_time_step/time_step sub-steps and advances "
             "global time by time_step in each", source="upstream_code", ref=f"{GYM}:240-245"),
        Fact("The robot action is ActionXY(vx, vy) with holonomic kinematics and ActionRot(v, r) with unicycle "
             "kinematics", source="upstream_code", ref="crowd_nav/utils/action.py:3-4"),
        Fact("The unicycle update moves by v in the direction yaw+r and then adds r to yaw; the holonomic update "
             "moves by (vx, vy)", source="upstream_code", ref="social_gym/src/robot_agent.py:116-136"),
        Fact("The repository's example env.config sets time_limit 50 s, time_step 0.0125 s and robot_time_step "
             "0.25 s", source="upstream_code", ref=f"{CONFIG}:2-4"),
        Fact("configure reads the time steps and rejects a robot time step that is not a multiple of the time step",
             source="upstream_code", ref=f"{GYM}:61-65"),
        Fact("The observation is the list of the humans' observable states, computed by "
             "compute_humans_observable_state", source="upstream_code", ref=f"{GYM}:100-105"),
        Fact("An observable human state carries px, py, vx, vy and radius", source="upstream_code",
             ref="crowd_nav/utils/state.py:24-30"),
        Fact("The reward is zero and truncated at time_limit-1; a collision pays collision_penalty and terminates; "
             "reaching the goal pays success_reward and terminates; a close pass pays a discomfort penalty",
             source="upstream_code", ref=f"{SIM}:1004-1028"),
        Fact("The example env.config sets success_reward 1, collision_penalty -0.25, discomfort_dist 0.2 and "
             "discomfort_penalty_factor 0.5", source="upstream_code", ref=f"{CONFIG}:11-14"),
        Fact("The constructor starts the circular_crossing scenario with the robot inserted", source="upstream_code",
             ref=f"{GYM}:25"),
        Fact("The circular crossing generator defaults to 10 actors, a circle radius of 7 and a robot radius of "
             "0.3", source="upstream_code", ref=f"{SIM}:207-209"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the last observation and counters stay readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity).  The bridge would derive the engine,
    #: determinism and lockstep clock from the environment; they are written out so the contract reads in one place.
    fidelity = {
        "engine": "social_gym:SocialGym-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake draws its one human's start offset from random.Random(seed) and then integrates "
                     "deterministically, so one seed and one action sequence repeat an observation; the upstream "
                     "reset seeds numpy from its phase case counter instead of a caller seed "
                     f"({GYM}:137), so the two do not repeat each other",
        },
        "timestep_ms": 250.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the upstream action and observation spaces are dummy Discrete(1) values for registration "
            f"({GYM}:55-57); the fake exposes the actual two-number robot action (ActionXY or ActionRot, "
            "crowd_nav/utils/action.py:3-4) as a Box and the five-number ObservableState of one human "
            "(crowd_nav/utils/state.py:24-30) instead of the ten-actor default (social_gym/social_nav_sim.py:209) "
            "or the five-human example configuration (crowd_nav/configs/env.config:23)",
            "one simulated human with a constant velocity: no social force, headed social force or ORCA model, no "
            "walls or other humans and no pygame rendering",
            "the upstream reset requires configure(config) and set_robot(robot) first "
            f"({GYM}:59-98,125); the fake is self-contained and does not model those setup calls",
            "no wall-clock pacing: realtime_factor 0; one step advances 0.25 s of simulated time, which is 20 "
            "sub-steps of the example time_step 0.0125 s (social_gym/social_nav_gym.py:240-245)",
            "the fake was never compared with the upstream environment: gymnasium, pygame, scipy and torch are "
            "not importable where the gate ran, and the upstream package was not installed",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
