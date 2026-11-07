OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Complete bounded ROS PointCloud2 artifacts

The fixed-stream ROS bridge can now bind `cap.sensing.point_cloud.v1` and publish
the complete binary message data with its field layout and exact received header
as a deterministic local ZIP artifact. All point and row padding, byte order,
overlapping field views and floating point bit patterns are preserved. Strict
layout, whole-sample budgets and existing artifact ownership/commit barriers
refuse malformed, oversized or interrupted captures without a new readable grant.

The stock gate supplies its normal artifact store for this class and protects
the new conversion module from driver mutation. ROS1/ROS2, all eight field
datatypes, full 128 x 2048 controlled data, MCP resource framing, lifecycle and
source/policy controls are covered by 17 focused test methods. The point-cloud
helper does not complete a multi-sensor upstream package or establish native
ROS/PCL ABI, calibration, synchronization or hardware acceptance.

The private candidate's complete regression results and immutable input hashes
are recorded by its validation runner; integration requires independent review.
No driver package, registry card, human signature or publication is changed by
this candidate. See `MHS/sdk/docs/ros-pointcloud-artifacts.md` for the format and
explicit limits.
