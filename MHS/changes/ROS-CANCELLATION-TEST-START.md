# Synchronize the ROS cancellation regression with actual goal dispatch

OpenMHS is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

The stock safety-freshness regression now waits for the controlled transport to receive the action goal before requesting e-stop. A long-running command can return its running receipt before its worker dispatches that goal. Stopping in that earlier window correctly cancels the local operation without transmitting a ROS goal or cancel frame; the former test nevertheless required a cancel callback.

Only the test schedule changes: a transport-observed start event establishes the active-goal precondition. Every previous assertion, the 10 ms reply deadline, operation execution budget, cancellation budget, both ROS profiles, rearm/terminal holds, and post-terminal fresh-stop requirement remain unchanged. No ROS, server, safety or hardware runtime behavior is changed.

The preserved unchanged-test control delays only entry to the ordinary operation worker. It reproduces the old assertion failure for both profiles with zero goal and cancel frames, while normal scheduling passes. The correction must pass that same delayed-worker control and the full SDK composition before acceptance. The earlier full run remains failed; it did not capture enough trace to prove its precise scheduler ordering. No physical/native claim follows from these controlled tests.
