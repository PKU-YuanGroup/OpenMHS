# Facts and tags for gh.electronicelephant/pybullet_ur5_robotiq

Every fact cites its source at commit `37f7d66d3196490618bf89ffe2b49dcb7e07aec3`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| ClutteredPushGrasp is the user-facing environment class | upstream_code | env.py:19 |
| The constructor opens an in-process PyBullet connection, GUI or DIRECT, and loads the plane, the robot and a fixed box; it opens no serial, VISA, USB or network transport | upstream_code | env.py:23-58 |
| SIMULATION_STEP_DELAY is 1/240 s | upstream_code | env.py:21 |
| step_simulation calls p.stepSimulation and sleeps the delay only when the GUI is shown | upstream_code | env.py:60-67 |
| step accepts a seven-element action, asserts control_method is joint or end, calls move_ee(action[:-1], control_method) and move_gripper(action[-1]), and runs 120 simulation steps | upstream_code | env.py:81-92 |
| The end-effector action is (x, y, z, roll, pitch, yaw, gripper_opening_length) | upstream_code | env.py:83 |
| The interactive sliders bound x and y to -0.224..0.224, z to 0..1.0, roll and pitch to -3.14..3.14, yaw to -pi/2..pi/2 and the gripper opening to 0..0.085 | upstream_code | env.py:40-46 |
| read_debug_parameter returns the seven slider values in the action order | upstream_code | env.py:69-79 |
| The documented user-control demo passes read_debug_parameter() and 'end' to step | upstream_code | main.py:30 |
| step returns (observation, reward, done, info), with done true only when reward == 1 | upstream_code | env.py:94-97 |
| The reward becomes 1 when the box has been opened and the button pressed and the box is then closed; the joint thresholds are 1.9, -0.02 and 0.1 | upstream_code | env.py:99-114 |
| The observation is the camera's rgb, depth and seg arrays when a Camera is configured, plus the robot's joint observation | upstream_code | env.py:116-125 |
| get_joint_obs returns the controllable joints' positions and velocities and the end-effector position | upstream_code | robot.py:130-138 |
| reset resets the robot and the box and returns the observation | upstream_code | env.py:127-134 |
| RobotBase.reset resets the arm to the rest poses and opens the gripper; it takes no seed | upstream_code | robot.py:86-108 |
| close disconnects the PyBullet client | upstream_code | env.py:136-137 |
| UR5Robotiq85 loads ur5_robotiq_85.urdf with fixed base, eef 7, six arm dofs and gripper range 0..0.085 | upstream_code | robot.py:168-176 |
| UR5Robotiq140 loads ur5_robotiq_140.urdf with the same eef, six arm dofs and 0..0.085 gripper range | upstream_code | robot.py:209-218 |
| The README lists a Gym-styled API for reinforcement learning in push-and-grasp, 6D end-effector IK with Position XYZ and Orientation RPY, and PyBullet as the only prerequisite | vendor_doc | README.md:11-20 |

Limits: the driver binds the action envelope of the clone's own interactive sliders (`env.py:40-46`): x and y are
-0.224 to 0.224 m, z is 0 to 1.0 m, roll and pitch are -3.14 to 3.14 rad, yaw is -pi/2 to pi/2 rad and the gripper
opening is 0 to 0.085 m. `step` itself does not assert these values; the cited sliders are the bounds the documented
demo passes to `step` (`main.py:30`). The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `pybullet:ClutteredPushGrasp`, level F1 (rigid-body
PyBullet scene with contacts and inverse kinematics), determinism `exact` with seed control `none` (the scene and
reset are fixed and the clone seeds no random generator), `timestep_ms` 0 because the clone states no PyBullet
physics time step (`SIMULATION_STEP_DELAY = 1/240` at `env.py:21` only paces the GUI), realtime factor 0, clock
`lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled, that one tick is one
`ClutteredPushGrasp.step` call of 120 physics iterations (`env.py:91`), and that the fake was not compared with the
upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the last observation and tick stay readable.

`cap.world.seed.v1` is not bound: `ClutteredPushGrasp` has no seed method and reset restores fixed rest poses and a
fixed box (`robot.py:86-108`, `env.py:127-134`). A `seed` supplied to `cap.world.reset.v1` is recorded only, and the
required `seed` output defaults to 0, because there is no random generator to seed.

Tags: ur5, robotiq, gripper, pybullet, simulation, reinforcement-learning
