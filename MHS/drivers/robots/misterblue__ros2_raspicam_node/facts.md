# Facts and tags for gh.misterblue/ros2_raspicam_node

Every fact cites the pinned clone at commit `cebf5fdacd18b50943bd234600e8fc3622ae4a46`.
`upstream_code` refs name `path/in/clone.py:LINE`; a bounded range is used where
the statement spans adjacent lines.  The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from
this page.

## Facts

| fact | source | ref |
|---|---|---|
| The node constructor names it `ros2_raspicam_node` and sets `namespace='raspicam'`; the topic parameters are relative to that namespace. | upstream_code | src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:30 |
| The constructor seeds `compressed_image=True` and `compressed_image_topic='raspicam_compressed'` as ROS parameter defaults; a deployment may override them. | upstream_code | src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:33-35 |
| The module imports `CompressedImage` from `sensor_msgs.msg`. | upstream_code | src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:23 |
| `initialize_publisher` creates a `CompressedImage` publisher from `compressed_image_topic` when `compressed_image` is true; the false branch references `Image`, which the module never imports. | upstream_code | src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:88-94 |
| `take_pictures` requests `capture_continuous(..., format='jpeg')`, and `write_capture` builds a `CompressedImage` with the captured bytes, `format='jpeg'` and `header.frame_id` set to the frame number. | upstream_code | src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:158-188 |
| `publish_images` takes each queued `CompressedImage` and publishes it unchanged on the publisher. | upstream_code | src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:193-207 |
| README documents the absolute topic `/raspicam/raspicam_compressed` carrying JPEG bytes in `sensor_msgs` CompressedImage form with `header.frame_id` equal to the frame number. | vendor_doc | README.md:7 |
| README states the project does not output a raw image, does not output camera info and does not accept parameters. | vendor_doc | README.md:9 |
| `destroy_node` closes the PiCamera object when one exists and then calls the base `destroy_node`. | upstream_code | src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:80-86 |
| `main` calls `stop_workers` and `destroy_node` only after `rclpy.spin` returns. | upstream_code | src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:252-266 |
| `write_capture` sets `format` and `header.frame_id`; its only `header.stamp` assignment is commented out. | upstream_code | src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:180-187 |
| The node defines its own `has_parameter` helper, which calls `get_parameter` and treats a `NOT_SET` type as unset, and `set_parameter_defaults` sets only the parameters that helper reports unset. | upstream_code | src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:229-249 |

## Scope

The primary and only working interface is the node's compressed JPEG stream.
The constructor's `compressed_image` parameter defaults to true, and the
compressed publisher is created from the relative name `raspicam_compressed`
under the `raspicam` namespace.  The package binds
`/raspicam/raspicam_compressed` as a fixed `cap.sensing.image.v1` subscription
and records the relative token as `source_name`; a deployment that remaps or
re-namespaces the node is operator configuration outside these upstream facts.
The README's absolute topic name corroborates the namespace.

The uncompressed branch is not exposed.  It constructs an `Image` message at
`src/ros2/ros2_raspicam_node/ros2_raspicam_node/ros2_raspicam_node.py:93`, but
the module imports only `CompressedImage` at line 23, so that branch cannot
construct its message.  The README also states that no raw image and no camera
info are output (`README.md:9`).

Camera settings are ROS parameters read once in `set_camera_parameters` during
construction.  The pinned node creates no service or action for changing them,
so this package exposes no camera-control capability and invents no parameter
service.  There is no CameraInfo stream to bind as metadata.

## Safety

The device is a passive camera observation endpoint at R0.  The package
declares no stop or safe-state binding because the pinned node exposes no ROS
service or action that stops capture; `destroy_node` closes the camera only
when the node object is destroyed.  Stopping a rosbridge subscription stops
the observer, not physical acquisition.  The package makes no physical
emergency-stop claim and declares no safe state.

## Deployment limits

The upstream README requires ROS 2 and `python3-picamera` on a Raspberry Pi
(`README.md:18-29`) and builds with colcon (`README.md:22`).  The card's
`install` block is empty, so this package does not claim those system
dependencies are installed.  The rosbridge endpoint, ROS domain, node
namespace, remapping and QoS are operator deployment configuration.

Start-up is not established.  The node (copyright 2018) overrides `has_parameter`
with a helper that calls `get_parameter` and reads undeclared parameters as
`NOT_SET` (lines 229-249); whether that construction path starts under a current
rclpy, which declares parameters before reading them, was not checked (rclpy is
outside the clone).  A RosDriver only subscribes to a running graph and never
starts the node, so a node that fails to start shows as capture timeouts, never as
an image.

The fake is an event-driven protocol responder, not a replay of captured ROS
traffic.  It returns a 2x2 placeholder JPEG; the pinned node's real image size
is whatever its width and height parameters select, and no source text states
a universal resolution bound.  The SDK's default local artifact store holds at
most 2 MiB per image; a larger decoded PNG needs a programmatic
`LocalArtifactStore(max_artifact_bytes=...)` (at most 16 MiB).  The declared
encoded-byte, pixel and transport limits are client execution bounds, not
upstream camera limits.

## Tags

`ros`, `ros2`, `camera`, `image`, `jpeg`, `raspberry-pi`
