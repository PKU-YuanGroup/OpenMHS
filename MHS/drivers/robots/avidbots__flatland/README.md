# Flatland ROS exemplar

A configuration-only `RosDriver` for the pinned Flatland ROS 1 interfaces: explicit
`/clock` observation and acknowledged `/pause` and `/resume` services. This is the
ROS family exemplar; use its structure and cite your own repository's endpoints,
types, response predicates and stop semantics.

The recording fake runs without ROS or Flatland and claims only F0 contract evidence.
It emits no new clock sample while paused; observation then fails at its deadline.
The empty resource snapshot reports no simulator state. Pause is a simulator stop,
not a physical emergency stop. No device or live ROS validation has run, and
`driver.lock.json` keeps `reviewed_by: null`.

See [facts.md](facts.md), [REFERENCE.md](REFERENCE.md) and
[the ROS helper contract](../../../sdk/docs/ros-driver.md) for scope and source evidence.
