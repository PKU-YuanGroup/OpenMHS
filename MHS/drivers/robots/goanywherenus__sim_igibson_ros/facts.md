# Facts and tags for gh.goanywherenus/sim_igibson_ros

Every fact cites the read-only clone at `cf9a546437e00bce59237571e0a1b5b7e2ba3e05`.
`upstream_code` is a code, launch or YAML line of the clone; `vendor_doc` is text of the clone.

The chosen device is the simulated TurtleBot RGB camera stream published by `turtlebot_rgbd.py` as
`sensor_msgs/Image` on `/gibson_ros/camera/rgb/image`.  The package captures complete pixels as
bounded local PNG artifacts.  It does not run or claim iGibson, ROS or the upstream node.

| fact | source | ref |
|---|---|---|
| The node initializes as igibson_sim and loads the igibson-ros package configuration. | upstream_code | igibson-ros/turtlebot_rgbd.py:26-30 |
| The node constructs a headless iGibsonEnv with action_timestep 1/30 and calls reset. | upstream_code | igibson-ros/turtlebot_rgbd.py:49-52 |
| The node creates an Image publisher on the absolute topic /gibson_ros/camera/rgb/image with queue size 10. | upstream_code | igibson-ros/turtlebot_rgbd.py:35 |
| The run loop converts the iGibson rgb observation to uint8 and creates the ROS image with cv2_to_imgmsg using encoding rgb8. | upstream_code | igibson-ros/turtlebot_rgbd.py:85-90 |
| The image header stamp is rospy.Time.now and the image frame_id is camera_depth_optical_frame. | upstream_code | igibson-ros/turtlebot_rgbd.py:94-100 |
| turtlebot_rgbd.yaml sets image_width and image_height to 256 and vertical_fov to 90. | upstream_code | igibson-ros/turtlebot_rgbd.yaml:61-63 |
| The configured sensor output list includes rgb, depth and scan. | upstream_code | igibson-ros/turtlebot_rgbd.yaml:55 |
| The same configuration bounds depth with depth_low 0.8 and depth_high 3.5. | upstream_code | igibson-ros/turtlebot_rgbd.yaml:65-66 |
| The node publishes depth images on /gibson_ros/camera/depth/image and /gibson_ros/camera/depth/image_raw. | upstream_code | igibson-ros/turtlebot_rgbd.py:36-38 |
| The depth message is created from a float32 depth array with encoding passthrough. | upstream_code | igibson-ros/turtlebot_rgbd.py:86-92 |
| The node publishes a PointCloud2 lidar cloud on the absolute topic /gibson_ros/lidar/points. | upstream_code | igibson-ros/turtlebot_rgbd.py:37 |
| The node subscribes to the absolute topic /mobile_base/commands/velocity with a Twist callback and to /reset_pose with a PoseStamped callback. | upstream_code | igibson-ros/turtlebot_rgbd.py:43-44 |
| cmd_callback stores data.linear.x in cmdx and the negated data.angular.z in cmdy. | upstream_code | igibson-ros/turtlebot_rgbd.py:223-225 |
| tp_robot_callback calls reset_new_pose with the message position and orientation and records the teleport time. | upstream_code | igibson-ros/turtlebot_rgbd.py:227-237 |
| The main loop calls iGibsonEnv.step with [cmdx, cmdy] until ROS shuts down. | upstream_code | igibson-ros/turtlebot_rgbd.py:77-79 |
| The launch starts the igibson-ros turtlebot_rgbd.py node and remaps /mobile_base/commands/velocity to /cmd_vel. | upstream_code | igibson-ros/launch/turtlebot_rgbd.launch:13-14 |
| The README states that the repository provides instructions and code to set up an iGibson environment with a ROS interface and ROS navigation stack. | vendor_doc | README.md:3 |
| SimNode.__init__ of turtlebot_rgbd.py takes no argument besides self. | upstream_code | igibson-ros/turtlebot_rgbd.py:24-26 |
| The main block of turtlebot_rgbd.py parses --enable_left_right_cams with argparse and then calls SimNode(args) and node.run(args). | upstream_code | igibson-ros/turtlebot_rgbd.py:240-248 |
| The run loop has no rate limiter: each pass steps iGibsonEnv once and publishes one image. | upstream_code | igibson-ros/turtlebot_rgbd.py:77-221 |
| The README runs the simulation with roslaunch turtlebot_custom_nav.launch. | vendor_doc | README.md:13 |
| turtlebot_custom_nav.launch starts turtlebot_rgbd.py as the node turtlebot_gibson_sim. | upstream_code | igibson-ros/launch/turtlebot_custom_nav.launch:13-14 |
| turtlebot_env.py creates the same Image publisher on /gibson_ros/camera/rgb/image. | upstream_code | igibson-ros/turtlebot_env.py:33 |
| turtlebot_env.py converts the rgb observation with cv2_to_imgmsg using encoding rgb8. | upstream_code | igibson-ros/turtlebot_env.py:62 |
| The main block of turtlebot_env.py constructs SimNode() and calls node.run() without arguments. | upstream_code | igibson-ros/turtlebot_env.py:187-190 |

## Tags

`ros`, `ros1`, `igibson`, `turtlebot`, `simulation`, `camera`, `image`, `rgb`

## Scope and limits

The selected camera is passive: it commands no motion, exposure, focus or gain.  The same upstream
node has effectful inputs (the `/mobile_base/commands/velocity` `Twist` motion command and the
`/reset_pose` `PoseStamped` teleport) and other outputs (depth `Image`, `PointCloud2`, `/odom`,
`/ground_truth_odom`, `CameraInfo` and TF).  They are NOT COVERED here.  The clone declares no
acknowledged ROS service or action that stops the simulator, and a zero-velocity topic publication
or node shutdown is not an acknowledged stop, so this passive camera package claims neither motion
control nor simulator stepping.

The fake returns a 2x2 placeholder frame, not the configured 256x256 image.  All fake numbers,
pixels, frame ids and stamps are test data, not facts.  No live ROS graph, iGibson renderer or
hardware run is claimed, and the package declares no numeric input bound (so
`site-limits.example.json` is not needed).

Model review (2026-11-05): as pinned, `turtlebot_rgbd.py` cannot start. Its main block parses
`--enable_left_right_cams` with argparse and calls `SimNode(args)`, while `SimNode.__init__` takes
only `self` (`igibson-ros/turtlebot_rgbd.py:25`, `:247`), and every launch file of the clone,
including the README's `turtlebot_custom_nav.launch`, starts that script.  Until the operator
repairs the node or runs `turtlebot_env.py` (the same `/gibson_ros/camera/rgb/image` publisher and
`rgb8` encoding, `SimNode()` without arguments, started by no launch file), the topic stays silent
and every live capture fails with a timeout, never with a fabricated image.  The node's loop has no
rate limiter: it publishes one image per `iGibsonEnv` step of `action_timestep` 1/30.
