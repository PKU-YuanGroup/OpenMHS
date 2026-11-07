"""OpenMHS driver for gh.maximecb/gym-miniworld: the MiniWorld-Maze-v0 environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
whole contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action
``{index}`` bounded by the environment's ``Discrete(3)`` (turn left 0, turn right 1, move forward 2),
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated
(R0): there is no hardware backend, no operator-required limit and no path to a machine.

The real environment needs numpy, pyglet and an OpenGL context (``miniworld/miniworld.py:507-518``), and package
code never imports the clone, so the ``fake`` backend is the package's own pure Python kinematic stand-in (fake.py).
A backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make("MiniWorld-Maze-v0")``
(GymnasiumDriver.open_native); that path was not run here and is not claimed (see the fidelity gaps and RESULT.json).

The ``fidelity`` attribute is the fidelity contract of the model as deployed (MHS-005 FID-002).  Everything the
driver claims cites the clone at the pinned commit c660156dd73994e55ad81a4e2925582399446aba.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENVS = "miniworld/envs/__init__.py"
MAZE = "miniworld/envs/maze.py"
ENV = "miniworld/miniworld.py"
ENTITY = "miniworld/entity.py"
PARAMS = "miniworld/params.py"
README = "README.md"
SETUP = "setup.py"


class MiniWorldMaze(GymnasiumDriver):
    device_id = "miniworld-maze"
    env_id = "MiniWorld-Maze-v0"
    native = "miniworld.envs.maze:Maze"
    backends = {"fake": ".fake:FakeMazeEnv"}
    display_name = "MiniWorld Maze (gymnasium simulation)"
    vendor, model = "Farama Foundation", "MiniWorld-Maze-v0"
    tags = ["miniworld", "maze", "navigation", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("MiniWorld-Maze-v0 is registered to the miniworld.envs.maze:Maze class", source="upstream_code",
             ref=f"{ENVS}:59-62"),
        Fact("Maze restricts the action space to Discrete(move_forward + 1), the three movement actions",
             source="upstream_code", ref=f"{MAZE}:70-71"),
        Fact("MiniWorldEnv numbers turn_left 0, turn_right 1 and move_forward 2 in its Actions enumeration",
             source="upstream_code", ref=f"{ENV}:452-457"),
        Fact("The default observation is a 60 by 80 RGB image with 3 channels", source="upstream_code",
             ref=f"{ENV}:473-491"),
        Fact("The observation space is Box(low=0, high=255, shape=(obs_height, obs_width, 3), dtype=uint8)",
             source="upstream_code", ref=f"{ENV}:488-491"),
        Fact("Every step renders a fresh observation from the agent camera", source="upstream_code",
             ref=f"{ENV}:716-717"),
        Fact("The base step truncates when step_count reaches max_episode_steps and reports reward 0 on that step",
             source="upstream_code", ref=f"{ENV}:719-724"),
        Fact("Maze defaults max_episode_steps to num_rows * num_cols * 24 and its default grid is 8 by 8",
             source="upstream_code", ref=f"{MAZE}:48-58"),
        Fact("The sparse reward is 1.0 - 0.2 * (step_count / max_episode_steps)", source="upstream_code",
             ref=f"{ENV}:1012-1017"),
        Fact("Maze adds the sparse reward and sets termination when the agent is near the red box",
             source="upstream_code", ref=f"{MAZE}:155-162"),
        Fact("The default movement parameters are forward_step 0.15, forward_drift 0 and turn_step 15, with "
             "randomization ranges 0.12-0.17, -0.05-0.05 and 10-20", source="upstream_code",
             ref=f"{PARAMS}:123-125"),
        Fact("Domain randomization is disabled by default (domain_rand=False)", source="upstream_code",
             ref=f"{ENV}:478"),
        Fact("reset takes the gymnasium seed parameter and options, seeds the random generator and rebuilds the "
             "agent, the entities and the rooms", source="upstream_code", ref=f"{ENV}:544-563"),
        Fact("Maze places the red Box and then the agent in the generated world", source="upstream_code",
             ref=f"{MAZE}:148-153"),
        Fact("Motion is kinematic: move_agent and turn_agent change the agent position and direction directly and "
             "a move is rejected when intersect() reports a collision", source="upstream_code",
             ref=f"{ENV}:620-668"),
        Fact("The default Box size is 0.8 and its bounding radius is sqrt(sx * sx + sz * sz) / 2",
             source="upstream_code", ref=f"{ENTITY}:391-402"),
        Fact("The agent has a bounding radius of 0.4", source="upstream_code", ref=f"{ENTITY}:469-470"),
        Fact("near() compares the distance with both radii plus 1.1 * max_forward_step", source="upstream_code",
             ref=f"{ENV}:965-975"),
        Fact("The constructor opens a 1 by 1 hidden pyglet window and allocates frame buffers, so the real "
             "environment needs an OpenGL context", source="upstream_code", ref=f"{ENV}:507-518"),
        Fact("MiniWorld is a minimalistic 3D interior environment simulator for reinforcement learning and "
             "robotics research", source="vendor_doc", ref=f"{README}:19-21"),
        Fact("The upstream lists its physics as very basic, not sufficient for robot arms or manipulation",
             source="vendor_doc", ref=f"{README}:43-45"),
        Fact("The package requirements are Python >=3.8, numpy>=1.22.0, pyglet>=1.5.27,<2.0 and gymnasium>=0.29.1",
             source="upstream_code", ref=f"{SETUP}:48-62"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (MHS-005 section 2).  The bridge derives the engine, the
    #: determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:MiniWorld-Maze-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the initial pose and the dynamics are deterministic, "
                     "so this package's fake repeats a trajectory for the same seed and actions; the fake draws "
                     "with Python's random.Random and upstream with gymnasium's numpy generator, so a seed does "
                     "not reproduce an upstream trajectory",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic/analytic model: each action is a direct move or turn, with no rigid-body dynamics, contact "
            "solver, actuator, sensor or noise model (the upstream says its physics are very basic, README.md:43-45)",
            "timestep_ms is 0 because the environment is event-driven: one action is one transition and there is no "
            "physics timestep; realtime_factor 0 means no wall-clock pacing",
            "the fake backend does not generate the 8x8 room maze, walls or portals and has no collision "
            "detection; the agent moves on an open plane and the red box is placed 1.5 m ahead of it instead of in "
            "a random room (those values are test data, not device facts)",
            "the fake returns a 3x4x3 coarse RGB stand-in (36 values) instead of the real 60x80x3 rendered camera "
            "image; there is no 3D rendering, texture, lighting or occlusion because pyglet/OpenGL is not used",
            "initial poses come from Python's random.Random in the fake and from gymnasium's numpy generator "
            "upstream, so one seed does not reproduce an upstream trajectory",
            "snapshot and restore are not offered: MiniWorldEnv exposes no get_state or set_state",
        ],
    }
