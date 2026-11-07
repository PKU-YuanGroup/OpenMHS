# Facts and tags for gh.avisengine/avis-engine-python-api

Every fact cites its source at commit `32b9a9e063a5608b9b60a87aa32171d44c116316`: `vendor_doc` (a text file of the
clone) or `upstream_code` (code or a comment of the clone). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The project is a Python API for AVIS Engine, an autonomous-vehicle simulation platform | vendor_doc | README.md:3 |
| The README's Getting Started section launches the simulator and starts its server (section 1) before it connects and controls the vehicle (section 2) | vendor_doc | README.md:56-68 |
| The simulator's documented default server address is 127.0.0.1 and port 25001 | vendor_doc | README.md:62-63 |
| config.py sets SIMULATOR_IP to 127.0.0.1 and SIMULATOR_PORT to 25001 | upstream_code | config.py:5-6 |
| AVIS Engine's main class is Car, the object a client instantiates to drive the simulated car | upstream_code | avisengine.py:17 |
| The Car transport is a TCP socket (AF_INET, SOCK_STREAM) | upstream_code | avisengine.py:47 |
| The request is a comma-separated text command with Speed, Steering, ImageStatus, SensorStatus, GetSpeed and SensorAngle fields | upstream_code | avisengine.py:51 |
| connect(server, port) connects the socket and sets a 5.0 s socket timeout | upstream_code | avisengine.py:58-64 |
| setSpeed stores speed_value, disables image and sensor replies, updates the request and sends it | upstream_code | avisengine.py:108-121 |
| setSteering stores steering_value, disables image and sensor replies, updates the request and sends it | upstream_code | avisengine.py:92-106 |
| setSensorAngle stores sensor_angle, disables image and sensor replies, updates the request and sends it | upstream_code | avisengine.py:123-137 |
| getData requests image, sensor and speed data and parses the <image>, <sensor> and <speed> tags of the reply | upstream_code | avisengine.py:139-176 |
| getSensors returns the three distance readings as a list [left, middle, right] | upstream_code | avisengine.py:185-191 |
| getSpeed returns current_speed | upstream_code | avisengine.py:193-197 |
| getData decodes the reply's <image> payload from base64 and OpenCV into self.image | upstream_code | avisengine.py:154-160 |
| getImage returns self.image, the image the client stored | upstream_code | avisengine.py:179-183 |
| stop sets speed and steering to 0, sends the text command 'stop' and closes the socket | upstream_code | avisengine.py:206-214 |
| The README documents the throttle range as -100 to 100 | vendor_doc | README.md:132 |
| The README documents the steering range as -100 to 100 | vendor_doc | README.md:133 |
| The README documents sensor distances in cm | vendor_doc | README.md:102 |
| The README documents the current speed in km/h | vendor_doc | README.md:107 |
| The README documents getSensors as [left, middle, right] distances in cm and getSpeed as km/h | vendor_doc | README.md:137-139 |
| The example comment calls setSteering a steering angle in degrees | upstream_code | example.py:33 |
| The example sets the angle between sensor rays to 45 degrees, once from the client | upstream_code | example.py:36-38 |
| The example returns three sensor values and an integer speed in KMH | upstream_code | example.py:48-56 |
| The README's license section says MIT License and refers to a LICENSE file | vendor_doc | README.md:208-210 |

Limits (each `Limit` in `driver.py` cites its line):

| capability | path | bound | source | ref |
|---|---|---|---|---|
| cap.device.configure.v1 | throttle (1) | -100 .. 100 | vendor_doc | README.md:132 |
| cap.device.configure.v1 | steering (deg) | -100 .. 100 | vendor_doc | README.md:133 |
| cap.device.configure.v1 | sensor_angle (deg) | operator_required: the clone states no range; example.py:36 passes 45 degrees but that is not a bound | | |

Safety: the native stop is `Car.stop` (speed and steering 0, the text command "stop", socket closed,
avisengine.py:206-214), declared as the `@estop` native and as the `cap.motion.stop.v1` action. The device is
simulated (R1), so no independent hardware stop is declared; the e-stop drives the simulator's stop command and the
runtime latches it. A reset is a plain software reset (the upstream class has no reset call), and no hardware backend
is offered.

Units: throttle is the dimensionless -100..100 command scale (the README calls it throttle and the clone states no
physical unit); steering is in degrees (example.py:33); sensor distances are cm (README.md:102, :137); the current
speed is km/h (README.md:107, :139); the angle between sensor rays is degrees (avisengine.py:129-130, example.py:36).

Fidelity: the only backend is the package fake (`.fake:FakeCar`), an analytic F0 stand-in. It has no socket, no Unity
scene or vehicle dynamics and no image decoding; the three sensor distances and the speed are placeholders. The real
camera image array returned by `Car.getImage` is **NOT COVERED**: MHS 0.9 has no image array field, and the scalar
telemetry and controls are served instead. The external simulator was never run or compared with the fake.

Tags: avis-engine, autonomous-vehicle, simulator, car, mobile-base, sensor, telemetry
