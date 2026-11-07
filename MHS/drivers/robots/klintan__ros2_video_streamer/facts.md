# Facts and tags for gh.klintan/ros2_video_streamer

Every fact cites the pinned clone at commit `4fc6d858d748322250cb0dc5a7864ac2576d148f`:
`vendor_doc` for documentation text and `upstream_code` for source code or comments. The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from
this page.

## Facts

| fact | source | ref |
|---|---|---|
| The node declares the image_topic parameter with the absolute default '/image/image_raw'. | upstream_code | camera_simulator/camera_simulator.py:39 |
| The node declares the camera_info_topic parameter with the absolute default '/image/camera_info'. | upstream_code | camera_simulator/camera_simulator.py:40 |
| The module imports Image, CompressedImage and CameraInfo from sensor_msgs.msg. | upstream_code | camera_simulator/camera_simulator.py:18 |
| The node creates a sensor_msgs Image publisher on image_topic_ with queue size 5 and a CameraInfo publisher on camera_info_topic_ with queue size 5. | upstream_code | camera_simulator/camera_simulator.py:47-48 |
| The node declares the frame_id parameter with the literal default 'camera'. | upstream_code | camera_simulator/camera_simulator.py:42 |
| image_callback calls get_time_msg and passes the result with the frame to get_image_msg. | upstream_code | camera_simulator/camera_simulator.py:117-118 |
| get_time_msg fills builtin_interfaces Time sec and nanosec from the node clock's seconds_nanoseconds(). | upstream_code | camera_simulator/camera_simulator.py:147-153 |
| get_image_msg converts the frame with CvBridge().cv2_to_imgmsg(image, encoding='bgr8'). | upstream_code | camera_simulator/camera_simulator.py:161 |
| get_image_msg sets header.stamp to its time argument and header.frame_id to self.frame_id_. | upstream_code | camera_simulator/camera_simulator.py:162-163 |
| image_callback publishes CameraInfo only when self.calib is truthy, then publishes the Image. | upstream_code | camera_simulator/camera_simulator.py:120-124 |
| get_camera_info fills CameraInfo width, height, distortion_model and d, k, r and p from the calibration YAML. | upstream_code | camera_simulator/camera_simulator.py:132-141 |
| get_compressed_msg constructs a CompressedImage and sets format 'jpeg'. | upstream_code | camera_simulator/camera_simulator.py:166-175 |
| For video mode the node creates a timer with period 1.0/video_fps and registers image_callback. | upstream_code | camera_simulator/camera_simulator.py:90-93 |
| In CameraSimulator.__init__, when type is not 'video', the node publishes every .jpg, .jpeg or .png file of the folder in natural-sort order without a timer and then logs that all images have been published. | upstream_code | camera_simulator/camera_simulator.py:36-98 |
| In video mode, when a read fails and loop is false, image_callback cancels the timer, destroys the node and calls exit(); when loop is true it rewinds to 0 ms and reads again. | upstream_code | camera_simulator/camera_simulator.py:100-110 |
| main constructs CameraSimulator and only then calls rclpy.spin. | upstream_code | camera_simulator/camera_simulator.py:191-196 |
| The README describes the package as a ROS2 python node that streams video files or folder images to a topic and is used as a camera simulator. | vendor_doc | README.md:3-5 |
| The README documents supplying a camera calibration file to publish camera_info. | vendor_doc | README.md:10 |

## Selected observation contract

The profile binds the source default `/image/image_raw` as ROS 2 `sensor_msgs/msg/Image` with the
`color` selector. `get_image_msg` converts every decoded frame to `bgr8`, so the standard ROS image
path preserves every pixel and the frame's own header. A capture returns one complete PNG artifact
with `image_ref`, `width`, `height` and `media_type`; the artifact descriptor's
`x-vendor.openmhs.ros_image` retains the exact ROS 2 `stamp` and `frame_id` from that same packet.
The capture does not establish producer freshness, a fixed resolution or a capture rate.

Only video mode streams (model review of 2026-11-04). In image-folder mode the constructor publishes
every image once, without a timer (`camera_simulator.py:36-98`), and `main` calls `rclpy.spin` only
after construction (`191-196`), so a rosbridge subscription opened later receives no frame; in video
mode without `--loop` the node cancels its timer and calls `exit()` at the end of the file
(`100-110`). A capture then fails `MHS.DEVICE.NOT_READY` after the binding's default 2 s wait (the
action's 10 s `max_duration_ms` does not extend it), so only a looping video gives repeatable captures,
and a video slower than 0.5 fps cannot be captured with the default wait.

The node's `image_topic` and `camera_info_topic` parameters are absolute source defaults and can be
overridden at deployment. This profile binds the defaults; a deployment that overrides them needs an
explicitly reviewed remapping. The camera name and ROS graph are not discovered.

The CameraInfo publication is optional: `image_callback` publishes it only when a calibration file
was read successfully (`camera_simulator.py:120-124`), and the command-line calibration default is
empty (`camera_simulator.py:181`). It is calibration metadata, not the primary image, and this
profile does not bind it. The constructor creates an Image publisher and a CameraInfo publisher
(`camera_simulator.py:47-48`); `get_compressed_msg` has no caller, so no compressed-image endpoint
is declared.

## Bounds and provenance

The image mapping's 8 MiB raw-byte and 4,194,304-pixel limits and the class's 16 MiB rosbridge
message budget are client conversion and transport policies, not camera limits. The upstream node
declares no fixed resolution: it publishes the decoded frame's own size, and its video-mode timer is
`1.0/video_fps` from the selected file. The upstream artifact store's default 2 MiB per-artifact
allowance may refuse a large noisy PNG; a deployment must choose its own store bound explicitly.

There is no numeric actuation input, Limit or hardware bound in this sensor-only package. The
camera simulator has no stop service in the pinned source; the fake backend is observation-only, and
a stock software e-stop latch refuses later captures. No hardware backend exists.

## Fidelity of the fake

The fake is a ROS-free controlled peer, not captured ROS traffic. It answers the declared
`/image/image_raw` subscription with a complete 4x2 placeholder BGR8 packet and an exact ROS 2
header. It runs no ROS node, OpenCV, video decoder, timer or camera. The placeholder's dimensions
and timestamps are test data, not facts. The real stream's dimensions follow the chosen video or
image files, and the upstream timer runs at the file's FPS.

## Validation and provenance

`test_driver.py` keeps the stock `check_driver` call and adds cases for complete PNG capture and
header retention, the closed camera selector, the declared subscribe/unsubscribe wire operation,
malformed stride, unsupported encoding, a missing header, a silent image topic (added by the model
review of 2026-11-04), the e-stop latch, and the ROS-free peer.
All checks are controlled fake-backend evidence (`contract_checked`), not a ROS, video or hardware
run. `driver.lock.json` keeps `reviewed_by: null`.

## Tags

`ros`, `ros2`, `camera`, `simulator`, `image`, `video`, `replay`
