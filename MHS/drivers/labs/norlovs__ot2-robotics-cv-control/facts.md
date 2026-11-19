# Facts and tags for gh.norlovs/ot2-robotics-cv-control

Every fact cites its source at commit `a0a621e5a79c32e70c8c97864d256693d3b3eac0`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| OT2Env is the real environment class the sim backend builds (a Gymnasium environment wrapper for the OT-2 pipetting robot digital twin) | upstream_code | src/ot2/ot2_gym_wrapper.py:7-9 |
| OT2Env.__init__ takes render and max_steps (defaults False and 1000) and builds the one-agent Simulation the sim backend constructs | upstream_code | src/ot2/ot2_gym_wrapper.py:19-24 |
| The clone is run from its repository root as a top-level src package (python -m src.integration.test_wrapper) | vendor_doc | README.md:219 |
| The clone's own smoke test imports the environment as src.ot2.ot2_gym_wrapper | upstream_code | src/integration/test_wrapper.py:1 |
| The wrapper imports its sibling simulation relatively (from .sim_class import Simulation) | upstream_code | src/ot2/ot2_gym_wrapper.py:4 |
| The observation is [pipette_x, pipette_y, pipette_z, goal_x, goal_y, goal_z] | upstream_code | src/ot2/ot2_gym_wrapper.py:10 |
| The action is [vx, vy, vz] continuous velocities in [-1, 1] | upstream_code | src/ot2/ot2_gym_wrapper.py:11 |
| The reward is the negative Euclidean distance to the goal with a +10 bonus on success | upstream_code | src/ot2/ot2_gym_wrapper.py:12 |
| The action space is Box(low=[-1, -1, -1], high=[1, 1, 1]) | upstream_code | src/ot2/ot2_gym_wrapper.py:26-30 |
| The observation space is Box(shape=(6,)) with unbounded low and high | upstream_code | src/ot2/ot2_gym_wrapper.py:31-33 |
| The goal sampling bounds are x [-0.1875, 0.2535], y [-0.1705, 0.2195], z [0.1196, 0.2895] | upstream_code | src/ot2/ot2_gym_wrapper.py:16-17 |
| A reset seeds numpy when a seed is given, resets the simulation and draws the goal uniformly between _LOW and _HIGH | upstream_code | src/ot2/ot2_gym_wrapper.py:38-49 |
| A step runs the simulation with the action plus a drop flag of 0 and re-reads the pipette position | upstream_code | src/ot2/ot2_gym_wrapper.py:55-59 |
| A distance below 0.01 terminates the episode and adds 10 to the reward | upstream_code | src/ot2/ot2_gym_wrapper.py:63-71 |
| The episode truncates when the step counter reaches max_steps | upstream_code | src/ot2/ot2_gym_wrapper.py:73-74 |
| The info dictionary reports current_position, target_position and distance_to_goal | upstream_code | src/ot2/ot2_gym_wrapper.py:76-80 |
| The OT-2 digital twin runs in PyBullet | vendor_doc | README.md:165 |
| The twin connects PyBullet in GUI mode when render is true and in DIRECT mode otherwise | upstream_code | src/ot2/sim_class.py:16-21 |
| The twin loads the simulated robot from ot_2_simulation_v6.urdf | upstream_code | src/ot2/sim_class.py:109-111 |
| The pipette position is the robot base position minus the joint positions plus the pipette offset | upstream_code | src/ot2/sim_class.py:173-186 |

Configuration: no `env_id` and no `env_module`, because the upstream registers no Gymnasium id (`src/ot2/__init__.py`
is empty and no module calls `register`); `src/ot2/ot2_gym_wrapper.py:7` defines `OT2Env` directly. The `fake`
backend is the package's own `.fake:FakeOT2Env`. The `sim` backend is the callable factory `_build_sim_ot2` in
`driver.py`: it locates the exported read-only clone (`task.json` `local_path`, or `labs/norlovs/ot2-robotics-cv-control`
beside the project root), makes the clone's own top-level `src` package importable from its file
(`src/__init__.py`, which is empty), imports the real `src.ot2.ot2_gym_wrapper` (whose relative
`from .sim_class import Simulation` is how the upstream packages it, `src/ot2/ot2_gym_wrapper.py:4`), checks that
the loaded wrapper is that clone's file, and returns `OT2Env()`. That is the clone's own import root and layout, used
by its scripts from the repository root (`README.md:219`; `src/integration/test_wrapper.py:1`). The constructor
defaults are `render=False` and `max_steps=1000`, and it builds the one-agent `Simulation`
(`src/ot2/ot2_gym_wrapper.py:19-24`), exactly as the clone's own scripts construct it
(`src/integration/test_wrapper.py:4`, `src/control/RL_training.py:37`), so nothing in the environment is replaced or
wrapped. The loader does not add to `sys.path`, does not itself assign into `sys.modules`, does not alter an
imported module or class, and creates no stand-in or alias module: the loader registers the clone's real `src`
package under its real name, and the environment class is the clone's real `src.ot2.ot2_gym_wrapper.OT2Env`. The
clone has no `setup.py`/`pyproject.toml`; `pip install -r requirements.txt` installs its dependencies but not the
clone itself, which is why the factory loads the real package file. The `sim` entry is a callable factory (the
SDK's supported form for a backend the driver builds itself); `driver.lock.json` keeps its locked `fake` entry and
is not edited this round.

Limits: the driver declares none. The only bound is the environment's action space, which the Gymnasium bridge derives
from the fake action space (`Box(-1, 1, shape (3,))`: every element of `action.values` from -1 to 1, with the source
`upstream_code` and the ref `src/ot2/ot2_gym_wrapper.py:26-30`); `ticks` is bounded by the bridge (1 to `max_ticks`,
10000 by default). The device is simulated (R0), so no limit is `operator_required` and there is no site-limits
overlay.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `pybullet:OT-2-digital-twin`, level F0 (kinematic: a direct
position update per transition, no dynamics), determinism `seeded` with `seed_control` `parameter`, timestep
0 ms (the fake has no simulated time base), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The gaps say what is not modelled, that the fake was never compared with the upstream environment, and that
the upstream reset accepts only `seed`.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: ot-2, opentrons, digital-twin, pipetting, pybullet, reinforcement-learning, simulation, gymnasium
