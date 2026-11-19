# Facts and tags for gh.cvzone/pysimverse

Every fact cites its source at commit `ec3f362f50f24278c7f30e5fe09bc2a7ae98e72f`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are declared in `driver.py`;
the reference file is generated from the driver, not from this page. The only vendor text is the project title
(`README.md:1`), so every behavioural statement comes from the source.

| fact | source | ref |
|---|---|---|
| The upstream README contains only the project title and no usage, unit, range or safety text | vendor_doc | README.md:1 |
| The package exports Drone and DroneManager from pysimverse.simulators.drone | upstream_code | __init__.py:1-2 |
| The Drone constructor takes host='*', cmd_port=5550, state_port=5556, video_port=5557, speed=300 and rotation_speed=15 | upstream_code | simulators/drone/drone.py:11 |
| The constructor sets command_address to tcp://{host}:{cmd_port}, state_address to tcp://localhost:{state_port} and video_address to tcp://localhost:{video_port} | upstream_code | simulators/drone/drone.py:24-33 |
| connect() binds the command socket, connects and subscribes the state and video sockets and sleeps 0.25 s | upstream_code | simulators/drone/drone.py:43-60 |
| send_rc_control publishes a JSON object with left_right, forward_backward, up_down, yaw, cameraangle, streamon and a red/green/blue color object | upstream_code | simulators/drone/drone.py:72-91 |
| send_rc_control catches every exception, prints it and returns, so a failed publish has no error value | upstream_code | simulators/drone/drone.py:93-94 |
| streamon and streamoff assign self.stream_on and publish it with all motion axes None | upstream_code | simulators/drone/drone.py:96-102 |
| Each move_* method acts only while is_flying is true, otherwise it prints 'Take off the drone first.' | upstream_code | simulators/drone/drone.py:166-218 |
| move_forward publishes the current speed on the forward axis, sleeps distance / speed and then publishes a zero command | upstream_code | simulators/drone/drone.py:166-171 |
| move_backward, move_right, move_left, move_up and move_down mirror move_forward with the opposite sign or another axis | upstream_code | simulators/drone/drone.py:175-218 |
| take_off sets is_flying true, publishes takeoff_speed on the up axis, sleeps takeoff_height / takeoff_speed and then publishes a zero command | upstream_code | simulators/drone/drone.py:220-227 |
| land publishes -landing_speed on the up axis, sleeps 3 s, publishes a zero command and sets is_flying false | upstream_code | simulators/drone/drone.py:231-237 |
| rotate publishes rotation_speed / 70 on the yaw axis with the sign of the angle, sleeps abs(angle / 60) and then publishes a zero command | upstream_code | simulators/drone/drone.py:241-249 |
| rotate_camera publishes the angle as cameraangle, sleeps abs(angle / 40) and then publishes a zero command | upstream_code | simulators/drone/drone.py:253-257 |
| set_speed and set_rotation_speed assign their argument to the corresponding attribute | upstream_code | simulators/drone/drone.py:261-265 |
| get_battery receives and prints the state message, parses it as a float and sleeps 1 s, but never returns the parsed value and catches only KeyboardInterrupt | upstream_code | simulators/drone/drone.py:152-164 |
| get_frame calls self.fpsReader.update when a frame is available | upstream_code | simulators/drone/drone.py:123-130 |
| get_frame catches exceptions, prints the error and returns frame and is_success | upstream_code | simulators/drone/drone.py:134-139 |
| shutdown closes the command, state and video sockets, terminates the context and calls cv2.destroyAllWindows | upstream_code | simulators/drone/drone.py:141-150 |
| DroneManager.create_drones connects, publishes the drone count, reads a port list and constructs one Drone per port | upstream_code | simulators/drone/drone_manager.py:64-72 |
| DroneManager.takeoff_all_drones starts one thread per drone and calls take_off with 300 | upstream_code | simulators/drone/drone_manager.py:89-116 |

Tags (short lowercase keywords): drone, simulation, zeromq, rc control, mobile base, pysimverse.

## Why the numeric inputs are operator_required

The clone states no range or unit for the takeoff height, takeoff speed, landing speed, move distance, rotation angle,
camera angle, RC speed or rotation speed. The constructor values 300 and 15 are defaults, not bounds, and every motion
method divides or multiplies the caller's value directly. The operator supplies the deployment bounds in
`site-limits.json`; `site-limits.example.json` holds example test values only.

## Not covered

Battery telemetry (`get_battery` never returns its parsed value), video capture (`get_frame` calls an undefined
`fpsReader`), and the DroneManager handshake and fleet takeoff path are not exposed by this package.

## Model review stop limitation

The zero RC call has no acknowledgement; send errors are suppressed upstream. The absent simulator consumer
provides no evidence of holding position, stopping or landing. The e-stop attempts zero and raises
`MHS.SAFETY.SAFE_STATE_UNREACHED`, retaining the latch. The ordinary stop action is not a safe-state action.
This package is blocked on `HELPER_MISSING` until a reviewed stop and confirmation path exists. Numeric units
are omitted because the clone does not state them; unit `1` would incorrectly claim dimensionless quantities.
`get_frame` catches its undefined-fpsReader error and may return `is_success=True` anyway. Native motion
sleeps cannot be interrupted; exceptions can skip the final zero command, and the first motion send can race
with an e-stop. Native printing and ZeroMQ cleanup also need review before any live factory is declared.
