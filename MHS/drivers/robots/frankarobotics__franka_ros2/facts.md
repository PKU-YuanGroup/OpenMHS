OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.frankarobotics/franka_ros2

Every fact cites the pinned clone at commit `4acc05c01ebfcdf916ee6b3df966df0ad7b2f9ec`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used when the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Scope

The package exposes the ROS 2 interfaces of two concrete upstream nodes:

* `franka_spine_node` (`franka_spine/franka_spine_server/franka_spine_server/spine_action_server.py`)
  registers the private `~/move_absolute` `MoveAbsolute` action, the private
  `~/halt`, `~/switch_off` and `~/switch_on` services, and the private `~/position` and
  `~/state` topics. The node wraps `SpineController`, one of the card's entry
  symbols. The move input is a single linear position in metres, so the
  catalogue joint-position class (radians, joint-position array) does not fit;
  the move capability is the extension `x-cap.frankarobotics.spine_move.v1`.
* `franka_battery_node` (`franka_mobile/franka_mobile/battery_server.py`)
  publishes `sensor_msgs/BatteryState` on the private `~/battery_state` topic
  and registers the private `std_srvs/Trigger` services
  `~/stop_wireless_charging` and `~/try_start_wireless_charging`. The node
  wraps `BatteryController`, another card entry symbol.

This is a `RosDriver` with local input-domain validation and paired topic projection.
It declares no Python `native` class and does not import the clone. The card's `RosDriver`/`ros` decision is
confirmed by the upstream ROS 2 action/service/topic interface.

The node names and the empty default namespace are deployment assumptions, not
upstream facts. The configured absolute endpoints assume the launch defaults:
the nodes are named `franka_spine_node` and `franka_battery_node` in the root
namespace. A deployment that namespaces or remaps either node must expose the
same absolute endpoints; this package does not discover the ROS graph.

## Facts

| fact | source | ref |
|---|---|---|
| A failed position read republishes the last successful position with valid=false; the state sample carries validity and error details. | upstream_code | franka_spine/franka_spine_server/franka_spine_server/spine_action_server.py:146-164 |
| Cancellation waits for the blocking motion worker, then re-arms before returning the cancelled motion result. | upstream_code | franka_spine/franka_spine_server/franka_spine_server/spine_controller.py:404-434 |
| The battery node sets voltage, current, charge, capacity and design_capacity to NaN. | upstream_code | franka_mobile/franka_mobile/battery_server.py:133-138 |
| SpineActionServer constructs the ROS 2 node with the base name franka_spine_node. | upstream_code | franka_spine/franka_spine_server/franka_spine_server/spine_action_server.py:35-39 |
| The spine node registers the private MoveAbsolute action '~/move_absolute' with a ReentrantCallbackGroup. | upstream_code | franka_spine/franka_spine_server/franka_spine_server/spine_action_server.py:115-123 |
| The spine node registers private services '~/get_state', '~/get_position', '~/switch_off', '~/halt' and '~/get_parameters_spine'. | upstream_code | franka_spine/franka_spine_server/franka_spine_server/spine_action_server.py:72-113 |
| The spine node publishes SpinePosition on '~/position' and SpineState on '~/state' at 1/feedback_rate, and only while each topic has a subscriber. | upstream_code | franka_spine/franka_spine_server/franka_spine_server/spine_action_server.py:125-164 |
| The spine action server fills MoveAbsolute.Result.success from the motion result and copies stop_by and error from the same result. | upstream_code | franka_spine/franka_spine_server/franka_spine_server/spine_action_server.py:195-216 |
| SpineController.move_absolute requires the drive to be SwitchedOn before it starts motion and returns an error otherwise. | upstream_code | franka_spine/franka_spine_server/franka_spine_server/spine_controller.py:376-385 |
| SpineController.switch_off posts the REST switch-off call, invalidates the cached state and reports success only when the REST call succeeded. | upstream_code | franka_spine/franka_spine_server/franka_spine_server/spine_controller.py:307-316 |
| The spine REST client's switch_off method posts 'spine:switch-off'. | upstream_code | franka_spine/franka_spine_server/franka_spine_server/spine_api_client.py:58-60 |
| SpineController.halt posts the DS402 quick-stop, waits for SwitchedOff and then re-arms with switch-on, so a successful Halt returns the drive to SwitchedOn rather than leaving it disabled. | upstream_code | franka_spine/franka_spine_server/franka_spine_server/spine_controller.py:318-334 |
| The spine REST client has no motion:halt route; halt_motion posts 'motion:quick-stop', which enters QuickStopActive and then SwitchedOff. | upstream_code | franka_spine/franka_spine_server/franka_spine_server/spine_api_client.py:95-100 |
| Halt.srv describes the halt service as immediately halting ongoing motion and ending in SwitchedOn. | upstream_code | franka_spine/franka_spine_msgs/srv/Halt.srv:1 |
| SwitchOff.srv describes the switch-off service as transitioning to SwitchedOff and disabling motion. | upstream_code | franka_spine/franka_spine_msgs/srv/SwitchOff.srv:1 |
| The spine node registers the private SwitchOn service '~/switch_on' with the ReentrantCallbackGroup. | upstream_code | franka_spine/franka_spine_server/franka_spine_server/spine_action_server.py:90-95 |
| The switch-on callback calls SpineController.switch_on and copies its success, state and message into the SwitchOn response. | upstream_code | franka_spine/franka_spine_server/franka_spine_server/spine_action_server.py:242-248 |
| SpineController.switch_on posts the REST switch-on call, invalidates the cached state and reports success only when the REST call succeeded. | upstream_code | franka_spine/franka_spine_server/franka_spine_server/spine_controller.py:296-305 |
| The spine REST client's switch_on method posts 'spine:switch-on'. | upstream_code | franka_spine/franka_spine_server/franka_spine_server/spine_api_client.py:62-64 |
| SwitchOn.srv describes the switch-on service as transitioning to SwitchedOn and enabling motion. | upstream_code | franka_spine/franka_spine_msgs/srv/SwitchOn.srv:1 |
| MoveAbsolute.action declares position in metres and velocity, acceleration and deceleration as float64 values with a strictly positive requirement. | upstream_code | franka_spine/franka_spine_msgs/action/MoveAbsolute.action:1-5 |
| MOTION_READ_TIMEOUT is 600.0 seconds: a hang guard for the blocking motion-mm:start POST, not a device motion limit; the device holds the POST until the move finishes or is quick-stopped. | upstream_code | franka_spine/franka_spine_server/franka_spine_server/spine_api_client.py:21-24 |
| UserLimitsData stores lower_limit and upper_limit with 0.0 dataclass defaults. | upstream_code | franka_spine/franka_spine_server/franka_spine_server/spine_controller.py:205-210 |
| SpineController.get_parameters reads the device parameters response and returns its lower_limit and upper_limit values. | upstream_code | franka_spine/franka_spine_server/franka_spine_server/spine_controller.py:336-352 |
| BatteryServer constructs the ROS 2 node with the base name franka_battery_node. | upstream_code | franka_mobile/franka_mobile/battery_server.py:32-36 |
| BatteryServer registers std_srvs/Trigger services '~/stop_wireless_charging' and '~/try_start_wireless_charging'; their callbacks copy the controller result's success and message. | upstream_code | franka_mobile/franka_mobile/battery_server.py:62-106 |
| BatteryServer publishes sensor_msgs/BatteryState on '~/battery_state' when enable_battery_topic is true and publish_rate is positive. | upstream_code | franka_mobile/franka_mobile/battery_server.py:75-92 |
| BatteryServer converts battery_level_rsoc to BatteryState.percentage by dividing by 100 and copies batt_pos_terminal to temperature; charging flags select the power-supply status and location. | upstream_code | franka_mobile/franka_mobile/battery_server.py:108-139 |
| BatteryController.stop_wireless_charging and try_start_wireless_charging call the battery REST API and return success with a message. | upstream_code | franka_mobile/franka_mobile/battery_controller.py:170-182 |
| The battery API client exposes 'wireless-charging:stop' and 'wireless-charging:try-start' POST routes. | upstream_code | franka_mobile/franka_mobile/battery_api_client.py:50-56 |

## Limits

The spine move has four numeric inputs: position, velocity, acceleration and
deceleration. `MoveAbsolute.action` gives the position unit (metres) and states
that the other three must be greater than zero, but the repository gives no
numeric travel range and no maximum for any of them. `GetParameters` returns
the installed spine's user limits only at runtime; `UserLimitsData`'s `0.0`
values are dataclass defaults, not device bounds. Every move input therefore
uses `Limit.operator_required`: without a `site-limits.json` overlay the
runtime refuses every move with `MHS.SAFETY.LIMITS_UNSET`. Independently, the
published input schema uses `exclusiveMinimum: 0` for velocity, acceleration and
deceleration. The same finite strictly positive check runs before direct family
calls can dispatch a goal. A permissive operator overlay cannot remove this
source-defined domain requirement; no arbitrary positive epsilon is invented.

`site-limits.example.json` is an example operator overlay, not a source of
device facts. It supplies narrow example ranges for a bench so that a
deployment can exercise the move; an operator must replace them with the
limits read from the installed spine and the site's risk assessment. The
overlay can only narrow the declared bounds.

The battery services and topic have no numeric inputs, so they declare no
`Limit`. The fake's numbers are test data.

## Safety

The device is hardware at R2: the spine is a powered linear axis on the Franka
TMR mobile manipulator, and the move action is a motion command with pinch,
collision and unexpected-contact hazards. The package is model-authored;
`driver.lock.json` keeps `reviewed_by: null`, so the ROS hardware backend is
refused until a human signs the lock. No hardware or live ROS run has been
performed.

The native e-stop binding and the input-free safe-state action are the same
acknowledged `/franka_spine_node/switch_off` service:
`x-cap.frankarobotics.spine_switch_off.v1` is `Action(safe_state=True)`, so it
remains callable during the latch and supplies the independent safe-state path
(SAFE-045). The runtime latches before the native call. Normal safe-state
invocation does not itself engage the e-stop latch.

The upstream `halt` service is exposed as
`x-cap.frankarobotics.spine_halt.v1` but is deliberately not the safe state:
its implementation posts a DS402 quick-stop, waits for `SwitchedOff`, and then
re-arms the drive to `SwitchedOn`. `switch_off` transitions the drive to
`SwitchedOff` and disables motion. The service callback acknowledges the REST
transition; it does not sense position, velocity or quiescence. The separate
physical e-stop, if fitted to the TMR, remains authoritative; the clone does not
document one, so no `estop_physical_ref` is claimed.

During an e-stop the runtime first invokes the switch-off service and then the
declared safe-state action. A running `MoveAbsolute` action is cancelled with
`cancel_action_goal`; the upstream cancel callback accepts the request and the
controller's cancel path posts the quick-stop and re-arms. An ordinary move
command is refused while the latch is engaged. Observational extension actions,
including the battery-state subscription, remain latched even though their verb
is `read`, because the server does not trust an extension's read verb as a safety
exemption.

Recovery after an e-stop is explicit. A safety reset releases the latch only:
the package declares no reset binding, so the drive stays `SwitchedOff` and a
move still fails at the device (`spine_controller.py:376-385`). The upstream's
own `~/switch_on` service is bound as `x-cap.frankarobotics.spine_switch_on.v1`
and declared with `Action(reenable=True)` as the device's re-enable
(`safety.estop.reenable`, CORE-086): the runtime refuses it with
`MHS.SAFETY.ESTOP_ENGAGED` while the latch is engaged, a completed reset names
it in `output.reenable`, and conformance test TSAFE-001 sends it after the reset
and before its recovery move. Its acknowledgement is the REST result of
`spine:switch-on`, not a sensed drive state. Re-arming inside the reset, which an
earlier review rejected, is not done; the switch-on is a separate command that a
host or operator sends after deciding to resume.

The declared re-enable is not the only command that leaves the drive
`SwitchedOn`. A successful `~/halt` (bound as `x-cap.frankarobotics.spine_halt.v1`)
also re-arms the drive with switch-on after its quick-stop
(`spine_controller.py:318-334`), and cancelling a running move does the same
(`spine_controller.py:404-434`). Both are ordinary effectful commands, so the
latch refuses them like the re-enable; after a reset, a host that sends `halt`
re-enables the drive as surely as one that sends `switch_on`. Only `switch_on` is
declared because it does nothing else.

Because the package declares a re-enable, an e-stop that lands while a move is
running is answered only after that move settled, and the stop path then runs
again (CORE-086): the cancel path's re-arm cannot outlive a confirmed stop. The
ROS bridge has its own guards as well (a goal still pending, or native activity
after a stop, leaves the safe state unconfirmed, and the background retry stops
the drive again), so the drive ended switched off before this rule too; the rule
makes the e-stop answer wait for the move. `test_safety_freshness.py` shows both:
the stop that runs after the cancel path's re-arm, and the counterfactual without
the rule. Its stock case now sends the e-stop from its own thread, because the
answer no longer comes before the cancelled move ends.

## Fidelity and fake

The fake is a ROS-free `RecordingRosTransport`, not an upstream simulator. It
normally answers each declared request synchronously with a fixed event and runs no ROS
node, physics step, wall-clock pacing, reset or snapshot/restore, so its F0
evidence is contract-only. The manifest's standard fake view reports F0,
`timestep_ms: 0`, `realtime_factor: 0`, no snapshot/restore and the standard
"transport replaced by fake backend" gap. Its action result is immediate and
does not demonstrate real stop latency; the switch-off and halt replies are
canned application results, not sensed device states. The battery percentage,
temperature, charging flag and position values are placeholders, not device
facts.

The spine resource snapshot uses the upstream's recommended `~/position` and
`~/state` topic observations rather than polling the services. Each read opens
a fresh subscription and waits for a sample; the real node publishes only while
subscribed. One complete message supplies each scalar and its validity/error
companions, so a second message cannot be paired with an earlier value. Invalid
source samples return null for `position` or `state`, with the corresponding
`position_valid`/`state_valid` false; state errors remain available. This avoids
presenting the source's retained last position as a valid current measurement. The battery state is an explicit extension observation, not an
automatic resource snapshot: it also opens a fresh subscription for its sample.

## Tags

`ros`, `ros2`, `franka`, `tmr`, `spine`, `battery`, `linear-axis`

## Private reviewer revision (not an accepted hardware package)

The optional event-controlled fake goal now holds a goal through cancellation,
quick-stops, re-arms, and only then emits its correlated terminal result. These
are manual test barriers, not timing or physical simulation. The ordering comes
from `spine_controller.py:404-434,477-485,522-528` and
`spine_action_server.py:195-216`. The default immediate path also refuses motion
while the fixture drive is switched off, following controller lines 376-385.

The paired private SDK requires a fresh successful switch-off after cancellation
has settled. Pending or timed-out effectful callbacks prevent an achieved safety
claim and safety reset; stop requests still dispatch. Transport reconnect or a
new endpoint does not prove any prior remote callback stopped. The package stays
blocked pending independent core and package review; its old gate files are historical author evidence.

## Model review, 2026-11-05 (claude-opus-5-5, a model and not a human)

The SDK now supports a declared re-enable after a safety reset (CORE-086,
`MHS/changes/RE-ENABLE-AND-TERMINAL-STOP.md`), the remaining blocker of the
previous section. The package binds the upstream `~/switch_on` service as that
re-enable (see Safety); the reset still re-arms nothing. G1-G9 pass on the fake
with no finding; this is contract evidence only, with no ROS graph, rosbridge
connection, physical drive or human review. This supersedes the blocked status
stated above.

### Battery JSON representation evidence

The five unknown battery quantities are NaN before serialization in the pinned
source. The full fake wire message includes all those fields as JSON null.
`fixtures/battery-wire.json` preserves an actual controlled ROS2 publication
observed through rosbridge-library 2.7.1 / rosbridge-server 2.7.1, with sensor_msgs
5.3.8. It includes the raw frame and exact distribution versions; its finite
values are test data, including the float32 representation of 0.84. No physical
battery was connected. The separate source-shaped fixture retains the NaNs for
a negative JSON test: MHS still rejects nonfinite input. No global JSON policy was
relaxed and no compatibility claim extends beyond that tested rosbridge version.
