# Facts and tags for gh.snu-pi/humanoidtoolbench

Every fact cites its source at commit `2cd4f006f6f2ebc536a3fb45aff8ce2eaf1382d7`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Every condition is registered as humanoidtoolbench/{scenario}-L{level}-{mode} for the three scenarios, three levels and two modes, with entry point humanoidtoolbench.envs.sonic_loco_manip:SonicLocoManipEnv | upstream_code | src/humanoidtoolbench/envs/__init__.py:25-38 |
| Every cell is registered with max_episode_steps=3000, one minute at the 50 Hz control rate | upstream_code | src/humanoidtoolbench/envs/__init__.py:27-37 |
| Environment IDs have the form humanoidtoolbench/G1<Scenario>-L<level>-<mode>; the default condition is G1BallMove-L0-S | vendor_doc | docs/ENVIRONMENTS.md:11-15 |
| Every condition uses 3000 policy-control steps per episode at 50 Hz | vendor_doc | docs/ENVIRONMENTS.md:3-7 |
| SonicLocoManipEnv.reset takes seed and options and returns (observation, info); step takes one action and returns (observation, reward, terminated, truncated, info) | upstream_code | src/humanoidtoolbench/envs/sonic_loco_manip.py:57-99 |
| A control step applies the action and advances the simulator control_decimal times, where control_decimal = (1/physics_dt)/render_hz | upstream_code | src/humanoidtoolbench/envs/sonic_loco_manip.py:70-80 |
| The task metadata declares physics_dt 0.005 s, control_hz 200 and render_hz 50 | upstream_code | src/humanoidtoolbench/tasks/g1_toolbench_tabletop.py:70-73 |
| The G1 whole-body robot has wholebody_dof 43 | upstream_code | src/humanoidtoolbench/robots/g1_sonic.py:118 |
| The whole-body joint list is 6 left leg, 6 right leg, 3 waist, 7 left arm, 7 right arm, 7 left hand and 7 right hand joints | upstream_code | src/humanoidtoolbench/robots/g1_sonic.py:32-94 |
| The action space is a Dict of seven Box spaces named left_leg, right_leg, waist, left_arm, right_arm, left_eef and right_eef | upstream_code | src/humanoidtoolbench/robots/controllers/combo.py:44-56 |
| The leg, waist and arm joint-position controllers bound every joint to -1 to 1 | upstream_code | src/humanoidtoolbench/robots/controllers/qpos.py:22-23 |
| The dexterous-hand controllers bound every hand joint to -pi to pi | upstream_code | src/humanoidtoolbench/robots/controllers/eef.py:18-22 |
| The observation space starts with joint_qpos, a Box from -pi to pi with shape wholebody_dof | upstream_code | src/humanoidtoolbench/tasks/g1_toolbench_tabletop.py:165-174 |
| The observation space also declares a head stereo pair and left and right wrist camera spaces | upstream_code | src/humanoidtoolbench/tasks/g1_toolbench_tabletop.py:86-120 |
| A camera observation space is a Box from 0 to 255 with shape (height, width, 3) | upstream_code | src/humanoidtoolbench/sensors/config.py:45-48 |
| Every camera stream is 640 by 360 pixels | upstream_code | src/humanoidtoolbench/tasks/g1_toolbench_tabletop.py:38-41 |
| The environment returns joint_qpos as a float32 array from the MuJoCo simulator, and render_obs decides whether camera frames are added | upstream_code | src/humanoidtoolbench/envs/sonic_loco_manip.py:40-48 |
| The environment terminates on task success or failure and its step returns truncated False | upstream_code | src/humanoidtoolbench/envs/sonic_loco_manip.py:86-99 |
| The reward is the task's compute_reward result; ToolReasoningTask returns the lifted height fraction | upstream_code | src/humanoidtoolbench/tasks/tool_reasoning.py:316-318 |
| Task.reset(seed) seeds the layout randomizers: DRManager.reset sets Python's random and numpy seeds when a seed is given | upstream_code | src/humanoidtoolbench/dr/manager.py:29-36 |
| SonicLocoManipEnv.__init__ requires a sonic_config mapping | upstream_code | src/humanoidtoolbench/envs/sonic_loco_manip.py:22-39 |
| The evaluation CLI creates the environment with gym.make and passes split, sim_mode, physics_dt, headless and sonic_config | upstream_code | src/humanoidtoolbench/cli/eval_decoupled_wbc.py:154-161 |
| The project requires Python 3.10.* and depends on mujoco 3.11.0, gymnasium > 0.29.1, numpy 1.26.4, torch 2.7.0 and gear_sonic | upstream_code | pyproject.toml:8-22 |
| The README requires Linux x86_64 with an NVIDIA GPU and EGL headless rendering | vendor_doc | README.md:20-28 |
| The docs describe a (T, 36) policy action chunk of 50 Hz controller commands, separate from the environment action vector | vendor_doc | docs/PUBLIC_EVALUATION.md:246-259 |
| The docs state joint angles and angular commands use radians, base height metres and navigation velocities metres per second | vendor_doc | docs/PUBLIC_EVALUATION.md:261-266 |
| The docs state the raw robot observation has 43 joint values and the policy state excludes the leg joints | vendor_doc | docs/PUBLIC_EVALUATION.md:267-269 |

Limits: the driver declares none of its own. The only bounds are the action space, which the Gymnasium bridge derives
from the fake environment: `action.left_leg`, `action.right_leg`, `action.left_arm` and `action.right_arm` are arrays
of 6, 6, 7 and 7 values from -1 to 1 (`controllers/qpos.py:22-23`), `action.waist` is three values from -1 to 1,
`action.left_eef` and `action.right_eef` are arrays of 7 values from -pi to pi (`controllers/eef.py:18-22`), plus the
bridge's `ticks` bound (1 to 10000). The device is simulated (R0), so no limit is `operator_required` and the package
needs no `site-limits.example.json`.

The environment's action space is the whole-body controller's 43-value `Dict`; the `(T, 36)` policy contract in
`docs/PUBLIC_EVALUATION.md:246-259` is the policy-server interface, which the controller decodes into those 43 joint
targets. It is not the Gymnasium action space this driver exposes.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:humanoidtoolbench/G1BallMove-L0-S`, level F0
(the fake is kinematic: joint positions are set to the commanded values, with no dynamics, contacts, actuator, sensor
or noise model), determinism `seeded` with `seed_control` `parameter` (the upstream reset seeds the layout
randomizers), `timestep_ms` 5 ms (the task physics step, four of which make one 20 ms control step, as FID-015
requires when the two are separated), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the last world state stays readable.

Tags: humanoid, humanoidtoolbench, mujoco, tool-use, reinforcement-learning, simulation, gymnasium

NOT COVERED by the fake and not claimed: the MuJoCo rigid-body dynamics, contacts, actuator forces and the whole-body
controller; the layout and object randomization; the task success and failure predicates, the contact metrics and the
reward; the four camera streams (head stereo left and right, wrist left and right), each 640 by 360 by 3 uint8 in the
real observation, which the driver only names in its fidelity `gaps`; rendering; the sim backend (not run), which needs
the upstream stack and a `sonic_config` from the evaluation CLI.
