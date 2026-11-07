OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Isolated live ROS validation

The ROS helper has now been exercised against a real ROS 2 Jazzy graph, using the upstream turtlesim tutorial
simulator and rosbridge. This is additional interoperability evidence beyond controlled-peer tests. It is not
validation of Panda, Gazebo, MoveIt, other corpus packages, a physical camera or hardware.

The user selected a local isolated Docker deployment. The ARM64 Ubuntu Noble base was pinned to the official
ROS image digest `sha256:8eed0a4669bbf43ee331878a4c39bd8ebddea8e3312a58b4fae8edb14526b617`. The resulting image used
turtlesim 1.8.4 and rosbridge 2.7.1; complete package versions and image inspection are retained in the private run
evidence. It ran as UID 1000 with a read-only root, a bounded temporary filesystem, dropped capabilities, no new
privileges, and CPU/memory/process limits. No host repository, credentials, Docker socket or physical devices
were mounted. DDS discovery stayed within the container.

Docker Desktop did not activate the requested published port on its internal network. A temporary bounded host
listener on `127.0.0.1` forwarded through owned Docker exec pipes to rosbridge inside that same container. The
internal network was retained; no external runtime network was added. Initial connection failures and the first
forwarding timeout are preserved. The successful configuration gives connection establishment enough time for
Docker exec startup while keeping operation deadlines bounded.

The stock RosDriver, MHSServer and MCP projection passed these live checks:

- An acknowledged teleport service was followed by an independent pose observation at the requested location.
  Reusing the MCP retry token returned the original receipt and sent exactly one native service request.
- Velocity topic publication returned `published=true, confirmed=false`. A separate pose observation showed
  motion, then zero velocity. Publication itself was not treated as a native acknowledgement or safety stop.
- A zero-displacement RotateAbsolute goal returned its actual terminal success and application result.
  A separate nonzero goal was observed moving, then cancelled with its exact native goal identifier. The SDK
  retained UNKNOWN because this declaration had no independent acknowledged safe-state service, even though
  subsequent pose observations showed the native rotation had stopped.
- The actual MCP stdio loop, in a separate child process, repeated service/pose/replay/action checks and returned
  a valid evidence chain. The live path did not replace WebSocket messages or native responses with a fake.

A separate, explicitly controlled ROS node published known `sensor_msgs/Image` patterns. Real rosbridge packets
then passed through the stock image binding and actual MCP stdio `resources/read`. Both padded BGR8 and
little-endian mono16 inputs reconstructed exact PNG samples, with correct dimensions, byte-order handling,
padding removal, size and SHA-256. Replay retained the original grant, and endpoint shutdown removed each owned
temporary artifact store. These small fixtures establish the live serialization path; the separate large-frame
review establishes configured size limits. Neither is an image from a physical camera.

Primary interface sources: [turtlesim](https://github.com/ros/ros_tutorials/tree/jazzy/turtlesim),
[ROS Jazzy installation support](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Installation/Ubuntu-Install-Debs.rst),
and [rosbridge launch configuration](https://github.com/RobotWebTools/rosbridge_suite/blob/ros2/rosbridge_server/launch/rosbridge_websocket_launch.xml).
The deployed package manifest and observed graph types determine the tested environment; these source links do
not claim compatibility with every branch, release or simulator configuration.
