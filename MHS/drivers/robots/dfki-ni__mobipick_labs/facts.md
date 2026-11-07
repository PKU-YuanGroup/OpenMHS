# Facts and tags for gh.dfki-ni/mobipick_labs

Every fact cites the pinned clone at commit `adbfa53af2f6221501215bfb18d2d108225bc04f`:
`vendor_doc` for documentation text and `upstream_code` for source code or comments.
The same facts are written into `facts = [...]` in `driver.py`; the generated
reference is built from the driver, not from this page.

## Scope

The selected concrete device is `experiment_camera`, the static Gazebo RGB camera
shipped by `experiment_camera_recorder`. Its primary output is the
`sensor_msgs/Image` stream on `/experiment_camera/image_raw`; this package
captures one complete frame per invocation through the stock ROS artifact path.
The planning/demo nodes are not bound: they orchestrate an external Mobipick
mobile-manipulator stack that is not part of this pinned clone, and this
repository exposes no upstream stop service or action for their motion.

The camera dimensions and update rate are launch arguments. The launch defaults
are recorded as configuration facts, not as fixed device limits. A deployment
may resolve a different width, height or rate.

## Facts

| fact | source | ref |
|---|---|---|
| The `experiment_camera_recorder` package provides a transparent, static Gazebo RGB camera named `experiment_camera` and publishes `sensor_msgs/Image` messages on `/experiment_camera/image_raw`. | vendor_doc | experiment_camera_recorder/README.md:3-5 |
| The camera description declares a Gazebo sensor of type camera with `always_on` true, an update rate from the `update_rate` argument, image width and height from the `width` and `height` arguments, and format `R8G8B8`. | upstream_code | experiment_camera_recorder/urdf/experiment_camera.urdf.xacro:25-36 |
| The camera description loads `libgazebo_ros_camera.so` with `cameraName` `experiment_camera`, `robotNamespace` `/`, `imageTopicName` `image_raw` and `cameraInfoTopicName` `camera_info`. | upstream_code | experiment_camera_recorder/urdf/experiment_camera.urdf.xacro:42-49 |
| `camera.launch` declares the launch arguments `width`, `height` and `update_rate` with the defaults 1280, 720 and 10.0. | upstream_code | experiment_camera_recorder/launch/camera.launch:9-11 |
| `camera.launch` sets the `experiment_camera_description` parameter by running xacro on `experiment_camera.urdf.xacro` with `width`, `height` and `update_rate` taken from its launch arguments. | upstream_code | experiment_camera_recorder/launch/camera.launch:17-19 |
| `camera.launch` starts `frame_recorder.py` only when its `record` argument is true and passes it the `image_topic` parameter `/experiment_camera/image_raw`. | upstream_code | experiment_camera_recorder/launch/camera.launch:26-28 |
| The sensor and its camera plugin both set their always-on flags true (`always_on` and `alwaysOn`). | upstream_code | experiment_camera_recorder/urdf/experiment_camera.urdf.xacro:27-43 |

## Image contract and bounds

The supported raw encoding is the URDF `R8G8B8` camera format; the stock bridge
converts the complete ROS 1 `sensor_msgs/Image` sample to a lossless PNG artifact.
The fixed-stream path returns the stable four-field image output and does not
add a source header to the artifact descriptor.

Transport and artifact numbers are client policy, not manufacturer or device
limits: 16 MiB per rosbridge JSON message, 8 MiB of raw image input, 4,194,304
pixels and a 2000 ms capture budget. The pinned launch defaults are 1280x720
(921,600 pixels, 2,764,800 raw bytes), which fit those host limits. The fake
returns a 4x3 placeholder frame to keep receipts small; that smaller array is
test data, not the deployed camera size. A full-size frame also needs an
operator-supplied artifact store large enough for the encoded PNG (the SDK
default is 2 MiB per artifact). This package does not silently enlarge the
host's artifact allowance.

NOT COVERED: `/experiment_camera/camera_info`, calibration, camera pose, pose
tuning, exposure control, recording controls and the planner/robot stack. The
pinned clone does not expose those as a fixed image-capture contract.

## Tags

`ros`, `ros1`, `gazebo`, `simulation`, `camera`, `image`, `mobipick`
