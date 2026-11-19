# Facts and tags for gh.nico-bohlinger/one_policy_to_run_them_all

Every fact cites its source at commit `7c1819444028c529b0a964fe3f32878333b1310a`: `vendor_doc` (a text file of the
clone, here README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the generated reference reads them from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is the implementation of the paper One Policy to Run Them All: an End-to-end Learning Approach to Multi-Embodiment Locomotion | vendor_doc | README.md:1-3 |
| The requirements pin mujoco 3.1.3 | upstream_code | requirements.txt:64 |
| The multi-robot module defines create_env(config), the environment factory | upstream_code | one_policy_to_run_them_all/environments/multi_robot/create_env.py:15 |
| AnymalB is registered in the ROBOTS list | upstream_code | one_policy_to_run_them_all/environments/multi_robot/robot_helper.py:41 |
| AnymalB is a gymnasium.Env subclass | upstream_code | one_policy_to_run_them_all/environments/anymal_b/environment.py:27 |
| AnymalB stores twelve nominal joint positions, twelve max_joint_velocities values of 15.0 and an initial_drop_height of 0.5 | upstream_code | one_policy_to_run_them_all/environments/anymal_b/environment.py:59-66 |
| AnymalB loads the MJCF with mujoco.MjModel.from_xml_path and then overwrites model.opt.timestep with the timestep of its configuration | upstream_code | one_policy_to_run_them_all/environments/anymal_b/environment.py:112-115 |
| The action-space size starts at model.nu and is replaced by multi_robot_max_action_size when that value is not -1; its Box has infinite lower and upper bounds | upstream_code | one_policy_to_run_them_all/environments/anymal_b/environment.py:132-140 |
| AnymalB.reset replaces the model state with the qpos and qvel of its initial-state function | upstream_code | one_policy_to_run_them_all/environments/anymal_b/environment.py:199-214 |
| AnymalB.step runs the action through the control function's process_action, writes the resulting torques to data.ctrl and calls mujoco.mj_step for nr_substeps | upstream_code | one_policy_to_run_them_all/environments/anymal_b/environment.py:246-252 |
| The shipped anymal_b configuration sets timestep 0.005 s and an episode length of 20 s | upstream_code | one_policy_to_run_them_all/environments/anymal_b/default_config.py:31-32 |
| Rudin2022Control defaults to a control frequency of 50 Hz, p_gain 80, d_gain 2.0 and a scaling factor of 0.5 | upstream_code | one_policy_to_run_them_all/environments/anymal_b/control_functions/rudin2022.py:2 |
| process_action scales the action by the scaling factor, adds the nominal joint positions and computes a PD torque from qpos[7:] and qvel[6:] | upstream_code | one_policy_to_run_them_all/environments/anymal_b/control_functions/rudin2022.py:24-29 |
| The default initial state puts the base at the initial drop height plus the terrain centre height and the twelve joints at their nominal positions | upstream_code | one_policy_to_run_them_all/environments/anymal_b/initial_state_functions/default.py:8-13 |
| The MJCF root element names the model anymal_b | upstream_code | one_policy_to_run_them_all/environments/anymal_b/data/anymal_b.xml:1 |
| The model uses radians, resolves its meshes from assets/ and enables autolimits | upstream_code | one_policy_to_run_them_all/environments/anymal_b/data/anymal_b.xml:2 |
| The model's option element selects the pyramidal cone and impratio 100 | upstream_code | one_policy_to_run_them_all/environments/anymal_b/data/anymal_b.xml:4 |
| The default joint is a hinge with damping 1, frictionloss 0.1 and range -3.14 to 3.14 | upstream_code | one_policy_to_run_them_all/environments/anymal_b/data/anymal_b.xml:10 |
| The default motor is ctrllimited with ctrlrange -40.0 to 40.0 | upstream_code | one_policy_to_run_them_all/environments/anymal_b/data/anymal_b.xml:56 |
| The world contains a plane floor and a trunk body at 0 0 0 that carries the free joint | upstream_code | one_policy_to_run_them_all/environments/anymal_b/data/anymal_b.xml:124-132 |
| The actuator section has twelve motor actuators, one per leg joint from LF_HAA to RH_KFE | upstream_code | one_policy_to_run_them_all/environments/anymal_b/data/anymal_b.xml:340-351 |
| The home keyframe holds 19 qpos values with the base at height 0.5 and the listed joint positions | upstream_code | one_policy_to_run_them_all/environments/anymal_b/data/anymal_b.xml:355 |

## Limits

The driver declares none of its own. `cap.world.step.v1` takes `{ticks, action: {ctrl: [12 numbers]}}`; the bridge
derives every `ctrl` element from the model's `actuator_ctrlrange` (`anymal_b.xml:56`, the default motor
`ctrlrange="-40.0 40.0"`, inherited by the twelve actuators) and refuses an out-of-range value with
`MHS.SAFETY.ENVELOPE_VIOLATION` before writing `data.ctrl`. `ticks` is bounded by the bridge (1 to `max_ticks`, 10000
by default). The device is simulated (R0), so no limit is `operator_required` and no `site-limits.example.json` is
needed.

## Contract

`MujocoDriver` serves `cap.world.step.v1` and `cap.world.reset.v1` on the `world` resource. A step writes the control
vector and integrates `ticks` times; the state is `{time_ms, qpos, qvel, ctrl, tick, timestep_ms, seed}`, with 19 qpos
values (a free base of 7 plus 12 hinges) and 18 qvel values (a free base of 6 plus 12 hinges). A reset calls
`mj_resetData` and `mj_forward`, restoring the model defaults; a seed is accepted for the class contract but MuJoCo
does not use it. The model file is read from the read-only clone; it is never copied into this package or imported.

## What this package does not serve

The card's concrete entry is `AnymalB`, a Gymnasium environment. Its `step` takes a twelve-element joint-position
offset action, scales it, converts it to torques with the Rudin2022 PD controller and integrates the same MJCF. This
package serves the model's own torque control through the card's `MujocoDriver` helper. It does not run `create_env`,
`AnymalB`, RL-X or the observation, reward, termination, command-sampling, domain-randomization and vectorization
pipeline. A reset restores the compiled model defaults (base at the origin, joints at zero), not the environment's
initial drop pose. The MJCF states no timestep, so the served step is MuJoCo's 0.002 s default, not the 0.005 s
configuration value of `AnymalB`. The fidelity `gaps` in `driver.py` state all of these differences.

## Fidelity contract

The real-engine contract is engine `mujoco:anymal_b`, level F1. The served fake overrides it with engine
`analytic:stand-in mujoco module (no physics)`, level F0. Both declare determinism kind `none` with `seed_control`
`none`, timestep 2 ms, `realtime_factor` 0, clock `lockstep`, reset `full`, snapshot and restore available. The fake is a stand-in
`mujoco` module that parses the MJCF for the free base, the hinges and the motors; its integration is a placeholder,
with no mesh, contact, inertia, gravity, constraint, damping or actuator dynamics. No trajectory was compared with the
real engine and no hardware was attached.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch; there is no native stop and no physical e-stop claim.
After an e-stop no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.
The last controls are retained; a later explicit step without `action` reuses them.

Tags: anymal, quadruped, legged, locomotion, mujoco, simulation, robot.
