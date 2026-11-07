# Facts and tags for gh.ros2/ros_astra_camera

Every fact cites the pinned clone at commit `ac20ab9eea9ff14d4b2dd841d580cf9b3c875110`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The node main creates an rclcpp node named astra_camera. | upstream_code | ros/astra_camera_node.cpp:131 |
| The color branch creates a publisher on the relative topic 'image' with message type sensor_msgs::msg::Image and sensor-data QoS. | upstream_code | src/astra_driver.cpp:190 |
| The driver requests the color video mode with PIXEL_FORMAT_RGB888. | upstream_code | src/astra_driver.cpp:153-154 |
| The frame listener maps PIXEL_FORMAT_RGB888 to the ROS RGB8 encoding and sets step to 3 bytes per pixel. | upstream_code | src/astra_frame_listener.cpp:145-147 |
| The frame listener fills width and height from the device frame, copies the frame data, and sets is_bigendian to 0. | upstream_code | src/astra_frame_listener.cpp:115-123 |
| The color callback assigns the configured color frame id to the image header and publishes the image on the color publisher. | upstream_code | src/astra_driver.cpp:555-559 |
| The color publisher is created only inside the hasColorSensor branch. | upstream_code | src/astra_driver.cpp:185-191 |
| The node main initializes the color request to width 1280, height 1024 and frame rate 30. | upstream_code | ros/astra_camera_node.cpp:110-112 |
| parse_command_options replaces the color width, height and frame rate from the -w, -h and -f command-line options. | upstream_code | ros/astra_camera_node.cpp:56-69 |
| rawToFloatingPointConversion sets the new image encoding to TYPE_32FC1 and step to sizeof(float)*width, maps unsigned-short samples equal to 0 or 0x7FF to NaN and divides every other sample by 1000. | upstream_code | src/astra_driver.cpp:1114-1145 |
| The depth branch creates a publisher on the relative 'depth' topic with message type sensor_msgs::msg::Image. | upstream_code | src/astra_driver.cpp:210 |
| The depth branch publishes the converted floating-point image through pub_depth_raw_. | upstream_code | src/astra_driver.cpp:623 |
| The depth branch publishes a CameraInfo message on the relative 'depth_camera_info' topic. | upstream_code | src/astra_driver.cpp:211 |
| The -C command-line option sets use_color to false. | upstream_code | ros/astra_camera_node.cpp:101 |
| The node sets the use_color parameter from the parsed command-line option when it is not already set. | upstream_code | ros/astra_camera_node.cpp:135 |

## Scope

The package exposes the node's primary color image publisher. The publisher is
created with the relative literal `"image"` (`src/astra_driver.cpp:190`) on a
node named `astra_camera` (`ros/astra_camera_node.cpp:131`), so the default root
namespace resolves the endpoint to `/image`. The driver records the upstream
relative token as `source_name`; a deployment that namespaces or remaps the node
must expose the capture at `/image`, and that graph assumption is not an upstream
fact. The driver is a fixed subscription: it cannot select a camera, resolution,
exposure, encoding or topic at call time.

The pinned color pipeline requests `PIXEL_FORMAT_RGB888`
(`src/astra_driver.cpp:153-154`), the frame listener maps that format to `RGB8`
with `step = 3 * width` (`src/astra_frame_listener.cpp:145-147`), and the Image
data is copied from the device frame with `is_bigendian = 0`
(`src/astra_frame_listener.cpp:115-123`). The SDK image profile carries exactly
that encoding into a bounded lossless PNG artifact; this flat fixed-subscription
profile keeps the legacy `image_ref`/`width`/`height`/`media_type` output and
does not add the ROS source header to the artifact descriptor.
The node's default color frame is 1280x1024 at 30 Hz
(`ros/astra_camera_node.cpp:110-112`), replaced by the `-w`, `-h` and `-f`
command-line options (`ros/astra_camera_node.cpp:56-69`); those are defaults of
the node's main, not a device
bound, and a deployment may select another supported mode.

The node also publishes `ir_image` and `depth`
(`src/astra_driver.cpp:199`, `:210`) and `depth_camera_info`
(`src/astra_driver.cpp:211`). Depth is not bound: `rawToFloatingPointConversion`
publishes `TYPE_32FC1` with NaN for invalid samples (`src/astra_driver.cpp:1114-1145`), which the fixed image
artifact profile refuses (it supports rgb8, bgr8, rgba8, bgra8, mono8, mono16
and 16UC1). IR is not bound because the pinned source never assigns the active
IR video mode's pixel format, so a verifiable encoding citation is unavailable.
`depth_camera_info` is not exposed as a resource snapshot because the main
resource is an empty action-only resource and automatic snapshots are not
substituted for the primary image capture.

## Safety

The camera is a passive R0 observation endpoint. It commands no motion, heat,
light emission, dispensing or other actuation. Closing a subscription is not
camera power-off, and this package claims no stop, safe state or hardware
e-stop. The upstream node has no e-stop service in the pinned source; the
`get_serial` service is commented out (`src/astra_driver.cpp:235`), and no
other ROS service is advertised in the ROS 2 branch.

## Fidelity

The fake is a ROS-free synthesized controlled peer, not a captured recording
and not the upstream simulator. It answers the declared `/image` subscription
with a complete placeholder 4x2 RGB8 Image and no other endpoint. The real
device's default frame is 1280x1024 and its size/contents are whatever the
device and deployment produce; no camera acquisition, ROS graph or hardware run
is claimed.

## Tags

`ros`, `ros2`, `camera`, `image`, `rgb`, `astra`, `orbbec`
