# Facts and tags for gh.buenos-dan/cheetah_sim

Every fact cites its source at commit `8c8948fbf041e2f5bc8e0225de0a665a262572ab`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or
`upstream_code` (`path/in/clone.py:LINE`). Copy each fact
into `facts = [Fact(text, source=..., ref=...)]` in `driver.py`; the reference
file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is a quadrupedal robot simulation by ROS and Gazebo. | vendor_doc | README.md:7 |
| The quick start launches cheetah_gazebo, cheetah_control and the cheetah_core stand_demo script. | vendor_doc | README.md:23-28 |
| LegController stores the leg name, the joint_name list, the leg's JOINT_OFFSET and three publisher objects. | upstream_code | ros_package/cheetah_core/src/leg_control/legController.py:14-25 |
| LegController assembles the command topic from /cheetah/, the leg name, _joint, the 1-based index and _position_controller/command, and creates a rospy Publisher of Float64 with queue_size 5 on it. | upstream_code | ros_package/cheetah_core/src/leg_control/legController.py:22-25 |
| _writeJointPosInRad adds the fixed offset and publishes the sum as a Float64 message. | upstream_code | ros_package/cheetah_core/src/leg_control/legController.py:32-35 |
| writeEndPos runs inverseKinematics and writes the three resulting joint angles. | upstream_code | ros_package/cheetah_core/src/leg_control/legController.py:37-40 |
| The __main__ block of legController.py ends with the Python 2 print statement print "hello world". | upstream_code | ros_package/cheetah_core/src/leg_control/legController.py:43-48 |
| Cheetah.__init__ stores the leg_names list and a controllers dict that maps each leg name to a LegController. | upstream_code | ros_package/cheetah_core/src/stand_demo.py:15-18 |
| Cheetah.stand commands the four legs to a fixed end-effector pose through writeEndPos. | upstream_code | ros_package/cheetah_core/src/stand_demo.py:20-26 |
| Cheetah.run calls stand every 0.1 s until rospy shuts down; the script's main initialises the anonymous node control_node and runs it. | upstream_code | ros_package/cheetah_core/src/stand_demo.py:28-37 |
| trot_demo.py's trot writes each leg's end position through self.controllers[leg].writeEndPos, and its run calls trot every 0.01 s until rospy shuts down. | upstream_code | ros_package/cheetah_core/src/trot_demo.py:82-97 |
| The control launch spawns twelve position controllers and the joint_state_controller under /cheetah. | upstream_code | ros_package/cheetah_control/launch/cheetah_control.launch:7-20 |
| The controller configuration loads joint_state_controller at 50 Hz and twelve effort_controllers/JointPositionController entries. | upstream_code | ros_package/cheetah_control/config/cheetah_control.yaml:3-56 |
| The URDF's gazebo_ros_control plugin declares robotNamespace /cheetah and robotSimType gazebo_ros_control/DefaultRobotHWSim. | upstream_code | ros_package/cheetah_description/urdf/cheetah.urdf:3-6 |
| The URDF declares the leg joint LF_JOINT1 as a continuous joint without a limit element. | upstream_code | ros_package/cheetah_description/urdf/cheetah.urdf:311-325 |
| settings.py defines BODY_LENGTH, BODY_WIDTH, the hip, thigh and calf lengths in LEG_LENGTH, LEG_NAME and the per-leg JOINT_OFFSET values. | upstream_code | ros_package/cheetah_core/src/lib/settings.py:7-19 |
| The Gazebo launch includes empty_world.launch with paused=true and spawns the cheetah model. | upstream_code | ros_package/cheetah_gazebo/launch/cheetah.launch:2-16 |

Tags: `ros`, `ros1`, `gazebo`, `simulation`, `quadruped`, `joint-position`.

## Scope

This package serves the pinned Python control classes, not a ROS node wrapper. `LegController._writeJointPosInRad`
publishes one `std_msgs/Float64` per joint; `Cheetah.stand` commands the fixed stand pose; `Cheetah.controllers` is a
dict keyed by leg name. The twelve command topics are assembled at runtime, and the clone contains no stop, pause,
reset or e-stop service/action. The e-stop path sends `Cheetah.stand`, an active posture command of twelve
unacknowledged publications, and then reports `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held (model review,
2026-11-05): it is not a measured stop, no joint-state or quiescence feedback is exposed, and the README's
`stand_demo` node (stand every 0.1 s) or `trot_demo` (gait every 0.01 s) overrides it while running. The pinned modules
are Python 2 code, so no live backend can import the native class. The fake is an analytic Python stand-in, not the
Gazebo simulator; it is not a recording of captured ROS traffic. The package is blocked (HELPER_MISSING).
