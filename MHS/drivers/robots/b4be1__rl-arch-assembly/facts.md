# Facts and tags for gh.b4be1/rl-arch-assembly

Every fact cites its source at commit `187e460c79e41ae38e1b750d75e369f3473dd3eb`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (a file of the clone with its line). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The project documentation says the task package defines the gym environment used to train the placing controller | vendor_doc | README.md:55 |
| StackingTask is the task in which the robot stacks a given number of parts on an existing structure | upstream_code | python/task/stacking_task.py:26-29 |
| BaseTask is the gym.Env base of the task classes | upstream_code | python/task/base_task.py:25 |
| BaseTask.initialize builds observation_space and action_space as gym.spaces.Dict from the sensors and controllers | upstream_code | python/task/base_task.py:73-87 |
| BaseTask.step returns the legacy four-value tuple observation, reward, done, info | upstream_code | python/task/base_task.py:146 |
| BaseTask.reset takes no seed or options and returns only the initial observation | upstream_code | python/task/base_task.py:160-181 |
| BaseTask.step ends the episode when the configured time_limit_steps is reached | upstream_code | python/task/base_task.py:111-112 |
| Controller.initialize returns a normalized gym.spaces.Box action in [-1, 1] per joint | upstream_code | python/task/controllers/controller.py:33-35 |
| ContinuousSensor normalizes every observation to [-1, 1] and clips only when clip=True | upstream_code | python/task/sensors/continuous_sensor.py:18-22 |
| The controller interval of the canonical stacking configuration is 0.05 s and time_limit_steps is round(time_limit_s / controller_interval) | upstream_code | python/algorithm/run_config/env/stacking.py:25-26 |
| The canonical stacking configuration uses a joint-velocity-difference arm controller and a joint-position gripper controller | upstream_code | python/algorithm/run_config/env/stacking.py:33-38 |
| The canonical stacking configuration observes the arm joint sin/cos and velocity, the gripper joint angle and velocity, the end-effector pose and velocity, the current part's pose, velocity and target pose, and the time | upstream_code | python/algorithm/run_config/env/stacking.py:41-43 |
| The controller Dict key is '<name_prefix>_controller_<robot_name>_<component>' | upstream_code | python/task/controllers/robot_component_controller.py:22-23 |
| StackingTask requires controllers, sensors, rewards, a task path, aggregation properties, spawn position and orientation limits and a target position; it has no zero-argument constructor | upstream_code | python/task/stacking_task.py:31-41 |
| The episode ends when the last part is released from the gripper, or when the optional target-reached condition is enabled and met | upstream_code | python/task/stacking_task.py:142-154 |
| assembly-gym is declared as the git submodule at submodule/assembly-gym | upstream_code | .gitmodules:21-24 |

## Limits

The driver declares no Limit and no operator-required bound. The only limits are the bridge's derived action-space
bounds (`action.<controller>` in [-1, 1], from the controllers' normalized `gym.spaces.Box`) and the class's `ticks`
range (1 to `max_ticks`). They are derived from the fake environment's spaces at load, so they are not copied into
`driver.py`; there is no safety bound a human stated for this simulated task. The environment's own spawn-position,
spawn-orientation, grasp-offset, time-step and time-limit values are constructor arguments of `StackingTask` and of
`get_env_config`, not fixed device limits, so no value from them was turned into a Limit.

## Safety and risk

The device is `mode = "simulated"` and `risk = "R1"`: a tick advances a simulated UR10 arm, so a wrong action changes
simulated state, but there is no hardware backend, no physical actuator and no hardware stop. The card's floor is R0;
R1 reflects the simulation stepping described by MHS-004 section 2.1. A simulated R1 driver needs no independent
hardware stop (SAFE-045 is a hardware R2/R3 rule). The e-stop is the runtime's software latch: after it, no step,
reset or seed is accepted until `mhs.safety.reset` clears the latch, and the last state stays readable.

## Fidelity

The `fidelity` block in `driver.py` describes the analytic fake (F0), not the PyBullet upstream: engine
`rl-arch-assembly:StackingTask (analytic fake)`, determinism `seeded` with `seed_control = parameter` (the fake's
`random.Random(seed)`), `timestep_ms` 50.0, `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot/restore.
The gaps name what is absent: PyBullet and the scene, rigid-body dynamics, contacts, inverse kinematics, the task
data, the real reward and termination logic, rendering, DIGIT sensors, wrappers and a validated comparison with the
upstream environment; the fake stops at a placeholder episode-step count, not at the upstream part-release condition.

## Package notes

- The clone has no `LICENSE` file; the card's `license_spdx` is `NOASSERTION` and `license_class` is `unknown`. The
  lock records both unchanged and does not claim a licence.
- The upstream environment needs the `assembly-gym` submodule (`.gitmodules:21-24`), which is not present in the
  clone, plus PyBullet, gym, numpy and scipy. The gate does not install or import any of them; only the pure-Python
  fake backend was checked.
- The clone registers no gym id for `StackingTask`; the driver sets no `env_id`. The only backend is `fake`
  (`.fake:FakeStackingTask`), so there is no `sim` backend to run the upstream environment.
- The fake's numbers are placeholder test data. None of them is used as a Fact, a Limit or a reference.

Tags: assembly, gym, placing, reinforcement-learning, robot-arm, simulation, stacking, ur10
