OpenMHS is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Facts and tags for gh.alrhub/fancy_gym

Every fact cites its source at commit `da1bced0181ced8267247779c001509a2fc94635`; all sources here are
`upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| fancy/SimpleReacher-v0 is registered with entry point SimpleReacherEnv and n_links=2 | upstream_code | fancy_gym/envs/__init__.py:38-45 |
| fancy/SimpleReacher-v0 is registered with max_episode_steps=200 | upstream_code | fancy_gym/envs/__init__.py:42 |
| The action space is a Box with one torque per link, low=-1000 and high=+1000 (max_torque 1000) | upstream_code | fancy_gym/envs/classic_control/base_reacher/base_reacher_torque.py:16-18 |
| The simulation timestep is 0.01 s | upstream_code | fancy_gym/envs/classic_control/base_reacher/base_reacher.py:21 |
| A step adds dt times the torque to the angular velocity and then dt times the angular velocity to the joint angle | upstream_code | fancy_gym/envs/classic_control/base_reacher/base_reacher_torque.py:25-26 |
| The torque step returns terminated False and truncated False: the environment class has no terminal state | upstream_code | fancy_gym/envs/classic_control/base_reacher/base_reacher_torque.py:34-35 |
| Every link has length 1.0 | upstream_code | fancy_gym/envs/classic_control/base_reacher/base_reacher.py:19 |
| The distance reward starts at step 199 (steps_before_reward=199) | upstream_code | fancy_gym/envs/classic_control/simple_reacher/simple_reacher.py:31 |
| The reward is the distance term minus the sum of the squared torques; the distance term is zero before steps_before_reward | upstream_code | fancy_gym/envs/classic_control/simple_reacher/simple_reacher.py:63-69 |
| The observation concatenates cos(angle), sin(angle), angular velocity, end-effector minus goal and the step count | upstream_code | fancy_gym/envs/classic_control/simple_reacher/simple_reacher.py:75-83 |
| The observation space bounds the cos and sin components by +-pi and the velocity, target-distance and step components by infinity | upstream_code | fancy_gym/envs/classic_control/simple_reacher/simple_reacher.py:33-40 |
| A reset with random_start samples the first joint angle uniformly between pi/4 and 3*pi/4 and sets the other joints to zero | upstream_code | fancy_gym/envs/classic_control/base_reacher/base_reacher.py:77-86 |
| SimpleReacherEnv.reset generates a goal, resets, generates the goal again and resets again so a seeded reset is deterministic | upstream_code | fancy_gym/envs/classic_control/simple_reacher/simple_reacher.py:46-54 |
| The goal is drawn uniformly from a square of side 2*total_length until its norm is below total_length | upstream_code | fancy_gym/envs/classic_control/simple_reacher/simple_reacher.py:89-92 |
| The joint limits are -pi and +pi | upstream_code | fancy_gym/envs/classic_control/base_reacher/base_reacher.py:38-39 |
| A joint angle outside the joint limits is reported as a self collision | upstream_code | fancy_gym/envs/classic_control/base_reacher/base_reacher.py:105-112 |

Limits: The checked fake keeps two default-link torque action values in -1000..1000. The Gymnasium bridge derives these unchanged action bounds with source `upstream_code` and ref `fancy_gym/envs/classic_control/base_reacher/base_reacher_torque.py:16-18`, where the same-span ones assignment and Box construction state the bounds. The selected environment and width were source-reviewed separately; symbolic shapes alone do not prove a width. `ticks` remains the SDK bridge budget (1 to max_ticks, 10000 by default), not a device limit. This simulated R0 package declares no operator-required hardware limit.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:fancy/SimpleReacher-v0`, level F1 (a
torque-integrated kinematic arm, no contacts or actuator model), determinism `seeded` with `seed_control`
`parameter`, timestep 10 ms (`dt = 0.01` s, `base_reacher.py:21`), `realtime_factor` 0, clock `lockstep`, reset
`full`, no snapshot and restore. The gaps say what is not modelled, that the fake was not compared with the upstream
environment, and that the 200-step episode limit is the registration's TimeLimit.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable. There is no hardware
backend and no operator-required bound.

Tags: reacher, classic-control, torque-control, reinforcement-learning, simulation, gymnasium
