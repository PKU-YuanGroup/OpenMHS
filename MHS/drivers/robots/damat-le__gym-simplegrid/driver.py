"""OpenMHS driver for gh.damat-le/gym-simplegrid: the SimpleGrid-4x4-v0 grid world (a Gymnasium family driver).

A ``GymnasiumDriver`` is configuration only: ``env_id`` names the registered environment and the bridge derives the
whole contract from the environment's spaces.  ``SimpleGridEnv`` navigates a grid from a start cell to a goal cell;
the action space is ``Discrete(4)`` (0 up, 1 down, 2 left, 3 right, ``simple_grid.py:22-42``) and the observation
space is ``Discrete(nrow * ncol)``, the flattened cell index (``simple_grid.py:43`` and ``grid.py:89``).  The bridge
serves ``cap.world.step.v1`` as ``{ticks, action}`` with ``action.index`` bounded by that space,
``cap.world.reset.v1`` as ``{seed, options}`` (the environment's ``start_loc`` and ``goal_loc``) and
``cap.world.seed.v1`` as ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a
machine and no operator-required limit.

The package serves the pre-registered ``SimpleGrid-4x4-v0`` entry (``gym_simplegrid/__init__.py:28-33``), so the
``obstacle_map`` that the generic ``SimpleGrid-v0`` requires is supplied by the registration itself.  The gate cannot
import gym_simplegrid (it needs gymnasium, numpy and matplotlib), so the ``fake`` backend is the package's own pure
Python implementation of the same state machine.  A backend name that ``backends`` does not list (``sim``) is served
by ``gymnasium.make(env_id)`` through ``GymnasiumDriver.open_native``; that path needs the upstream package and was not
run here (README.md).

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
every member of ``device.schema.json`` that applies to a simulator without a physical counterpart.  The environment
is a discrete state machine with no time base, so ``timestep_ms`` is 0.  Every constant and rule cites a line of the
clone at the pinned commit (6ded2fcf684727b27b5569688cad6f92bc3bc52b).  This package is model-authored and
unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "gym_simplegrid/envs/simple_grid.py"
INIT = "gym_simplegrid/__init__.py"
GRID = "gym_simplegrid/grid.py"


class SimpleGrid(GymnasiumDriver):
    device_id = "simplegrid"
    env_id = "SimpleGrid-4x4-v0"
    #: The bridge's configured seed for the first episode (GymnasiumDriver.seed); the environment itself has no
    #: default seed.  Placeholder configuration, not a device parameter.
    seed = 21
    native = "gym_simplegrid.envs:SimpleGridEnv"
    backends = {"fake": ".fake:FakeSimpleGridEnv"}
    display_name = "gym-simplegrid SimpleGrid-4x4-v0 (grid world, simulated)"
    vendor, model = "damat-le", "SimpleGrid-4x4-v0"
    tags = ["simplegrid", "grid-world", "navigation", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("MOVES maps action 0 to up, 1 to down, 2 to left and 3 to right, and the action space is "
             "Discrete(4)", source="upstream_code", ref=f"{ENV}:22-42"),
        Fact("The observation space is Discrete(nrow * ncol), one integer per grid cell", source="upstream_code",
             ref=f"{ENV}:43"),
        Fact("An observation is the flattened cell index row * ncol + col", source="upstream_code",
             ref=f"{GRID}:89"),
        Fact("A grid cell is free when it holds 0 and an obstacle when it holds 1", source="upstream_code",
             ref=f"{GRID}:28-29"),
        Fact("GridModel.is_free returns False for a cell outside the grid", source="upstream_code",
             ref=f"{GRID}:69-71"),
        Fact("A step moves the agent to the target cell when it is in bounds and free, and leaves it in place "
             "otherwise", source="upstream_code", ref=f"{ENV}:90-96"),
        Fact("The reward is +1.0 on the goal, -0.1 for a valid non-goal cell and -1.0 for an invalid move",
             source="upstream_code", ref=f"{ENV}:140-144"),
        Fact("The episode terminates when the agent reaches the goal", source="upstream_code", ref=f"{ENV}:105"),
        Fact("The episode truncates when step_count is at least max_steps and the goal was not reached on that "
             "step", source="upstream_code", ref=f"{ENV}:108-112"),
        Fact("step returns (observation, reward, terminated, truncated, info)", source="upstream_code",
             ref=f"{ENV}:114"),
        Fact("The reset info carries agent_xy and step_count", source="upstream_code", ref=f"{ENV}:149-150"),
        Fact("reset(seed) calls super().reset(seed=seed), so the sampled positions come from the environment's "
             "numpy generator", source="upstream_code", ref=f"{ENV}:68"),
        Fact("A reset without a start_loc or goal_loc option samples a free cell with GridModel.sample_valid_xy",
             source="upstream_code", ref=f"{ENV}:167-168"),
        Fact("The start_loc and goal_loc options accept a flat integer index or a (row, col) pair, and an invalid "
             "start or goal raises ValueError", source="upstream_code", ref=f"{ENV}:158-174"),
        Fact("SimpleGrid-4x4-v0 is registered with entry point gym_simplegrid.envs:SimpleGridEnv, kwargs "
             "obstacle_map=MAP_4x4 and max_episode_steps=200", source="upstream_code", ref=f"{INIT}:28-33"),
        Fact("MAP_4x4 has four rows of four cells: 0000, 0101, 0001 and 1000", source="upstream_code",
             ref=f"{INIT}:5"),
        Fact("The environment declares the render modes human, rgb_array and ansi with render_fps 8",
             source="upstream_code", ref=f"{ENV}:20"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:SimpleGrid-4x4-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) seeds the environment's numpy generator (simple_grid.py:68) and the sampled start "
                     "and goal (simple_grid.py:167-168); after that the grid transition is deterministic, and "
                     "cap.world.seed.v1 supplies the seed of the next reset.  The fake draws those positions with "
                     "Python's random.Random instead of numpy's Generator, so one seed gives different positions on "
                     "the two.  The environment has no time base: timestep_ms is 0 and every cap.world.step.v1 tick "
                     "is one state transition.",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "F0: the environment is a discrete grid state machine with no dynamics: no forces, contacts, friction, "
            "actuator, sensor or noise model, and a step changes the cell directly",
            "no wall-clock pacing: realtime_factor 0 and timestep_ms 0, so only commands advance the state and no "
            "simulated time passes",
            "no physical device is modelled and the model was never validated against one",
            "the fake backend is a pure-Python re-implementation of the clone's state machine; it samples the start "
            "and goal with Python's random.Random while upstream samples them from numpy's generator "
            "(simple_grid.py:68 and :167-168), so one seed gives different positions on the two, and it was not "
            "compared with the upstream environment",
            "the fake models the 200-step TimeLimit that gymnasium.make adds to SimpleGrid-4x4-v0 "
            "(gym_simplegrid/__init__.py:31) itself, because the bridge drives an environment object and does not "
            "call gymnasium.make; the upstream SimpleGridEnv class alone does not truncate when max_steps is None",
            "snapshot and restore are not offered: SimpleGridEnv exposes no get_state or set_state",
            "rendering is not exposed: the environment's human, rgb_array and ansi modes (simple_grid.py:20 and "
            ":116-128) need matplotlib, and cap.world.render.v1 is unbound",
        ],
    }
