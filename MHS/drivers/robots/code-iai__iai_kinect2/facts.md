# Facts and tags for gh.code-iai/iai_kinect2

Every fact cites the pinned clone at commit
`0e2c5f63134a076606bb79963406e1d47f2da651`. `upstream_code` refs name
`path/in/clone:LINE`; a bounded range is used where the statement spans
adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not
from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The bridge README describes the node as a bridge between libfreenect2 and ROS. | vendor_doc | kinect2_bridge/README.md:11 |
| initialize reads the private base_name parameter with std::string(K2_DEFAULT_NS) as its default. | upstream_code | kinect2_bridge/src/kinect2_bridge.cpp:247 |
| K2_DEFAULT_NS is the literal "kinect2". | upstream_code | kinect2_bridge/include/kinect2_bridge/kinect2_definitions.h:24 |
| The topic macros define the /sd group and the /image_color, /image_depth, /image_ir, _rect and /camera_info suffixes. | upstream_code | kinect2_bridge/include/kinect2_bridge/kinect2_definitions.h:32-41 |
| initTopics composes the SD color-rectified, depth-rectified and raw IR topic names from those macros. | upstream_code | kinect2_bridge/src/kinect2_bridge.cpp:487-495 |
| initTopics advertises sensor_msgs::Image and sensor_msgs::CompressedImage publishers for every composed topic as base_name + topics[i]. | upstream_code | kinect2_bridge/src/kinect2_bridge.cpp:513-514 |
| initTopics advertises sensor_msgs::CameraInfo on base_name + K2_TOPIC_SD + K2_TOPIC_INFO. | upstream_code | kinect2_bridge/src/kinect2_bridge.cpp:518 |
| The constructor sets sizeColor to 1920x1080, sizeIr to 512x424 and sizeLowRes to half sizeColor. | upstream_code | kinect2_bridge/src/kinect2_bridge.cpp:138 |
| The README states that the SD raw IR and depth topics carry 512x424 images. | vendor_doc | kinect2_bridge/README.md:80 |
| createImage assigns TYPE_16UC1 to the IR and depth images, BGR8 to the color images and TYPE_8UC1 to the mono images. | upstream_code | kinect2_bridge/src/kinect2_bridge.cpp:1380-1402 |
| createImage copies the Mat height, width and step, sets is_bigendian to false and copies the byte payload into the ROS Image. | upstream_code | kinect2_bridge/src/kinect2_bridge.cpp:1407-1413 |
| The SD color-rectified image is produced by registration->apply into sizeIr buffers and converted from BGRA/RGBA to BGR. | upstream_code | kinect2_bridge/src/kinect2_bridge.cpp:1171-1188 |
| The SD depth-rectified image is produced by remapping depthShifted at sizeIr. | upstream_code | kinect2_bridge/src/kinect2_bridge.cpp:1208-1215 |
| createCameraInfo copies its size argument into CameraInfo height and width; infoIR is created with sizeIr. | upstream_code | kinect2_bridge/src/kinect2_bridge.cpp:739-747 |
| publishImages assigns the frame id baseNameTF + K2_TF_IR_OPT_FRAME to the SD group, including the SD CameraInfo. | upstream_code | kinect2_bridge/src/kinect2_bridge.cpp:1273-1279 |
| callbackStatus starts the device streams when a client subscribes and stops the device when no client remains. | upstream_code | kinect2_bridge/src/kinect2_bridge.cpp:785-810 |
| The README states that images from the same frame share a timestamp and recommends ExactTime synchronization. | vendor_doc | kinect2_bridge/README.md:102 |
| The README states that point clouds are only published when the launch file is used. | vendor_doc | kinect2_bridge/README.md:101 |

## Scope

The selected primary interface is three fixed SD image streams from the
upstream's IR/Depth topic group: the registered color image
(`/kinect2/sd/image_color_rect`, BGR8), the registered depth image
(`/kinect2/sd/image_depth_rect`, 16UC1) and the raw infrared image
(`/kinect2/sd/image_ir`, 16UC1). The bridge composes them from
`base_name` and the topic macros; the default `base_name` is `kinect2`.
The driver records the resolved absolute endpoints. A deployment that
changes `base_name` or namespaces the node must expose the same
endpoints through rosbridge; that is operator configuration, not an
upstream fact.

The image selector returns one complete image per call. Color, depth and
IR are three independent subscriptions, so a single capture does not
return a synchronized triple. The upstream notes that images from the
same frame share a timestamp and recommends ExactTime synchronization;
this package makes no cross-stream synchronization or age claim.

The SD CameraInfo geometry (`frame_id`, `width`, `height`) is a read-only
resource observation. The message is the IR CameraInfo published on
`/kinect2/sd/camera_info`; `width` and `height` come from `sizeIr`. Full
intrinsics, distortion, projection, calibration validity and the TF tree
are not exposed.

The SD depth and IR streams carry 16-bit samples. The artifact path
preserves the sample bytes losslessly in a 16-bit PNG, but the bridge
does not publish depth units or a colormap and this package does not
infer them. `min_depth` and `max_depth` are ROS parameters of the
upstream node, not universal measurement bounds.

## Not covered

The HD and QHD streams, the SD `image_depth` and `image_ir_rect`
variants, all compressed-image transports, the mono streams, the
point-cloud topics, TF, camera controls and ROS parameter writes are
not bound. Point clouds are produced by `depth_image_proc` only when the
upstream launch file is used. The package does not start or validate a
ROS graph; rosbridge parameters, QoS, authentication and reconnection
are outside the helper.

## Safety

The device is a passive camera observation endpoint at R0. The pinned
node exposes no ROS stop service: its `callbackStatus` starts and stops
the libfreenect2 streams as subscribers connect and disconnect, but that
is not an emergency stop and stopping a subscription is not camera
power-off. This package therefore claims no physical stop or safe state
and declares no `estop_physical_ref`.

## Deployment limits

The 2 MiB input and 2 Mi-pixel limits on each fixed subscription are
client conversion bounds, not camera limits. The driver's 4 MiB
`max_message_bytes` is a local rosbridge frame budget. The upstream
node fixes the SD image size at 512x424; a deployment that only needs
a different stream must bind that stream explicitly rather than expect
resolution conversion from this fixed subscription. The rosbridge
endpoint, node namespace and `base_name` are operator configuration.

The fake is an event-driven protocol responder, not a replay of captured
ROS traffic. It returns 4x2 placeholder frames, much smaller than the
fixed 512x424 upstream stream; its pixel values, header values,
calibration and geometry are test data and are marked `# placeholder`.

## Tags

`ros`, `ros1`, `camera`, `depth`, `infrared`, `kinect2`, `image`
