"""OpenMHS driver for gh.norlovs/ot2-robotics-cv-control: the OT-2 pipetting-robot digital twin (a Gymnasium family driver).

The upstream entry point ``src.ot2.ot2_gym_wrapper:OT2Env`` (ot2_gym_wrapper.py:7) is a Gymnasium environment over
the repository's PyBullet digital twin (sim_class.py:12).  The twin is simulated (R0): there is no hardware backend,
no physical stop path and no operator-required bound.  ``GymnasiumDriver`` is configuration only: the bridge derives
the ``cap.world.step.v1`` action schema from the environment's action space (three velocities in [-1, 1],
ot2_gym_wrapper.py:26-30) and serves ``cap.world.reset.v1`` and ``cap.world.seed.v1``; the observation is six values
(ot2_gym_wrapper.py:31-33).

The fake-backend gate cannot import gymnasium or pybullet (neither is installed there; requirements.txt:1-17 lists
both), so the ``fake`` backend is the package's own pure Python kinematic stand-in (fake.py).  The ``sim`` backend is
the real class: the upstream does not register a Gymnasium id (``src/ot2/__init__.py`` is empty and no module calls
``register``), so the package declares no ``env_id``; instead ``_build_sim_ot2`` imports
``src.ot2.ot2_gym_wrapper`` from the exported clone and returns the class its constructor builds
(ot2_gym_wrapper.py:7 and 19-24).  The clone has no setup.py/pyproject.toml and ``pip install -r requirements.txt``
does not install it as a package, so the factory loads the clone's own ``src`` package file from its path,
then imports the wrapper and its ``src.ot2`` package as the real modules (whose relative simulation import,
ot2_gym_wrapper.py:4, is how the upstream packages it).  That is the upstream's own layout, used from the repository
root by its scripts (README.md:219; src/integration/test_wrapper.py:1); no module is aliased or replaced and
``sys.path`` is not changed.  The upstream environment was not run here.  The fidelity contract is the contract of the
model as deployed (spec 05-fidelity FID-002): the fake is kinematic (F0), has no simulated clock and no physics, and
its gaps say what is not modelled.

Every Fact cites a line of the clone at the pinned commit (a0a621e5a79c32e70c8c97864d256693d3b3eac0).  This package
is model-authored and unreviewed: it is checked on the fake backend here.
"""

import importlib
import importlib.machinery
import json
import threading
from pathlib import Path

from mhs.driver import Fact, GymnasiumDriver

WRAPPER = "src/ot2/ot2_gym_wrapper.py"
SIM = "src/ot2/sim_class.py"
CLONE = "labs/norlovs/ot2-robotics-cv-control"
_IMPORT_LOCK = threading.Lock()


def _upstream_clone() -> Path:
    """The exported read-only clone: ``task.json``'s ``local_path`` under the project root, or the tree beside us.

    ``package.__file__`` is ``<root>/MHS/drivers/<track>/<package>/driver.py``; the clone is
    ``<root>/<task.json local_path>`` (``labs/norlovs/ot2-robotics-cv-control``).  This resolver does not import
    the clone; the sim factory does.
    """
    package = Path(__file__).resolve().parent
    candidates: list[Path] = []
    try:
        card = json.loads((package / "task.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        card = {}
    if not isinstance(card, dict):
        card = {}
    local = card.get("local_path")
    if isinstance(local, str) and local:
        path = Path(local)
        if path.is_absolute():
            candidates.append(path)
        else:
            for base in (package, *package.parents):
                if (base / "MHS" / "sdk").is_dir():
                    candidates.append(base / path)
                    break
    candidates.append(package.parents[3] / CLONE)
    for clone in candidates:
        clone = clone.resolve()
        if (clone / "src" / "ot2" / "ot2_gym_wrapper.py").is_file():
            return clone
    raise RuntimeError(f"the pinned upstream clone is not at {candidates[0]}: "
                       f"{candidates[0] / 'src' / 'ot2' / 'ot2_gym_wrapper.py'} is missing")


def _clone_src(clone: Path) -> None:
    """Make the clone's real top-level ``src`` package importable, from its own file (README.md:219).

    ``pip install -r requirements.txt`` (requirements.txt:1-17) installs the dependencies but not the clone, and the
    clone is used from its repository root by its own scripts (README.md:219; src/integration/test_wrapper.py:1).
    Loading the package's empty ``__init__.py`` from its path gives the normal import system the real package
    directory, so ``src.ot2`` and the wrapper's relative ``from .sim_class import Simulation``
    (ot2_gym_wrapper.py:4) resolve inside the clone.  The loader registers that real package under its real name
    ``src`` (not an alias or stand-in), no attribute of an imported object is assigned, and ``sys.path`` is not
    changed.  An already imported package is reused and its real file checked.
    """
    init = (clone / "src" / "__init__.py").resolve()
    try:
        package = importlib.import_module("src")
    except ModuleNotFoundError:
        package = importlib.machinery.SourceFileLoader("src", str(init)).load_module()
    loaded = getattr(package, "__file__", None)
    if loaded is None or Path(loaded).resolve() != init:
        raise RuntimeError(f"imported src from {loaded}, not the pinned clone's {init}")


def _build_sim_ot2(**_options):
    """Build the clone's real ``OT2Env`` for the ``sim`` backend (ot2_gym_wrapper.py:7, 19-24).

    The upstream registers no id, so this is not ``gymnasium.make``: the class is imported from the clone the gate
    exports (its ``src`` top-level package is not installed by ``pip install -r requirements.txt``) and constructed
    with its own defaults, render=False and max_steps=1000.  The wrapper is the real module at its real path; the
    imported modules stay importable exactly as a normal import of the clone's own ``src`` package leaves them.  The
    env is never monkeypatched.
    """
    clone = _upstream_clone()
    wrapper = (clone / "src" / "ot2" / "ot2_gym_wrapper.py").resolve()
    with _IMPORT_LOCK:
        try:   # a normal import when the clone's source tree is somehow already importable
            module = importlib.import_module("src.ot2.ot2_gym_wrapper")
        except ModuleNotFoundError as exc:
            if exc.name not in ("src", "src.ot2", "src.ot2.ot2_gym_wrapper"):
                raise
            _clone_src(clone)   # the clone is not installed: load its real package from its own file
            importlib.invalidate_caches()
            module = importlib.import_module("src.ot2.ot2_gym_wrapper")
    if Path(module.__file__).resolve() != wrapper:
        raise RuntimeError(f"imported {module.__file__}, not the pinned clone's {wrapper}")
    return module.OT2Env()


class OT2DigitalTwin(GymnasiumDriver):
    device_id = "ot2-twin"
    native = "src.ot2.ot2_gym_wrapper:OT2Env"
    backends = {"fake": ".fake:FakeOT2Env", "sim": _build_sim_ot2}
    action_space_ref = f"{WRAPPER}:26-30"
    display_name = "OT-2 pipetting-robot digital twin (OT2Env)"
    vendor, model = "norlovs", "OT-2 Robotics CV Control"
    tags = ["ot-2", "opentrons", "digital-twin", "pipetting", "pybullet", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("OT2Env is the real environment class the sim backend builds (a Gymnasium environment wrapper for the "
             "OT-2 pipetting robot digital twin)", source="upstream_code", ref=f"{WRAPPER}:7-9"),
        Fact("OT2Env.__init__ takes render and max_steps (defaults False and 1000) and builds the one-agent Simulation "
             "the sim backend constructs", source="upstream_code", ref=f"{WRAPPER}:19-24"),
        Fact("The clone is run from its repository root as a top-level src package "
             "(python -m src.integration.test_wrapper)", source="vendor_doc", ref="README.md:219"),
        Fact("The clone's own smoke test imports the environment as src.ot2.ot2_gym_wrapper", source="upstream_code",
             ref="src/integration/test_wrapper.py:1"),
        Fact("The wrapper imports its sibling simulation relatively (from .sim_class import Simulation)",
             source="upstream_code", ref=f"{WRAPPER}:4"),
        Fact("The observation is [pipette_x, pipette_y, pipette_z, goal_x, goal_y, goal_z]", source="upstream_code",
             ref=f"{WRAPPER}:10"),
        Fact("The action is [vx, vy, vz] continuous velocities in [-1, 1]", source="upstream_code",
             ref=f"{WRAPPER}:11"),
        Fact("The reward is the negative Euclidean distance to the goal with a +10 bonus on success",
             source="upstream_code", ref=f"{WRAPPER}:12"),
        Fact("The action space is Box(low=[-1, -1, -1], high=[1, 1, 1])", source="upstream_code",
             ref=f"{WRAPPER}:26-30"),
        Fact("The observation space is Box(shape=(6,)) with unbounded low and high", source="upstream_code",
             ref=f"{WRAPPER}:31-33"),
        Fact("The goal sampling bounds are x [-0.1875, 0.2535], y [-0.1705, 0.2195], z [0.1196, 0.2895]",
             source="upstream_code", ref=f"{WRAPPER}:16-17"),
        Fact("A reset seeds numpy when a seed is given, resets the simulation and draws the goal uniformly between "
             "_LOW and _HIGH", source="upstream_code", ref=f"{WRAPPER}:38-49"),
        Fact("A step runs the simulation with the action plus a drop flag of 0 and re-reads the pipette position",
             source="upstream_code", ref=f"{WRAPPER}:55-59"),
        Fact("A distance below 0.01 terminates the episode and adds 10 to the reward", source="upstream_code",
             ref=f"{WRAPPER}:63-71"),
        Fact("The episode truncates when the step counter reaches max_steps", source="upstream_code",
             ref=f"{WRAPPER}:73-74"),
        Fact("The info dictionary reports current_position, target_position and distance_to_goal",
             source="upstream_code", ref=f"{WRAPPER}:76-80"),
        Fact("The OT-2 digital twin runs in PyBullet", source="vendor_doc", ref="README.md:165"),
        Fact("The twin connects PyBullet in GUI mode when render is true and in DIRECT mode otherwise",
             source="upstream_code", ref=f"{SIM}:16-21"),
        Fact("The twin loads the simulated robot from ot_2_simulation_v6.urdf", source="upstream_code",
             ref=f"{SIM}:109-111"),
        Fact("The pipette position is the robot base position minus the joint positions plus the pipette offset",
             source="upstream_code", ref=f"{SIM}:173-186"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: determinism kind and lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "pybullet:OT-2-digital-twin",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) fixes the goal draw and the fake's position update is deterministic, so one seed "
                     "and one action sequence repeat a trajectory; upstream seeds numpy's global generator and runs "
                     "PyBullet on its own clock, so a seed does not repeat a trajectory across the two",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is kinematic: one direct position update per transition, not PyBullet rigid-body dynamics, "
            "contacts, friction, forces or the simulation clock; no actuator, sensor or noise model",
            "no simulated time base: timestep_ms is 0 and a step is one discrete transition, not a physical duration",
            "the PyBullet GUI/DIRECT renderer is not modelled: render() is a no-op",
            "the upstream environment was not run (gymnasium and pybullet are not installed where the gate ran), so "
            "the fake was never compared with it; the goal draw uses random.Random, upstream numpy's global generator",
            "observations are Python lists of floats, upstream returns float32 numpy arrays and rounds the pipette "
            "position to four decimals",
            "reset accepts only seed, like the upstream signature; cap.world.reset.v1 options are not supported and "
            "the bridge falls back to a seedless reset when options are supplied",
            "no droplet, specimen or plate physics is modelled",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
