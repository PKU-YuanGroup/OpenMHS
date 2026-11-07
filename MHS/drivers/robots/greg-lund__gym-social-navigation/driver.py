"""OpenMHS driver for gh.greg-lund/gym-social-navigation: the SocialNavEnv gym environment.

``GymnasiumDriver`` is configuration only.  ``env_id`` names the registered training environment and the bridge derives
the whole contract from ``SocialNavEnv``'s spaces: ``cap.world.step.v1`` takes ``{ticks, action}`` with
``action.index`` bounded by the 10-value ``Discrete`` action list, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware backend and no
operator-required limit.

The upstream package imports ``gym``, ``numpy`` and ``matplotlib`` and reads the ETH pedestrian data files under
``gym_social_navigation/envs/data``.  The gate does not install or import the clone, so the ``fake`` backend is the
package's own pure Python model of the class in ``fake.py``.  A backend name that ``backends`` does not list (``sim``)
would be served by ``gymnasium.make(env_id)`` (``GymnasiumDriver.open_native``); that path needs the upstream package
and its data files and was not run here (fidelity ``gaps``).

This package is model-authored and unreviewed (``driver.lock.json``).  Every fact cites a line of the clone at the
pinned commit bdc8e72c0f7f738ebe99b6966b1c37af26a342af.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "gym_social_navigation/envs/social_nav_env.py"
REGISTRATION = "gym_social_navigation/__init__.py"


class SocialNav(GymnasiumDriver):
    device_id = "social-nav"
    env_id = "social-nav-train-env-v0"
    env_kwargs = {"test": False}                 # registration kwargs at gym_social_navigation/__init__.py:3-7
    autoreset = True                             # a step after a terminal state starts a new episode
    native = "gym_social_navigation.envs:SocialNavEnv"
    backends = {"fake": ".fake:FakeSocialNavEnv"}
    display_name = "Social Navigation Gym environment (social-nav-train-env-v0)"
    vendor, model = "greg-lund", "gym_social_navigation 0.0.1"
    tags = ["social-navigation", "pedestrian", "dubins-car", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("The package registers social-nav-train-env-v0 with kwargs test=False and social-nav-test-env-v0 with "
             "kwargs test=True; both use the entry point gym_social_navigation.envs:SocialNavEnv",
             source="upstream_code", ref=f"{REGISTRATION}:3-12"),
        Fact("The environment uses data from the ETH Pedestrian dataset", source="vendor_doc", ref="README.md:3"),
        Fact("The test flag selects the data/val files; otherwise the data/train files are used",
             source="upstream_code", ref=f"{ENV}:31-38"),
        Fact("The robot keeps 3 previous states per agent, tracks at most 4 agents within a 10-unit proximity radius, "
             "uses 4 path points and requires a normalised start-goal distance of at least 0.45",
             source="upstream_code", ref=f"{ENV}:11-18"),
        Fact("The maximum robot velocity is 0.75 m/s, velocity is discretised by 0.25 m/s and the fixed steering "
             "angle is 30 degrees", source="upstream_code", ref=f"{ENV}:12-14"),
        Fact("An episode lasts 60 s", source="upstream_code", ref=f"{ENV}:19"),
        Fact("The dataset timestep is 0.4 s and the episode time is divided by it to give the step limit",
             source="upstream_code", ref=f"{ENV}:51-52"),
        Fact("The observation space is a Box of 3 + 2*num_agents*(agent_hist+1) + 2*num_path_points values with "
             "low 0 and high 1", source="upstream_code", ref=f"{ENV}:55-58"),
        Fact("The action list has three left actions, four straight actions (including speed 0) and three right "
             "actions; the action space is Discrete(len(actions))",
             source="upstream_code", ref=f"{ENV}:59-60"),
        Fact("The reward weights are alpha 3.5 for the change in path distance and beta 5 for the change in goal "
             "distance; the goal reward is 10, the collision penalty 20 and the out-of-bounds penalty 15",
             source="upstream_code", ref=f"{ENV}:22-26"),
        Fact("The goal threshold is 0.05 and the collision distance is 0.30",
             source="upstream_code", ref=f"{ENV}:27-28"),
        Fact("A reset picks a random dataset, a random start time and a random start and goal position",
             source="upstream_code", ref=f"{ENV}:192-205"),
        Fact("Step moves the pose with the fixed steering angle and timestep, then computes the reward from the "
             "change in goal distance and path distance", source="upstream_code", ref=f"{ENV}:224-263"),
        Fact("A collision ends the episode with -collision_penalty, reaching the goal with goal_reward, the time "
             "limit with the current reward and leaving the unit square with -out_of_bounds_penalty",
             source="upstream_code", ref=f"{ENV}:266-292"),
        Fact("The class derives from gym.Env", source="upstream_code", ref=f"{ENV}:1-6"),
        Fact("The observation and action spaces are gym.spaces.Box and gym.spaces.Discrete",
             source="upstream_code", ref=f"{ENV}:58-60"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gym:social-nav-train-env-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake's reset(seed=...) repeats its synthetic start, goal and pedestrian trace; upstream "
                     "SocialNavEnv.reset() takes no seed and draws from numpy's global generator, so the sim backend "
                     "is not seeded by cap.world.seed.v1 (it only records the seed for the next reset)",
        },
        "timestep_ms": 400.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic model only: the robot pose moves directly from the action with the fixed steering angle and "
            "the pedestrians follow a canned trace; there are no contacts, friction, actuator, sensor or noise "
            "dynamics",
            "the pedestrian trace in the fake is synthetic test data with two agents, not the ETH Pedestrian "
            "dataset (README.md:3) the clone loads; the real trace is not modelled",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms (0.4 s) only",
            "the fake reproduces the 43-value observation layout, but its start and goal are drawn from a narrow "
            "safe band instead of the clone's full unit square, and no rendering was run",
            "the driver sets autoreset=True: a step after a terminal state resets the world and starts a new "
            "episode, whereas upstream SocialNavEnv requires an explicit reset() and keeps the terminal state",
            "upstream reset() takes no seed or options (social_nav_env.py:186), so the fake's seed/options parameters "
            "and the bridge's seed control do not exist on the upstream environment",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
