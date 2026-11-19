"""OpenMHS driver for gh.mattchantk/gym-maze: the ``maze-v0`` sample environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the
whole contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with
``action`` ``{index}`` bounded by ``Discrete(4)`` (0 to 3), ``cap.world.reset.v1`` takes ``{seed,
options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required limit.

``maze-v0`` is registered to ``MazeEnvSample5x5`` with ``max_episode_steps=2000``
(``gym_maze/__init__.py:4-8``).  The upstream class uses the legacy gym API: ``reset()`` returns the
observation only and ``step(action)`` returns ``(observation, reward, done, info)``
(``gym_maze/envs/maze_env.py:88-97``).  The Gymnasium bridge accepts both shapes, which is why the
card's ``GymnasiumDriver`` fits this environment without a direct Driver.

The fake gate does not import the clone or its gym, pygame and numpy dependencies (``setup.py:12``).
The ``fake`` backend is the package's own pure Python re-implementation of the upstream grid rules
(see ``fake.py``).  A backend name that ``backends`` does not list (``sim``) is left to the bridge.
It imports ``env_module`` (``gym_maze``), whose module body runs ``register(...)`` for ``maze-v0``
(``gym_maze/__init__.py:1-8``), then calls ``make(env_id)`` in whichever registry holds the id.
No constructor kwargs are supplied, so ``MazeEnvSample5x5`` keeps its default ``enable_render=True``
(``gym_maze/envs/maze_env.py:111-112``) and ``MazeView2D`` creates the pygame display
(``gym_maze/envs/maze_view_2d.py:34-36``).  That path needs the upstream package and display support;
it is not exercised by the fake gate.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec
05-fidelity FID-002): every member of ``device.schema.json`` that applies to a simulator without a
physical counterpart.  Every constant and rule cites a line of the clone at the pinned commit
(83176811b49b5538a6213520612f44fb1bc49114).  This package is model-authored and unreviewed: it is
checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "gym_maze/envs/maze_env.py"
VIEW = "gym_maze/envs/maze_view_2d.py"
REG = "gym_maze/__init__.py"


class MazeSample5x5(GymnasiumDriver):
    device_id = "gym-maze-5x5"
    env_id = "maze-v0"
    #: Importing gym_maze runs register(...) at gym_maze/__init__.py:1-8 in the legacy gym registry.
    env_module = "gym_maze"
    native = "gym_maze.envs:MazeEnvSample5x5"
    backends = {"fake": ".fake:FakeMazeEnvSample5x5"}
    display_name = "gym-maze maze-v0 (5x5 sample maze)"
    vendor, model = "Matthew T.K. Chan", "gym-maze 0.4"
    tags = ["maze", "grid-world", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("MazeEnvSample5x5 loads the pre-generated maze file maze2d_5x5.npy, a 5x5 world",
             source="upstream_code", ref=f"{ENV}:111-112"),
        Fact("The action space is Discrete(2*len(maze_size)), so the 5x5 sample maze has four "
             "integer actions", source="upstream_code", ref=f"{ENV}:44"),
        Fact("ACTION lists the four directions N, S, E, W", source="upstream_code", ref=f"{ENV}:14"),
        Fact("An integer action is an index into ACTION; step calls move_robot with that direction",
             source="upstream_code", ref=f"{ENV}:73-77"),
        Fact("If the destination is blocked, move_robot does not move the robot",
             source="upstream_code", ref=f"{VIEW}:97-103"),
        Fact("is_open requires the destination to be inside the grid and allows the move when either "
             "side of the shared wall is open", source="upstream_code", ref=f"{VIEW}:442-453"),
        Fact("The observation space is a two-element Box of integers from 0 to maze_size-1",
             source="upstream_code", ref=f"{ENV}:46-49"),
        Fact("The entrance is cell (0, 0) and the goal is the last cell, maze_size - (1, 1)",
             source="upstream_code", ref=f"{VIEW}:39-43"),
        Fact("reset puts the robot back at the entrance, sets state to zeros(2), clears "
             "steps_beyond_done, sets done False and returns the state", source="upstream_code",
             ref=f"{ENV}:92-97"),
        Fact("A step gives reward 1 and done True at the goal, otherwise reward "
             "-0.1/(maze_size[0]*maze_size[1]) and done False", source="upstream_code",
             ref=f"{ENV}:79-84"),
        Fact("step returns the legacy four-tuple (state, reward, done, info) and has no truncated flag",
             source="upstream_code", ref=f"{ENV}:88-90"),
        Fact("MazeEnv.seed seeds a numpy random generator and returns [seed]", source="upstream_code",
             ref=f"{ENV}:69-71"),
        Fact("reset takes no arguments and returns the fixed zero state; it does not draw from the "
             "generator set by seed", source="upstream_code", ref=f"{ENV}:92-97"),
        Fact("step moves the robot on the fixed maze data and does not draw from a random generator",
             source="upstream_code", ref=f"{ENV}:73-90"),
        Fact("maze-v0 is registered to MazeEnvSample5x5 with max_episode_steps=2000",
             source="upstream_code", ref=f"{REG}:4-8"),
        Fact("Importing gym_maze runs that registration: line 1 imports register from gym.envs.registration "
             "and lines 4-8 register maze-v0 in the legacy gym registry",
             source="upstream_code", ref=f"{REG}:1-8"),
        Fact("MazeEnvSample5x5 defaults enable_render to True and passes it through to MazeEnv",
             source="upstream_code", ref=f"{ENV}:111-112"),
        Fact("MazeView2D always calls pygame.init and pygame.display.set_caption, and calls "
             "pygame.display.set_mode only when enable_render is true",
             source="upstream_code", ref=f"{VIEW}:14-36"),
        Fact("The upstream package declares gym, pygame and numpy as install requirements",
             source="upstream_code", ref="setup.py:12"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the maze state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives
    #: the engine, the determinism kind and the lockstep clock; they are written out so the whole
    #: contract reads in one place.
    fidelity = {
        "engine": "gym_maze:maze-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "the sample maze and the start cell are fixed and every step is a deterministic "
                     "grid transition; MazeEnv.seed exists but reset and step never draw from its "
                     "generator, so a seed is echoed and does not change a trajectory. The bridge's "
                     "state_hash also counts the episode, so two runs compare from a fresh world or "
                     "from the same episode ordinal.",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no physics and no continuous time: one tick is one grid-cell transition on a fixed 5x5 "
            "wall layout, so timestep_ms is 0 (an event-driven analytic model)",
            "no wall-clock pacing and no rendering: the pygame viewer and the rgb_array image are "
            "not modelled; cap.world.render.v1 stays unbound",
            "the fake re-implements the MazeEnv and MazeView2D grid rules in pure Python and embeds "
            "the shipped 5x5 wall layout as test data; it was not compared with a run of the upstream "
            "environment (gym, pygame and numpy are not imported where the gate runs)",
            "the raw MazeEnv.step returns a four-tuple and never truncates; the fake emulates the "
            "2000-step TimeLimit that gym.make adds to maze-v0 (gym_maze/__init__.py:7), so the bridge "
            "reports truncated at 2000 ticks",
            "only the fixed 5x5 sample environment is modelled, not the random, portal or loop "
            "variants, and the observation is a plain two-element array rather than a numpy int64 "
            "array",
            "snapshot and restore are not offered: MazeEnv exposes no get_state or set_state",
        ],
    }
