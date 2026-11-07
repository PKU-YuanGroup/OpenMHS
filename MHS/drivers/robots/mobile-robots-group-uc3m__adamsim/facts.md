# Facts and tags for gh.mobile-robots-group-uc3m/adamsim

Every fact cites the pinned clone at commit `85a9b1fce83a36c45bb29412546f67bc8a03c29b`:
`vendor_doc` is text documentation in the clone, and `upstream_code` is a file and line of the clone.
The same facts are written into `driver.py`; the reference file is generated from the driver, not from
this page.

## Facts

| fact | source | ref |
|---|---|---|
| ADAM is the ADAMSim robot class; its constructor connects a PyBullet GUI client and loads the robot URDF with the requested fixed-base flag. | upstream_code | scripts/adam.py:20-70 |
| The ADAM constructor defaults use_realtime, use_fixed_base and use_ros to True. | upstream_code | scripts/adam.py:21-31 |
| The ADAM constructor sets the control period self.t to 0.01. | upstream_code | scripts/adam.py:77 |
| The ADAM constructor creates the Sensors and ArmsKinematics modules and creates Navigation only when use_fixed_base is false. | upstream_code | scripts/adam.py:88-98 |
| The ADAM constructor imports and constructs ROSConnection only when use_ros is true. | upstream_code | scripts/adam.py:107-109 |
| ADAM.step calls p.stepSimulation() only when use_realtime is false, measures the execution speed, and then sleeps for self.t or delegates to the ROS rate. | upstream_code | scripts/adam.py:173-193 |
| Navigation.send_velocity clamps the linear and angular velocity to self.linear_speed and self.angular_speed, converts them to left/right wheel velocities with the wheel radius and wheel distance, and applies PyBullet VELOCITY_CONTROL to both wheel joints. | upstream_code | scripts/navigation.py:200-217 |
| Navigation.move_wheels applies PyBullet VELOCITY_CONTROL to both wheel joints with the given left and right wheel speeds and force. | upstream_code | scripts/navigation.py:23-34 |
| Navigation.move_base_continuous commands both wheel targets to zero with force 10 when its target is reached. | upstream_code | scripts/navigation.py:160-169 |
| The Navigation constructor sets wheel_radius 0.0762, wheel_distance 0.436, linear_speed 6.55 and angular_speed 1.0. | upstream_code | scripts/navigation.py:7-18 |
| Sensors.get_camera_angle returns the camera joint position converted to degrees minus 45. | upstream_code | scripts/sensors.py:117-124 |
| ArmsKinematics.get_arm_joint_angles reads the arm joint angles in radians from PyBullet. | upstream_code | scripts/arms_kinematics.py:365-380 |
| semantic_groups_inspire_hands.json lists six joints for the right arm and six for the left arm. | upstream_code | models/robot/rb1_base_description/config/semantic_groups_inspire_hands.json:2-19 |
| The README describes ADAMSim as a PyBullet-based simulation environment for the ADAM domestic mobile manipulator, with navigation, arm and hand kinematics, perception and ROS communication. | vendor_doc | Readme.md:4-12 |
| The README requires ROS 1 Noetic and Python 3.8 and says ADAMSim is developed for Ubuntu/Linux. | vendor_doc | Readme.md:39-42 |
| The navigation example constructs ADAM with use_fixed_base=False and use_ros=False. | upstream_code | examples/example_navigation.py:9 |
| The navigation loop calls move_base_continuous and then advances the simulation with adam.step() in the same iteration. | upstream_code | examples/example_navigation.py:48-71 |
| The ADAM constructor calls p.setRealTimeSimulation(1) when use_realtime is true and p.setRealTimeSimulation(0) otherwise. | upstream_code | scripts/adam.py:54-55 |
| The ADAM constructor stores the real-time flag as self.use_realtime and the ROS flag as self.use_ros. | upstream_code | scripts/adam.py:74-75 |
| When the robot_info JSON file is missing, the ADAM constructor generates it with print_robot_info(save=True). | upstream_code | scripts/adam.py:81-83 |
| ROSConnection.sleep reads self.adam.useRealTimeSimulation to choose between rospy.sleep(self.adam.t) and self.rate.sleep(). | upstream_code | scripts/ros_connection.py:59-65 |
| The ROSConnection constructor initialises the ROS node adam_ros_node, subscribes /robot/left_arm/joint_states and /robot/right_arm/joint_states, creates JointTrajectory publishers on /robot/left_arm/scaled_pos_traj_controller/command and /robot/right_arm/scaled_pos_traj_controller/command and a Twist publisher on /robot/move_base/cmd_vel, and starts a 0.02 s hand-service timer and a 1/120 s real_to_sim timer. | upstream_code | scripts/ros_connection.py:12-37 |
| ROSConnection.real_to_sim moves the simulated arms and hands to the latest arm joint states and hand states received from the robot. | upstream_code | scripts/ros_connection.py:159-180 |
| ROSConnection.call_get_angle_act calls rospy.wait_for_service on /robot/<arm>/inspire_hand/get_angle_act with no timeout before calling the service. | upstream_code | scripts/ros_connection.py:183-196 |
| The README says the architecture allows synchronized operation between the real robot and its digital twin, including experiments running both simulated and real robots simultaneously. | vendor_doc | Readme.md:12 |

## Scope

The package exposes the differential-drive base of the ADAMSim PyBullet simulation. The card names a
`RosDriver`, but the pinned control surface is the Python `scripts.adam:ADAM` object: `Navigation.send_velocity`
sets the two wheel targets (`scripts/navigation.py:200-217`) and `ADAM.step` advances the simulation
(`scripts/adam.py:173-193`). The ROS layer is the simulator's bridge to a real ADAM robot, not a ROS
control node for the simulator: `ROSConnection.__init__` creates a node, subscribes to the two
`/robot/<arm>/joint_states` topics, publishes the two `/robot/<arm>/scaled_pos_traj_controller/command`
JointTrajectory topics and `/robot/move_base/cmd_vel` (`scripts/ros_connection.py:14-25`), and offers no
pause, stop or reset service. A configuration-only `RosDriver` cannot start a PyBullet process, and
declaring those real-robot publications as the control path would misdescribe the simulator. The package
therefore uses a direct `Driver`; this is recorded as DEVIATION FROM THE CARD in RESULT.json.

The base action applies the control pattern of the navigation example: call the upstream velocity
controller and then `adam.step()` (`examples/example_navigation.py:48-71`).
The package does not command the arms. `ArmsKinematics` exposes no stop, hold, quiescence readback or
cancellation hook, and a safe-state action that only wrote cached joint positions would not be fresh
stopped-state evidence. The arm joint angles and the camera angle are therefore read-only state, not a
motion interface.

## Safety

The device is simulated at R2 because the upstream is a mobile base (`MHS/spec/04-safety.md`). The card
floor is R0. The input velocities and the command duration have no sourced bound: the only upstream
velocity clamp uses `Navigation.linear_speed` and `Navigation.angular_speed`, configurable constructor
defaults (`scripts/navigation.py:14-15`, applied at `:208-209`), and `ADAM.step` is a caller-driven
loop with no maximum period (`scripts/adam.py:173-193`). Each of those inputs is therefore
`Limit.operator_required`, and the runtime refuses the action with `MHS.SAFETY.LIMITS_UNSET` until the
operator supplies a site overlay. `site-limits.example.json` is an example overlay, not a device limit.

The stop path is `Navigation.move_wheels(0.0, 0.0)`, the same PyBullet velocity-target call that the
upstream's own `move_base_continuous` uses to stop the wheels at the target
(`scripts/navigation.py:160-169` and `:23-34`). The @estop method and the input-free
`x-cap.mobile-robots-group-uc3m.zero_wheels.v1` safe-state action both use it. The driver stops calling `ADAM.step` when the run is
cancelled. Reviewer correction: that does not stop the simulation in PyBullet real-time mode
(`use_realtime`, the ADAM default; `scripts/adam.py:54`), where the world advances by itself and the wheel
motors brake toward the zero target; only in stepped mode does the world stay frozen until the next
`ADAM.step`. The drive action now zeroes the wheel targets on every exit, including a failing `ADAM.step`
(reviewer change; before, only a cancellation zeroed them). The upstream exposes no wheel-velocity or
base-odometry getter, so the native backend cannot prove that the simulated wheels reached zero speed:
`stopped` is the applied-command result, not measured quiescence. The runtime's latch and the zero wheel
targets are the local safety barrier; no physical e-stop is claimed and none is cited.

Reviewer note on a live backend: the ADAM defaults `use_fixed_base=True` and `use_ros=True`
(`scripts/adam.py:21-31`) do not fit this driver. With a fixed base the constructor creates no `Navigation`
(`:97-98`); with `use_ros`, `ADAM.step` calls `ROSConnection.sleep`, which reads
`self.adam.useRealTimeSimulation` (`scripts/ros_connection.py:64`), an attribute ADAM never assigns (it
stores `use_realtime`, `scripts/adam.py:74`), so every step fails at the pin. `ROSConnection` is also the
bridge to the real ADAM robot: it mirrors the real arms into the simulation at 120 Hz, waits without a
timeout for the real hands' services, and holds publishers to the real arm controllers and base
(`scripts/ros_connection.py:12-37`, `:159-196`). No method of this driver calls it.

## Fidelity

The deployed fake is an analytic kinematic stand-in, level F0, with no PyBullet, physics, contacts,
wheel friction, sensors, GUI or wall-clock pacing. One fake tick is the 10 ms ADAM control period
(`scripts/adam.py:77`), not a PyBullet physics timestep; ADAM never calls `setTimeStep`, so the physics
timestep is outside the clone and is not claimed. The fake's wheel radius, wheel distance and velocity
clamps are the upstream constructor values copied to mirror the pinned conversion, not device limits.
All start positions, camera angles and arm angles in the fake are placeholders.

A native/sim backend is intentionally not declared. The real simulator needs PyBullet and a GUI client
(`scripts/adam.py:51`), ROS 1 Noetic and Python 3.8 (`Readme.md:39`); it was neither installed nor run,
and a separate reviewed backend would be required before a deployment could rely on it.

## Tags

`pybullet`, `simulation`, `mobile-base`, `differential-drive`, `adamsim`
