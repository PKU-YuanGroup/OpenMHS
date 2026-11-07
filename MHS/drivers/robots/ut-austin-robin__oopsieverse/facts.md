# Facts and tags for gh.ut-austin-robin/oopsieverse

Every fact cites its source at commit `a739f99e94f32c3229ae6932299e2e0e8c065480`: `vendor_doc` for a text file of the
clone (README.md or docs/*.md) or `upstream_code` for a line of the clone's code. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| OopsieVerse is a damage-aware, simulator-agnostic framework and benchmark for learning and evaluating safer robot manipulation | vendor_doc | README.md:10 |
| OopsieVerse builds on BEHAVIOR-1K/OmniGibson, RoboCasa and RoboSuite | vendor_doc | README.md:38 |
| OopsieBench spans OmniGibson (NVIDIA Omniverse) and Robosuite (MuJoCo) | vendor_doc | docs/oopsiebench.md:3 |
| The environment registry's default robot is PandaOmron and its default control frequency is 20 | upstream_code | oopsiebench/envs/registry.py:20-21 |
| close_drawer is registered with environment class CloseDrawer and damageable class DamageableCloseDrawer | upstream_code | oopsiebench/envs/registry.py:65 |
| DamageableCloseDrawer constructs the environment with task_name close_drawer | upstream_code | oopsiebench/envs/robocasa/close_drawer.py:152-156 |
| CloseDrawer sets randomize_scene to True, so the scene is randomized per episode | upstream_code | oopsiebench/envs/robocasa/close_drawer.py:31-35 |
| The drawer starts with a door state between 0.95 and 1.0 | upstream_code | oopsiebench/envs/robocasa/close_drawer.py:87-89 |
| The close_drawer episode starts with the drawer open | vendor_doc | docs/oopsiebench.md:41 |
| CloseDrawer computes the reward as 10.0 times one minus the mean door state | upstream_code | oopsiebench/envs/robocasa/close_drawer.py:123-129 |
| The success check rejects the episode while any drawer joint position is above 0.05 | upstream_code | oopsiebench/envs/robocasa/close_drawer.py:131-136 |
| The success check uses a gripper-to-drawer-root-body distance threshold of 0.75 m | upstream_code | oopsiebench/envs/robocasa/close_drawer.py:19-21 |
| The damageable environment reset returns (observation, info) and reinitializes damage tracking | upstream_code | damagesim/robosuite/damageable_env.py:382-398 |
| The damageable environment step returns (observation, reward, done, info) | upstream_code | damagesim/robosuite/damageable_env.py:400-409 |
| The observation appends a float32 health array | upstream_code | damagesim/core/damageable_env.py:259-269 |
| The proprio vector concatenates 7 joint sines, 7 joint cosines, 3 end-effector positions, 4 quaternion values and 2 gripper positions when those keys are present | upstream_code | damagesim/robosuite/damageable_env.py:289-301 |
| The tests build the environment from the registry robot and a composite controller, with camera observations off and the registry control frequency | upstream_code | scripts/tests/test_robocasa.py:49-59 |
| The teleoperation loop builds the environment action with robot.create_action_vector and steps the environment with the concatenated result | upstream_code | scripts/teleop_robocasa.py:838-845 |
| Installation clones RoboSuite and RoboCasa and pip-installs both | upstream_code | install.py:130-150 |
| The package's declared dependencies are open3d, matplotlib, scipy, tyro, tqdm and numba | upstream_code | pyproject.toml:17-25 |

Limits: the driver declares none. The environment is simulated at R0 and the fake serves an unbounded action Box,
because the real PandaOmron composite-controller action is assembled at run time (`scripts/teleop_robocasa.py:838-845`)
and its size and bounds are not stated in the clone. `ticks` is bounded by the Gymnasium bridge, not by a device
limit. There is no operator-required bound.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:close_drawer on RoboCasa/Robosuite (MuJoCo)`,
level F1 (the upstream MuJoCo rigid-body model), determinism `seeded` with `seed_control` `parameter` for the fake,
`timestep_ms` 50 (the registry's 20 Hz control period, `oopsiebench/envs/registry.py:21`), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. The gaps say that the fake is an analytic stand-in without
contacts, friction, actuators, cameras, rendering or the full Robosuite observation and action spaces; that the
upstream `reset()` takes no seed (`damagesim/robosuite/damageable_env.py:382`), so a sim deployment would ignore the
seed; and that the sim backend was not run because the clone registers `close_drawer` in its own registry and not with
`gymnasium.register`.

Safety: simulated R0 device. There is no hardware backend and no native stop. The e-stop is the runtime's latching
software stop: after it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the last world
state stays readable. A simulated world step has no physical effect, so no operator-required limit is declared.

Tags: oopsieverse, robocasa, robosuite, mujoco, damage, manipulation, simulation, gymnasium
