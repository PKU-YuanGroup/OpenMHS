# Facts and tags for gh.rgalljamov/drloco

Every fact cites its source at commit `3a1e4999b726be67dccc5d332b52edb76a7bde09`. The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from
this page.

| fact | source | ref |
|---|---|---|
| The README titles the project Deep Reinforcement Learning by Imitation with MuJoCo and Stable Baselines 3 | vendor_doc | README.md:2 |
| The README says the repository implements DeepMimic and learns controllers for walking robots simulated with the MuJoCo physics engine | vendor_doc | README.md:6-9 |
| The documentation says the environment's step runs the simulation for the configured number of frames and that the MuJoCo simulation runs at 1 kHz, with the policy control frequency equal to the simulation frequency divided by the frame skip | vendor_doc | docs/scripts/mimic_env.rst:21-29 |
| MimicEnv subclasses gym's MujocoEnv and gym.utils.EzPickle | upstream_code | drloco/mujoco/mimic_env.py:18 |
| MimicEnv reads the control frequency from the configuration, computes the frame skip from it and initializes MujocoEnv with the MJCF path and that frame skip | upstream_code | drloco/mujoco/mimic_env.py:47-52 |
| MimicEnv.step(action) rescales the action before applying it to the simulation | upstream_code | drloco/mujoco/mimic_env.py:60-83 |
| The upstream step applies the same action for the configured frame skip with do_simulation and, on a MuJoCo exception, resets the environment and ends the episode | upstream_code | drloco/mujoco/mimic_env.py:81-91 |
| The upstream step ends the episode when the COM z position is below 0.5 or the episode reaches the configured maximum length, and returns the old gym four-tuple (observation, reward, done, info) | upstream_code | drloco/mujoco/mimic_env.py:116-126 |
| The alive bonus is 0.2 and the maximum episode duration is 3000 control steps | upstream_code | drloco/config/hypers.py:51-58 |
| The default environment id is StraightMimicWalker with a control frequency of 200 Hz | upstream_code | drloco/config/config.py:18-21 |
| The configured simulation frequency of StraightMimicWalker is 1000 Hz | upstream_code | drloco/mujoco/config.py:5-14 |
| _rescale_actions clips the policy action to [-1, 1] and scales each element by the action space's high or low value; the comment calls those the joint torque ranges specified in the MJCF file | upstream_code | drloco/mujoco/mimic_env.py:170-192 |
| The observation concatenates the phase variable, the desired walking speed, the joint positions without COM x and the joint velocities | upstream_code | drloco/mujoco/mimic_env.py:403-431 |
| The upstream reset_model takes the initial qpos and qvel from the reference trajectories and applies them to the simulation | upstream_code | drloco/mujoco/mimic_env.py:526-539 |
| The upstream reset lowers the COM z position by the lowest foot corner so that the walker starts in ground contact | upstream_code | drloco/mujoco/mimic_env.py:541-559 |
| MimicWalker3dEnv is the main 3D bipedal walker environment and loads drloco/mujoco/xml/walker3d_flat_feet.xml | upstream_code | drloco/mujoco/mimic_walker3d.py:27-40 |
| MimicWalker165cm65kgEnv loads drloco/mujoco/xml/walker_165cm_65kg.xml | upstream_code | drloco/mujoco/mimic_walker_165cm_65kg.py:20-28 |
| The MJCF root element is <mujoco model="walker3d"> and its compiler element declares angle radian, coordinate local and inertiafromgeom false | upstream_code | drloco/mujoco/xml/walker3d_flat_feet.xml:1-2 |
| The default class gives every motor ctrllimited true, ctrlrange -300 300, gear 1, forcelimited true and forcerange -300 300 | upstream_code | drloco/mujoco/xml/walker3d_flat_feet.xml:6-10 |
| The option element selects the RK4 integrator with timestep 0.001 s | upstream_code | drloco/mujoco/xml/walker3d_flat_feet.xml:11 |
| The torso body is at 0 0 1.08 and its inertial element gives mass 53.5 | upstream_code | drloco/mujoco/xml/walker3d_flat_feet.xml:15-16 |
| The torso carries three slide joints (com_x, com_y, com_z) and three hinge joints (trunk_rot_x, trunk_rot_y, trunk_rot_z); com_z has joint position 0 0 -1.08 and ref 1.08 | upstream_code | drloco/mujoco/xml/walker3d_flat_feet.xml:18-23 |
| The right leg has a sagittal hip joint with range -0.8727 0.8727 rad, a frontal hip joint with range -0.7854 0.0873 rad, a knee joint with range 0 2.6180 rad and an ankle joint with range -0.3491 0.6981 rad | upstream_code | drloco/mujoco/xml/walker3d_flat_feet.xml:28-37 |
| The left leg has a sagittal hip joint with range -0.8727 0.8727 rad, a frontal hip joint with range -0.0873 0.7854 rad, a knee joint with range 0 2.6180 rad and an ankle joint with range -0.3491 0.6981 rad | upstream_code | drloco/mujoco/xml/walker3d_flat_feet.xml:50-59 |
| The actuator section declares one motor actuator for each of the eight actuated leg joints | upstream_code | drloco/mujoco/xml/walker3d_flat_feet.xml:71-80 |

Limits: the driver declares none. `cap.world.step.v1` takes `{ticks, action: {ctrl: [8 numbers]}}`; the
bridge derives the per-element control bounds from the model's `actuator_ctrlrange`, which the global
default motor class states as -300 to 300 (`drloco/mujoco/xml/walker3d_flat_feet.xml:8`), and refuses an
out-of-range element with `MHS.SAFETY.ENVELOPE_VIOLATION` before writing `data.ctrl`. `ticks` is
bounded by the bridge (1 to `max_ticks`, 10000). The model gives every actuator a range, so no control is
`operator_required` and no `site-limits.example.json` is needed. The device is simulated (R0).

Contract: `MujocoDriver` serves `cap.world.step.v1` and `cap.world.reset.v1` on the `world` resource.
A step applies the control vector and integrates `ticks` times; the state is `{time_ms, qpos, qvel,
ctrl, tick, timestep_ms, seed, native_checkpoint}`, with 14 qpos values (three COM slides, three trunk
hinges and four joints per leg) and 14 qvel values. A reset calls `mj_resetData` and `mj_forward`,
restoring the model defaults (`com_z` starts at its `ref` of 1.08); a seed is accepted for the class
contract but a MuJoCo reset does not use it.

Fidelity contract (`driver.py`, `fidelity` and `fidelity_by_backend`): the real engine path is
`mujoco:walker3d_flat_feet`, level F1, determinism `none` with `seed_control` `none`, timestep 1 ms
(`walker3d_flat_feet.xml:11`), `realtime_factor` 0, clock `lockstep`, reset `full`, snapshot and restore
available. The fake backend publishes `analytic:stand-in mujoco module (no physics)`, level F0, same
1 ms lockstep timestep, and the gaps list every difference: the stand-in is not MuJoCo, it has no
contact, inertia, actuator or sensor dynamics, and the bridge uses its basic checkpoint profile. The
upstream environment task layer (normalized action, observation, reward, termination, reference
trajectory reset) is NOT COVERED by the model-level bridge.

Safety: simulated R0 device. The e-stop is the runtime's software latch; there is no native stop and no
physical e-stop claim. After an e-stop no step or reset is accepted until `mhs.safety.reset` clears the
latch (a simulator needs no operator for that), and the state stays readable.
Safety reset advances no ticks and retains the stored control vector. A later explicit step without a new action
reuses it.

Tags: drloco, deepmimic, biped, legged, mujoco, mjcf, walker, simulation
