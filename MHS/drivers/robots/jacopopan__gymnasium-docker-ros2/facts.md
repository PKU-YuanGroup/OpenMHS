OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.jacopopan/gymnasium-docker-ros2

Every fact cites the pinned clone at commit `b3a00f77da38b7f074bed00d3569c56dbfe114df`:
`upstream_code` refs name `path/in/clone:LINE` (a bounded range where the statement spans
adjacent lines). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| GDR2Env derives from gym.Env and models a simple 1D point-mass system whose state is position and velocity and whose action is one force value. | upstream_code | src/gymnasium_docker_ros2/env.py:11-18 |
| The environment advertises the human render mode with render_fps 20. | upstream_code | src/gymnasium_docker_ros2/env.py:19 |
| The constructor sets max_steps to 1000 and dt to 0.05. | upstream_code | src/gymnasium_docker_ros2/env.py:24-25 |
| The observation space is Box([-1.0, -5.0], [1.0, 5.0], dtype=float32) over position and velocity. | upstream_code | src/gymnasium_docker_ros2/env.py:27-31 |
| The action space is Box(low=-1.0, high=1.0, shape=(1,), dtype=float32), one force value. | upstream_code | src/gymnasium_docker_ros2/env.py:33-34 |
| The constructor creates a Docker network named gdr2-network, the simulation-container and dynamics-container from gdr2-image:latest, and a ZeroMQ REQ socket to 10.42.0.20:5555. | upstream_code | src/gymnasium_docker_ros2/env.py:44-116 |
| reset sends the special control value 9999.0 over ZeroMQ, unpacks a ddii position/velocity/time reply, stores position and velocity and resets step_count. | upstream_code | src/gymnasium_docker_ros2/env.py:124-160 |
| step sends the force over ZeroMQ, unpacks the same ddii position/velocity/time reply and stores position and velocity. | upstream_code | src/gymnasium_docker_ros2/env.py:162-179 |
| A step returns reward -abs(position), terminated false, truncated when step_count reaches max_steps, and (observation, reward, terminated, truncated, info). | upstream_code | src/gymnasium_docker_ros2/env.py:198-214 |
| close stops the simulation and dynamics containers, removes the network and closes the ZeroMQ socket and context. | upstream_code | src/gymnasium_docker_ros2/env.py:231-256 |
| _get_obs returns the float32 array [position, velocity] and _get_info returns position and velocity. | upstream_code | src/gymnasium_docker_ros2/env.py:118-122 |
| test.py registers GDR2Env-v0 with entry_point GDR2Env and creates the environment with render_mode human. | upstream_code | test.py:18-23 |
| The declared runtime requires Python ^3.13 with numpy, gymnasium, docker and pyzmq. | upstream_code | pyproject.toml:10-19 |
| The README describes GDR2 as a multi-container Docker/Gazebo/ROS2 app wrapped in gymnasium, installed with pip install -e . and exercised with test.py --mode step, speed or learn. | vendor_doc | README.md:3-24 |
| DynamicsNode computes dt as 1.0 / rate and seeds NumPy to 42 once at construction. | upstream_code | resources/ros2_ws/src/dynamics/dynamics/dynamics_node.py:14-21 |
| The DynamicsNode command line defaults rate to 50 Hz. | upstream_code | resources/ros2_ws/src/dynamics/dynamics/dynamics_node.py:64-66 |
| The simulation launch runs the dynamics node with --rate 20. | upstream_code | resources/tmux_session.yml.erb:18 |
| The world SDF fixes max_step_size to 0.050 s and real_time_factor to 0.0. | upstream_code | resources/gdr2-world.sdf:4-6 |
| The dynamics reset branch triggers within 0.1 of control input 9999.0, draws position uniformly from -0.8 to 0.8 and sets velocity to 0. | upstream_code | resources/ros2_ws/src/dynamics/dynamics/dynamics_node.py:39-43 |
| The dynamics update integrates velocity += control_input * dt, multiplies velocity by 0.99, integrates position += velocity * dt, clips position to [-1, 1] and multiplies velocity by -0.5 at a wall. | upstream_code | resources/ros2_ws/src/dynamics/dynamics/dynamics_node.py:44-52 |
| The Python ZeroMQ bridge requests one Gazebo multi-step per request with a 1 s service timeout, then waits up to 2.0 s for a new /state and packs the reply as ddii. | upstream_code | resources/zeromq_bridge.py:78-96 |

## Scope and deviation from the card

The card names `RosDriver`, but the confirmed entry symbol `gymnasium_docker_ros2.env:GDR2Env`
is a Gymnasium environment (`src/gymnasium_docker_ros2/env.py:11`), not a ROS transport client.
The ROS 2 `dynamics` node and the ZeroMQ/Gazebo bridge are the environment's backend, not its
public interface; wrapping them with `RosDriver` would replace `reset`/`step` with observation-
only endpoints. This package is therefore a `GymnasiumDriver` over the Gymnasium interface
(`DEVIATION FROM THE CARD` in `RESULT.json`). The bridge serves `cap.world.step.v1`,
`cap.world.reset.v1` and `cap.world.seed.v1`; the action space is the upstream
`Box(low=-1.0, high=1.0, shape=(1,))` and its per-element limit is derived from the
fake backend and cited by `action_space_ref` to `src/gymnasium_docker_ros2/env.py:34`.

## Fake backend

The gate has no Docker daemon, ROS 2, Gazebo or ZeroMQ, and the upstream constructor starts
Docker containers (`env.py:44-116`). The `fake` backend is the package's own pure Python
model of the upstream dynamics node (`dynamics_node.py:39-52`): one Euler point-mass update
per step, the reset draw from [-0.8, 0.8], reward -abs(position), truncation at 1000 steps and
the two-value observation. It copies the upstream action space, which is why that line is
cited. It does not reproduce Docker, ZeroMQ, ROS 2, Gazebo, the /state round trip, contacts,
actuators, sensors, noise or rendering. The live dynamics node seeds NumPy once to 42 and
ignores the Gymnasium seed; the fake reseeds from `reset(seed)` so its own seed control is
real. The start state and reset draws are test data, not facts.

## Safety

The device is simulated at R0. There is no hardware backend, no physical e-stop and no
numeric input requiring an operator limit. An e-stop latches in software and the runtime
refuses `cap.world.step.v1`, `cap.world.reset.v1` and `cap.world.seed.v1` until
`mhs.safety.reset` clears the latch; reads of the last world state remain available. This is
a simulation freeze, not a physical stop. The upstream `close` method stops its containers
(`env.py:231-256`), but closing is not declared as an e-stop or a safe-state action.

## Tags

`gymnasium`, `docker`, `ros2`, `gazebo`, `zeromq`, `point-mass`, `reinforcement-learning`, `simulation`

## Deployment boundary after source review

Only the declared fake backend is accepted as a contract test. There is no
package simulator factory; installing dependencies does not create one. Native
ROS process ownership, independent interruption/pause, seed behavior and fresh
response checks remain deployment work. The fake's software latch does not
prove that a real ROS/Gazebo world has stopped. No live backend was executed.

The upstream constructor removes/recreates a fixed-name Docker network and starts
fixed-name containers from a mutable image tag (`env.py:44-116`). Native step/reset
error branches can print a transport error and return cached state rather than
fail the operation (`env.py:124-214`). A future live adapter must validate fresh
replies and explicit resource ownership before construction; none is enabled here.
