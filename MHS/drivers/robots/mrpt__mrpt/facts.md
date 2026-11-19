# Facts and tags for gh.mrpt/mrpt

Every fact cites its source at commit `dfa5194b3f613a5cfdafb035915e06a8c63e7b77`. The driver's `facts` list in
`driver.py` is the authority; this page mirrors it. There are no numeric Limits: the device is a passive IMU with no
actuation, no writable parameter and no stop, so no bound is required from the operator and there is no
`site-limits.example.json`.

| fact | source | ref |
|---|---|---|
| The Python binding declares CTaoboticsIMU as a py::class_ expression without a variable name, then chains .def calls for the default constructor, setSerialPort and setSerialBaudRate. | upstream_code | modules/mrpt_hwdrivers/python_bindings/mrpt_hwdrivers_py.cpp:121-129 |
| setSerialPort and setSerialBaudRate assert they run before initialize(), then store the port and baud rate. | upstream_code | modules/mrpt_hwdrivers/src/CTaoboticsIMU.cpp:40-52 |
| initialize() selects parser_hfi_b6 for hfi-b6 and parser_hfi_a9 for hfi-a9, and throws for another model. | upstream_code | modules/mrpt_hwdrivers/src/CTaoboticsIMU.cpp:96-105 |
| The sensor model member defaults to hfi-a9. | upstream_code | modules/mrpt_hwdrivers/include/mrpt/hwdrivers/CTaoboticsIMU.h:130 |
| initialize() opens the serial port at the configured baud, sets timeouts, purges buffers and sets ssWorking; on failure it prints the port and sets ssError without rethrowing. | upstream_code | modules/mrpt_hwdrivers/src/CTaoboticsIMU.cpp:111-128 |
| doProcess() asserts initialize() ran, retries it after 200 ms in ssError, reads the port, parses the bytes and appends each observation. | upstream_code | modules/mrpt_hwdrivers/src/CTaoboticsIMU.cpp:54-94 |
| The Python binding exposes initialize, doProcess, getObservations and getState on CGenericSensor; getObservations returns (timestamp, observation) pairs and removes them. | upstream_code | modules/mrpt_hwdrivers/python_bindings/mrpt_hwdrivers_py.cpp:65-89 |
| The observation queue type is a multimap from a TTimeStamp to a CSerializable pointer. | upstream_code | modules/mrpt_hwdrivers/include/mrpt/hwdrivers/CGenericSensor.h:82-84 |
| getObservations is declared to return that queue. | upstream_code | modules/mrpt_hwdrivers/include/mrpt/hwdrivers/CGenericSensor.h:245 |
| The hfi-a9 parser reads a 49-byte 0xAA 0x55 0x2c frame of nine little-endian floats (wx, wy, wz, ax, ay, az, mx, my, mz), stores the acceleration as -9.8 times ax/ay/az, the angular velocity and the magnetometer values, then reads a 25-byte 0xAA 0x55 0x14 frame of roll, pitch and yaw in degrees and stores the resulting quaternion. | upstream_code | modules/mrpt_hwdrivers/src/CTaoboticsIMU.cpp:248-389 |
| The hfi-b6 parser reads 11-byte frames; it prints the acceleration without storing it, stores nothing for the angular-velocity frame, and appends an observation only on the euler frame without setting a measurement. | upstream_code | modules/mrpt_hwdrivers/src/CTaoboticsIMU.cpp:144-246 |
| TIMUDataIndex documents the acceleration in the local/vehicle frame in m/s2, the angular velocity in the local/vehicle frame in rad/s, and the quaternion in the global/navigation frame. | upstream_code | modules/mrpt_obs/include/mrpt/obs/CObservationIMU.h:27-84 |
| CObservationIMU.get throws when the requested entry was not set. | upstream_code | modules/mrpt_obs/include/mrpt/obs/CObservationIMU.h:148-153 |
| The Python binding exposes CObservationIMU.get with a TIMUDataIndex argument. | upstream_code | modules/mrpt_obs/python_bindings/mrpt_obs_py.cpp:213-217 |
| The clone's Python example constructs CTaoboticsIMU, sets the serial port, calls initialize(), checks getState() against ssError, loops doProcess()/getObservations() and reads IMU_WZ in rad/s and IMU_Z_ACC in m/s2. | upstream_code | mrpt_examples_py/hwdriver-tao-imu-usb.py:25-38 |
| The class documentation's configuration example lists process_rate 500 Hz (larger than the sensor rate), serialPort /dev/ttyUSB0, sensorModel hfi-a9, sensor pose in meters and degrees, and a sensorLabel. | upstream_code | modules/mrpt_hwdrivers/include/mrpt/hwdrivers/CTaoboticsIMU.h:56-71 |
| CTaoboticsIMU declares construction, destruction, configuration, initialize, doProcess and the two parsers; this declaration has no stop, enable, motion or reset method. | upstream_code | modules/mrpt_hwdrivers/include/mrpt/hwdrivers/CTaoboticsIMU.h:90-152 |
| CGenericSensor defines getState, getProcessRate, getSensorLabel, setSensorLabel and enableVerbose in this range. | upstream_code | modules/mrpt_hwdrivers/include/mrpt/hwdrivers/CGenericSensor.h:97-108 |

Tags (short lowercase keywords): `imu`, `inertial`, `taobotics`, `mrpt`, `serial`, `sensor`.
