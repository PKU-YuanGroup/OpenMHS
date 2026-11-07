OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# ROS drivers through rosbridge

`RosDriver` is a configuration-only driver over ROS 1 or ROS 2 topics, services and explicit action profiles. It does not import ROS, start a node,
launch a simulator, or discover a device graph. The operator runs the upstream nodes and rosbridge separately. The
helper speaks the [rosbridge JSON protocol](https://github.com/RobotWebTools/rosbridge_suite/blob/ros2/ROSBRIDGE_PROTOCOL.md)
over an injected transport, or an optional WebSocket client. Parameters are explicit service bindings: ROS parameter
operations are not rosbridge opcodes, and ROS 1 rosapi and ROS 2 node services have different contracts.

For camera and depth output, use the complete bounded [local image artifact path](image-artifacts.md).
That guide specifies fixed Image/CompressedImage subscriptions, supported sample encodings, explicit store activation,
independent message/pixel/artifact bounds and MCP retrieval. Metadata-only readings do not provide image capture.

## A driver declaration

Set `ros_version = 1` or `2`, the usual `device_id`, `device_kind`, `mode` and `risk`, and `backends =
{"fake": ".fake:FakeDevice"}`. A ROS interface needs no Python `native` class; do not invent one for a C++ node.
The gate checks the declared wire interfaces against the pinned clone instead.

The hardware endpoint is `endpoint = "ws://host:9090"`, overridable by `options={"endpoint": ...}`. There is no default
destination. A fake or offline sim backend must return its own transport and cannot fall back to the hardware endpoint.
A simulated driver can use the explicit live simulation configuration below. Creating
the declaration, reference or bridge does not open a connection. `timeout_s` defaults to 2 seconds and
`max_message_bytes` to 1,048,576. These are client execution bounds, not sourced device limits.

| Declaration | Binding |
|---|---|
| `reads[field]` | `topic`, `type`, optional `path` (default `$`), `timeout_ms`; or a service binding plus `path` |
| `commands[capability]`, topic observation | `topic`, `type`, `operation: "subscribe"`, `path`, optional `result` |
| `commands[capability]`, effectful service | `service`, `type`, required `success`, optional `request`, `args`, `result`, `timeout_ms` |
| `commands[capability]`, service observation | Same service binding with `operation: "read"`; application success predicate optional |
| `commands[capability]`, publication | `topic`, `type`, `operation: "publish"`, optional `message`, `args`, `result` |
| `commands[capability]`, publication then step | A publication plus `then: {"step": <service call>, "observe": <read>}` (`observe` optional); see "Publish, then step" |
| `commands[capability]`, action | `action`, `type`, `profile`, required application `success`, optional `request`, `args`, `result`, `feedback`, `timeout_ms` |
| `writes[field]` | Service binding with an application `success` predicate; `args` reads `input.value` |
| `safety_bindings.estop`, `.safe_state` | Fixed, input-free service or action binding with an application `success` predicate |
| `safety_bindings.reset` | Fixed service binding with an application `success` predicate; action reset is unsupported |
| `safety_bindings.interlocks[]` | Read binding, `id`, `closed_when`, optional `description`, `blocks`, `source`, `reset_exempt` |

All bindings carry `source_ref: "path/in/clone:LINE"` (or a bounded line range). The cited text must show the endpoint
and message/service type. If the type is declared elsewhere, add `type_ref`. If a node declares a relative or private
name, use `source_name` to name that exact upstream token and configure its resolved absolute endpoint. The gate accepts
only the same endpoint or a namespace-qualified suffix; it does not prove the operator's remapping or ROS graph.

`args` and `result` use the SDK's `FieldMapping` grammar. `args` maps `input.<field>` to request/message fields; dotted
target names set nested ROS message fields. These mapped values overlay the literal `request` or `message` object.
`result` maps from the returned service `values` or selected topic value, for example
`{"map": {"state": "output.$"}}`. Input limits remain `Field`/`Limit` or `Action` declarations enforced by the server.

Every driver needs a capability, including an observational sensor. A sensor can expose a read-only resource and an
extension capability with `operation: "subscribe"` for the same topic; neither publishes a command. Its `Action`
declares the output schema, and its `RESULT.json` requests the extension if no catalogue class fits.

One package can serve outputs of different resource kinds through one rosbridge transport: declare
`extra_resources = {"pointcloud": {"kind": "sensor.depth"}}` and bind the command to it with
`actions["cap.sensing.point_cloud.v1"] = Action(resource="pointcloud")`, while images stay on the main
`sensor.camera` resource. The bridge routes each command to its declared resource and refuses a call naming another
one (`MHS.CAPABILITY.NOT_BOUND`); an extra resource reads as `{}` without a transport request. Do not write a
`resource` key into a command map: routing comes from the declared contract, and a disagreeing key is a definition
problem. One latch and one close cover every resource; independent subscriptions on different resources are not a
synchronized pair. The model and the gate rules are in [driver-authoring.md](driver-authoring.md) ("Package
composition"); `MHS/drivers/robots/realsenseai__realsense-ros` is the reference package.

An action-only driver may leave `parameters` and `reads` empty. Its declared main resource then reads as `{}`
without a transport request, so the stock server can snapshot it before and after commands. This empty state does
not describe the simulator or prove an action's physical effect. Do not add an automatic resource read from a topic
that stops publishing after the action: Flatland emits no new `/clock` sample while paused. Its clock remains an
explicit observation capability, which may time out while paused; the pause receipt uses the acknowledged service
and an empty resource snapshot.

## Success and stopping

Service transport success (`service_response.result`) is distinct from application success. For a service returning a
boolean, use `success={"path": "success", "equals": True}`. An acknowledged `std_srvs/Empty` service can use
`success={"path": "$", "equals": {}}`. When the field to compare is one element of a list (ros2_control's
`list_controllers` answers `controller[]` in load order), select the element by the values of its fields:
`success={"path": "controller", "where": {"name": "joint_trajectory_controller"}, "field": "state",
"equals": "inactive"}` passes only when the value at `path` is a list, exactly one of its elements is an object whose
`where` keys (1 to 4 plain field names with JSON scalar values) all equal their values, and that element's `field`
equals `equals`; no element, several, a value that is not a list or a missing field fails (both for service answers and
action results). When several named elements must all hold that same field value, `where` may instead be a list of
2 to 4 such selector objects, for example `[{"name": "arm_controller"}, {"name": "gripper_controller"}]`. Each
selector must match exactly one element, the matched elements must be distinct, and each selected element's `field`
must equal `equals`. One selector stays an object, so a one-element list is refused, as are five or more selectors,
an empty selector, a repeated selector and two selectors that match the same element. List order does not matter.
Compare the actual upstream response contract; never ignore failure codes,
missing values or rejected authentication. Configurations that need credentials do not gain permission from this helper.
Trace the callback into the upstream implementation before describing its resulting state. A pause flag can disable
continuous running while queued or external manual steps still advance physics. Keep namespace/remapping assumptions
outside upstream Facts, and distinguish a component container's namespace from an explicit node namespace.
An effectful service command requires the application predicate. Use `operation: "read"` only for an upstream service
whose callback is observational; that declaration needs source review and does not make an effectful callback safe.

Publishing only confirms that the client sent a message. Its raw output is `{"published": True, "confirmed": False}`;
it does not establish execution, target attainment or stopping. Do not turn this into a completed-motion claim. Native
actions use the separate lifecycle below. Action cancellation, zero-velocity
publication and node shutdown are not accepted as acknowledged stop bindings.

The server owns limits, interlocks and the persistent latch. ROS stop bindings must call a source-backed
upstream stop service or fixed stop action, with the resulting state described in `safe_state`. `Action(safe_state=True)` declares an
input-free, acknowledged service or action command allowed during the latch and independent of the ordinary command queue.
The driver derives this permission from the Action; a raw command-map flag cannot grant it. Normal safe-state
invocation does not itself engage the e-stop latch. The server does not trust an extension capability's read verb as
a latch exemption; resource reads and catalogue-confirmed read classes retain their existing exemptions. An e-stop fences queued
actuating sends and interrupts pending ordinary requests. A timeout or disconnect after sending a request gives an
unknown outcome; the helper does not retry an uncertain command.

A software latch alone does not prove that an external ROS controller stopped, including in a simulated deployment
or recording fake. If a profile exposes a publication, effectful service/action, write or native reset without an
acknowledged stop binding or declared safe-state Action, its safety status remains unconfirmed. A stock e-stop then
fails with `MHS.SAFETY.SAFE_STATE_UNREACHED` while keeping the latch engaged. A profile containing only topic/service
observations retains software-latch behavior. A safe-state Action without a separate estop binding uses the same
current stop proof; later native work, pending work, connection failure or close prevents a stale success claim.

One e-stop does not send an identical stop request again once it was confirmed successful (CORE-074). Two bindings are
identical when they call the same service or action with the same type, profile, literal request, success predicate
and timeout; a binding with another timeout sends its own request. A safe-state Action whose request the e-stop's
`safety_bindings.estop` or `.safe_state` binding, or an earlier safe-state Action of the same e-stop, already sent and
saw confirmed successful is answered from that request's response, which the Action still maps and checks against its
own output contract; it is not sent again. After any other outcome the Action sends its own request at once: the
earlier request failed, timed out or was not confirmed (a repeated stop is harmless; the safe-state path is never lost
within an e-stop). A request still in flight is awaited until the Action's budget is down to its own request's timeout
or to half, whichever is less; if it has not succeeded by then, the Action sends its own request with the rest.
Identical `estop` and `safe_state` bindings are one request once the first succeeded. The bridge's own stop never
consults the ledger: should a safe-state Action ever send the identical request before it (by winning the safety lane
first), the request goes out twice; a stop is never lost. Native work after the request (an interrupted goal's terminal
result) makes a fresh stop due, as before, and a client's own call of the Action is always sent. Only the SDK's own
call path takes part: a package that overrides `call` or `make_bridge` is served as before. The e-stop receipt lists
the Actions that shared a request in `x-vendor.shared_stop_requests`. A stop that must never arrive twice (a LAND that
re-enables motors) is still not a stop: a failed or late first request, the post-terminal stop and the retry may send
it again.

Every `RosDriver` hardware backend, including R0 and human-authored packages, requires a schema-valid `driver.lock.json`
with a human `reviewed_by` entry of scope `hardware` before its backend factory or WebSocket can run. A model must keep
this field null. The normal adapter requirements (`allow_hardware=True`, persistent `state_dir`) still apply. A signed
lock is a local review record, not cryptographic attestation or a hardware-safety certification.

## Publish, then step

Some nodes apply a published command only when a separate service advances the world: a simulator whose controller
runs synchronized (Webots `--synchronize`) or a Gym-style bridge whose step service runs one simulation step. A
publication alone then shows nothing, and a command that binds only the topic has no observable effect (conformance
test `TCAP-003`). A publication command may therefore add `then`:

```python
commands = {"x-cap.owner.act.v1": {
    "topic": "/joint_actuators/value", "type": "gym_env/ActuatorMessage", "operation": "publish",
    "source_ref": "src/node.cpp:258", "type_ref": "src/node.cpp:17",
    "message": {"actions": [0.0] * 9}, "args": {"actions": {"from": "input.actions"}}, "timeout_ms": 5000,
    "then": {
        "step": {"service": "/webots/step", "type": "gym_env/StepEnv", "request": {},
                 "success": {"path": "$", "equals": {}}, "source_ref": "src/node.cpp:253",
                 "type_ref": "src/node.cpp:20"},
        "observe": {"topic": "/joint_sensors/value", "type": "gym_env/SensorMessage", "path": "observations",
                    "source_ref": "src/node.cpp:259", "type_ref": "src/node.cpp:16"},
    },
    "result": {"map": {"stepped": "output.stepped", "observations": "output.observation"}},
}}
```

The bridge publishes, then calls `step` once, then (when declared) takes `observe`: a fresh topic sample on a new
subscription opened after the step was acknowledged, or an observational service (`operation: "read"`). The raw output
is `{"published": true, "confirmed": false, "step": <the step's response values>, "stepped": true, "observation":
<the observed value at its path>}`, which `result` maps. `step` is an effectful service call with a literal `request`
and the required application `success` predicate; it takes no `args` (the command's input belongs to the publication).
Neither stage names a `resource` or carries `safe_state`, `then`, `image`, `point_cloud` or its own `result` (the
command's `result` maps every stage); each stage cites its own `source_ref` (and `type_ref`), and gate G7 checks it
and allows exactly its wire operations. The command's `timeout_ms` (default `timeout_s`) bounds the whole sequence; a
stage's own `timeout_ms` narrows its part.

The step is sent under the command's wire epoch: an e-stop, a cancellation or an expired budget after the publication
keeps it from being sent. Because the publication cannot be recalled and is never acknowledged, the bridge reports
every failure after it (a refused, failed, unanswered or interrupted step, no sample in time, a missing observation
path, a `result` that cannot be mapped) as an **unknown** outcome (`MHS.OUTCOME.UNKNOWN`, `details.stage` `step`,
`observe` or `result`, `details.stepped`), never a failure that invites a blind retry: the node may hold the published
command, and an increment applied twice is not the same command. Nothing is retried. A `result` path whose first field
the raw output never carries (`output.observation` without `observe`, a misspelled stage) is refused when the bridge
is configured. The server's strict output-contract check runs after the bridge returns: an output that violates the
action's `output_schema` gives a failed receipt (`MHS.CAPABILITY.OUTPUT_INVALID`), as for every effectful command
whose native call ran. A step that was sent and not settled is retained like any effectful service call: it fences
further effectful commands until its late response, a fresh successful stop and an explicit reset (see "Action
lifecycle"). While it stays unanswered, a stop reports the safe state unreached. A driver whose only stop is a declared
safe-state Action cannot finish that reset on the connection even after the late response, because the reset
re-confirms through a `safety_bindings` stop; the latch then stays (a known limitation that fails safe). Whether a live
node publishes a sample after its step's reply depends on that node; when none arrives in time the receipt is unknown,
not completed. The composition does not make the publication a stop: a package still
needs an acknowledged stop or safe-state action.

The bridge sends the publication before the step, but they reach the node on different ROS connections (rosbridge's
publisher of the topic and its service client), so the order in which the node runs their callbacks is not guaranteed,
and a subscriber that connects to the bridge's newly advertised publisher after the first message misses it. A
completed receipt (`stepped` and an observation) therefore does not prove that the node applied the publication before
the step; say so in the package's fidelity gaps and action description.

## Sensed-confirmation stop (simulated devices only)

A request that a simulated device acknowledges (a LAND, a mode switch, a zero velocity, a motor cut) is not a stop by
itself. Since the user's decision of 2026-11-05 a `mode = "simulated"` `RosDriver` whose only stop is such a request
may declare `safety_bindings["sensed_stop"]` (SAFE-049, CORE-088): the e-stop sends the request and is achieved only
when a confirming state is read from fresh samples within a bound (producer-stamped, or arrival time from a cited volatile publisher when the producer does not stamp). Real hardware, real MAVLink
vehicles included, never may: the model, gate G3 (`SENSED_STOP_CARD` for a card that is not simulated,
`SENSED_SERVED` for a served manifest that is not simulated or does not publish the confirmation), the bridge (only
`RosDriver` passes `device_mode="simulated"`; a raw adapter file is refused) and `MHSServer` start-up (every mode,
`sensed_stop_not_simulated`) all refuse it elsewhere. The bridge's `device_mode` can only refuse: a confirmation
commits a safe state only on a `RosBridge` that the endpoint bound to the mode it serves (`MHSServer` binds it at
start-up, or on first use of a late device, when the served manifest is `simulated` and declares the confirmation, and
only on the SDK's own route: a `RosDriver` that overrides none of `call`, `make_bridge`, `inner`, `estop`,
`safety_status`, `_run_safe_state`, and whose instance builds no bridge of its own; G3 `SENSED_ROUTE` otherwise). An
unbound bridge, such as one a package's own Driver builds with `device_mode="simulated"`, still sends the request but
never confirms (`not_simulated`).

```python
safety_bindings = {"sensed_stop": {
    "request": [  # 1-3 fixed steps, sent in order on the safety lane; each idempotent
        {"service": "/land", "type": "std_srvs/SetBool", "request": {"data": True},
         "success": {"path": "success", "equals": True}, "timeout_ms": 1000,
         "source_ref": "src/base.cpp:32", "type_ref": "src/base.cpp:12"}],
    "sources": {  # 1-3 topics. Stamp sources use header.stamp; a headerless type needs freshness "arrival"
        "state": {"topic": "/mavros/state", "type": "mavros_msgs/State", "source_ref": "src/base.cpp:19-20",
                  "fill_refs": {"armed": "src/base.cpp:167"}}},
        # a ROS 2 source also declares its publisher's history (see Counting below), e.g.
        # "history": {"durability": "volatile", "ref": "src/node.cpp:40"}
    "predicate": [  # every term must hold: equals, range, abs_max, norm_max, span_max (over the window)
        {"source": "state", "path": "armed", "equals": False},
        {"source": "pose", "path": "pose.position.z", "name": "landed_z", "unit": "m",
         "range": {"max": Limit.operator_required("no landed band in the clone")}}],
    "consecutive": 3, "min_span_ms": 200, "max_gap_ms": 500, "confirm_within_ms": 1500,
    "description": "landed and disarmed, sensed in three consecutive fresh samples within the bound"}}
```

- **Request steps** are services with their success predicate or fixed topic publications (no action goals, no
  mapped arguments). They go out on the safety lane: not fenced by the latch or the e-stop epoch, not refused by
  unresolved ordinary goals, never native activity. Every step is attempted; its outcome is recorded (`succeeded`,
  `refused`, `unknown`, `published`, `not_sent`) and decides nothing, but at least one must have been transmitted.
  Each step must be idempotent: the background retry and every later e-stop send it again (a review obligation;
  the package tests repeat the e-stop).
- **Sources** are topic subscriptions opened after the last step, never a request topic or a state echo of the
  request handler. Every field a term reads needs a `fill_refs` line (where the producer assigns it, where the
  clone's own code reads it from that topic, or a vendor document that states it); gate G7 checks that the line
  exists and shows the field's name. Optional `throttle_ms` becomes rosbridge's `throttle_rate`.
- **Replay** (verification F1 of phase 3): a new subscription can receive samples its publisher sent before it
  existed, and those never count. On ROS 1 the bridge has no proven offset between the producer clock and its wall
  clock, so a producer stamp is not a freshness proof: every ROS 1 stamp sample is discarded and does not refresh
  counted freshness, including a stamp one second ahead, a ROS simulation clock, a delayed latch, a frame already in
  a client buffer, and a sample from a transport that cannot report its buffer. An empty queue, a socket poll, a
  client library buffer, a continuation flag, and a fixed lead are not that proof. A
  ROS 1 source declares no `history`. On ROS 2 a transient-local publisher replays up to its history
  depth, so every ROS 2 source declares its publisher's `history`: `{"durability": "volatile", "ref": "path:LINE"}` or
  `{"durability": "transient_local", "depth": N, "ref": "path:LINE"}`, citing the line that creates the publisher with
  its QoS (gate G7 `ROS_HISTORY_NOT_SHOWN` unless the line shows the transient-local durability and the depth, or
  creates the publisher without one, or says volatile; a word in a comment shows nothing, and a volatile publisher
  whose QoS is a variable the cited lines do not define shows nothing either), or `{"operator_required": reason}` when the clone does not
  show it. The operator states an operator_required history for a live simulation in
  `simulation_deployment["estop_confirmation"]["history"] = {source: {"durability": ...}}`, the fake backend reads a
  placeholder from the fixture's `history` member, and either may only raise a cited replay; a live driver with an
  unstated one does not construct. The bridge discards that many samples (at least one) of each subscription, by
  arrival ordinal numbered before its ring drops any; the newest stamp among them is the baseline a counted sample
  must exceed. The declared history is the bound the bridge trusts: understating it lets the replay count, which is
  why it is cited and checked.
- **Counting** (`mhs.bridge.ros_sensed`): after the replay, a stamp source's producer stamps (ROS 1 `secs`/`nsecs`,
  ROS 2 `sec`/`nanosec`) must strictly increase; a repeated stamp, an arrival gap above
  `max_gap_ms` measured from the newest counted sample, a lost sample or a failing per-sample term restarts the count,
  and a discarded replay does not advance that arrival; a missing, zero or decreasing stamp,
  or a missing, non-numeric or mistyped field ends the attempt. A source with `freshness: "arrival"` (ROS 2 only)
  has no `stamp_path`. It requires `history: {"durability": "volatile", "ref": "path:LINE"}` and `min_interval_ms`
  (an integer from 1 to 1000). The first sample is discarded; a later sample closer than `min_interval_ms` restarts
  the count; `min_span_ms` is arrival time. Transient-local history and ROS 1 are refused: a replay spaced at least
  `min_interval_ms` apart cannot be told from live samples without a stamp. Headerless types are allowed only with
  arrival freshness. A source confirms when its last `consecutive` samples
  hold every term (window terms over the window), span `min_span_ms` and the newest arrived within
  `max_gap_ms`; the stop is committed only when every source confirms before `confirm_within_ms` after the first
  transmission, with no native activity, new e-stop epoch, disconnect or close in between. When the declaration names
  an exclusion on a request topic, the commit also needs a passive sample on that subscription (every watched field a
  finite zero), observed after it opened and still within `max_gap_ms` at the commit. Silence, a subscription error,
  a sample whose watched fields are not all zero, and a sample the exclusion ring drops each refuse it
  (`not_confirmed`). A dropped sample was not inspected, so the tail that remains is not a passive command. The exclusion is not a
  confirmation source. `confirm_within_ms` must
  hold `consecutive` samples spaced by `min_interval_ms`.
- **Outcomes**: confirmed gives a `completed` e-stop with `x-vendor.sensed_confirmation` (request outcomes, samples,
  first and last stamps per source, elapsed time). Otherwise the e-stop is `failed` `SAFE_STATE_UNREACHED`
  (`bridge_reports_unsafe`, or `timeout` when the budget ended first) with `details.sensed.reason`
  (`request_not_sent`, `sensed_missing`, `sensed_stale`, `sensed_invalid`, `not_confirmed`, `superseded`,
  `not_simulated`); the latch
  holds and the background retry sends the request again and confirms on new subscriptions. A reset re-confirms
  read-only and is refused while the sensed state does not hold. A stop that only a restart undoes (a Crazyflie
  motor cut) also declares `estop_terminal`. Both reports come only from the SDK's own ROS route.
- **Thresholds** (every number of a term) are `Limit`s: cited (`vendor_doc`/`upstream_code`, G4 shows the number)
  or `Limit.operator_required(reason)`. A live deployment fills them, narrow-only against a cited value, in
  `simulation_deployment["estop_confirmation"] = {"thresholds": {name: value}, "confirm_within_ms": ...,
  "max_gap_ms": ..., "min_span_ms": ..., "consecutive": ...}` (a `range` side is `name.min` or `name.max`); a live
  driver with an unfilled one does not construct. The fake backend reads placeholders from the package's
  `fixtures/estop-confirmation.json`, and nothing else does. `consecutive` (at least 2), `min_span_ms`,
  `max_gap_ms`, `confirm_within_ms`, `throttle_ms` and the step timeouts are client execution bounds: a wrong
  value can only withhold the confirmation, so they need no source; set the class values for the fake and the
  deployment's for its simulation rate. `estop_latency_ms` must cover the step timeouts plus `confirm_within_ms`;
  the live model recomputes it from the deployment.
- **The fake** is a state machine: the device moves before the request, the request starts a transition that
  reaches the safe state after a few ticks, and every subscription answers stamped samples whose first is the state
  before the request. Package tests switch off the transition, silence the stream, freeze the stamps and null a
  field, each expecting `SAFE_STATE_UNREACHED` with the latch held. Gate G6 adds its own filters on the transport
  (withheld samples, a repeated stamp, a nulled field; `SENSED_FAIL_OPEN` if the e-stop then completes).
- **Honest limit**: the SDK cannot prove that a ROS graph is simulated. MAVROS and cflib stacks drive real vehicles
  with another endpoint; such a package says so in its facts and gaps, and the real path is out of scope.

## Recording fake and verification

Subclass `mhs.bridge.ros_transport.RecordingRosTransport` in the package's `fake.py`. Its `handler(message)` returns a
response/event or list of events; `feed(message)` injects an event; `sent` records outbound JSON. Alternatively provide
strict `exchanges=[{"send": {...}, "recv": {...}}]` and call `assert_complete()`. A response without an id inherits the
request id. No ROS installation, WebSocket library or hardware is used by this fake.

The fake must model the upstream endpoints, response shapes and negative cases. Mark invented state values as
placeholders. Add repository-specific cases for failed services and refused application results; cover limits and
stopping when exposed. Gate G7 checks endpoint/type citations and recorded operations, not response semantics or the
physical effect of a stop. A passing fake gate remains `contract_checked`.

The optional live transport uses `websocket-client` (`openmhs[ros]`). It supports text JSON with ws/wss URLs without
embedded credentials, query strings, redirects or reconnect/replay. Authentication, QoS configuration, compression
and hosting ROS action servers are outside this helper. Topic observations use a new
subscription rather than an old cached value. Explicit event IDs must match the active subscription; an ID-less event
cannot prove which subscription originally caused it, nor does arrival prove the producer's sample age. The message
limit is checked after the WebSocket library receives a complete frame, so it is not a pre-allocation memory bound.
Live ROS compatibility and hardware behavior require separate testing.

The live transport reconstructs rosbridge text `fragment` messages in per-message wire order. Both each frame and
the completed JSON must fit `max_message_bytes`; all retained partial data together share that same UTF-8 byte budget.
At most eight incomplete IDs, 256 UTF-8 bytes per ID and 1024 nonempty parts per message are accepted. The first part
starts a fixed `timeout_s` assembly deadline; the bridge's short receive-slice timeouts preserve partial state and
never extend that deadline. Duplicate, conflicting, out-of-order, expired or malformed fragments close the connection
and clear pending state. IDs may be reused only after completion. Unfragmented responses and other valid fragment IDs
may interleave; normal command deadlines, subscription identity checks and protective publication checks still apply.
Nested fragmentation, PNG and binary frames remain unsupported. These bounds are client policy, not physical limits
or a pre-allocation bound on the WebSocket library. The protocol is described in the
[pinned rosbridge specification](https://github.com/RobotWebTools/rosbridge_suite/blob/6bc3fa46108aad223145e30ffa0c97a72a3a7782/ROSBRIDGE_PROTOCOL.md#32-fragmentation--fragment--experimental).

## Action lifecycle

An action binding belongs in `commands`, or as a fixed stop in `safety_bindings.estop`/`.safe_state`, and explicitly selects `profile="ros1-actionlib"` with
`type="package/NameAction"`, or `profile="ros2-native"` with `type="package/action/Name"`. The profile must match
`ros_version`. Both use `action="/resolved/name"`, the usual pinned `source_ref`/`type_ref`/`source_name`, `request` for
fixed goal fields and `args` for mapped inputs. `result` maps the native result object. A `success={"path": ..., "equals": ...}`
predicate is required in addition to a successful native terminal status. Transport success, feedback, a status topic,
goal publication or accepted cancellation alone never completes an action.

ROS 1 uses the generated goal/cancel/status/result/feedback topics and wrapper types derived from the cited action.
ROS 2 uses rosbridge's native `send_action_goal`, `action_result` and `cancel_action_goal` operations; the outgoing
protocol field is `action_type`. The status enums differ between ROS versions. G7 checks the declared action and its
generated wire types, and refuses cancellation without an exact goal sent on that transport. ROS 1 cancellation also
uses a zero timestamp to avoid cancelling unrelated goals by time.

Declare long-running/cancellable behavior and `max_duration_ms` in the capability's `Action`. The action lifetime uses
the server execution budget; `timeout_s` bounds individual wire operations. An optional binding `timeout_ms` narrows
execution further. `feedback=True` retains only the latest matching feedback; it does not extend the deadline or establish
completion. Native goal identifiers are unique per goal; ROS 2's wire ID is connection-local correlation, not a durable
ROS UUID or a way to reconcile after reconnection.

Ordinary cancellation requests the exact goal's cancellation and independently confirms the declared safe state. An e-stop
fences sends and invokes its separate acknowledged stop service or action before ordinary action cancellation. A cancelled receipt requires
both terminal cancellation and a fresh safe-state acknowledgement obtained after that terminal. The initial stop
has an independent bounded admission path, but cannot report achieved while a pending callback might re-arm the device. A goal that wins the race may instead complete if its successful
terminal result arrived within the execution budget. Disconnects, malformed terminal data, missing confirmation and late
results produce an unknown outcome, with no retry or replay.

An unknown transmitted goal retains bounded correlation state on the same connection. It prevents subsequent mutating
commands, writes and resume calls. Observations and declared safe-state stops remain available, subject to the bounded safety-goal ownership below. A late trustworthy
terminal result does not rewrite the unknown receipt; an explicit safety reset must also confirm the independent safe
state before releasing the retained goal. A disconnected or contradictory goal cannot be cleared by reset. Restarting a
process is not native goal reconciliation and must not be used to resume an unresolved deployment.

Effectful service calls (including a configured native reset) also retain their request ID after an uncertain
transmission outcome. A correlated, valid protocol-success service response proves that callback returned; an
application rejection still proves callback settlement, but not successful actuation. Malformed, mismatched,
disconnected, or protocol-failure responses do not clear uncertainty. Retained calls fence further effectful
commands, writes and reset until a late trustworthy response, a fresh successful stop, and explicit reset.
Observational services declared `operation: "read"` do not get an effectful callback exemption by inference.

Safety acknowledgement is tied to the local stop epoch and observed native activity. New effectful service/goal
registration and sends, cancellation sends, and terminal transitions invalidate the prior acknowledgement.
A stop or declared safe-state action still dispatches while callbacks are pending, but reports unachieved
(or a failed safe-state action) until all tracked callbacks have settled without changing during that stop.
The bounded interruption budget includes the fresh post-terminal stop; insufficient time keeps the original
outcome unknown. Reconnect, endpoint replacement or process restart is not evidence that an earlier remote
callback terminated. A deployment must reconcile that native work externally before resuming.

These checks cover callbacks correlated by this helper and the source-reviewed stop contract. They do not
sense physical quiescence or establish safety against unrelated ROS clients. Topic publication remains
transmission-only: its stamp is invalidated at send, but no terminal callback acknowledgement is invented.

A fixed stop action has no mapped inputs. Its literal `request`, exact action type/profile and application predicate
are source-reviewed like an ordinary action; selecting an endpoint named `stop` does not establish its safety contract.
For example, a gripper whose pinned upstream node exposes a separate empty-goal StopAction can declare:

```python
safety_bindings = {
    "estop": {
        "action": "/franka_gripper/stop",
        "profile": "ros1-actionlib",
        "type": "franka_gripper/StopAction",
        "request": {},
        "success": {"path": "success", "equals": True},
        "source_name": "stop",
        "source_ref": "franka_gripper/src/franka_gripper_node.cpp:101-107",
        "type_ref": "franka_gripper/src/franka_gripper.cpp:16",
    },
}
```

Confirm those references against the selected pin before using the declaration. A successful native StopAction means
only the source-described stop operation succeeded. It does not prove an independent physical emergency stop, force
retention, interruption of every other action, or safe handling of a suspended load. The Franka source-shaped pilot
covers all selected gripper controls; its concurrent callbacks have no actionlib preempt check. Cancellation therefore
remains uncertain until the original callback supplies a trustworthy terminal result. In particular, the helper does
not infer that StopAction interrupts homing or that reset should home or re-arm a device.

For a driver with an action stop, one bounded confirmation attempt owns the safety-action path through terminal,
output validation and freshness commit. Its lock is separate from ordinary command transactions. Ordinary action
capacity cannot consume the separate four-record safety allowance. A previously sent unresolved safety goal prevents
another action stop from preempting it; observations and service-based diagnostics remain available. A timed-out safety
goal is retained without recursively issuing cancellation or another stop, and its late result still requires fresh
confirmation plus explicit reset. An interrupted or closed client never sends a prepared-but-unsent goal after close.
An expired caller budget does not prove the native callback ended. These are controlled-peer guarantees; deployed
server scheduling, native device synchronization and stop latency require separate validation.

Abandoned safety goals with a trustworthy terminal result are retired before admitting another stop. Retirement keeps
the ordinary-command fence until explicit reset and a fresh successful stop; it does not revise the earlier unknown
receipt or evict live, erroneous or ordinary goals. Passive ROS 1 cleanup completes under the same bounded safety lane
before a new stop setup, including when reset initiates retirement. Reset releases that lane before its later native
reset service, preserving independent e-stop admission.

Retired safety goals keep at most 16 compact terminal fingerprints plus a per-bridge random identity and increasing
sequence. A recent identical terminal is harmless; a contradictory, malformed or mismatched terminal makes safety and
reset unachievable on that connection. Active and retired terminal comparison preserves JSON types: boolean success
and numeric one are not identical acknowledgements. An attributable result older than the bounded fingerprint history is also
refused because its consistency cannot be proved. Periodic old status/feedback alone is not a new terminal. This finite
history prevents completed stop records from exhausting recovery capacity without silently dropping late-result
uncertainty. A connection restart still does not reconcile native work or authorize an unresolved deployment.

Retirement rechecks terminal/error state under the receive condition after interpreting either success or failure.
A result that becomes contradictory in that interval remains owned and returns unknown; an earlier local success
flag cannot erase it. An archived-history fault keeps achievement false, ordinary mutation fenced and reset refused,
but permits another bounded protective stop after all earlier stop owners have ended with trustworthy terminals.
This supports background protection without claiming recovery. A still-active, timed-out or erroneous stop record
continues to prevent another goal from preempting that possibly running single-goal server. Failed passive retirement
also blocks later setup, even when the connection remains open. The checks are repeated at the goal transmission
boundary; close, cancellation, deadlines and connection failure still prevent dispatch.

For ROS 2 native actions, the deployed rosbridge must process goals without blocking cancel/stop traffic; configure and test
`send_action_goals_in_new_thread`. Pin the deployed rosbridge version and test its frame shapes and executor behavior.
The SDK's controlled-peer tests do not verify a particular ROS graph, its action callbacks, or real stop responsiveness.
See the [official rosbridge protocol](https://github.com/RobotWebTools/rosbridge_suite/blob/ros2/ROSBRIDGE_PROTOCOL.md)
and [ROS action semantics](https://design.ros2.org/articles/actions.html).

## Companion sources (a simulator's own stop)

Some simulator packages have no stop in their own clone: the only stop is the simulator's world control (the
Gazebo `pause_physics` service of gazebo_ros), which lives in the simulator's repository. A reviewed registry
override may then declare that repository as a **companion source** of the card (user decision of 2026-11-05):
`task.json` `companions` lists each corpus clone with its alias, its corpus-lock commit, a profile
(`ros1-noetic-gazebo11`) and version evidence that ties the package's stack to that pin; `driver.lock.json` repeats
`[{package_id, commit}]`. A package cannot add or rewrite one: gate G1 refuses a `task.json` that differs from the
registry card `MHS/registry/tasks/<track>/<dir>.json` (`CARD_EDITED`) and a `task.json` that declares companions
without a registry card to confirm them (`COMPANION_CARD`, so the gate fails closed outside the project tree), and
`MHS/registry/validate.py` refuses a `task.json` whose companions differ from the card's and a card whose companions
differ from the reviewed override.

A binding cites a companion as `companion:<alias>/<path>:<LINE>[-<END>]`. Only `safety_bindings.estop`, its read-back
`safety_bindings.safe_state` and the command of the one action declared `reenable=True` may do so (and facts, gate
G4); every other binding cites the package's clone (G7 `ROS_COMPANION_SCOPE`, `ROS_COMPANION_UNDECLARED`). A stop
that cites a companion needs a read-back that reads the stopped state, never only an acknowledgement
(G7 `ROS_COMPANION_READBACK`): a service call other than the stop whose `success` compares one state field
(`path` not `$`) with a scalar, and `state_ref` on both bindings, citing the callback that sets the state and the line
that fills the field the read-back compares. Gate G7 also checks what the read-back means (verification F2 of phase
3): the read-back is in the stop's namespace, the same simulator world (both names global, relative or private, with
equal segments before the last: `/gazebo/get_physics_properties` for `/gazebo/pause_physics`, never
`/other_world/...`); its `success` path names no acknowledgement field (`success`, `status_message`, `message`,
`result`, `ok`, `error`, `error_code`, `error_message`, `error_string`, `errmsg`, `ack`, `acknowledged`, `accepted`,
`succeeded`, and the status, done, code, sent and completed style fields `status`, `status_code`, `code`,
`return_code`, `result_code`, `done`, `is_done`, `sent`, `completed`, `complete`, `finished`, `executed`, `handled`,
`received`); and its `state_ref` line assigns the compared field from something other than a constant or the request
(`res.pause = world_->IsPaused();`, never `res.pause = true;`, `res.pause = req.pause;` or a bare field declaration).
For a stall read-back the compared field is the stall path (its own `success` only accepts each answer), and for a
list-element predicate the selected element's `field`. Whether the assigned value
is the state the simulator's step loop reads stays the reviewer's trace:

```python
_API = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp"
safety_bindings = {
    "estop": {"service": "/gazebo/pause_physics", "type": "std_srvs/Empty", "source_name": "pause_physics",
              "source_ref": _API + ":492-498", "type_ref": _API + ":494", "state_ref": _API + ":1725-1729",
              "request": {}, "success": {"path": "$", "equals": {}}, "timeout_ms": 500},
    "safe_state": {"service": "/gazebo/get_physics_properties", "type": "gazebo_msgs/GetPhysicsProperties",
                   "source_name": "get_physics_properties", "source_ref": _API + ":383-389",
                   "type_ref": _API + ":385", "state_ref": _API + ":1489",
                   "request": {}, "success": {"path": "pause", "equals": True}, "timeout_ms": 500},
}
```

The runtime is unchanged: the e-stop runs the stop and then the read-back, and any failure (no answer, a service
returning false, `pause` false because another client unpaused the world) is `MHS.SAFETY.SAFE_STATE_UNREACHED` with
the latch held and a background retry. The unpause is the declared re-enable (CORE-086); the reset only releases the
latch. Gate G1 checks that each companion clone exists, is a git checkout whose HEAD is the pin, has no modified
tracked file before or after the run, and that every version-evidence range shows its token and the profile's distro
on both sides; G2 compares the lock with the card.

**Fetched (lock) companions.** A companion at a version the corpus does not hold (a gazebo_ros release of another ROS
distro, an older Gazebo, a ros2_control release) may be a clone fetched at one pinned commit under
`work/companions/<owner>__<repo>@<first 12 hex of the commit>`, listed in `work/companions/LOCK.json` (the user's
authorisation of 2026-11-05). Its override entry adds `lock`, the LOCK.json alias (`ros-simulation__gazebo_ros_pkgs@2.5.21`):
its commit and profile must be the LOCK.json entry's, its `package_id` the one that entry's `repo_url` names, and the
card's package must be in that entry's `needed_by`; the registry copies the LOCK.json path, `repo_url`, `ref` and
licence onto the card, and `driver.lock.json` repeats `lock`. Gate G1 also refuses a fetched companion whose LOCK.json
is missing or lacks the alias or differs from the card (`COMPANION_LOCK`), whose work tree holds an untracked file
(`COMPANION_MODIFIED`) or has a write bit (`COMPANION_WRITABLE`: the fetched clones are kept `chmod -R a-w`, `.git`
excluded). `work/` is not part of the open-source tree: in an export the card still carries the pin and the gate fails
G1 (`NO_COMPANION_CLONE`, `COMPANION_LOCK`) until `tools/fetch_companions.py <driver dir>` puts the clones back, offline
first (`--from` another workspace's `work/companions` or a bundle; the network only with `--network` and a recorded
authorisation). `python3 -m mhs.driver check <dir> --companions-root DIR`, `collect.py --companions-root DIR` and
`show_refs.py --companions-root DIR` read the clones and their LOCK.json from another directory.

**A stall read-back (E1).** ROS 2 gazebo_ros has no service that reports the paused flag. The read-back may instead
confirm that a value which advances only while the world steps no longer does: `safety_bindings.safe_state` (a fixed
service call with a success predicate) adds `stall: {"path": "header.stamp", "samples": 2, "interval_ms": 250,
"unchanged": True}`. The e-stop then calls the read-back `samples` times (2 to 4), each call at least `interval_ms`
(100 to 2000) after the previous answer arrived and only while that wait and the call's own timeout still fit in the
budget; every answer must satisfy `success` and carry the same value at `path`, and that value must be a finite
number or a ROS time (`{sec, nanosec}` or `{secs, nsecs}`, integers): null, an empty value, a string, a list, a boolean
or any other object cannot show a running clock and fails closed. A change, a missing value or a value of another kind,
a failed call or a budget that cannot hold the next sample leaves the e-stop unconfirmed with the latch held;
`safe_state()` repeats the check. Gate G7 accepts a stall only on the read-back of a companion-cited stop (`ROS_STALL_SCOPE`), wants
its `state_ref` to show the stalled field (`stamp` at gazebo_ros_factory.cpp:168) and a fact that cites a companion
(the line where that value advances only while the world steps); G3 refuses a stall whose worst case (stop timeout +
`samples` x read-back timeout + (`samples` - 1) x `interval_ms`) exceeds the e-stop budget (`estop_latency_ms`, 1000 ms
when undeclared); G6 breaks the stall on purpose (a filter that advances the value on every answer) and requires the
e-stop to fail (`STALL_FAIL_OPEN`). A frozen value is also what a hung but unpaused simulator shows; say so.

```python
_FACTORY = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_factory.cpp"
estop_latency_ms = 1500  # pause 400 + 2 x 300 + 250 exceeds the default 1000 ms
safety_bindings = {
    "estop": {...},  # /pause_physics, as above
    "safe_state": {"service": "/get_model_list", "type": "gazebo_msgs/srv/GetModelList",
                   "source_name": "get_model_list", "source_ref": _FACTORY + ":139-143",
                   "type_ref": _FACTORY + ":139", "state_ref": _FACTORY + ":168", "request": {},
                   "success": {"path": "success", "equals": True},
                   "stall": {"path": "header.stamp", "samples": 2, "interval_ms": 250, "unchanged": True},
                   "timeout_ms": 300},
}
```

**A list-element read-back (E4).** A controller switch (ros2_control `switch_controller` deactivating a trajectory
controller) is confirmed by `list_controllers` with the list-element predicate above; G7 wants the read-back's
`state_ref` to show the selected `field` and every `where` key of every selector (`controller_state.name`,
`controller_state.state`). A `where` list of 2 to 4 selectors confirms several elements in that one answer (each a
distinct element, the same `field` and `equals`). Different fields per element are two read-backs, not one list.

**A fresh-sample topic read-back (E2).** gz-sim reports its paused flag only in `WorldStatistics.paused` on
`/world/<name>/stats`, and the reply of its WorldControl request is true for any request it queued, so the reply
confirms nothing. `safety_bindings.safe_state` may then be a topic subscription: `{"topic", "type", "operation":
"subscribe", "success": {"path": <one boolean flag>, "equals": true|false}, "fresh": {"after_request": True,
"discard_first": True, "consecutive": 2..5, "within_ms": 200..5000, "min_interval_ms": 10..1000}}` and the provenance
keys (no request, mapping, result or `timeout_ms`: the bound is `within_ms`, and `within_ms` must hold the discarded
sample and `consecutive` samples `min_interval_ms` apart). After the stop request returned, the e-stop opens a new
subscription (queue length 1), discards its first sample (a latched one or one in flight), and counts samples in
arrival order: a sample that arrives less than `min_interval_ms` after the previous one restarts the count (a history
replayed on subscribe arrives as one burst; a live stream arrives at its producer's rate: gz-sim throttles the stats to
10 per second), so does a sample whose flag is not `equals`, and `consecutive` samples in a row that hold the flag
confirm the stop. Silence, a sample without a boolean at the path, a lost sample or the bound leave the e-stop
unconfirmed with the latch held; `safe_state()` repeats the check without a request. Freshness is the arrival time
only: use it for one boolean world-state flag whose bridged header carries no producer stamp. A motion
standstill on an unstamped stream is a sensed stop with `freshness: "arrival"`, not this read-back. The discarded
first sample and the burst rule do not detect a replay spaced at least `min_interval_ms` apart (BL-18), and asking
rosbridge for a volatile reader is not proof because an older rosbridge ignores it. Gate G7 accepts it only on the read-back of a companion-cited stop
(`ROS_FRESH_SCOPE`) and wants a boolean `equals`, a field that the cited `state_ref` line shows and that is not an
acknowledgement (`success`, `status_message`), and a topic in the stop's namespace (`/world/<name>/stats` beside
`/world/<name>/control`, `ROS_COMPANION_READBACK`); G3 refuses a worst case (stop timeout + `within_ms`) beyond the
e-stop budget; G6 flips the flag, withholds every sample and answers each subscription only with a burst of stale
confirming samples, and requires the e-stop to fail each time (`FRESH_FAIL_OPEN`).

**Bridges the operator runs (E3).** A simulator's own transport names (gz-sim's `/world/<name>/control` service and
`/world/<name>/stats` topic) exist on the ROS graph only through a ros_gz `parameter_bridge` that the clone may not
start. `RosDriver.operator_bridges` lists what the operator must run, one `parameter_bridge` argument each, with a
citation that shows its ROS type (a companion citation is allowed here) and an optional sentence; the package never
starts them, and `REFERENCE.md` lists them under "Operator must run" (`reference.json` `safety.operator_bridges`).
G3 parses each argument as the bridge's usage text states it (`<name>@<pkg/srv/Name>` for a service,
`<name>@<pkg/msg/Name>` then `@`, `[` or `]` and a `gz.msgs`/`ignition.msgs` type for a topic); G7 wants every bridge
to serve a declared binding with the same name, type and direction (`ROS_OPERATOR_BRIDGE_UNUSED`) and its citation
to show the type (`ROS_OPERATOR_BRIDGE_REF`), and, with an E2 read-back, every companion-cited endpoint of the stop,
the read-back and the re-enable to be one of them (`ROS_OPERATOR_BRIDGE_MISSING`). Without the bridge the stop
fails closed: the service call is not answered, and the read-back sees no sample.

```python
_RUN = "companion:gz_sim/src/SimulationRunner.cc"
_BRIDGE = "companion:ros_gz/ros_gz_bridge"
estop_latency_ms = 1500  # control 400 + within_ms 600 = 1000 ms; the declared budget leaves margin for the bridge
operator_bridges = [
    {"args": "/world/default/control@ros_gz_interfaces/srv/ControlWorld", "ref": _BRIDGE + "/README.md:86"},
    {"args": "/world/default/stats@ros_gz_interfaces/msg/WorldStatistics[gz.msgs.WorldStatistics",
     "ref": _BRIDGE + "/README.md:52"},
]
safety_bindings = {
    "estop": {"service": "/world/default/control", "type": "ros_gz_interfaces/srv/ControlWorld",
              "source_name": "control", "source_ref": _RUN + ":325", "state_ref": _RUN + ":1443",
              "type_ref": _BRIDGE + "/src/service_factories/ros_gz_interfaces.cpp:43-52",
              "request": {"world_control": {"pause": True}}, "success": {"path": "success", "equals": True},
              "timeout_ms": 400},
    "safe_state": {"topic": "/world/default/stats", "type": "ros_gz_interfaces/msg/WorldStatistics",
                   "operation": "subscribe", "source_name": "stats", "source_ref": _RUN + ":807-808",
                   "type_ref": _BRIDGE + "/README.md:52", "state_ref": _RUN + ":534",
                   "success": {"path": "paused", "equals": True},
                   "fresh": {"after_request": True, "discard_first": True, "consecutive": 2, "within_ms": 600,
                             "min_interval_ms": 40}},
}
```

**Re-enabling a paused world.** An unpause re-enable must not resume a stored motion command (the orchestrator's
SAFE-042 condition): clear the stored command first where the plugin allows it (cite it; a zero Twist that the plugin
stores is unacknowledged, so say so), and where it cannot be cleared (a controller the package does not command, a
position target, a learned policy that keeps acting) offer no unpause at all, neither as the re-enable nor as an
ordinary command, and say in `safe_state` how the operator recovers outside MHS. Keep the topics that the stop silences (a paused world publishes no
odometry, no `/clock`, no model states) out of the device resource: a reset device must stay readable. A paused
world is a flag, not a measured standstill; say what still acts (callbacks that store commands, world edits, manual
steps, another client's resume) in `safe_state`, the facts and the fidelity gaps. Review checklist: REVIEW.md item 13.

## Explicit simulation deployments

The operator runs the simulator and rosbridge separately in an environment isolated from hardware. The SDK does not
launch ROS nodes or prove that a graph is simulated: an endpoint, namespace, ROS domain, `/clock` or `use_sim_time` alone
does not establish isolation. Hardware continues through the signed hardware backend.

For a `mode="simulated"` RosDriver, pass `simulation_deployment` to `mhs.adapter.load`, `load_driver` or the driver
constructor with `backend="sim"`. This named argument is separate from backend `options`. It contains exactly:

| Key | Contract |
|---|---|
| `endpoint` | The deployed rosbridge WebSocket URL, under the transport's normal URL policy. |
| `deployment_id` | One 1–64 character path segment, starting with an alphanumeric character; subsequent characters may also be `_`, `.` or `-`. |
| `fidelity` | The complete deployed contract: engine, fidelity level, determinism, timestep, pacing, reset, snapshot support and known gaps; optional clock and validation follow the device schema. |

The following shape uses operator-provided values; it supplies no invented timing or determinism:

```python
from mhs.adapter import load

server = load(
    package_directory,
    backend="sim",
    simulation_deployment={
        "endpoint": simulator_rosbridge_url,
        "deployment_id": deployment_name,
        "fidelity": measured_deployment_fidelity,
    },
)
```

Validation finishes before connection. Missing or incomplete configuration is refused; no recording fake is used as a
fallback. A configured endpoint connects lazily through the SDK's optional WebSocket transport. This runtime configuration
cannot be combined with a declared `backends["sim"]` factory, an endpoint in `options`, or a custom device ID. An injected
transport must be the bundled `WebSocketTransport` for the same URL (Recorder wrapping is supported).

The live device ID is the declared ID plus `/sim/<deployment_id>`. The original fake reference and class fidelity stay
unchanged. Configuration is copied for the lifetime of the instance; changing it requires a new instance. A live instance
cannot be exported as a fake or hardware view. An adapter file whose single bridge points to the RosDriver forwards this
configuration; raw adapter bridges and other driver families refuse it.

Current SDK verification exercises the actual loader, strict server and WebSocket transport with controlled in-memory
peers, including invalid configuration and fake/hardware refusal. It does not establish compatibility with a running ROS
deployment. Package fake gates retain `contract_checked` evidence; actual ROS simulation and hardware runs are separate.

A declared safe-state action also validates its entire mapped output against a
copied, resolved capability output schema before committing an achieved stamp.
This validation runs inside the bridge because the server's achieved_by path may
call it directly. Missing or invalid contracts and wrong/missing nested fields
refuse acknowledgement. RosDriver supplies the trusted constructor contract;
request metadata cannot grant or replace it. Direct RosBridge users declaring
safe-state commands must supply capability_schemas with output_schema entries.
