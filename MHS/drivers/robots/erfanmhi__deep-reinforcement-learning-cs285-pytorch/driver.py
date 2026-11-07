"""OpenMHS driver for gh.erfanmhi/deep-reinforcement-learning-cs285-pytorch: the CS285 obstacle environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with
``action.values`` a Box of two elements bounded by -0.99 and 0.99, ``cap.world.reset.v1`` takes ``{seed, options}``
and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to
a machine and no operator-required limit.

Only ``obstacles-cs285-v0`` is served; the card's other entry symbols (AntEnv, HalfCheetahEnv, Reacher7DOFEnv) are
MuJoCo environments that need MuJoCo 2.1 and mujoco-py (README.md:102-119) and are left for their own packages.

The gate never imports the clone, and this package's fake needs neither gym nor numpy, so the ``fake`` backend is a
pure Python obstacle environment (fake.py).  A backend name that ``backends`` does not list (``sim``) is served by
``gym.make(env_id)`` (GymnasiumDriver.open_native); that path needs the upstream package (gym 0.17.2 and numpy,
plus matplotlib for rendering) and was not run here.

The ``fidelity`` attribute is the complete contract of the model as deployed (spec 05-fidelity FID-002).  Every
constant and rule cites a line of the clone at commit 6da04f367e52a451c202ae7e5477994c1d149baf.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

OBSTACLES = "hw4/cs285/envs/obstacles/obstacles_env.py"
REGISTRATION = "hw4/cs285/envs/obstacles/__init__.py"


class CS285Obstacles(GymnasiumDriver):
    device_id = "obstacles"
    env_id = "obstacles-cs285-v0"
    native = "cs285.envs.obstacles:Obstacles"
    backends = {"fake": ".fake:FakeObstacles"}
    display_name = "CS285 obstacles-cs285-v0 (2D navigation)"
    vendor, model = "erfanmhi", "obstacles-cs285-v0"
    tags = ["obstacles", "navigation", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The environment is registered as obstacles-cs285-v0 with max_episode_steps=500",
             source="upstream_code", ref=f"{REGISTRATION}:3-7"),
        Fact("The action dimension is 2 and the observation dimension is 4",
             source="upstream_code", ref=f"{OBSTACLES}:11-12"),
        Fact("The action space is a Box of 2 elements bounded by boundary_min -0.99 and boundary_max 0.99",
             source="upstream_code", ref=f"{OBSTACLES}:13-18"),
        Fact("The observation space is a Box of 4 elements bounded by -inf and inf",
             source="upstream_code", ref=f"{OBSTACLES}:20-22"),
        Fact("The constructor defaults are start [-0.5, 0.75], end [0.7, -0.8] and random_starts True",
             source="upstream_code", ref=f"{OBSTACLES}:6"),
        Fact("The five obstacles are axis-aligned rectangles [x of top left, y of top left, width x, height y]",
             source="upstream_code", ref=f"{OBSTACLES}:32-38"),
        Fact("seed(seed) seeds numpy's global random generator",
             source="upstream_code", ref=f"{OBSTACLES}:43-44"),
        Fact("With random_starts, reset draws x uniformly between boundary_min and boundary_min+1.25 and y "
             "between boundary_max-0.4 and boundary_max, and re-draws while the point is invalid",
             source="upstream_code", ref=f"{OBSTACLES}:48-55"),
        Fact("reset sets current to the drawn start and end to the configured end, clears the counter and "
             "returns the observation", source="upstream_code", ref=f"{OBSTACLES}:59-78"),
        Fact("The observation is [current x, current y, end x, end y]",
             source="upstream_code", ref=f"{OBSTACLES}:82-83"),
        Fact("The score is the negation of the absolute current-to-end difference per axis",
             source="upstream_code", ref=f"{OBSTACLES}:85-89"),
        Fact("The done threshold is eps 0.1", source="upstream_code", ref=f"{OBSTACLES}:40"),
        Fact("The reward is minus the Euclidean distance between current and end; done is 1 when the distance "
             "is below eps or the current position is out of the boundary", source="upstream_code",
             ref=f"{OBSTACLES}:114-132"),
        Fact("step increments the counter, clips the action to [-1, 1], scales it by 0.1, and moves current "
             "only when the new point is valid", source="upstream_code", ref=f"{OBSTACLES}:139-147"),
        Fact("step returns (observation, reward, done, info) and has no truncated flag",
             source="upstream_code", ref=f"{OBSTACLES}:149-156"),
        Fact("render returns a matplotlib RGB image of the boundaries, obstacles, current position and end",
             source="upstream_code", ref=f"{OBSTACLES}:162-192"),
        Fact("A point is valid when it is strictly inside the boundary on both axes and not strictly inside "
             "any obstacle rectangle", source="upstream_code", ref=f"{OBSTACLES}:194-225"),
    ]
    safe_state = ("the simulation stops advancing: no step, seed or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine, the
    #: determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "analytic:cs285.envs.obstacles",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) seeds the fake's Python random generator and the dynamics are deterministic, so "
                     "one implementation repeats a trajectory for the same seed and actions; upstream draws the "
                     "start from numpy's global generator and ignores seed 0, so the same seed gives different "
                     "start positions on the two implementations",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic navigation only: no forces, contacts, friction, actuator, sensor or noise model; a step "
            "applies the clipped action divided by 10 directly to the current position",
            "no timestep: the model is event-driven, timestep_ms is 0 and ticks count discrete moves, not "
            "simulated seconds",
            "no wall-clock pacing: realtime_factor is 0, so no wall-clock timing or control-loop latency can be "
            "reasoned about",
            "the 500-step TimeLimit that gym.make adds around obstacles-cs285-v0 is not modelled by the fake, "
            "which serves the raw class; step never truncates",
            "the fake draws the random start with Python's random.Random and applies seed 0, while upstream draws "
            "from numpy's global generator and ignores seed 0, so the same seed gives different start positions",
            "the fake returns Python lists and floats; upstream returns float32/float64 numpy arrays",
            "NOT COVERED: the render() RGB image array; the fake cannot draw and cap.world.render.v1 is not bound",
            "no physical device is modelled and the model was never validated against one",
            "snapshot and restore are not offered: the class exposes no get_state or set_state",
        ],
    }
