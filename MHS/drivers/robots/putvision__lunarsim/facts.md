# Facts and tags for gh.putvision/lunarsim

Every fact cites the pinned clone at commit `0f3b202624d398ecacbb1e4bab9aec02e394a2d2`.
`vendor_doc` refs name text of the clone (`README.md:LINE`); `upstream_code` refs name
the container recipe that installs ROS 2 and extracts the simulator binary. The same
facts are written into `driver.py` (`facts = [...]`); the reference file is generated
from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The container installs ROS 2 Humble with ros-humble-desktop. | upstream_code | Dockerfile:41-45 |
| The image downloads LunarSim.tar.xz from the project's releases/latest URL and extracts LunarSim.x86_64. | upstream_code | Dockerfile:55-59 |
| The README runs the extracted simulator binary with ./LunarSim.x86_64. | vendor_doc | README.md:27-28 |
| The README warns not to source ROS in the terminal where LunarSim runs. | vendor_doc | README.md:31 |
| The README's ROS 2 Topics section lists /cmd_vel as the subscribed topic and five published topics: /lunarsim/gt/pose, /lunarsim/imu, the left and right camera images and the depth image; it documents no service, action, pause, reset or stop endpoint. | vendor_doc | README.md:53-93 |
| The README documents /cmd_vel as a geometry_msgs/Twist velocity command for the robot. | vendor_doc | README.md:59-61 |
| The README example publishes one geometry_msgs/msg/Twist on /cmd_vel with linear.x 1.0 and angular.z 0.0. | vendor_doc | README.md:69 |
| The README documents /lunarsim/gt/pose as a geometry_msgs/PoseStamped ground-truth robot pose. | vendor_doc | README.md:65-67 |
| The README documents /lunarsim/imu as sensor_msgs/Imu data. | vendor_doc | README.md:71-73 |
| The README documents /lunarsim/camera_left/raw as a sensor_msgs/Image left camera image. | vendor_doc | README.md:75-81 |
| The README documents /lunarsim/camera_right/raw as a sensor_msgs/Image right camera image. | vendor_doc | README.md:83-89 |
| The README documents /lunarsim/camera_depth/depth as a sensor_msgs/Image depth image. | vendor_doc | README.md:91-93 |

## Scope and deployment

The primary control is the documented `/cmd_vel` publication. The observations are one fresh sample from
`/lunarsim/gt/pose`, `/lunarsim/imu` and the three raw camera streams. The single catalogue binding is
`cap.sensing.image.v1` for the three camera streams; because one `Driver` has one catalogue kind, the
package uses `device_kind = "sensor.camera"` and exposes the drive, pose and IMU as extension capabilities.
The README also documents `/lunarsim/camera_left/compressed` and `/lunarsim/camera_right/compressed`; those
compressed streams are NOT COVERED because the driver selects the raw `sensor_msgs/Image` streams.

The simulator is a closed-source binary downloaded from a release archive (`Dockerfile:55-59`), so its
internal timing, physics, camera encodings and image dimensions are not in the pinned source. The
`/cmd_vel` linear and angular bounds are `operator_required`: the clone states no maximum, and the values
in `site-limits.example.json` are example operator input, not device facts.

The README says not to source ROS in the terminal where LunarSim runs (`README.md:31`); the operator runs
the simulator and rosbridge separately and exposes the resolved endpoints. No ROS graph, simulator process
or hardware is started or validated by this package.

## Safety

The device is simulated but controls a rover through `/cmd_vel`; the driver therefore declares the drive
capability at R2, the catalogue class level for a mobile base. The pinned README documents no service,
action, pause, reset or stop endpoint. A zero-velocity Twist is a publication, not an acknowledged stop,
and the SDK rejects it as a safe-state binding. The driver consequently declares no fabricated
`safety_bindings`; the stock e-stop latches in software and reports `MHS.SAFETY.SAFE_STATE_UNREACHED`.
`RESULT.json` records this as the concrete blocker instead of claiming that the rover stopped.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS-free contract fake with canned placeholder
replies (no physics)`, level F0, determinism `none`, `timestep_ms: 0` (event-driven canned replies with no
physics step), `realtime_factor: 0` (not paced), reset `none`, and no snapshot/restore. It is not a
recording of captured ROS traffic. All pose, IMU and image values are placeholders. The fake returns a
4x2 BGR8 left/right frame and a 4x2 16UC1 depth frame; the real sizes and encodings are not stated in the
clone.

## Tags

`ros`, `ros2`, `simulation`, `lunarsim`, `lunar-rover`, `mobile-base`, `cmd-vel`, `pose`, `imu`, `camera`
