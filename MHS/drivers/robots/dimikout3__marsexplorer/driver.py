"""OpenMHS driver for gh.dimikout3/marsexplorer: the Mars Explorer grid-world environment (Gymnasium family).

The card's family helper fits the interface: ``Explorer`` is a legacy ``gym.Env`` and the Gymnasium bridge accepts
the legacy four-tuple ``(observation, reward, done, info)`` of ``step`` and the one-value ``reset`` of the clone
(``mars-explorer/mars_explorer/envs/explorer.py:38-92``, ``:207-216``).  The environment is registered as
``explorer-v01`` (``mars-explorer/mars_explorer/__init__.py:3-6``).  ``cap.world.step.v1`` takes ``{ticks, action}``
with ``action.index`` bounded by ``Discrete(4)`` (0 to 3); ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` takes ``{seed}``.  The bridge's ``autoreset`` is on, so a step after a terminal state starts the
next episode (the environment itself ends the episode; the wrapper starts the next one).  The device is simulated
(R0): there is no hardware backend, no stop path to a machine and no operator-required limit.

The upstream package needs legacy ``gym``, ``numpy``, ``pygame`` and (through its utilities) ``matplotlib``
(``mars-explorer/setup.py:9-13``, ``mars-explorer/mars_explorer/utils/randomMapGenerator.py:1-2``); the gate cannot
import any of it, so the ``fake`` backend is the package's own pure Python grid world.  A backend name that
``backends`` does not list (``sim``) would be served by the bridge's environment factory and needs the upstream
package installed; that path was not run here.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002).  ``Explorer`` has no
seed argument, no ``seed()`` method and draws its map from numpy's global generator
(``mars-explorer/mars_explorer/envs/explorer.py:38``, ``mars-explorer/mars_explorer/utils/randomMapGenerator.py:71-72``),
so the upstream model is not seeded; the bridge still records a seed for the next reset, but the upstream environment
does not consume it.  This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

EXPLORER = "mars-explorer/mars_explorer/envs/explorer.py"
SETTINGS = "mars-explorer/mars_explorer/envs/settings.py"
REGISTRY = "mars-explorer/mars_explorer/__init__.py"
GENERATOR = "mars-explorer/mars_explorer/utils/randomMapGenerator.py"
LIDAR = "mars-explorer/mars_explorer/utils/lidarSensor.py"


class MarsExplorer(GymnasiumDriver):
    device_id = "mars-explorer"
    env_id = "explorer-v01"
    native = "mars_explorer.envs:Explorer"
    backends = {"fake": ".fake:FakeExplorer"}
    action_space_ref = f"{EXPLORER}:32"
    #: A terminal step (out of bounds, collision, 95 percent explored or the step limit) ends an episode; the bridge
    #: starts the next episode on the following step instead of refusing it.  The environment itself never autoresets
    #: (explorer.py:185-197); this is the bridge wrapper's configuration, kept on so one command stream can continue
    #: after an episode ends.
    autoreset = True
    display_name = "Mars Explorer v0.1 (grid-world exploration)"
    vendor, model = "dimikout3", "mars_explorer 0.0.1"
    tags = ["mars", "exploration", "grid-world", "lidar", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("The gym environment explorer-v01 is registered with entry point mars_explorer.envs:Explorer",
             source="upstream_code", ref=f"{REGISTRY}:3-5"),
        Fact("The action space is Discrete(4): four integer actions 0, 1, 2 and 3", source="upstream_code",
             ref=f"{EXPLORER}:32"),
        Fact("The observation space is a Box with minimum 0 and maximum 1", source="upstream_code",
             ref=f"{EXPLORER}:33"),
        Fact("The default map is 21 by 21 cells", source="upstream_code", ref=f"{SETTINGS}:5"),
        Fact("Action 0 moves one cell on the first axis, action 1 the opposite way, action 2 one cell on the second "
             "axis and action 3 the opposite way", source="upstream_code", ref=f"{EXPLORER}:111-120"),
        Fact("A move outside the map sets out_of_bounds and a move into an obstacle sets collision",
             source="upstream_code", ref=f"{EXPLORER}:128-141"),
        Fact("The step reward is the number of newly explored cells minus the movement cost", source="upstream_code",
             ref=f"{EXPLORER}:178-182"),
        Fact("The default movement cost is 0.2", source="upstream_code", ref=f"{SETTINGS}:7"),
        Fact("The episode ends when timeStep is greater than max_steps", source="upstream_code",
             ref=f"{EXPLORER}:187"),
        Fact("The default max_steps is 400", source="upstream_code", ref=f"{SETTINGS}:25"),
        Fact("The episode ends with bonus_reward when more than 95 percent of the map is explored",
             source="upstream_code", ref=f"{EXPLORER}:189-191"),
        Fact("The default bonus_reward is 400", source="upstream_code", ref=f"{SETTINGS}:26"),
        Fact("A collision or an out-of-bounds move ends the episode with collision_reward or out_of_bounds_reward",
             source="upstream_code", ref=f"{EXPLORER}:192-197"),
        Fact("The default collision_reward and out_of_bounds_reward are -400", source="upstream_code",
             ref=f"{SETTINGS}:27-28"),
        Fact("The lidar scans 32 channels with a range of 6 cells", source="upstream_code",
             ref=f"{SETTINGS}:31-32"),
        Fact("The default initial position is [0, 0]", source="upstream_code", ref=f"{SETTINGS}:4"),
        Fact("The default configuration places 12 obstacles with margins [1, 1] and obstacle size [2, 2]",
             source="upstream_code", ref=f"{SETTINGS}:12-23"),
        Fact("reset() takes no arguments and returns the initial observation", source="upstream_code",
             ref=f"{EXPLORER}:38-92"),
        Fact("step() returns the legacy four-tuple (observation, reward, done, info)", source="upstream_code",
             ref=f"{EXPLORER}:207-216"),
        Fact("reset() has no seed parameter and the class defines no seed() method", source="upstream_code",
             ref=f"{EXPLORER}:38"),
        Fact("Obstacle positions are drawn with numpy's global random generator (np.random.randint)",
             source="upstream_code", ref=f"{GENERATOR}:71-72"),
        Fact("The lidar resolution default is 200 samples", source="upstream_code", ref=f"{LIDAR}:6-7"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the last observation and grid state are kept and stay readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).
    fidelity = {
        "engine": "gym:explorer-v01",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "The map generator draws obstacle positions and sizes from numpy's global RNG "
                     "(randomMapGenerator.py:71-72) and Explorer.reset() takes no seed (explorer.py:38); "
                     "cap.world.seed.v1 records a seed for the next reset but the upstream environment does not "
                     "consume it, so two resets do not repeat a trajectory.",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic grid world only: one step is one discrete move to a neighbouring cell, with no forces, "
            "velocities, contacts, actuator, sensor or noise dynamics (fidelity level F0)",
            "the map and lidar come from numpy's global RNG and reset() accepts no seed; reset is stochastic and "
            "cap.world.seed.v1 is not consumed by the upstream environment",
            "no wall-clock pacing and no fixed timestep: one step is one control transition, so timestep_ms is 0 "
            "(an event-driven analytic model)",
            "the package's fake re-implements the map generator, lidar, reward and terminal rules in pure Python "
            "without numpy or pygame; it was not compared with the upstream environment and its random stream "
            "differs from numpy's",
            "the bridge flattens the 21 x 21 x 1 observation array to 441 numbers in the JSON observation; "
            "cap.world.render.v1 is not bound and the pygame viewer is not modelled",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
