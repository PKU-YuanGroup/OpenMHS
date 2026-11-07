OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# ROS receiver startup and bounded close

A request can send its first rosbridge frame and publish the receiver Thread
before Thread.start has finished. Concurrent close previously joined that
unstarted thread and raised RuntimeError. The sole Thread remains retained from
startup, while a new event records entry into its receive target. Close joins
only after that entry proves the thread has started, keeping the existing
100 ms join budget and taking no startup lock. A receiver that starts after
close sees the stop event and exits without receiving.

A startup failure now stops the receiver attempt and faults/wakes the
connection. No later request reconnects, retries setup, or replays a goal on
that connection. Retaining the Thread also covers an injected failure after
the real start: bounded close may return while a deliberately held receive is
still finishing, but the live owner remains reachable and exits after release.
This injection tests ownership; it is not a claim that standard Thread.start
normally raises after successful startup.

Validation uses both ROS protocol profiles, controlled startup and receive
barriers, repeated close, concurrent starters, pre-start and partial-start
failures, and ordinary successful service controls. The original action safety
and retirement rules remain unchanged. These are ROS-free SDK tests; they do
not establish new native ROS, hardware, transport plugin, or publication
guarantees. The bound specifically excludes waiting for receiver startup;
arbitrary injected transport.close implementations retain their own contract.

The integrated repair passed independent deterministic before/after probes,
221 focused ROS tests and 18 Franka package tests. All five existing passing
RosDriver packages retain their gate digests. On 2026-11-04, the complete SDK
ran 2687 tests with five skips and no failures; all 392 SDK inputs and 1034
existing dependency files remained unchanged.

A fresh isolated ROS2 Jazzy turtlesim and controlled Image regression passed
service/topic/action/cancel/replay, actual MCP stdio, exact BGR8/mono16 pixels
and artifact authorization. It recorded 98 native frames and verified all
163 SDK/package inputs unchanged. Owned fixture, tunnel and container exited
cleanly, with no listener or artifact store left behind. The initial rerun
selected a test interpreter without websocket-client and failed before native
commands; that record is preserved, and the successful rerun used the existing
ROS validation interpreter without a product-code change. This remains
simulator evidence, not action-backed native safety or hardware validation.
