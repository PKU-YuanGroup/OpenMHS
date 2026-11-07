# Facts and tags for gh.maximecb/gym-miniworld

Every fact cites its source at commit `c660156dd73994e55ad81a4e2925582399446aba`. The same facts are written into
`driver.py` (`facts = [...]`); the reference files are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| MiniWorld-Maze-v0 is registered to the miniworld.envs.maze:Maze class | upstream_code | miniworld/envs/__init__.py:59-62 |
| Maze restricts the action space to Discrete(move_forward + 1), the three movement actions | upstream_code | miniworld/envs/maze.py:70-71 |
| MiniWorldEnv numbers turn_left 0, turn_right 1 and move_forward 2 in its Actions enumeration | upstream_code | miniworld/miniworld.py:452-457 |
| The default observation is a 60 by 80 RGB image with 3 channels | upstream_code | miniworld/miniworld.py:473-491 |
| The observation space is Box(low=0, high=255, shape=(obs_height, obs_width, 3), dtype=uint8) | upstream_code | miniworld/miniworld.py:488-491 |
| Every step renders a fresh observation from the agent camera | upstream_code | miniworld/miniworld.py:716-717 |
| The base step truncates when step_count reaches max_episode_steps and reports reward 0 on that step | upstream_code | miniworld/miniworld.py:719-724 |
| Maze defaults max_episode_steps to num_rows * num_cols * 24 and its default grid is 8 by 8 | upstream_code | miniworld/envs/maze.py:48-58 |
| The sparse reward is 1.0 - 0.2 * (step_count / max_episode_steps) | upstream_code | miniworld/miniworld.py:1012-1017 |
| Maze adds the sparse reward and sets termination when the agent is near the red box | upstream_code | miniworld/envs/maze.py:155-162 |
| The default movement parameters are forward_step 0.15, forward_drift 0 and turn_step 15, with randomization ranges 0.12-0.17, -0.05-0.05 and 10-20 | upstream_code | miniworld/params.py:123-125 |
| Domain randomization is disabled by default (domain_rand=False) | upstream_code | miniworld/miniworld.py:478 |
| reset takes the gymnasium seed parameter and options, seeds the random generator and rebuilds the agent, the entities and the rooms | upstream_code | miniworld/miniworld.py:544-563 |
| Maze places the red Box and then the agent in the generated world | upstream_code | miniworld/envs/maze.py:148-153 |
| Motion is kinematic: move_agent and turn_agent change the agent position and direction directly and a move is rejected when intersect() reports a collision | upstream_code | miniworld/miniworld.py:620-668 |
| The default Box size is 0.8 and its bounding radius is sqrt(sx * sx + sz * sz) / 2 | upstream_code | miniworld/entity.py:391-402 |
| The agent has a bounding radius of 0.4 | upstream_code | miniworld/entity.py:469-470 |
| near() compares the distance with both radii plus 1.1 * max_forward_step | upstream_code | miniworld/miniworld.py:965-975 |
| The constructor opens a 1 by 1 hidden pyglet window and allocates frame buffers, so the real environment needs an OpenGL context | upstream_code | miniworld/miniworld.py:507-518 |
| MiniWorld is a minimalistic 3D interior environment simulator for reinforcement learning and robotics research | vendor_doc | README.md:19-21 |
| The upstream lists its physics as very basic, not sufficient for robot arms or manipulation | vendor_doc | README.md:43-45 |
| The package requirements are Python >=3.8, numpy>=1.22.0, pyglet>=1.5.27,<2.0 and gymnasium>=0.29.1 | upstream_code | setup.py:48-62 |

Limits: the driver declares none. The only bound is the environment's action space, which the Gymnasium bridge derives
from the fake's `Discrete(3)` (`action.index` 0 to 2, no source, ref
`action_space of the fake backend .fake:FakeMazeEnv`). `ticks` is bounded by the catalogue class (`cap.world.step.v1`:
1 to 10000) and the reset `seed` by its non-negative catalogue constraint; those are class constraints, not limits of
this device. There is no `operator_required` bound because the simulated device has no writable state and no numeric
action input besides the discrete action.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:MiniWorld-Maze-v0`, level F0 (kinematic/analytic
transitions, no rigid-body dynamics, contacts, actuator or sensor model), determinism `seeded` with `seed_control`
`parameter`, `timestep_ms` 0 (event-driven: one action is one transition), `realtime_factor` 0, clock `lockstep`, reset
`full`, no snapshot and restore. The gaps name the missing maze geometry, the smaller observation stand-in and the
different random generator.

Safety: simulated R0 device. The e-stop is the runtime's software latch (the upstream environment exposes no stop
method); after it no step or reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no
operator for that), and the state stays readable.

Tags: miniworld, maze, navigation, reinforcement-learning, simulation, gymnasium
