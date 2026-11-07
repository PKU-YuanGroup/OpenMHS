# Facts and tags for gh.stanfordvl/lasersuite

Every fact cites its source at commit `8b78c3d202f2a4b8712c5f228feaf5fae61f16e9`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or `upstream_code`
(`path/in/clone.py:LINE`). The reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The entry class DoorOpen subclasses RobotEnv | upstream_code | `robosuite/environments/door_open.py:19` |
| RobotEnv subclasses MujocoEnv | upstream_code | `robosuite/environments/robot_env.py:8` |
| The project describes itself as a simulation benchmark powered by the MuJoCo physics engine | vendor_doc | `README.md:11` |
| The package install requires numpy, scipy and mujoco-py==2.0.2.9 | upstream_code | `setup.py:19-22` |
| The environment reset method calls _reset_internal, forwards the simulation and returns _get_observation() | upstream_code | `robosuite/environments/base.py:137-142` |
| The environment step method advances the simulation, collects the next observation and returns (next_state, reward, done, info) | upstream_code | `robosuite/environments/base.py:180-201` |
| The environment close method exists on the environment base class | upstream_code | `robosuite/environments/base.py:344` |
| The DoorOpen constructor default control_freq is 25 and its default horizon is 250 | upstream_code | `robosuite/environments/door_open.py:43-44` |
| The DoorOpen constructor default initialization_noise is 0.02 | upstream_code | `robosuite/environments/door_open.py:29` |
| The DoorOpen constructor defaults enable camera observations and name the agentview camera | upstream_code | `robosuite/environments/door_open.py:32-46` |
| The camera observation default is 256 pixels high and 256 pixels wide | upstream_code | `robosuite/environments/door_open.py:47-48` |
| The observation dictionary carries robot state and, when camera observations are enabled, one image per camera | upstream_code | `robosuite/environments/robot_env.py:247-273` |
| DoorOpen builds a TableArena, a DoorObject and a DoorTask from the robot models | upstream_code | `robosuite/environments/door_open.py:131-142` |
| The card's baxter model is an MJCF document whose root element is `<mujoco model="baxter">` | upstream_code | `robosuite/models/assets/robots/baxter/robot.xml:1` |
| The card's panda model is an MJCF document whose root element is `<mujoco model="panda">` | upstream_code | `robosuite/models/assets/robots/panda/robot.xml:1` |
| The card's sawyer model is an MJCF document whose root element is `<mujoco model="sawyer">` | upstream_code | `robosuite/models/assets/robots/sawyer/robot.xml:1` |
| The panda robot wrapper loads robots/panda/robot.xml as its model | upstream_code | `robosuite/models/robots/panda_robot.py:15` |

## Interface served

| member | kind | source |
|---|---|---|
| `reset()` | environment method, called by `cap.world.reset.v1` | `robosuite/environments/base.py:137-142` |
| `step(action)` | environment method, called once per `cap.world.step.v1` tick | `robosuite/environments/base.py:180-201` |
| `close()` | environment method, called by teardown | `robosuite/environments/base.py:344` |

The step returns `(next_state, reward, done, info)`; the driver reports `done` as `terminated`. The observation is a
dictionary; the real dictionary also carries the camera images named at `robosuite/environments/robot_env.py:264-273`,
which the package does not serve (see `RESULT.json` notes). The action vector is selected by `controller_configs`, a
constructor option (`robosuite/environments/door_open.py:21`), so the package declares no action bound and the fake
accepts any non-empty finite numeric vector.

## Units and ranges

- No physical unit is published for `tick`, `seed`, `reward` or `terminated`; the count fields use UCUM `1`.
- `timestep_ms` is 0: `control_freq` is a constructor option whose default is 25
  (`robosuite/environments/door_open.py:43`), so a tick counts one environment step, not a stated physical duration.
- The class schemas of `cap.world.step.v1` (ticks 1 to 10000) and `cap.world.reset.v1` (seed at least 0) are the
  catalogue's bounds, not device facts; the runtime enforces them before the driver is called.
- No `Limit` is declared by this package: nothing in the clone states a device action envelope, and the device is
  simulated (R0), so there is no hardware write to bound.

## Stop path

The device is simulated (R0): there is no hardware backend, no physical e-stop and no native stop. The runtime's
e-stop latch refuses `cap.world.reset.v1` and `cap.world.step.v1`; the last observation stays readable. The driver does
not claim a hardware stop, a watchdog or an independent stop.

Tags: `door-open`, `manipulation`, `mujoco`, `robosuite`, `simulation`, `robot`.
