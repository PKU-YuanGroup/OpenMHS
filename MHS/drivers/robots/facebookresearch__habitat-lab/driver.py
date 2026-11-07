"""OpenMHS driver for gh.facebookresearch/habitat-lab: the Gym wrapper of a Habitat-Lab environment.

Habitat-Lab is a modular embodied-AI environment layer; the simulation engine itself is Habitat-Sim, a separate
repository (``README.md:26``).  ``habitat.env_task`` defaults to ``GymHabitatEnv``
(``habitat-lab/habitat/config/default_structured_configs.py:1922``), a ``gym.Wrapper`` that builds an ``RLTaskEnv``
and wraps it in ``HabGymWrapper`` (``habitat-lab/habitat/core/environments.py:116-128``).  The card's entry symbol is
that class; ``gym.make("Habitat-v0")`` reaches it through ``_make_habitat_gym_env``
(``habitat-lab/habitat/gym/gym_definitions.py:80-110``).

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment, ``env_kwargs`` passes its
``cfg_file_path`` and the bridge derives ``cap.world.step/reset/seed`` from the environment's spaces.  For the
point-navigation test configuration the action space is ``Discrete(4)``
(``test/test_gym_wrapper.py:89-93``) over stop, move_forward, turn_left and turn_right
(``habitat-lab/habitat/config/habitat/task/pointnav.yaml:3-7``), the observations are a dict of the two simulator
sensors plus the 2-element point goal (``habitat-lab/habitat/config/default_structured_configs.py:405-406``), and a
step returns ``(observation, reward, done, info)`` (``habitat-lab/habitat/gym/gym_wrapper.py:254-281``).

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  The gate cannot import habitat-lab or habitat-sim, so the ``fake`` backend is the package's own pure Python
point-navigation stand-in (``fake.py``).  A backend name that ``backends`` does not list (``sim``) is served by
``gym.make(env_id, **env_kwargs)`` (GymnasiumDriver.open_native); that path needs habitat-sim with the habitat_test
dataset and was not run here.

The ``fidelity`` attribute describes the model as deployed: the fake is kinematic (F0), not the habitat-sim
rigid-body engine, so it claims no contacts, actuators or physics timestep.  Every fact cites a line of the clone at
the pinned commit (0fb6f43ffe806a8088a171b036336c093bcf604e).  This package is model-authored and unreviewed; it is
checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

POINTNAV_CONFIG = "habitat-lab/habitat/config/benchmark/nav/pointnav/pointnav_habitat_test.yaml"
POINTNAV_TASK = "habitat-lab/habitat/config/habitat/task/pointnav.yaml"
GYM_DEFINITIONS = "habitat-lab/habitat/gym/gym_definitions.py"
GYM_WRAPPER = "habitat-lab/habitat/gym/gym_wrapper.py"
STRUCTURED_CONFIGS = "habitat-lab/habitat/config/default_structured_configs.py"
ENVIRONMENTS = "habitat-lab/habitat/core/environments.py"
NAV = "habitat-lab/habitat/tasks/nav/nav.py"


class HabitatPointNav(GymnasiumDriver):
    device_id = "habitat"
    env_id = "Habitat-v0"
    #: ``_make_habitat_gym_env(cfg_file_path, override_options=None, use_render_mode=False)``
    #: (``habitat-lab/habitat/gym/gym_definitions.py:80-83``); the point-nav test config has no render sensor.
    env_kwargs = {"cfg_file_path": POINTNAV_CONFIG}
    native = "habitat.core.environments:GymHabitatEnv"
    backends = {"fake": ".fake:FakeHabitatEnv"}
    display_name = "Habitat-Lab point-navigation Gym environment"
    vendor, model = "Meta AI (facebookresearch)", "Habitat-v0 (pointnav_habitat_test.yaml)"
    tags = ["habitat", "embodied-ai", "pointnav", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("GymHabitatEnv is a gym.Wrapper that builds an RLTaskEnv and wraps it in HabGymWrapper to expose the "
             "standard Gym API", source="upstream_code", ref=f"{ENVIRONMENTS}:116-128"),
        Fact("make_gym_from_config returns the gym.Env for the environment class named by habitat.env_task",
             source="upstream_code", ref=f"{GYM_DEFINITIONS}:49-60"),
        Fact("Habitat-v0 is registered with entry point _make_habitat_gym_env, which takes cfg_file_path and "
             "override_options", source="upstream_code", ref=f"{GYM_DEFINITIONS}:80-110"),
        Fact("HabGymWrapper.step returns the legacy four-value tuple (observation, reward, done, info)",
             source="upstream_code", ref=f"{GYM_WRAPPER}:254-281"),
        Fact("HabGymWrapper.reset resets the wrapped environment and returns its initial observation",
             source="upstream_code", ref=f"{GYM_WRAPPER}:316-327"),
        Fact("The wrapper flattens a continuous action space into one Box, uses Discrete(n) for a single discrete "
             "action, and Discrete(len(actions)) otherwise", source="upstream_code", ref=f"{GYM_WRAPPER}:102-123"),
        Fact("For the point-navigation test configuration the gym action space is Discrete(4)",
             source="upstream_code", ref="test/test_gym_wrapper.py:89-112"),
        Fact("The point-navigation task defines the four actions stop, move_forward, turn_left and turn_right",
             source="upstream_code", ref=f"{POINTNAV_TASK}:3-7"),
        Fact("move_forward advances the agent by forward_step_size 0.25 m and the turn actions rotate it by "
             "turn_angle 10 degrees", source="upstream_code", ref=f"{STRUCTURED_CONFIGS}:1791-1792"),
        Fact("The point-navigation test environment allows 500 steps per episode", source="upstream_code",
             ref=f"{POINTNAV_CONFIG}:10"),
        Fact("The point-navigation test environment's rgb and depth sensors are 256 by 256 pixels",
             source="upstream_code", ref=f"{POINTNAV_CONFIG}:14-20"),
        Fact("The point-goal observation is polar with dimensionality 2", source="upstream_code",
             ref=f"{STRUCTURED_CONFIGS}:405-406"),
        Fact("The distance_to_goal_reward measure is -(new_distance - previous_distance), the decrease of the "
             "distance to the goal", source="upstream_code", ref=f"{NAV}:1004-1006"),
        Fact("The depth sensor's max_depth is 10.0", source="upstream_code", ref=f"{STRUCTURED_CONFIGS}:1573"),
        Fact("habitat.env_task defaults to GymHabitatEnv", source="upstream_code",
             ref=f"{STRUCTURED_CONFIGS}:1922"),
    ]
    safe_state = ("the simulation stops advancing: the runtime latches the e-stop and refuses further step, reset "
                  "and seed calls until mhs.safety.reset clears it; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2): the fake is a kinematic,
    #: event-driven stand-in for the habitat-sim environment, so level F0 and timestep 0 are claimed here.  The real
    #: engine (not run) advances rigid-body physics with contacts and an articulated agent; habitat-sim's physics
    #: timestep is defined in that separate repository, not in this clone.
    fidelity = {
        "engine": "habitat-lab:gym.Habitat-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake seeds its goal placement with reset(seed=...) and its motion is deterministic, so one "
                     "seed repeats an episode; the upstream legacy gym wrapper seeds through env.seed(), which the "
                     "bridge falls back to, and habitat-sim's own randomisation was not exercised",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic point-navigation stand-in: no rigid-body dynamics, contacts, articulated arm, grasping or "
            "physics; the agent moves by forward_step_size and rotates by turn_angle directly",
            "timestep_ms is 0 because this model is event-driven analytic; habitat-sim's physics timestep lives in "
            "the separate habitat-sim repository and was not run",
            "no wall-clock pacing: realtime_factor 0 and no control-loop timing is modelled",
            "the rgb and depth observations are 12- and 4-number flat stand-ins; the point-nav test config "
            "declares 256 x 256 x 3 rgb and 256 x 256 x 1 depth sensors, and the fake does not render",
            "the reward models only the distance-to-goal decrease; the slack reward, success reward and "
            "termination by success are not modelled",
            "the fake was never compared with habitat-sim or a real run; snapshot and restore are not offered",
        ],
    }
