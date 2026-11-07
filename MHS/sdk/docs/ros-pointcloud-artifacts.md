OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Complete ROS PointCloud2 artifacts

`RosDriver` can capture one fixed `sensor_msgs/PointCloud2` (ROS1) or
`sensor_msgs/msg/PointCloud2` (ROS2) stream through `cap.sensing.point_cloud.v1`.
The endpoint needs a [local artifact store](image-artifacts.md). A successful
capture returns an `artifact_ref`, the actual `width * height` point count, and
the received frame when it fits the catalogue's 64-character output bound.
The complete received header is always in the artifact, including longer frame
identifiers within the helper's 256-byte bound. No ROS, PCL or numeric package
is imported to read or package the bytes.

```python
from mhs.driver import Action, RosDriver

class FixedCloud(RosDriver):
    device_id = "fixed-cloud"
    device_kind = "sensor.depth"
    mode, risk = "hardware", "R0"
    ros_version = 2
    commands = {
        "cap.sensing.point_cloud.v1": {
            "topic": "/operator_verified_namespace/points",
            "type": "sensor_msgs/msg/PointCloud2",
            "operation": "subscribe",
            "point_cloud": {"max_input_bytes": 8 * 1024 * 1024},
        }
    }
    actions = {"cap.sensing.point_cloud.v1": Action(name="capture")}
```

The topic and message type are fixed by the driver and must match its declared
ROS version. A packaged driver must provide pinned upstream source evidence and
operator-verified deployment names; this example is not that evidence. Capture
takes an empty input. Caller-selected topics, range filtering, point limits,
field selection, coordinate conversion and reframing are not supported.
Declaring a custom action input for this conversion is an error.

## Artifact format

The media type is `application/zip`. Format `openmhs.ros-pointcloud2.v1` contains
exactly two uncompressed members, `pointcloud.json` and `data.bin`. ZIP dates,
member modes and order are fixed so the same complete message yields the same
bytes. The JSON member contains the format, original message type, fixed topic,
exact header, width, height, all fields in original order, endianness,
`point_step`, `row_step`, `is_dense`, and the SHA256 of `data.bin`.

`data.bin` is the complete original `data` sequence. It retains every point and
row padding byte, all declared fields and overlapping views, and every floating
point bit pattern, including NaN payloads and negative zero. The helper does not
decode floating point numbers, remove zero/invalid points, swap endianness,
reshape rows, or interpret units. The source `is_dense` flag is retained as a
source declaration; it is not an independent check that all points are finite.

The descriptor's `x-vendor.openmhs.ros_point_cloud` also retains format, topic,
message type, ROS version and the same received header. A ROS1 header includes
`seq`, `stamp.secs`, `stamp.nsecs` and `frame_id`; a ROS2 header includes
`stamp.sec`, `stamp.nanosec` and `frame_id`. Acquisition age, synchronization with
another sensor, calibration and coordinate-frame correctness are not inferred.

## Bounds and refusal

All standard PointCloud2 members are required; unknown members are rejected.
The eight standard PointField datatypes are supported with positive element
counts and unique bounded names. Each field span must fit inside `point_step`.
The row stride must cover all points and the exact data length must equal
`row_step * height`. Data must be canonical base64 or a JSON array of integer
bytes; booleans are not bytes or dimensions. A default empty cloud and a filtered
empty cloud with width zero and height zero or one are supported. Other empty
layouts are refused explicitly.

The `point_cloud` declaration accepts only these fixed admission budgets:

| Setting | Default | Maximum |
| --- | --- | --- |
| `max_input_bytes` | 8 MiB | 16 MiB |
| `max_points` | 1,048,576 | 10,000,000 |
| `max_fields` | 64 | 128 |

These budgets are limits on a whole sample, not instructions to truncate it.
The artifact must also fit its separately configured store limit, including the
JSON and ZIP overhead. A 16 MiB raw payload therefore cannot fit into a 16 MiB
artifact. The default artifact limit is 2 MiB. Large captures require explicit
transport and artifact budgets; base64 increases the transport message size.
The standard gate uses its normal default store and does not raise limits on
behalf of a driver. A missing store refuses before subscribing. Malformed data,
capacity exhaustion, interruption and failed receipt commit produce no new
readable artifact grant.

## Ownership and scope

Reads use the original receipt's session and principal. Replaying the same
command retains its receipt and artifact instead of taking a second sample.
Expiry and endpoint close revoke retrieval; receipt metadata remains an account
of the earlier operation. MCP resource reads carry complete bytes, including
samples larger than the ordinary request-frame limit within the artifact
response bound. A caller's modification of a decoded in-process response cannot
alter the server's retained receipt or operation result.

Controlled tests cover ROS1/ROS2 headers, both byte orders, field types, overlaps,
padding, empty and malformed samples, ownership, expiry, replay, interruption,
receipt-commit failure, and a complete 128 x 2048 sample at an explicitly chosen
48-byte test stride. That stride is not evidence of a deployed PCL ABI. These
tests use a recording transport and do not certify a native sensor or a hardware
stop. Closing an endpoint ends evidence recording immediately; the close test
checks worker retirement and lack of artifacts, not a final receipt after close.

This helper implements the point-cloud capability only. A complete multi-sensor
driver may also need images, scan arrays, IMU data, lifecycle and deployment
controls. One resource cannot bind both the stable image class (`sensor.camera`)
and the point-cloud class (`sensor.depth`); a package that serves both declares
the cloud on an extra resource of the same device (`extra_resources` plus
`Action(resource=...)`, "Package composition" in
[driver-authoring.md](driver-authoring.md)). That gives one transport, one latch
and one lifecycle; it does not make independent image and cloud captures a
synchronized pair, and every other output of the upstream workflow still needs
its own binding and validation.
