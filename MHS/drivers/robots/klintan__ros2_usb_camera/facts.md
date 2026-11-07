OpenMHS is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.klintan/ros2_usb_camera

Every fact cites the pinned clone at commit `146c5911ebcc5539eb8550e02763abe1fdfa8d05`:
`vendor_doc` for documentation text and `upstream_code` for source code or comments. The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from
this page.

## Facts

| fact | source | ref |
|---|---|---|
| README.md documents /camera_info as the topic for camera info. | vendor_doc | README.md:15 |
| The node declares a configurable frame_id parameter with the literal default 'camera'; a deployment may set a different frame name. | upstream_code | src/usb_camera_driver.cpp:37 |
| The node's CameraInfo message type is sensor_msgs::msg::CameraInfo, constructed from camera_info_manager::CameraInfoManager::getCameraInfo(). | upstream_code | src/usb_camera_driver.cpp:131-132 |
| The source includes sensor_msgs/msg/camera_info.hpp for the CameraInfo message. | upstream_code | include/usb_camera_driver.hpp:33 |
| ImageCallback takes the node clock's current time before stamping the messages. | upstream_code | src/usb_camera_driver.cpp:134 |
| ImageCallback assigns that timestamp and the configured frame_id value to the CameraInfo header. | upstream_code | src/usb_camera_driver.cpp:139-140 |
| The node creates an image_transport camera publisher on the relative 'image' base topic. | upstream_code | src/usb_camera_driver.cpp:46 |
| ImageCallback enters its publish branch only when the captured frame is non-empty and the fps interval has elapsed. | upstream_code | src/usb_camera_driver.cpp:112-113 |
| The publish call sends the image and CameraInfo pair. | upstream_code | src/usb_camera_driver.cpp:142 |
| The node launch file starts usb_camera_driver_node in the '/camera' namespace. | upstream_code | launch/usb_camera_node.launch.py:39-40 |
| The component launch file defines NAMESPACE = '/camera' and uses it for the container. | upstream_code | launch/usb_camera_component.launch.py:36-47 |
| ConvertFrameToMessage constructs a complete bgr8 Image, including dimensions, byte stride and all contiguous or row-wise bytes. | upstream_code | src/usb_camera_driver.cpp:63-103 |
| ImageCallback gives the image and CameraInfo the same node-clock stamp and configured frame id before publishing. | upstream_code | src/usb_camera_driver.cpp:134-142 |
| Camera identity, requested dimensions, fps and calibration file are startup parameters read before capture/timer initialization. | upstream_code | src/usb_camera_driver.cpp:37-60 |
| Compressed output is described as an external image_transport republisher with image_transport_plugins. | vendor_doc | README.md:42-48 |

## Complete primary observation contract

The fixed root-namespace profile provides both primary outputs of the selected C++ camera node:

- `cap.sensing.image.v1`, with the finite selector `camera: "color"`, subscribes to `/image` as `sensor_msgs/msg/Image`. All BGR8 samples become a lossless RGB PNG artifact. The stable four-field output contains `image_ref`, `width`, `height` and `media_type`. The artifact descriptor's `x-vendor.openmhs.ros_image` contains the exact captured ROS2 header, declared stream identity, endpoint and type.
- `x-cap.klintan.camera_calibration.v1` subscribes to `/camera_info` as `sensor_msgs/msg/CameraInfo` and returns the entire `camera_info` object: its own header, dimensions, distortion model, every `d`, `k`, `r` and `p` element, binning and all ROI fields.
- The original read-only `frame_id` resource and `x-cap.klintan.camera_info.v1` action remain available, with all original tests unchanged.

Each action opens a fresh bounded subscription and unsubscribes afterward. An arriving sample may itself be old. The source stamps its image and CameraInfo together, but two independent subscriptions are not an atomic pair; this package does not claim producer freshness, cross-topic synchronization, calibration validity or registration. Different captured timestamps and dimensions remain different. Zero/uncalibrated matrices and an empty distortion vector are preserved, not repaired or relabelled.

The source creates a publisher on relative `image` (`src/usb_camera_driver.cpp:46`), although README.md:16 says `/image_raw`. This profile follows the implementation's literal under a root node namespace and keeps `/camera_info` from README.md:15. The supplied node launch instead sets `/camera` (launch/usb_camera_node.launch.py:39-40). A deployment using that launch needs an explicitly reviewed graph/remapping to these fixed endpoints; caller arguments cannot select a topic or type. No native graph was started to prove that deployment.

## Source and bounded wire interpretation

The exact device source remains pinned at `146c5911ebcc5539eb8550e02763abe1fdfa8d05`. ROS2 message structure was independently compared with `ros2/common_interfaces` commit `40455bd4e4a2a8f18c85b221b31ae42727cba0b6`, especially `sensor_msgs/msg/CameraInfo.msg`, `RegionOfInterest.msg`, `Image.msg` and `std_msgs/msg/Header.msg`. The separate `builtin_interfaces/msg/Time.msg` definition is from `ros2/rcl_interfaces` commit `614f3c4942e1a67a568546cb805ff3e0ff7777f5`. These comparisons are a static message-definition basis, not a claim that the unrun camera deployment pins those dependency versions.

CameraInfo requires all declared fields, exact fixed matrix lengths (9/9/12), finite numbers, strict booleans and exact integer types. ROS2 seconds use signed 32-bit representation, nanoseconds are 0..999999999, and dimensions/binning/ROI use uint32. The complete observed values are returned unchanged after validation. Host bounds cap the variable distortion vector at 64 elements, distortion-model text at 128 characters, and frame ids at 256 UTF-8 bytes without control characters. These are finite parser/host policies, not manufacturer limits. Unsupported shapes and excess values fail rather than truncate.

Image transport allows at most 16 MiB per JSON message, 8 MiB of raw image input and 4,194,304 pixels, within the stock decoder's dimension bounds. These host budgets include the default requested 1280x720 BGR8 frame (src/usb_camera_driver.cpp:39-40). A host must explicitly supply an artifact store: 4 MiB per artifact admits the complete noncompressible default-size control. The unchanged default 2 MiB store refuses that sample with OUTPUT_INVALID and no grant. The package never silently raises the host's artifact allowance. Image conversion has a finite 2000 ms execution budget; it does not crop, resize or drop samples to fit it.

The source's shipped calibration YAML is 640x480 while its requested capture defaults are 1280x720. The profile preserves received calibration/image values without asserting that the calibration fits the image. The source also compares rows to requested width and columns to requested height before resizing (:69-71), and its flip branch computes `flipped_frame` but converts `frame` (:118-126). Those are upstream behaviors, not fixed or certified here.

## Lifecycle, scope and safety

The node owns USB capture, OpenCV, camera identity, startup parameters and its capture timer. This package observes its full Image and CameraInfo outputs through the shared ROS bridge; it does not construct or destroy that upstream node, start a camera, or invent runtime camera-setting endpoints absent from the source. External compressed-image republishers (README.md:42-48), physical calibration and the native dependency/build/graph are outside this selected node output contract. The pinned node has no additional depth, point-cloud or parallel-camera output to omit.

The package remains hardware-class R0, with its fake backend served as an F0 simulated view. There is no numerical actuation input, physical limit, stop or safe-state endpoint to invent. `reviewed_by` remains null, and the stock loader refuses a hardware backend before connection even when its caller sets the ordinary hardware opt-in. No ROS, USB, native library or hardware run is claimed.

Cancellation while the endpoint is open retires the subscription and records a cancelled/failed terminal receipt; late packets cannot publish an artifact. Endpoint closure ends evidence recording immediately. Its pending worker must retire, the transport/store must close and no grant may remain; a final recorded receipt after that endpoint close is not promised by the SDK. Session/principal authorization, TTL, exact receipt replay and cleanup use the stock artifact store. Caller mutation cannot change a retained descriptor or pixels.

## Validation and provenance

`test_driver.py` remains byte-identical, including its stock check_driver call and all six original cases. Added package tests decode every pixel of a nonconstant 1280x720 sample, preserve row padding semantics and both independent headers, verify complete/noncalibrated CameraInfo, malformed and nonfinite refusal, default-store refusal, finite selectors, cancellation/close and access/TTL/replay ownership. The separate host test exercises stock MCP image resource read; it remains outside the package because the unchanged G3 policy forbids package imports of the MCP runtime.

Original DeepSeek authorship, source pin, task card and null signature are retained. This local model-review repair adds primary output coverage to the former metadata-only package; controlled fake checks remain contract_checked evidence, not native qualification or publication approval.

## Tags

`ros`, `ros2`, `camera`, `camera-info`, `image`, `calibration`, `frame`
