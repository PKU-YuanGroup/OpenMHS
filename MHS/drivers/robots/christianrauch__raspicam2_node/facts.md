# Facts and tags for gh.christianrauch/raspicam2_node

Every fact cites the pinned clone at commit `749689a967bfc427e74520dfd107f30f5c50bf0e`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines.  The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The node constructor names the node `raspicam2` in the `camera` namespace. | upstream_code | src/RasPiCamPublisherNode.cpp:4 |
| The constructor always creates a `sensor_msgs::msg::CompressedImage` publisher on the relative topic `image/compressed` with QoS depth 1. | upstream_code | src/RasPiCamPublisherNode.cpp:124 |
| The constructor creates a `sensor_msgs::msg::CameraInfo` publisher on the relative topic `image/camera_info` with QoS depth 1. | upstream_code | src/RasPiCamPublisherNode.cpp:125 |
| The compressed-image callback stamps a header, sets `format` to `jpeg`, and publishes the encoded bytes on the compressed-image publisher. | upstream_code | src/RasPiCamPublisherNode.cpp:160-170 |
| The compressed-image callback also stamps and publishes the CameraInfo message after each compressed frame. | upstream_code | src/RasPiCamPublisherNode.cpp:172-174 |
| CameraInfo width and height are copied from the configured width and height ROS parameters before capture starts. | upstream_code | src/RasPiCamPublisherNode.cpp:64-65 |
| The constructor seeds the width, height, fps and JPEG quality parameters with 320, 240, 90 and 80; these are ROS parameter defaults, not device bounds. | upstream_code | src/RasPiCamPublisherNode.cpp:46-49 |
| The shipped parameter file selects image_transport `compressed`, width 320, height 240, fps 90 and JPEG quality 80 as an example deployment configuration. | upstream_code | cfg/params.yaml:4-8 |
| The constructor defaults image_transport to `raw` and creates the raw `sensor_msgs::msg::Image` publisher only when that parameter equals `raw`. | upstream_code | src/RasPiCamPublisherNode.cpp:76-84 |
| The raw Image callback sets the `rgb8` encoding, dimensions and byte data but never sets `Image.step`; the package does not use that malformed raw publication. | upstream_code | src/RasPiCamPublisherNode.cpp:142-157 |
| The `set_camera_info` service copies the request camera_info into the member and returns `success=true`; it performs no optical calibration or hardware control. | upstream_code | src/RasPiCamPublisherNode.cpp:179-184 |
| The constructor calls `init_cam` and `start_capture`, and the destructor calls `close_cam`. | upstream_code | src/RasPiCamPublisherNode.cpp:130-140 |
| README marks the package deprecated because the MMAL rawcam component is legacy and points deployments to `camera_ros` instead. | vendor_doc | README.md:2-4 |
| The build searches for MMAL, mmal_core, mmal_util, mmal_vc_client, vcos and bcm_host libraries under `/opt/vc` and includes `/opt/vc/include`. | upstream_code | CMakeLists.txt:28-35 |

## Scope

The primary interface is the node's unconditional compressed JPEG stream.  The
constructor registers the compressed callback and the compressed publisher
regardless of `image_transport`; the shipped `cfg/params.yaml:4` selects the
compressed transport.  The package binds `/camera/image/compressed` as a fixed
`cap.sensing.image.v1` subscription.  The relative publisher names are recorded
as `source_name` (`image/compressed`, `image/camera_info`); the absolute
endpoints follow the upstream constructor's `camera` namespace.  A deployment
that remaps or re-namespaces the node is outside this package's upstream
facts and must expose the same endpoints.

The raw `sensor_msgs/msg/Image` publisher is not exposed: the callback never
sets `Image.step` (`src/RasPiCamPublisherNode.cpp:142-157`), so the strict
image converter cannot accept its byte layout.  The compressed stream is the
genuinely complete image path.

CameraInfo geometry is exposed as read-only resource fields (`frame_id`,
`width`, `height`).  The `set_camera_info` service is deliberately not bound:
its callback only copies supplied metadata and returns success
(`src/RasPiCamPublisherNode.cpp:179-184`); it does not calibrate optics or
control the camera.

Camera controls are ROS parameters, and parameter access is an explicit
service binding that this package does not invent.  The image capability
therefore takes no inputs; `RosDriver` publishes a closed, empty input schema
for the fixed stream.

## Safety

The device is a passive camera observation endpoint at R0.  No stop, actuator
or safe-state binding is exposed because the pinned node establishes no ROS
stop service: capture starts in the constructor and is closed only by
destruction (`src/RasPiCamPublisherNode.cpp:130-140`).  Stopping a subscription
does not stop physical acquisition.  The package makes no physical emergency
stop claim and declares no safe state.

## Deployment limits

The package is pinned to a legacy MMAL/vcos/bcm_host Raspberry Pi platform
(`CMakeLists.txt:28-35`) and the upstream README deprecates it in favour of
`camera_ros` (`README.md:2-4`).  The rosbridge deployment, node namespace,
ROS domain and QoS remapping are operator configuration, not upstream facts.
The fake is an event-driven protocol responder, not a replay of captured ROS
traffic.  It returns a 2x2 placeholder JPEG; the shipped example configuration
publishes 320x240 (`cfg/params.yaml:5-6`), the actual deployment size is
whatever the node's `width`/`height` parameters select, and no source text
states a universal resolution bound.  The SDK's default local artifact store
holds at most 2 MiB per image, so a larger decoded PNG at a large configured
resolution is refused by that store; a programmatic deployment can raise the
per-image bound to at most 16 MiB.  This is the SDK artifact bound, not an
upstream camera limit.

## Tags

`ros`, `ros2`, `camera`, `image`, `jpeg`, `raspberry-pi`
