# Facts and tags for gh.lhy6900/mujoco-viewer-plus

Every fact cites its source at commit `3d2555369ab990cef6f29d8e65f099468c151fe8`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The table repeats the
`facts = [Fact(text, source=..., ref=...)]` list in `driver.py`; the reference file is generated from the driver, not
from this page.

| fact | source | ref |
|---|---|---|
| The README starts model simulation with scripts/run_robot_sim.py | vendor_doc | README.md:25-27 |
| The project requires Python 3.8 or newer and is installed with pip install -e . | vendor_doc | README.md:11-17 |
| MujocoSimulator is the MuJoCo environment class that is independent from ROS | upstream_code | deploy_robot/sim/mujoco_simulator.py:59-60 |
| The simulator loads its scene with mujoco.MjModel.from_xml_path on the configured xml_path and creates mujoco.MjData from that model | upstream_code | deploy_robot/sim/mujoco_simulator.py:81-83 |
| The simulator overwrites the model's integration step with cfg.dt | upstream_code | deploy_robot/sim/mujoco_simulator.py:82 |
| MujocoSimulator.step runs cfg.decimation physics iterations; each iteration computes a torque, writes it to data.ctrl and calls mujoco.mj_step | upstream_code | deploy_robot/sim/mujoco_simulator.py:275-283 |
| The simulator computes its joint torque as target_trq + kp * (q_target - q) + kd * (dq_target - dq) | upstream_code | deploy_robot/sim/mujoco_simulator.py:321-322 |
| set_joint_commands converts q, dq, trq, kp and kd to flattened float32 arrays | upstream_code | deploy_robot/sim/mujoco_simulator.py:339-346 |
| The simulator reset zeroes qvel, optionally writes the base pose and joint positions, and calls mujoco.mj_forward | upstream_code | deploy_robot/sim/mujoco_simulator.py:392-428 |
| MujocoEnv wraps MujocoSimulator with a fixed-Hz stepping thread and DDS publishing to mimic hardware | upstream_code | deploy_robot/sim/mujoco_env.py:15-24 |
| When step_hz is omitted, MujocoEnv sets its period to max(1e-6, dt * max(1, decimation)); otherwise it uses the supplied step_hz | upstream_code | deploy_robot/sim/mujoco_env.py:36-43 |
| G1MujocoConfig selects deploy_robot/assets/mjcf/g1.xml as the scene and the pelvis as its root body | upstream_code | deploy_robot/sim/config/g1.py:4-11 |
| G1MujocoConfig uses decimation 10 and dt 0.002 s | upstream_code | deploy_robot/sim/config/g1.py:8-10 |
| G1_NUM_MOTOR is defined as 29 | upstream_code | deploy_robot/g1/constants.py:3 |
| G1JointNames lists the 29 joint names in controller order from left_hip_pitch_joint to right_wrist_yaw_joint | upstream_code | deploy_robot/g1/constants.py:42-72 |
| The shipped simulation script builds MujocoEnv(G1MujocoConfig) | upstream_code | scripts/run_robot_sim.py:68 |
| The model root element is '<mujoco model="g1">' and its compiler element declares angle radian and meshdir ../meshes/g1 | upstream_code | deploy_robot/assets/mjcf/g1.xml:1-2 |
| The robot body is pelvis at 0 0 0.793 with a free joint named floating_base_joint | upstream_code | deploy_robot/assets/mjcf/g1.xml:133-136 |
| The actuator block declares one motor per actuated joint, named after the joint, and no motor element declares a ctrlrange | upstream_code | deploy_robot/assets/mjcf/g1.xml:386-416 |
| G1.__init__ calls ChannelFactoryInitialize in the real branch, but its function-local import and self.factory assignment occur in the sim branch | upstream_code | deploy_robot/g1/g1.py:58-69 |

Tags (short lowercase keywords): `g1`, `humanoid`, `mujoco`, `simulation`, `unitree`, `viewer`.

## The served model

The card's `models[0]` is `deploy_robot/assets/mjcf/g1.xml`, the scene `G1MujocoConfig` selects
(`deploy_robot/sim/config/g1.py:4-5`). The MuJoCo bridge loads that file directly; it never imports the clone and
never applies `G1MujocoConfig`. The model has one free joint on the pelvis (`g1.xml:136`) and one hinge joint per
actuated limb joint, and 29 `<motor>` actuators named after those joints (`g1.xml:386-416`). No motor declares a
`ctrlrange`, so the bridge derives `action.ctrl` as `operator_required`; the deployment's `site-limits.json` must
bound it before a step can set it, and `site-limits.example.json` is an example overlay (source `operator`), not a
model fact. The model declares no `<option timestep>`, so the bridge uses the MuJoCo library default; the upstream
simulator sets its own 0.002 s step (`mujoco_simulator.py:82`, `config/g1.py:10`) and the stand-in uses 0.002 s as
the same placeholder.

## What the fake is

`fake.py` is a stand-in for the `mujoco` library, not the upstream simulator and not a recording. It parses the
same MJCF file for the joint dimensions, the actuator count and targets, the absent control ranges and the option
time step, and integrates a placeholder velocity proportional to each control value. It loads no mesh, texture,
sensor or camera and resolves no contact, friction, gravity, equality, tendon or actuator constraint; the driver's
fidelity `gaps` list every difference. MuJoCo itself was not importable where the gate ran, so no trajectory was
compared with the engine, the upstream simulator or a physical G1.

The fake publishes engine `analytic:g1`, level F0 and `snapshot_restore: false`. Its checkpoint profile is
`mujoco_basic_v1`; it omits the full integration-state API. Construction and reset use the MJCF pelvis pose
`[0, 0, 0.793]` with a valid identity quaternion. They do not apply the upstream wrapper's configured joint pose.
The e-stop halts bridge-owned lockstep integration while retaining velocities and controls; releasing the latch
advances no ticks, and a new step without an action reuses the retained controls.

The excluded `G1` real-robot constructor calls a function that is imported locally only in its other branch,
and assigns `self.factory` only in simulation (`deploy_robot/g1/g1.py:58-69`). It cannot be treated as a working
hardware route at this pin. This package opens neither that class nor the DDS controller.

The card declares licence `NOASSERTION` and `publish_review: required`. Publication requires an owner decision;
fake contract validation does not resolve that licence requirement.
