# Facts and tags for gh.internrobotics/internutopia

Every fact cites its source at commit `b0a9520c586317c2743023c153cbf7c4f04f4732`. `upstream_code` refs are
`path/in/clone.py:LINE`; `vendor_doc` refs are text files of the clone. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The 2.0 feature list advertises a Gym-compatible environment implementation | vendor_doc | README.md:26 |
| The single-agent environment class is Env, a gymnasium.Env subclass | upstream_code | internutopia/core/gym_env.py:10 |
| Env.__init__ requires a Config and builds a SimulatorRunner and a task config manager from it | upstream_code | internutopia/core/gym_env.py:17-28 |
| Env accepts only env_num 1 and at most one robot per episode | upstream_code | internutopia/core/gym_env.py:41-54 |
| The action space is a hardcoded Dict with the key move_along_path, a Sequence of Tuples of three Box(-inf, inf) entries, independent of the Config | upstream_code | internutopia/core/util/space.py:11-25 |
| The observation space is a hardcoded Dict with position Box shape (3,) and orientation Box shape (4,), all bounds -inf to inf, independent of the Config | upstream_code | internutopia/core/util/space.py:28-34 |
| Env.reset accepts seed and options but uses neither; it delegates to runner.reset and returns the robot observation plus info['task_config'] | upstream_code | internutopia/core/gym_env.py:62-87 |
| Env.step wraps the action as {robot_name: action}, calls runner.step, and returns observation, reward, terminated, False and info; truncated is always False | upstream_code | internutopia/core/gym_env.py:100-140 |
| When the runner reports reward -1, Env.step reports 0.0; every other reward is reported unchanged | upstream_code | internutopia/core/gym_env.py:133-134 |
| A step before the first reset returns an empty observation, 0.0, False, False and None | upstream_code | internutopia/core/gym_env.py:121-128 |
| Env.get_dt returns the runner's dt | upstream_code | internutopia/core/gym_env.py:154-160 |
| SimulatorRunner.setup_isaacsim imports isaacsim.SimulationApp and constructs it | upstream_code | internutopia/core/runner.py:477-486 |
| The only Simulator member is ISAACSIM = 'isaac_sim' | upstream_code | internutopia/core/config/__init__.py:12-13 |
| SimConfig defaults physics_dt and rendering_dt to 1/60 s | upstream_code | internutopia/core/config/__init__.py:21-22 |
| The prerequisites list NVIDIA Omniverse Isaac Sim 4.5.0 and an NVIDIA GPU of RTX 2070 or higher | vendor_doc | README.md:69-71 |
| The vectorized internutopia.core.vec_env.Env documents itself as NOT gymnasium compatible | upstream_code | internutopia/core/vec_env.py:9-13 |

Limits: the driver declares none. The bridge derives the step input structure from the environment's action space,
whose Box entries are `-inf`/`inf`, so there is no finite action bound to publish. `ticks` is bounded 1 to 10000 by
the Gymnasium bridge (`max_ticks` default), not by this package. The device is simulated (R0), so no limit is
`operator_required` and there is no `site-limits.example.json`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `internutopia:isaac_sim`, level F0 (the checked model is
the package's kinematic fake, not Isaac Sim), determinism `none` with a note that upstream `Env.reset` accepts but
ignores the seed and that no Isaac Sim run was measured, timestep 1000/60 ms (the SimConfig physics_dt default at
`internutopia/core/config/__init__.py:21`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The gaps say what is not modelled and that the fake was never compared with Isaac Sim.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: embodied-ai, gymnasium, internutopia, isaac-sim, simulation
