# Facts and tags for gh.cyberorigin2077/open_cyber_glove

Every fact cites the read-only clone at commit `88910bec8433658ffe8e181f23fb259f5376bb88`. The same facts are in
`driver.py` (`facts = [...]`); `reference.json` is generated from the driver, not from this page.

## Device

The OpenCyberGlove is an input-only data glove: 19 tensile (flex) sensors on one hand, a 3-axis accelerometer,
gyroscope and magnetometer, a temperature sensor and a packet timestamp. The vendor ships left and right gloves and
the SDK can manage both at once, but one OpenMHS device serves one configured hand. There is no actuator, no haptic
feedback and no collision protection: the safety guide puts collision detection, limit switches and the controlled
system's emergency stop on the integrator (`docs/safety_en.md:25-27`).

The package follows the card's `direct-driver` decision. The card's `PythonObjectDriver` helper is not used: the
only packet getter is `OpenCyberGlove.get_data(hand_type)` (`open_cyber_glove/sdk.py:47-70`), whose return is a
`GloveSensorData` packet (`open_cyber_glove/glove.py:23-41`); the family's declarative read cannot pass the hand
argument nor select the packet fields. This is recorded as DEVIATION FROM THE CARD in `RESULT.json`.

## Facts

| fact | source | ref |
|---|---|---|
| The README states that the SDK connects to one or two data gloves over a serial port at 1 Mbps and samples at 120 Hz | vendor_doc | README.md:20-21 |
| The README lists 19 tensile sensors | vendor_doc | README.md:23 |
| The README documents tensile_data as 19 integers in the range 0-16384 and marks acc_data, gyro_data and mag_data as "To be added" | vendor_doc | README.md:114-117 |
| The user guide lists 19 sensors, a 120 Hz frequency and a sensor value range of 0 - 16380 | vendor_doc | docs/setup/user_guide_en.md:26-32 |
| The SDK constant SENSOR_MAX_VALUE is 8192 * 2 | upstream_code | open_cyber_glove/glove.py:72 |
| The reader skips a packet whose tensile values are not all within 0..SENSOR_MAX_VALUE | upstream_code | open_cyber_glove/glove.py:169 |
| The SDK's DEFAULT_BAUDRATE is 1000000 | upstream_code | open_cyber_glove/glove.py:73 |
| GloveSensorData documents the packet units: accelerometer in m/s2, gyroscope in rad/s, magnetometer in uT, temperature in Celsius and timestamp in microseconds | upstream_code | open_cyber_glove/glove.py:29-34 |
| The packet is 132 bytes: 19 int32 tensile values, three float accelerometer values, three float gyroscope values, three float magnetometer values, one float temperature and one uint32 timestamp | upstream_code | open_cyber_glove/glove.py:55-68 |
| parse_raw_data unpacks exactly those fields from the packet offsets | upstream_code | open_cyber_glove/glove.py:242-247 |
| The reader validates a packet with a CRC-32 over the first 120 bytes | upstream_code | open_cyber_glove/glove.py:369-374 |
| get_raw_data waits, with no timeout, until the queue has a packet and returns only the most recent one after draining the queue | upstream_code | open_cyber_glove/glove.py:212-222 |
| get_data reads the most recent raw packet and parses it | upstream_code | open_cyber_glove/glove.py:259-262 |
| OpenCyberGlove refuses construction unless at least one of left_port and right_port is provided | upstream_code | open_cyber_glove/sdk.py:17-18 |
| start connects each configured glove and starts its background reader | upstream_code | open_cyber_glove/sdk.py:29-37 |
| stop stops the readers of all configured gloves | upstream_code | open_cyber_glove/sdk.py:39-45 |
| get_data(hand_type) returns the packet of the requested glove and raises RuntimeError when that glove is not configured | upstream_code | open_cyber_glove/sdk.py:47-70 |
| stop_reader clears the reader event and joins the reader thread without a timeout | upstream_code | open_cyber_glove/glove.py:127-137 |
| stop_reader does not close the serial port and does not clear the data queue, so packets already queued remain after a stop | upstream_code | open_cyber_glove/glove.py:94-137 |
| connect opens the serial port with a one-second read timeout | upstream_code | open_cyber_glove/glove.py:111 |
| calibrate prints a pose prompt and waits on input() before its min/max samples, then prompts again for the static-average samples | upstream_code | open_cyber_glove/glove.py:264-284 |
| advanced_calibrate collects each pose through data_collection, which also waits on input() | upstream_code | open_cyber_glove/glove.py:303-325 |
| inference raises NotImplementedError for method="linear"; method="model" requires an ONNX model | upstream_code | open_cyber_glove/glove.py:376-397 |
| The safety guide states that the glove is an input-only device and does not provide haptic feedback or collision protection | vendor_doc | docs/safety_en.md:25 |
| The safety guide states that an integrator controlling robots or mechanical arms is responsible for collision detection, limit switches and emergency stops in the controlled system | vendor_doc | docs/safety_en.md:26 |
| The safety guide asks for a safety officer and immediate access to the emergency stop button when operating physical equipment | vendor_doc | docs/safety_en.md:27 |

## Units and ranges

The read-only packet values are exposed with the units of `GloveSensorData`:

| channel | shape | unit | source |
|---|---|---|---|
| tensile | 19 integers | 1 (raw sensor count) | glove.py:36 |
| accelerometer | 3 numbers | m/s2 | glove.py:30 |
| gyroscope | 3 numbers | rad/s | glove.py:31 |
| magnetometer | 3 numbers | uT | glove.py:32 |
| temperature | number | Cel | glove.py:33 |
| packet_timestamp_us | integer | us | glove.py:34 |

No `Limit` is declared: the driver has no numeric write and no numeric invoke input. The two vendor statements of
the tensile-value range disagree (0-16384 in `README.md:114`, 0-16380 in `docs/setup/user_guide_en.md:32`), so the
driver records both as facts and does not clamp or convert the packet's raw values. The reader already discards
packets outside 0..SENSOR_MAX_VALUE (`open_cyber_glove/glove.py:169`).

## Safety and stop

The glove is input-only (`docs/safety_en.md:25`); the driver is R1, the card's floor. The native stop is
`OpenCyberGlove.stop()` (`open_cyber_glove/sdk.py:39-45`), which stops the background readers of the configured
gloves; `stop_reader` joins the reader thread and the serial read has a 1 s timeout (`open_cyber_glove/glove.py:111`,
`:127-137`). It neither closes the serial port nor clears the packet queue, so packets already queued stay there
(`open_cyber_glove/glove.py:94-137`); the driver does not read them after a stop and returns its held packet instead. The e-stop sets the driver's acquisition flag first and then calls that stop. The declared safe state
is "the glove readers are stopped: no further packets are acquired". The device documents no hardware e-stop of its
own and is not a motion device; at R1 no independent physical stop (`estop_physical_ref`) is required, and the
safety guide assigns the controlled system's e-stop to the integrator (`docs/safety_en.md:26-27`).

`mhs.safety.reset` does not restart acquisition: `SAFE-042` says releasing an e-stop must not restart the device.
The SDK has no separate resume, and the driver never re-runs `start()` on its own; after an e-stop the device is
reopened by the deployment (the hardware backend was never run).

The driver fetches one packet per `mhs.resource.read` request: every getter of one request receives the same
`ctx`, so the fields of one state document come from one packet. After an e-stop the getters return the last held
packet instead of calling the blocking `get_data` (`open_cyber_glove/glove.py:198-222`), which would wait forever
once the reader is stopped; `cap.sensing.read.v1` likewise returns that held packet with `acquisition="stopped"`.

## Not covered

* `cap.device.calibrate.v1` is not exposed: `Glove.calibrate` and `Glove.advanced_calibrate` block on `input()`
  for pose prompts (`open_cyber_glove/glove.py:264-284`, `:303-325`), which cannot run inside a server call.
* Joint angles from `get_angles` are not exposed: the linear method is a `NotImplementedError` and the model method
  needs an ONNX model file (`open_cyber_glove/glove.py:376-397`, `open_cyber_glove/sdk.py:72-97`).
* The README marks the accelerometer, gyroscope and magnetometer data "To be added" (`README.md:115-117`); the
  driver exposes the fields the SDK parses but does not claim the vendor delivers meaningful IMU values yet.

Tags: data glove, wearable sensor, tensile sensors, imu, hand motion capture, serial
