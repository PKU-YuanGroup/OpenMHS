# Facts and tags for gh.kinovarobotics/ros_kortex

Every fact cites the pinned clone at commit `c3280d8a6a6b5d96590d51538e3f265710a6c77d`.
`upstream_code` refs name `path/in/clone:LINE`; bounded ranges are used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver,
not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| BaseRobotServices advertises the relative ROS 1 service "base/stop" and binds it to BaseRobotServices::Stop. | upstream_code | kortex_driver/src/generated/robot/base_services.cpp:154 |
| BaseRobotServices advertises the relative ROS 1 service "base/apply_emergency_stop" and binds it to BaseRobotServices::ApplyEmergencyStop. | upstream_code | kortex_driver/src/generated/robot/base_services.cpp:169 |
| BaseRobotServices::Stop declares kortex_driver::Stop::Request and kortex_driver::Stop::Response parameters in the service callback signature. | upstream_code | kortex_driver/src/generated/robot/base_services.cpp:2651 |
| BaseRobotServices::Stop calls m_base->Stop(m_current_device_id, m_api_options) and leaves the response message untouched. | upstream_code | kortex_driver/src/generated/robot/base_services.cpp:2651-2679 |
| BaseRobotServices::Stop catches Kinova::Api::KDetailedException and std::runtime_error, returns false in both handlers, and returns true after a successful call. | upstream_code | kortex_driver/src/generated/robot/base_services.cpp:2661-2678 |
| BaseRobotServices::ApplyEmergencyStop declares kortex_driver::ApplyEmergencyStop::Request and kortex_driver::ApplyEmergencyStop::Response parameters in the service callback signature. | upstream_code | kortex_driver/src/generated/robot/base_services.cpp:3136 |
| BaseRobotServices::ApplyEmergencyStop calls m_base->ApplyEmergencyStop(m_current_device_id, m_api_options) and leaves the response message untouched. | upstream_code | kortex_driver/src/generated/robot/base_services.cpp:3136-3164 |
| BaseRobotServices::ApplyEmergencyStop catches Kinova::Api::KDetailedException and std::runtime_error, returns false in both handlers, and returns true after a successful call. | upstream_code | kortex_driver/src/generated/robot/base_services.cpp:3146-3163 |
| Stop.srv declares "Empty input" before the request separator and "Empty output" after it, so the generated request and response nest an Empty message under input and output. | upstream_code | kortex_driver/srv/generated/base/Stop.srv:1-3 |
| ApplyEmergencyStop.srv declares "Empty input" before the request separator and "Empty output" after it, so the generated request and response nest an Empty message under input and output. | upstream_code | kortex_driver/srv/generated/base/ApplyEmergencyStop.srv:1-3 |
| The generated interface header includes "kortex_driver/Stop.h", the generated header of the Stop service type. | upstream_code | kortex_driver/include/kortex_driver/generated/interfaces/base_services_interface.h:106 |
| The generated interface header includes "kortex_driver/ApplyEmergencyStop.h", the generated header of the ApplyEmergencyStop service type. | upstream_code | kortex_driver/include/kortex_driver/generated/interfaces/base_services_interface.h:121 |

## Endpoints and namespace

Both upstream registrations use relative names without a leading slash: `base/stop`
and `base/apply_emergency_stop` (`base_services.cpp:154` and `:169`). ROS resolves
them under the node's namespace. This package binds them under the explicit
deployment namespace `/my_gen3`:

- `/my_gen3/base/stop` with type `kortex_driver/Stop`
- `/my_gen3/base/apply_emergency_stop` with type `kortex_driver/ApplyEmergencyStop`

The `/my_gen3` prefix is operator configuration, not a fact of the clone: the
operator must launch the Kortex node in that namespace (or remap the services to
those endpoints). A different launch namespace requires changing the two
`service` strings in `driver.py`; the source `base/stop` and
`base/apply_emergency_stop` tokens are recorded as `source_name`.

## Wire contract

`Stop.srv` and `ApplyEmergencyStop.srv` each declare `Empty input` and
`Empty output` (`Stop.srv:1-3`, `ApplyEmergencyStop.srv:1-3`). The generated
request and response therefore nest an Empty message under the field names
`input` and `output`. The driver sends `{"input": {}}` and requires the
application predicate `output` equals `{}`. A rosbridge `service_response` must
also carry `result: true`; the bridge checks that separately. The output field
`acknowledged` is a constant written only after the service response passed
both checks, so it reports callback acknowledgement, not a device measurement.

The callback returns `false` when the Kortex API call raises either
`Kinova::Api::KDetailedException` or `std::runtime_error`
(`base_services.cpp:2661-2678` and `:3146-3163`). It never writes a stopping
position, velocity or success boolean into the response. No motion, gripper,
fault-clearing, reenable, reset, state observation or clear-fault service is
exposed: `base/clear_faults` is registered at `base_services.cpp:170` but is
deliberately outside this package's scope.

## Scope

Only the two acknowledged services are bound:

- `x-cap.kinovarobotics.stop.v1` invokes `/my_gen3/base/stop`.
- `x-cap.kinovarobotics.apply_emergency_stop.v1` invokes
  `/my_gen3/base/apply_emergency_stop` and is the input-free safe-state action.

The no-input x-cap actions declare no `Limit`; there is no numeric input to
bound. No resource reads or guessed joint/state topics are declared, so the
main resource snapshot is the SDK's empty automatic snapshot.

The upstream `Stop` and `ApplyEmergencyStop` callbacks do not return a stopped
state. A true callback means the Kortex API call did not raise; it does not
prove that the arm has zero velocity, where it stopped, that a physical
emergency-stop circuit opened, or that power was removed. The driver makes no
such claim and exposes no state observation to infer one.

## Safety

The device is a robot arm and this package is at risk R2. The native e-stop
binding is the acknowledged `/my_gen3/base/apply_emergency_stop` service. The
`x-cap.kinovarobotics.apply_emergency_stop.v1` action declares
`safe_state=True`, so the input-free apply-emergency-stop command remains
callable during the latch; the ordinary `stop` action is refused while latched.
The runtime latches in software before the e-stop path. The package declares no
`estop_physical_ref`: the clone has no text establishing an independent
physical stop, and the upstream callback acknowledgement is not one.
`driver.lock.json` keeps `reviewed_by: null`. Every hardware backend is refused
by the SDK without a human hardware review, and the fake is not a hardware run.

## Fidelity contract

The fake is a package-local recording transport. It answers the two declared
services with the pinned nested Empty request/response shapes and records the
outbound JSON. It is an F0 contract fixture: it runs no ROS node, no Kortex API,
no controller dynamics and no hardware. All failure switches and the call
record are placeholders. It does not simulate motion, stopping distance,
emergency-stop wiring or service timing. No ROS or hardware validation has run.
