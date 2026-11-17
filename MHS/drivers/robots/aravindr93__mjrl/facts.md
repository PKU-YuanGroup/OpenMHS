# Facts and tags for gh.aravindr93/mjrl

Every fact cites its source at commit `3871d93763d3b49c4741e6daeaebbc605fe140dc`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (a Python file or an MJCF file of the clone).  The same facts are written
into `facts = [...]` in `driver.py`; the reference file is generated from the driver, not from this page.

The card's entry symbol `mjrl.envs.swimmer:SwimmerEnv` was confirmed in the clone: `mjrl/envs/swimmer.py:6` defines
the class, `mjrl/envs/swimmer.py:8` constructs it from `swimmer.xml`, and `mjrl/envs/__init__.py:15` names it in the
`mjrl_swimmer-v0` registration.  The package serves the card's `swimmer.xml` model (the fourth entry of the card's
`models` list and the file that entry environment loads) as a `MujocoDriver`.  The model is read from the read-only
clone in place; the package copies neither the model nor its assets.

| fact | source | ref |
|---|---|---|
| The README describes the package as implementations of various RL algorithms for continuous control tasks simulated with MuJoCo | vendor_doc | README.md:3 |
| The README lists MuJoCo, python=3.7, gym>=0.13, mujoco-py>=2.0 and pytorch>=1.0 as the main dependencies | vendor_doc | README.md:6 |
| setup.py describes the package as 'RL algorithms for environments in MuJoCo' | upstream_code | setup.py:18 |
| mjrl_swimmer-v0 is registered with entry_point mjrl.envs:SwimmerEnv and max_episode_steps 500 | upstream_code | mjrl/envs/__init__.py:13-17 |
| SwimmerEnv subclasses mujoco_env.MujocoEnv and utils.EzPickle | upstream_code | mjrl/envs/swimmer.py:6 |
| SwimmerEnv constructs MujocoEnv with the model name 'swimmer.xml' and frame_skip 5 | upstream_code | mjrl/envs/swimmer.py:8 |
| mujoco_env resolves a relative model path under its own assets directory and loads it with load_model_from_path, wrapped in MjSim | upstream_code | mjrl/envs/mujoco_env.py:17-25 |
| The action space is a Box whose low and high are the columns of model.actuator_ctrlrange | upstream_code | mjrl/envs/mujoco_env.py:56-59 |
| The environment step time is model.opt.timestep times frame_skip | upstream_code | mjrl/envs/mujoco_env.py:116-118 |
| do_simulation writes ctrl for every actuator and calls sim.step frame_skip times | upstream_code | mjrl/envs/mujoco_env.py:120-124 |
| SwimmerEnv.step returns reward -10.0 times the change of qpos[0] and done False | upstream_code | mjrl/envs/swimmer.py:11-22 |
| SwimmerEnv.get_obs concatenates qpos[2:] and the whole qvel | upstream_code | mjrl/envs/swimmer.py:24-28 |
| SwimmerEnv.reset_model draws qpos[2] uniformly from -pi to pi and keeps the other initial values | upstream_code | mjrl/envs/swimmer.py:30-35 |
| The model root element is '<mujoco model="swimmer">' and its compiler sets inertiafromgeom true and angle radian | upstream_code | mjrl/envs/assets/swimmer.xml:4-5 |
| The global default class declares limited=true range -1.5 1.5 for joints and ctrllimited=true ctrlrange -1 1 for motors | upstream_code | mjrl/envs/assets/swimmer.xml:6-8 |
| The option element sets timestep 0.005 s, viscosity 0.000894 and density 1000 | upstream_code | mjrl/envs/assets/swimmer.xml:16 |
| The torso body carries two slide joints and one hinge joint, and the tail is a chain of the hinge joints j1, j2, j3 and j4 | upstream_code | mjrl/envs/assets/swimmer.xml:29-52 |
| The actuator section declares four motor actuators, on joints j1 to j4 with gear 20, and states no ctrlrange on any of them | upstream_code | mjrl/envs/assets/swimmer.xml:59-63 |

Limits: a `MujocoDriver` declares no `Limit` for its action; the bridge derives `cap.world.step.v1` `action.ctrl`
from `model.actuator_ctrlrange`.  The four motors of `mjrl/envs/assets/swimmer.xml:59-63` state no range, and the
global default class of `mjrl/envs/assets/swimmer.xml:6-8` gives motors `ctrllimited="true" ctrlrange="-1 1"`, so
the bridge derives a -1 to 1 interval for each of the four controls (one per-element rule, `upstream_code`, ref
`mjrl/envs/assets/swimmer.xml:actuator_ctrlrange`).  That is the same array the upstream sets its action Box from
(`mjrl/envs/mujoco_env.py:56-59`), so the package invents no control bound and needs no operator overlay.  The model
states no numeric limit on any other input of the served classes.

Fidelity: the class-level contract describes the real MuJoCo engine (F1); `fidelity_by_backend` selects the
F0 contract of the package's fake, which is a stand-in for the `mujoco` library (fake.py), not MuJoCo.  The
stand-in reads the model for the joint layout, the actuator count, the inherited control ranges and the option
time step. Its placeholder integrator applies each motor's gear-scaled effort against an independent unit inertia;
it does not treat the control as a position target and resolves no body inertia, fluid drag, coupling, joint-limit
forces, mesh, contact, water, camera or sensor. The upstream swimmer task layer is not served: the reward, the
12-value observation, the random
`qpos[2]` reset and the 500-step time limit are NOT COVERED, and no physical device is modelled.  MuJoCo was not
importable where the gate ran, so no trajectory was compared with the real engine and the `sim` backend that
imports `mujoco` was not run.

Tags: continuous-control, gym, mujoco, reinforcement-learning, simulation, swimmer
