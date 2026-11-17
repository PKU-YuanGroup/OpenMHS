"""Fake backend of the MRPT Taobotics IMU driver: an in-memory stand-in for CTaoboticsIMU.

The fake preserves the upstream runtime surface this driver uses: ``setSerialPort``, ``setSerialBaudRate``,
``initialize``, ``doProcess`` and ``getObservations``.  ``setSerialPort`` and ``setSerialBaudRate`` are the two
methods the pybind11 binding defines on CTaoboticsIMU itself
(``modules/mrpt_hwdrivers/python_bindings/mrpt_hwdrivers_py.cpp:121-129``); ``initialize``, ``doProcess`` and
``getObservations`` are bound on the CGenericSensor base class
(``modules/mrpt_hwdrivers/python_bindings/mrpt_hwdrivers_py.cpp:65-89``).

``doProcess`` enqueues one observation whose ``get`` reports the same measurement entries the hfi-a9 parser stores
(``modules/mrpt_hwdrivers/src/CTaoboticsIMU.cpp:305-379``); ``getObservations`` returns and clears the queue, as the
upstream does.  The values, the sample time and the initial serial settings are placeholders, not measurements or
facts.  There is no serial port, no frame parsing, no hfi-b6 path and no hardware here.
"""

# Every value in this block is test data, not a device fact or a measurement.
_ACCELERATION = (1.0, 2.0, 3.0)          # placeholder
_ANGULAR = (0.1, 0.2, 0.3)               # placeholder
_QUATERNION = (0.0, 0.0, 0.0, 1.0)       # placeholder (identity)
_SAMPLED_AT = 1700000000.0               # placeholder

# The TIMUDataIndex integers of the entries the fake reports (CObservationIMU.h:27-84).
_INDEX = {
    "IMU_X_ACC": 0,
    "IMU_Y_ACC": 1,
    "IMU_Z_ACC": 2,
    "IMU_WX": 5,
    "IMU_WY": 4,
    "IMU_WZ": 3,
    "IMU_ORI_QUAT_X": 21,
    "IMU_ORI_QUAT_Y": 22,
    "IMU_ORI_QUAT_Z": 23,
    "IMU_ORI_QUAT_W": 24,
}


class _Observation:
    """One placeholder CObservationIMU: get() throws for an entry the parser did not set."""

    def __init__(self, timestamp, values):
        self.timestamp = timestamp
        self.sensorLabel = "IMU"
        self._values = dict(values)

    def get(self, index):
        key = index if isinstance(index, int) else getattr(index, "value", None)
        if key not in self._values:
            raise RuntimeError("Trying to access non-set value")
        return self._values[key]


class FakeTaoboticsIMU:
    def __init__(self, **_options):
        self._port = None                    # placeholder: native.py calls setSerialPort before initialize()
        self._baud = None                    # placeholder
        self._initialized = True             # placeholder: native.py calls initialize() after configuring
        self._observations = []
        self._values = {
            _INDEX["IMU_X_ACC"]: _ACCELERATION[0],
            _INDEX["IMU_Y_ACC"]: _ACCELERATION[1],
            _INDEX["IMU_Z_ACC"]: _ACCELERATION[2],
            _INDEX["IMU_WX"]: _ANGULAR[0],
            _INDEX["IMU_WY"]: _ANGULAR[1],
            _INDEX["IMU_WZ"]: _ANGULAR[2],
            _INDEX["IMU_ORI_QUAT_X"]: _QUATERNION[0],
            _INDEX["IMU_ORI_QUAT_Y"]: _QUATERNION[1],
            _INDEX["IMU_ORI_QUAT_Z"]: _QUATERNION[2],
            _INDEX["IMU_ORI_QUAT_W"]: _QUATERNION[3],
        }

    def setSerialPort(self, serialPort):
        self._port = serialPort

    def setSerialBaudRate(self, rate):
        self._baud = int(rate)

    def initialize(self):
        self._initialized = True

    def doProcess(self):
        if not self._initialized:
            raise RuntimeError("initialize() must be called first")
        self._observations.append((_SAMPLED_AT, _Observation(_SAMPLED_AT, self._values)))

    def getObservations(self):
        observations, self._observations = self._observations, []
        return observations

    # -- test hook (underscore, not an upstream member; never used by the driver) -------------------------
    def _set_measurements(self, acceleration=None, angular=None, quaternion=None):
        """Replace the placeholder measurements the next observation reports."""
        for names, values in ((("IMU_X_ACC", "IMU_Y_ACC", "IMU_Z_ACC"), acceleration),
                              (("IMU_WX", "IMU_WY", "IMU_WZ"), angular),
                              (("IMU_ORI_QUAT_X", "IMU_ORI_QUAT_Y", "IMU_ORI_QUAT_Z", "IMU_ORI_QUAT_W"), quaternion)):
            if values is None:
                continue
            for name, value in zip(names, values):
                self._values[_INDEX[name]] = float(value)
