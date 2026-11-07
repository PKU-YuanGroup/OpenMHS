# Facts and tags for gh.hrjp/easys_sim

Every fact cites the read-only clone at `65f5daeb8fb82970ea03b5a0cc7a24509ea8c5c5`.
`upstream_code` is a code, launch, SDF or YAML line of the clone; `vendor_doc` is text of the clone.

The chosen device is the shipped camera pipeline: the Gazebo camera feed bridged as a ROS 2
`sensor_msgs/msg/Image` on `/camera`, and the `balloon_detect` node's annotated
`sensor_msgs/Image` output on `image_processed`. The package captures complete pixels as
bounded local PNG artifacts. It does not run or claim the OpenCV detector.

| fact | source | ref |
|---|---|---|
| The README states Ubuntu 22.04, ROS 2 Humble and Gazebo Garden. | vendor_doc | README.md:4-7 |
| The simulation launch includes the ros_gz_sim Gazebo launch and starts the ros_gz_bridge parameter_bridge node with bridge_topic.yaml. | upstream_code | Easys_description/launch/sim.launch.xml:7-15 |
| bridge_topic.yaml maps ROS `/camera` to Gazebo `/camera` with ROS type `sensor_msgs/msg/Image` and Gazebo type `gz.msgs.Image`. | upstream_code | Easys_description/config/ros_gz_bridge/bridge_topic.yaml:38-42 |
| The Easys camera sensor is named `camera`, type `camera`, with width 320, height 240, horizontal FOV 1.047, update rate 30 Hz and Gazebo topic `camera`. | upstream_code | Easys_description/model/easys_a1.sdf:268-283 |
| `balloon_detect` imports `Image` from `sensor_msgs.msg`, subscribes to the absolute `/camera` topic with queue size 10 and creates an Image publisher on the relative `image_processed` topic with queue size 10. | upstream_code | balloon_detect/balloon_detect/balloon_detect.py:3-17 |
| `image_callback` converts the received frame from RGB to HSV, builds a red mask from two hue bands and blue and yellow masks, and passes each mask with the label Red, Blue or Yellow to `mask2boudingbox`. | upstream_code | balloon_detect/balloon_detect/balloon_detect.py:20-55 |
| `mask2boudingbox` finds the external contours of the mask it is given and, for each contour whose area exceeds 50, draws a green rectangle and the color label on the current frame. | upstream_code | balloon_detect/balloon_detect/balloon_detect.py:91-108 |
| `image_callback` converts the annotated frame back to an Image with `cv2_to_imgmsg` and encoding `rgb8`, passing no header, and publishes it with `self.publisher`. | upstream_code | balloon_detect/balloon_detect/balloon_detect.py:85-89 |
| The Under Water Robocon launch includes the simulation launch and starts the `balloon_detect` node. | upstream_code | uw_robocon_sim/launch/joy_sim.launch.xml:5-10 |
| bridge_topic.yaml maps four thruster command topics from `std_msgs/msg/Float64` to `gz.msgs.Double`. | upstream_code | Easys_description/config/ros_gz_bridge/bridge_topic.yaml:2-24 |
| bridge_topic.yaml also maps `/tf` as `tf2_msgs/msg/TFMessage` (Gazebo `gz.msgs.Pose_V`) and `/imu` as `sensor_msgs/msg/Imu` (Gazebo `gz.msgs.IMU`). | upstream_code | Easys_description/config/ros_gz_bridge/bridge_topic.yaml:26-36 |
| The simulation launch also starts `robot_state_publisher`, `joy_node`, the Easys_ros nodes `joy2cmd`, `Easys_controller` and `thruster_output_converter`, and `rviz2`. | upstream_code | Easys_description/launch/sim.launch.xml:17-41 |
| The README's manual setup clones the separate Easys_ros repository next to Easys_sim. | vendor_doc | README.md:11-19 |
| The `easys` model declares a camera sensor named `camera` with width 320, height 240, update rate 30 Hz and Gazebo topic `camera`, like `easys_a1`. | upstream_code | Easys_description/model/easys.sdf:268-283 |
| The `balloon_detect` package manifest leaves its licence as `TODO: License declaration`. | upstream_code | balloon_detect/package.xml:8 |

## Tags

`ros`, `ros2`, `gazebo`, `simulation`, `camera`, `image`, `balloon`, `underwater`

## Scope and limits

The camera is passive: it commands no motion, exposure, focus or gain, and the pinned clone
declares no acknowledged ROS stop, pause, reset or world-step service. The four thruster
command publications, `/imu`, `/tf`, Gazebo physics and world control are NOT COVERED. The
driver declares no numeric input bound, so `site-limits.example.json` is not needed.

The fake returns a 2x2 placeholder frame, not the sensor's 320x240 image. All fake numbers,
pixels, frame ids and stamps are test data, not facts. The detector assigns no header to its
output, so the fake answers `/image_processed` with a zero stamp and an empty frame id; only the
Under Water Robocon launch starts the detector. No live ROS graph, Gazebo render, OpenCV
detector or hardware run is claimed.

Model review (2026-11-05): four detector facts were narrowed to their lines, the `/tf` and
`/imu` fact no longer says "from Gazebo", and four facts were added (the other nodes of the
simulation launch, the separate Easys_ros repository, the `easys` model's camera and the
`balloon_detect` manifest's TODO licence).
