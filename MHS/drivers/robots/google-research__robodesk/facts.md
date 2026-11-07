# Facts and tags for gh.google-research/robodesk

Every fact cites its source at commit `a8edde34f879242730c026dfe7c6e3beb4318023`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| RoboDesk is a Gymnasium environment: the class subclasses gym.Env | upstream_code | robodesk/robodesk.py:16 |
| The environment loads the MuJoCo scene model robodesk/assets/desk.xml | upstream_code | robodesk/robodesk.py:23-24 |
| The MuJoCo model integrates with a 2 ms timestep (0.002 s) | upstream_code | robodesk/assets/desk.xml:5 |
| Each environment step applies the action action_repeat times and runs the physics 10 times per application | upstream_code | robodesk/robodesk.py:170-176 |
| The action space is Box(-1, 1, (5,)): five end-effector control values, each between -1 and 1 | vendor_doc | README.md:109-115 |
| The action is five-dimensional (action_dim = 5) | upstream_code | robodesk/robodesk.py:34 |
| The robot has nine actuated joints (num_joints = 9) | upstream_code | robodesk/robodesk.py:29 |
| The observation is a dictionary with image, qpos_robot, qvel_robot, end_effector, qpos_objects and qvel_objects | vendor_doc | README.md:96-107 |
| The image observation space is Box(0, 255, (image_size, image_size, 3), uint8) | upstream_code | robodesk/robodesk.py:104-105 |
| The constructor defaults image_size to 64 pixels | upstream_code | robodesk/robodesk.py:19-20 |
| The observation spaces are 9 floats for qpos_robot and qvel_robot, 3 floats for end_effector and 26 floats for qpos_objects and qvel_objects | upstream_code | robodesk/robodesk.py:106-111 |
| The observation key qpos_objects is populated from physics.data.qvel, not qpos | upstream_code | robodesk/robodesk.py:385 |
| An episode ends when episode_length is set and num_steps reaches it; there is no other termination condition in step() | upstream_code | robodesk/robodesk.py:192-197 |
| The constructor defaults episode_length to 500 time steps | upstream_code | robodesk/robodesk.py:19-20 |
| The reward is the task reward clamped to the interval [0, 1] | upstream_code | robodesk/robodesk.py:375-378 |
| reset() takes no seed or options argument: it resets the physics, then randomizes the drawer, slide, blocks and ball and the robot start pose with numpy's global random generator | upstream_code | robodesk/robodesk.py:207-229 |
| The reward type is one of dense, sparse or success; task defaults to open_slide and reward to dense | upstream_code | robodesk/robodesk.py:19-21 |
| step returns (observation, reward, done, info) with info {'discount': 1.0} | upstream_code | robodesk/robodesk.py:197 |
| Episodes end after 500 time steps by default and there are no early terminations | vendor_doc | README.md:92-94 |

Limits: the driver declares none of its own. The only bound is the action space, which the Gymnasium bridge derives
from `RoboDesk.action_space` (`Box(-1, 1, (5,))`, README.md:114) and publishes as `action.values` per element; the
step input `ticks` is the bridge's 1 to 10000 bound. The device is simulated (R0) and has no operator-required limit.
The declared `timestep_ms` of 20 ms is one nominal control step at the constructor default `action_repeat=1`: ten
MuJoCo 2 ms integrations per environment step (robodesk/robodesk.py:170-176, robodesk/assets/desk.xml:5).

Fidelity contract (`driver.py`, `fidelity = {...}`): the deployed model is the package's kinematic fake, so it is
declared F0 `custom:RoboDesk kinematic fake (upstream mujoco robodesk/assets/desk.xml not integrated)`, determinism
`statistical` with `seed_control` `none` because upstream reset() has no seed argument and draws from numpy's global
generator (robodesk/robodesk.py:207-229), timestep 20 ms, `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot and restore. The gaps say that the MuJoCo contacts, actuators, IK and rendering are not modelled, that the
fake image is 4 x 4 x 3 instead of the upstream 64 x 64 x 3 default, that the observations and reward are
placeholders, and that the fake was never compared with upstream.

Safety: simulated R0 device. The e-stop is the runtime's software latch (the environment has no native stop); after
it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable. No
hardware backend is declared and no hardware run is claimed.

Tags: robodesk, mujoco, manipulation, robot-arm, reinforcement-learning, simulation, gymnasium
