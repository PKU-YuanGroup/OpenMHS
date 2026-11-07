# Facts and tags for gh.pocketxjl/humanoid-control

Every fact cites its source at commit `3b5ffec98d29827730194b0dbf2f119fb7b265ca`: `vendor_doc` (a text file of the
clone such as `README.md`) or `upstream_code` (`path/in/clone:LINE`). The same facts are declared in
`facts = [Fact(text, source=..., ref=...)]` in `driver.py`; the reference file is generated from the driver, not from
this page.

The card's static scan chose the ROS family and `RosDriver` because this repository contains a ROS 1 controller
stack. The selected model is the MuJoCo MJCF named by the card, the card's role is `sim-env`, and the candidate
classes are `cap.world.*`; the repository's own simulation loop steps that model with MuJoCo. This package therefore
serves the model as a MuJoCo world (`MujocoDriver`), not as a rosbridge transport. The ROS nodes, controller, state
estimator and viewer are separate upstream components and are not run by this package. The switch is recorded as a
DEVIATION FROM THE CARD in `RESULT.json`.

| fact | source | ref |
|---|---|---|
| The README installs MuJoCo with pip3 and starts the simulation with roslaunch humanoid_controllers load_cheat_controller.launch. | `vendor_doc` | `README.md:36-53` |
| The README says the OCS2 controller is a separate monorepo build and must be compiled with catkin before the simulation is started. | `vendor_doc` | `README.md:7-28` |
| The MJCF names the model humanoid_legged_description. | `upstream_code` | `humanoid-legged-description/mjcf/humanoid_legged.xml:1` |
| The model sets timestep 0.001 seconds, the PGS solver, gravity 0 0 -9.81 and twenty noslip iterations. | `upstream_code` | `humanoid-legged-description/mjcf/humanoid_legged.xml:4` |
| The base_link body carries a free joint, so the model has a floating base. | `upstream_code` | `humanoid-legged-description/mjcf/humanoid_legged.xml:57-58` |
| The leg hinge joints have limited ranges: leg_l1 -0.2 to 1.5708 and leg_r1 -1.5708 to 0.2; leg_l2, leg_l3, leg_r2 and leg_r3 -1.5708 to 1.5708; leg_l4 and leg_r4 0 to 2.356; leg_l5 and leg_r5 -0.8 to 0.8; and leg_l6 and leg_r6 -0.5236 to 0.5236. | `upstream_code` | `humanoid-legged-description/mjcf/humanoid_legged.xml:85-144` |
| The actuator block declares twelve motor actuators with gear 1 and explicit ctrlrange bounds: +/-150 for leg_l1, leg_l2, leg_r1 and leg_r2; +/-200 for leg_l3, leg_l4, leg_r3 and leg_r4; and +/-90 for leg_l5, leg_l6, leg_r5 and leg_r6. | `upstream_code` | `humanoid-legged-description/mjcf/humanoid_legged.xml:156-167` |
| The upstream MuJoCo loop computes data.ctrl from targetTorque, targetKp, targetPos, targetKd, targetVel and the last twelve qpos/qvel entries, then calls mj_step. | `upstream_code` | `mujoco_sim/script/humanoid_sim.py:110-112` |
| The upstream simulator sets sim_rate to 1000 and only steps when the wall-clock epoch has reached 1/sim_rate. | `upstream_code` | `mujoco_sim/script/humanoid_sim.py:23-113` |
| The upstream simulator publishes /jointsPosVel at 500 Hz from the last twelve qpos and qvel entries. | `upstream_code` | `mujoco_sim/script/humanoid_sim.py:116-124` |
| The upstream simulator initializes the base at [0, 0, 1.225] and the leg joints at the init_joint_pos values, then writes them into data.qpos. | `upstream_code` | `mujoco_sim/script/humanoid_sim.py:14-53` |
| The humanoid controller subscribes to /jointsPosVel and /imu and advertises /targetTorque, /targetPos, /targetVel, /targetKp and /targetKd. | `upstream_code` | `humanoid_controllers/src/humanoidController.cpp:63-69` |
| The cheat controller node subscribes to pauseFlag and calls controller.update at 500 Hz unless the flag is set. | `upstream_code` | `humanoid_controllers/src/CheatControllerNode.cpp:25-69` |
| MuJoCoBase publishes /pauseFlag, toggles pause_flag on SPACE and resets the data with mj_resetData on BACKSPACE. | `upstream_code` | `mujoco_sim/script/mujoco_base.py:15-51` |

## Limits

The package authors no `Limit`: none of the clone's text states a per-run safe torque envelope for this humanoid.
`cap.world.step.v1` takes `{ticks, action: {ctrl: [12]}}`, and the MuJoCo bridge derives the per-element bounds at run
time from the model's own `actuator_ctrlrange` values on
`humanoid-legged-description/mjcf/humanoid_legged.xml:156-167` (the twelve `motor` elements). The bridge refuses an
out-of-range element with `MHS.SAFETY.ENVELOPE_VIOLATION` before writing `data.ctrl`; nothing is clamped. The
`ticks` bound is the bridge's declared execution policy (`max_ticks`), not a device fact.

The joint position ranges on `humanoid-legged-description/mjcf/humanoid_legged.xml:85-144` are model joint limits used
by MuJoCo's own constraint solver; they are not copied into a package `Limit` and the fake does not enforce them.

## Stop path and reset

This is a simulated world at R0 with no hardware backend and no route to a physical humanoid. The runtime owns the
e-stop latch: after `mhs.safety.estop` no step or reset is accepted until `mhs.safety.reset` clears the latch, and the
world state remains readable. The `MujocoBridge` takes its world lock for every mutation and refuses a reset while
native work is unsettled. A normal safe-state invocation does not itself engage the latch.

`cap.world.reset.v1` calls `mj_resetData` and `mj_forward`; it restores the MJCF defaults and does not reproduce the
upstream simulator's manual initial base and joint pose. The model has no keyframe and no RNG, so the seed in the
bridge state is metadata only; `cap.world.seed.v1` is not served.

## Not covered

The OCS2 NMPC/WBC controller, the linear Kalman state estimator, the ROS 1 topics and services, the gait command
publisher, the MuJoCo viewer and camera/rendering, and the arm/head/waist meshes (they have no joints or actuators in
this MJCF) are outside this package. MuJoCo itself was not importable where the gate ran, so `backends["fake"]` is the
package's stand-in `mujoco` module: it reads the same MJCF for the actuator count, ctrlrange and joint dimensions, but
its step is a placeholder first-order motion, not the engine's torque dynamics. The fake backend's published fidelity
is F0 with engine `analytic:stand-in mujoco module (no physics)`; the F1 `mujoco:humanoid_legged_description` contract
applies only to the implicit live `sim` backend that imports the official module. No trajectory was compared with the
real engine or the upstream simulator, and no physical device was attached.

Tags: `ros`, `ros1`, `mujoco`, `simulation`, `humanoid`, `biped`, `world`, `simulated`.
