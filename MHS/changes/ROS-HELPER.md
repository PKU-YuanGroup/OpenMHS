# ROS-HELPER — rosbridge topics and services, with an unsigned fake pilot

On 2026-11-02 the owner approved rosbridge JSON over WebSocket, a ROS-free recording fake, and a human hardware
review before any ROS hardware backend starts. This change implements that bounded first helper and pilots five
pinned repositories. It adds no ROS installation or process management and makes no hardware-validation claim.

## Implemented contract

`RosDriver` is a configuration-only family. It declares topic observations/publications, acknowledged service
commands, service-backed writes and explicit stop/interlock bindings. The bridge imports the optional
`websocket-client` extra lazily; declaration validation and reference generation perform no connection. A supplied
transport can instead record and replay JSON without ROS. ROS 1 and ROS 2 type spellings are supported.

Effectful services require an application-success predicate as well as rosbridge transport success. Publishing
reports transmission only, never execution or stopping. The server retains limits, interlocks, receipts and the
persistent latch. An input-free safe-state action must be an acknowledged service; its permission comes from the
Action declaration, not an untrusted raw command flag. Action-only packages expose an empty resource snapshot
without inventing a sensor or waiting for a topic.

All ROS hardware backends require a schema-valid human `reviewed_by` entry with `scope: hardware`, irrespective of
risk or author, before a factory or WebSocket can run. This applies to adapter loading and direct construction.
Fake/sim backends cannot fall back to a live endpoint or use the SDK WebSocket transport, including a wrapped or
subclassed transport. These checks do not turn arbitrary Python package code into a sandbox.

G7 checks ROS endpoint and type evidence in the pinned clone rather than demanding a nonexistent Python native
class. Separate `source_ref`, `type_ref` and relative/private `source_name` declarations support C++ ROS packages.
The gate also checks the observed wire operations against declared bindings. Scaffold, author/reviewer guidance,
family recipes and the [ROS API guide](../sdk/docs/ros-driver.md) describe the same supported surface.

## Review and repairs

The bridge and gate were independently reviewed before the pilot. Regression cases cover application failure,
late responses, stale subscription identifiers, connection delays crossing an e-stop, ordinary requests filling
all available slots, and ID-less observations arriving before subscription activation. Stop requests have reserved
capacity; queued actuation rechecks its stop epoch at the send boundary. A request with an uncertain outcome is not
retried automatically.

DeepSeek (`deepseek-v4.1-flash:1017`) authored the pilot packages through the existing headless harness in
workspace-write mode. Codex (`gpt-6`, a model and not a human) reviewed the packages against pinned upstream sources.
Every model-authored lock retains `reviewed_by: null`; original files and run logs are preserved privately.

The Flatland exemplar initially published fake clock samples while paused and attributed upstream physics timing
to the recording fake. Review made `/clock` an explicit observation, modeled silence while paused and corrected
F0 to event-driven fake state transitions with no physics or wall-clock pacing. Stock pause/resume now uses an empty
snapshot and does not wait for a paused clock. The package has eight repository tests including negative application
and ROS service results. With no numeric actuating input, SAFE-014 is not applicable and the gate reports CL2;
passing this package is not a claim of CL3 or physical safety.

## Pilot and registry

The registry names `RosDriver` and the Flatland exemplar. All five pilot packages pass independent strict collection,
with current stable digests and null human signatures:

| Package | Narrow scope | Model review |
|---|---|---|
| `gh.avidbots/flatland` | ROS 1 simulated clock and pause/resume | corrected paused-clock behavior and deployed fake fidelity |
| `gh.klintan/ros2_usb_camera` | ROS 2 camera frame metadata, hardware R0 | corrected node versus container namespace prose |
| `gh.universalrobots/universal_robots_ros2_driver` | ROS 2 dashboard stop/program state, hardware R2 | separated a deployment assumption from a Fact and corrected latch wording |
| `gh.kinovarobotics/ros_kortex` | ROS 1 Stop/ApplyEmergencyStop acknowledgements, hardware R2 | accepted source contract; added native-estop failure/malformed-output cases |
| `gh.ubi-agni/mujoco_ros_pkgs` | ROS 1 continuous-run pause and paused flag | disclosed pending manual steps and corrected stop-state/fidelity claims |

Four of five packages needed source, fidelity or behavior corrections before acceptance. This is the observed pilot
review result, not a population error estimate. Author guidance now explicitly addresses those failure modes before
any larger wave: callback side effects and queues, namespaces versus assumptions, recording-fake timing, snapshots
from silent topics, extension-read latching, and negative native-estop replies. Every pilot package was independently
read, exceeding the five-percent audit requirement.

The first two-card runner reported two outside writes: the parent's task-card schema enum update and its matching
availability test. The author logs and preserved parent write record account for both; there were no unexplained
agent writes. The second two-card run had no outside writes. All four agents exited successfully, without timeouts.
Together with the bootstrap exemplar these are five distinct DeepSeek author runs. The ten projected MCP capability
tools range below the 2,048-byte limit; the largest driver-owned tool is 617 bytes. Package hashes stayed unchanged
while measurement ran.

After the final registry refresh there are 596 completed packages (581 pass, 11 blocked, four skip-proposed), 188
remaining dispatchable ROS cards, three recon cards and 62 other helper-blocked cards. No remaining ROS wave was run
as part of this pilot.

## Found, not fixed

- The family does not yet expose a live WebSocket backend for simulated-mode packages. Its two simulator pilot
  packages serve recording fakes; they do not run the upstream simulator.
- Native ROS action goals, feedback, result tracking and cancellation are outside this helper. Canceling an action,
  sending zero velocity, or shutting down a node is not inferred to be an acknowledged emergency stop.
- No authentication configuration, QoS configuration, protocol compression/fragments, automatic reconnect or command
  replay is implemented. Deployment endpoint remapping and real ROS graph compatibility need separate validation.
- ID-less topic messages establish receive-time freshness only, not the age of a latched source measurement.
- `max_message_bytes` rejects decoded oversized frames after the WebSocket library receives them; it is not a
  pre-allocation WebSocket memory cap.
- The pre-existing `thorlabs_mcm3000` PDF citation warning remains unaccepted and awaits a human source check.

## Result

Final validation on 2026-11-02:

- All five ROS pilot packages pass independent `collect.py --strict`, without citation, limit-source, stale-digest or
  untrusted-result warnings. Their 47 repository tests include the gate calls. Every actual package lock remains
  model-authored and unsigned. All five report SAFE014_NOT_APPLICABLE/CL2 because they expose no numeric actuating input.
- The final full collection covers 581 passing packages: all 581 gates pass and every stored digest is current. 580
  packages have no strict warning; the one unchanged `thorlabs_mcm3000` PDF citation warning remains unaccepted. Thus
  this is a successful regression check, not an entirely warning-free strict sweep.
- Focused ROS tests: 74 passed after the final SDK change. Adapter/CLI tests: 46 passed. The earlier complete SDK run
  completed 2,187 tests with four skips and no failures; after the final action-only regression was added, the entire SDK suite passed
  again inside the clean export.
- `build_registry.py --check --jobs 8`: zero generated files differ. `validate.py --no-corpus`: zero errors. The original
  pilot check remains 20/20 passed. The registry and OpenAI4S integration suites pass inside the clean export.
- A real local WebSocket handshake exercised service success/failure, a topic observation and concurrent stop/unknown
  outcome against a rosbridge-shaped loopback peer. This was not a ROS node or hardware test.
- Ten projected capability tools measured with G8's canonical driver-owned size formula are within 2,048 bytes; the
  maximum is 617 bytes. Measurement left every package file unchanged.
- `tools/oss_export_check.py`: PASS on a fresh export of 13,316 tracked files, including data/generator checks, spec
  doctests, the SDK and registry suites, site build/freshness, the thermostat, all five exemplar gates and OpenAI4S
  integration. Static export checks also pass after the closing documentation update.
- The changelog index is regenerated and checked. PLAYBOOK, WAVES, the private runbook and the private handoff pointer
  carry the current counts and scope.

No real ROS graph, upstream simulator process, device run, human signature or publication was performed. The 188
remaining ROS cards were not dispatched in this pilot.
