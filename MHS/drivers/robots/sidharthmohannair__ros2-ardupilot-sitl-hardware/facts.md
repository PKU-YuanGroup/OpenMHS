OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Source facts for gh.sidharthmohannair/ros2-ardupilot-sitl-hardware

Pinned commit: `595f9916efe8efb8a08667f35fa515873b2f8450`. Source declarations and controlled fake evidence do not prove native execution.

| Fact | Source | Reference |
|---|---|---|
| The mission script imports mavros_msgs State, CommandBool, SetMode and CommandTOL and geometry_msgs PoseStamped. | upstream_code | `scripts/missions/mission_simple.py:20-22` |
| The mission script subscribes /mavros/state as State and /mavros/local_position/pose as PoseStamped with BEST_EFFORT, VOLATILE, KEEP_LAST depth 10. | upstream_code | `scripts/missions/mission_simple.py:30-51` |
| The mission script publishes /mavros/setpoint_position/local as PoseStamped at 20 Hz for the requested duration and then returns True without checking the final position. | upstream_code | `scripts/missions/mission_simple.py:147-176` |
| The mission script creates clients for /mavros/cmd/arming CommandBool, /mavros/set_mode SetMode and /mavros/cmd/takeoff CommandTOL. | upstream_code | `scripts/missions/mission_simple.py:60-63` |
| set_mode maps the mode string to custom_mode and treats the SetMode mode_sent response as success. | upstream_code | `scripts/missions/mission_simple.py:82-96` |
| arm sends value = true and checks the CommandBool success response. | upstream_code | `scripts/missions/mission_simple.py:98-112` |
| takeoff sets altitude and checks the CommandTOL success response, logging only that the command was sent. | upstream_code | `scripts/missions/mission_simple.py:114-129` |
| Altitude attainment is a separate observation loop over /mavros/local_position/pose with a 0.3 m default tolerance. | upstream_code | `scripts/missions/mission_simple.py:131-145` |
| The demo mission sets GUIDED, arms, requests 10.0 m takeoff, moves to (10.0, 0.0, 10.0) for 15 s and requests RTL; these are demo targets, not safe envelopes. | upstream_code | `scripts/missions/mission_simple.py:192-227` |
| The SITL guide documents a LAND request on /mavros/set_mode with mavros_msgs/srv/SetMode and custom_mode LAND. | vendor_doc | `docs/guides/SITL_SETUP.md:114-116` |
| The hardware guide's kill switch is an RC transmitter procedure: switch to manual mode, disarm via RC switch and emergency land. | vendor_doc | `docs/guides/REAL_HARDWARE_SETUP.md:454-459` |
| The hardware guide requires propellers to be removed and the drone secured for bench testing, because motors can spin when armed. | vendor_doc | `docs/guides/REAL_HARDWARE_SETUP.md:10-22` |
| The hardware guide's in-flight emergency procedure is manual RC control (STABILIZE) and a manual landing, not a ROS stop service. | vendor_doc | `docs/guides/REAL_HARDWARE_SETUP.md:440-452` |
| The hardware guide states that the same mission scripts used in SITL work on real hardware. | vendor_doc | `docs/guides/REAL_HARDWARE_SETUP.md:387` |
| The SITL MAVROS configuration sets the setpoint_position frame to map and the setpoint_velocity MAV frame to LOCAL_NED, and allowlists the setpoint_position and setpoint_velocity plugins. | upstream_code | `src/simtofly_mavros_sitl/config/mavros_params.yaml:52-88` |
| The real-hardware launch defaults fcu_url to /dev/ttyACM0:921600 and starts the external mavros_node with target system/component id 1. | upstream_code | `src/simtofly_mavros_real/launch/cube_orange.launch.py:32-81` |
| The SITL launch defaults fcu_url to udp://:14550@ and starts the external mavros_node with target system/component id 1. | upstream_code | `src/simtofly_mavros_sitl/launch/ardupilot_sitl.launch.py:20-69` |

## Scope, limits and safety

The full selected request surface remains: state/pose observations, GUIDED, arm, takeoff, one position setpoint, RTL and LAND. Mode and arm/takeoff replies retain application success predicates. No motion is replaced by diagnostic-only scope.

LAND is an ordinary mode request. A mode_sent=true response can coexist with GUIDED, armed=true and altitude 10 in the controlled negative peer. Even an observed LAND mode would not prove touchdown or rotor stop. LAND has no safe_state permission and no e-stop binding. The RC instructions remain cited operational procedures, not a software safe-state proof or physical_ref exemption. Full stock gates must remain blocked at G3 for missing native stop/safe state.

Position x/y are described only as map-frame coordinates. The separate velocity-plugin LOCAL_NED configuration does not establish north/east axes for the position plugin. Outgoing ROS 2 timestamp field names are sec/nanosec, replacing ROS 1 secs/nsecs. The zero stamp is an explicit controlled wire placeholder; it does not reproduce the upstream live clock in mission_simple.py:162. Native clock/transport admission remains unresolved. The source streams at 20 Hz and separately observes altitude; one package publication is transmission only, not streaming or attainment.

Takeoff altitude and position remain operator-required. The example overlay is illustrative, not a flight envelope. Native admission needs a pinned external MAVROS/rosbridge/controller profile plus flight-specific stop conditions, pending-command retirement and authorized runtime evidence. Disarm-in-flight or RTL is not substituted as a universal stop.
