"""OpenMHS driver for gh.erfanmhi/deep-reinforcement-learning-cs285-pytorch: the CS285 obstacle environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with
``action.values`` a Box of two elements bounded by -0.99 and 0.99, ``cap.world.reset.v1`` takes ``{seed, options}``
and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to
a machine and no operator-required limit.

Only ``obstacles-cs285-v0`` is served; the card's other entry symbols (AntEnv, HalfCheetahEnv, Reacher7DOFEnv) are
MuJoCo environments that need MuJoCo 2.1 and mujoco-py (README.md:102-119) and are left for their own packages.

The ``fake`` backend is a pure Python obstacle environment (fake.py).  The fake gate does not import the clone.
The ``sim`` backend is ``_build_sim_env``.  It executes the pinned ``obstacles_env.py`` and wraps ``Obstacles()``
from that file in the registration's 500-step ``TimeLimit`` (``obstacles/__init__.py:6``).
``gym.make('obstacles-cs285-v0')`` cannot be used: importing the module that registers the id
runs ``cs285/envs/__init__.py``, which imports the MuJoCo environments first (``ant.py``, ``cheetah.py``,
``reacher_env.py``).  ``hw4/setup.py`` lists only the top-level ``cs285`` package, and that directory has no
``__init__.py``, so installing the homework does not put ``cs285.envs`` on the import path either.  This workspace
did not run the sim backend.

The ``fidelity`` attribute is the complete contract of the model as deployed (spec 05-fidelity FID-002).  Every
constant and rule cites a line of the clone at commit 6da04f367e52a451c202ae7e5477994c1d149baf.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

import importlib.util
import os
from pathlib import Path

from mhs.driver import Fact, GymnasiumDriver

OBSTACLES = "hw4/cs285/envs/obstacles/obstacles_env.py"
REGISTRATION = "hw4/cs285/envs/obstacles/__init__.py"
ENVS_INIT = "hw4/cs285/envs/__init__.py"
_CLONE = Path("robots/erfanmhi/deep-reinforcement-learning-cs285-pytorch")
_ENV_REL = Path(OBSTACLES)
_REG_REL = Path(REGISTRATION)


def _obstacles_file() -> Path:
    """The pinned ``obstacles_env.py`` (``Obstacles`` at obstacles_env.py:5).

    The gate mounts this worktree, whose ``robots`` entry is the clone at the pinned commit, and mounts ``/src``
    only when an install put the exported tree there.  Either root is that commit's files.  The search is those
    two roots only.
    """
    roots = [Path("/src")]
    here = Path(__file__).resolve()
    roots.extend(parent / _CLONE for parent in here.parents)
    seen: set[str] = set()
    for root in roots:
        key = os.path.normcase(str(root))
        if key in seen:
            continue
        seen.add(key)
        script = root / _ENV_REL
        registered = root / _REG_REL
        try:
            if script.is_file() and registered.is_file():
                return script.resolve()
        except OSError:
            continue
    raise FileNotFoundError(
        f"{_ENV_REL.as_posix()} is not under /src or the pinned clone {_CLONE.as_posix()}")


def _load_obstacles():
    """Execute the real ``obstacles_env.py`` and return that module.

    ``hw4/cs285/envs/__init__.py:1-4`` imports ant, then cheetah, then obstacles, then reacher.  ant, cheetah
    and reacher import ``mujoco_py`` at module scope (``ant.py:16``, ``cheetah.py:2``, ``reacher_env.py:3-4``),
    so the ant import fails before obstacles is reached.  That binding needs the licensed MuJoCo 1.50 install
    (``README.md:103-121``).  The obstacles file itself
    imports only ``gym``, ``numpy`` and ``gym.spaces`` (``obstacles_env.py:1-3``).  Loading it by its path does
    not run the sibling imports.  The module object is that file.  It is not inserted into the import table, it
    is not an alias of ``cs285``, and the import path is left unchanged.
    """
    path = _obstacles_file()
    spec = importlib.util.spec_from_file_location("obstacles_env", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load the pinned {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    loaded = getattr(module, "__file__", None)
    if loaded is None or Path(loaded).resolve() != path:
        raise ImportError(f"loaded {loaded}, not the pinned {path}")
    return module


def _build_sim_env(**_options):
    """Build the real ``Obstacles`` the constructor at ``obstacles_env.py:6`` builds.

    The registration's entry point is ``cs285.envs.obstacles:Obstacles`` (``obstacles/__init__.py:3-7``), and the
    next line of that file imports the class through the package (``obstacles/__init__.py:8``), which runs
    ``envs/__init__.py`` first.  ``hw4/setup.py:4-8`` declares ``packages=['cs285']`` only, and ``hw4/cs285`` has
    no ``__init__.py``, so an install of that homework does not expose ``cs285.envs``.  This factory therefore
    calls the class in the loaded file and preserves its rendering configuration.  ``__init__`` imports
    ``matplotlib.pyplot`` and creates a figure (``obstacles_env.py:8`` and ``:41``).  The upstream instance is
    wrapped in the registration's 500-step ``TimeLimit`` (``obstacles/__init__.py:6``), as ``gym.make`` would do.
    """
    from gym.wrappers import TimeLimit

    return TimeLimit(_load_obstacles().Obstacles(), max_episode_steps=500)


class CS285Obstacles(GymnasiumDriver):
    device_id = "obstacles"
    env_id = "obstacles-cs285-v0"
    native = "cs285.envs.obstacles:Obstacles"
    #: ``sim`` is a callable, so the locked string backends stay ``{"fake": ".fake:FakeObstacles"}``.
    backends = {"fake": ".fake:FakeObstacles", "sim": _build_sim_env}
    display_name = "CS285 obstacles-cs285-v0 (2D navigation)"
    vendor, model = "erfanmhi", "obstacles-cs285-v0"
    tags = ["obstacles", "navigation", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The environment is registered as obstacles-cs285-v0 with max_episode_steps=500",
             source="upstream_code", ref=f"{REGISTRATION}:3-7"),
        Fact("The registration module then imports Obstacles through the package path",
             source="upstream_code", ref=f"{REGISTRATION}:8"),
        Fact("Importing cs285.envs imports ant, cheetah, obstacles and reacher",
             source="upstream_code", ref=f"{ENVS_INIT}:1-4"),
        Fact("The ant environment module imports mujoco_py at module scope",
             source="upstream_code", ref="hw4/cs285/envs/ant/ant.py:16"),
        Fact("The cheetah environment module imports mujoco_py at module scope",
             source="upstream_code", ref="hw4/cs285/envs/cheetah/cheetah.py:2"),
        Fact("The reacher environment module imports mujoco_env and mujoco_py.MjViewer at module scope",
             source="upstream_code", ref="hw4/cs285/envs/reacher/reacher_env.py:3-4"),
        Fact("The obstacles module imports gym, numpy and gym.spaces and does not import mujoco_py",
             source="upstream_code", ref=f"{OBSTACLES}:1-3"),
        Fact("hw4/setup.py installs only the top-level cs285 package and declares no dependencies",
             source="upstream_code", ref="hw4/setup.py:4-8"),
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
