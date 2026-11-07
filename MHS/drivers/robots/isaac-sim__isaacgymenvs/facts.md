# Facts and tags for gh.isaac-sim/isaacgymenvs

Every fact cites its source at commit `aeed298638a1f7b5421b38f5f3cc2d1079b6d9c3`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository contains example reinforcement-learning environments for the NVIDIA Isaac Gym | vendor_doc | README.md:8 |
| Isaac Gym itself is a separate Preview 4 download installed before this repository, so the simulator is external to the clone | vendor_doc | README.md:13-14 |
| The public factory is isaacgymenvs.make(seed, task, num_envs, sim_device, ...) | upstream_code | isaacgymenvs/__init__.py:14 |
| The documented Ant example calls isaacgymenvs.make(seed=0, task="Ant", num_envs=..., sim_device="cuda:0", rl_device="cuda:0") | vendor_doc | README.md:39-45 |
| Ant is the task class behind task="Ant": class Ant(VecTask) | upstream_code | isaacgymenvs/tasks/ant.py:41 |
| Ant sets numObservations to 60 and numActions to 8 | upstream_code | isaacgymenvs/tasks/ant.py:67-68 |
| The observation concatenates 1 torso height, 3 local velocities, 3 local angular velocities, yaw, roll, target angle, up projection, heading projection, 8 scaled joint positions, 8 scaled joint velocities, 24 contact-force values and 8 actions (60 values) | upstream_code | isaacgymenvs/tasks/ant.py:401-406 |
| The observation space is a Box from -inf to +inf over num_observations values | upstream_code | isaacgymenvs/tasks/base/vec_task.py:107 |
| The action space is a Box from -1 to 1 over num_actions values | upstream_code | isaacgymenvs/tasks/base/vec_task.py:113 |
| The Ant configuration sets clipActions to 1.0 | upstream_code | isaacgymenvs/cfg/task/Ant.yaml:13 |
| VecTask.step clamps every action to -clip_actions .. clip_actions before applying it | upstream_code | isaacgymenvs/tasks/base/vec_task.py:374 |
| The Ant episode length is 1000 control steps | upstream_code | isaacgymenvs/cfg/task/Ant.yaml:10 |
| An agent is reset when its progress reaches max_episode_length - 1, or when its torso height falls below termination_height | upstream_code | isaacgymenvs/tasks/ant.py:368-369 |
| The Ant termination height is 0.31 and a fallen agent receives the death cost | upstream_code | isaacgymenvs/cfg/task/Ant.yaml:29 |
| A fallen agent (torso height below termination_height) is reset | upstream_code | isaacgymenvs/tasks/ant.py:368 |
| The Ant timestep is dt=0.0166 s (1/60 s) | upstream_code | isaacgymenvs/cfg/task/Ant.yaml:43 |
| Ant takes its dt from the simulation configuration | upstream_code | isaacgymenvs/tasks/ant.py:112 |
| A reset draws joint positions uniformly from -0.2 to 0.2 and joint velocities uniformly from -0.1 to 0.1 | upstream_code | isaacgymenvs/tasks/ant.py:257-258 |
| The install requires gym==0.23.1, the legacy Gym API | upstream_code | setup.py:17 |

Limits: the driver declares none. The only bounds are the action Box (`action.values` from -1 to 1, derived by the
Gymnasium bridge from the fake's action space) and the bridge's `ticks` input (1 to `max_ticks`, 10000 by default).
The device is simulated (R0), so no limit is `operator_required`.

Fake (`fake.py`): a pure Python kinematic stand-in for the Ant task. It never imports the clone or Isaac Gym, which is
an external Preview 4 download (README.md:13-14). It exposes only `reset` and `step`, both inherited by `Ant` from
`VecTask`, and the `action_space`, `observation_space` and `dt` members those classes define. It returns a 60-element
observation in the upstream layout and accepts 8 action values clipped to -1..1. Its dynamics numbers are placeholders
marked in the source and are not facts. `close` is absent because the upstream class has none.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `isaacgymenvs:Ant` (kinematic stand-in), level F0
(kinematic, no rigid-body dynamics or contacts), determinism `seeded` with `seed_control` `parameter`, timestep 16.6 ms
(`Ant.yaml:43`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not
modelled: no physics, no contacts, no actuators, the fake's array values are synthetic, the upstream returns the legacy
four-tuple, and the real `isaacgymenvs.make` path (external Isaac Gym, CUDA) was not run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (there is no native actuator or stop method);
after it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the last observation stays
readable.

Tags: isaac-gym, ant, quadruped, reinforcement-learning, simulation, gymnasium
