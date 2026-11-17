"""OpenMHS driver for the Taobotics IMU of MRPT (gh.mrpt/mrpt): ``mrpt.hwdrivers.CTaoboticsIMU``.

The pinned clone exposes a C++ ``CTaoboticsIMU`` to Python only through the pybind11 binding
``modules/mrpt_hwdrivers/python_bindings/mrpt_hwdrivers_py.cpp``; there is no Python class to import into this
repository.  The binding name used as evidence is the pybind11 source selector
``pybind:modules/mrpt_hwdrivers/python_bindings/mrpt_hwdrivers_py.cpp#mrpt.hwdrivers.CTaoboticsIMU``.  This package is
model-authored and unreviewed; the gate never imports, builds or runs the clone and no IMU was attached.

Scope: one ``cap.sensing.imu.v1`` read.  The driver calls ``doProcess()`` until a complete observation arrives,
reads the acceleration, angular velocity and orientation that the upstream parser stores in a
``mrpt::obs::CObservationIMU`` (``modules/mrpt_hwdrivers/src/CTaoboticsIMU.cpp:248-389``), and converts the
body/vehicle-frame vectors to the world frame when the caller asks for it.  The default parser is hfi-a9
(``modules/mrpt_hwdrivers/include/mrpt/hwdrivers/CTaoboticsIMU.h:130``); the hfi-b6 parser stores no measurement
(``CTaoboticsIMU.cpp:144-246``), so an hfi-b6 observation is skipped and the read times out rather than reporting
zeros as data.

``sampled_at`` is the observation timestamp (the parser sets it from ``mrpt::Clock::now()`` at the frame), rendered
as RFC 3339 in UTC.  The sensor pose and label are configured on the native object and are not part of the
capability output.

The IMU is a passive sensor: the upstream class has no stop, enable, motion or reset command
(``CTaoboticsIMU.h:90-152``; the inherited surface is configuration and read accessors, ``CGenericSensor.h:97-108``),
so this package declares no e-stop, no safe-state action and no reset.  That is also why the risk is R0.
"""

import math
import time
from datetime import datetime, timezone

from mhs.driver import Driver, DriverFailed, Fact, Field, action

_BINDING = "modules/mrpt_hwdrivers/python_bindings/mrpt_hwdrivers_py.cpp"
_IMU_SOURCE = "modules/mrpt_hwdrivers/src/CTaoboticsIMU.cpp"
_IMU_HEADER = "modules/mrpt_hwdrivers/include/mrpt/hwdrivers/CTaoboticsIMU.h"
_OBS_HEADER = "modules/mrpt_obs/include/mrpt/obs/CObservationIMU.h"
_OBS_BINDING = "modules/mrpt_obs/python_bindings/mrpt_obs_py.cpp"

#: The integer values of the TIMUDataIndex entries this driver reads, in the order of CObservationIMU.h:27-84.
#: They are used only when the native observation's get() accepts a plain integer (the package fake); a real
#: pybind11 observation expects the mrpt.obs.TIMUDataIndex enum (CObservationIMU.h:148-153).
_IMU_INDEX = {
    "IMU_X_ACC": 0,
    "IMU_Y_ACC": 1,
    "IMU_Z_ACC": 2,
    "IMU_WZ": 3,
    "IMU_WY": 4,
    "IMU_WX": 5,
    "IMU_ORI_QUAT_X": 21,
    "IMU_ORI_QUAT_Y": 22,
    "IMU_ORI_QUAT_Z": 23,
    "IMU_ORI_QUAT_W": 24,
}
_REQUIRED = ("IMU_X_ACC", "IMU_Y_ACC", "IMU_Z_ACC", "IMU_WX", "IMU_WY", "IMU_WZ")
_QUATERNION = ("IMU_ORI_QUAT_X", "IMU_ORI_QUAT_Y", "IMU_ORI_QUAT_Z", "IMU_ORI_QUAT_W")

#: The capability class allows at most 2000 ms; polling follows the clone's own example (0.005 s between calls).
_READ_TIMEOUT_S = 2.0
_POLL_S = 0.005


def _rfc3339(seconds):
    """Render a UNIX time in seconds as an RFC 3339 UTC timestamp."""
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "the IMU observation timestamp is not a finite number")
    try:
        moment = datetime.fromtimestamp(float(seconds), tz=timezone.utc)
    except (OSError, OverflowError, ValueError) as exc:
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID",
                           "the IMU observation timestamp is not a representable time") from exc
    return moment.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _seconds(timestamp):
    """The observation timestamp in seconds: the package fake supplies a float, a real observation an MRPT Clock."""
    if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool):
        return float(timestamp)
    from mrpt.core import Clock

    return float(Clock.toDouble(timestamp))


def _measurement(observation, name):
    """One measurement of an observation, or None when the parser did not set it.

    The real pybind11 observation accepts only ``mrpt.obs.TIMUDataIndex``; the package fake accepts the integer
    index, so the integer call is tried first and never imports the upstream package in the fake backend.
    """
    try:
        value = observation.get(_IMU_INDEX[name])
    except TypeError:
        try:
            from mrpt.obs import TIMUDataIndex
        except ImportError as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "the observation does not accept an integer index and mrpt.obs is not importable") from exc
        try:
            value = observation.get(getattr(TIMUDataIndex, name))
        except (RuntimeError, KeyError, AttributeError):
            return None
    except (RuntimeError, KeyError):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _normalize(quaternion):
    """Return a unit quaternion, or None when the four values do not form one."""
    x, y, z, w = quaternion
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if norm == 0.0 or not math.isfinite(norm):
        return None
    return (x / norm, y / norm, z / norm, w / norm)


def _rotate(quaternion, vector):
    """Rotate a body-frame vector into the world frame with a unit quaternion."""
    x, y, z, w = quaternion
    vx, vy, vz = vector
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return [
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    ]


class TaoboticsImu(Driver):
    device_id = "mrpt-taobotics-imu"
    device_kind = "sensor.imu"
    mode = "hardware"
    risk = "R0"
    native = f"pybind:{_BINDING}#mrpt.hwdrivers.CTaoboticsIMU"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeTaoboticsIMU"}
    vendor = "MRPT"
    model = "Taobotics HFI-A9 / HFI-B9 / HFI-B6 (the upstream hfi-a9 parser is the one that stores measurements)"
    display_name = "Taobotics IMU through MRPT's CTaoboticsIMU"
    tags = ["imu", "inertial", "taobotics", "mrpt", "serial", "sensor"]
    facts = [
        Fact("The Python binding declares CTaoboticsIMU as a py::class_ expression without a variable name and "
             "then chains .def calls for the default constructor, setSerialPort and setSerialBaudRate.",
             source="upstream_code", ref=f"{_BINDING}:121-129"),
        Fact("setSerialPort and setSerialBaudRate assert that they are called before initialize() (the serial port "
             "member is still empty), then store the port and baud rate.", source="upstream_code",
             ref=f"{_IMU_SOURCE}:40-52"),
        Fact("initialize() selects parser_hfi_b6 when the sensor model is hfi-b6 and parser_hfi_a9 when it is hfi-a9, "
             "and throws for any other model.", source="upstream_code", ref=f"{_IMU_SOURCE}:96-105"),
        Fact("The sensor model member defaults to hfi-a9.", source="upstream_code", ref=f"{_IMU_HEADER}:130"),
        Fact("initialize() opens a serial port at the configured baud rate, sets its timeouts, purges its buffers and "
             "sets the sensor state to ssWorking; on an exception it prints the port and sets ssError without "
             "rethrowing.", source="upstream_code", ref=f"{_IMU_SOURCE}:111-128"),
        Fact("doProcess() asserts that initialize() ran, retries initialize() after 200 ms when the state is ssError, "
             "reads the bytes available on the serial port, feeds them to the active parser and appends every parsed "
             "observation.", source="upstream_code", ref=f"{_IMU_SOURCE}:54-94"),
        Fact("The Python binding exposes initialize, doProcess, getObservations and getState on the CGenericSensor "
             "base class; getObservations returns the gathered observations as (timestamp, observation) pairs and "
             "removes them from the queue.", source="upstream_code", ref=f"{_BINDING}:65-89"),
        Fact("The observation queue type is a multimap from a TTimeStamp to a CSerializable pointer.",
             source="upstream_code",
             ref="modules/mrpt_hwdrivers/include/mrpt/hwdrivers/CGenericSensor.h:82-84"),
        Fact("getObservations is declared to return the observation queue.", source="upstream_code",
             ref="modules/mrpt_hwdrivers/include/mrpt/hwdrivers/CGenericSensor.h:245"),
        Fact("The hfi-a9 parser reads a 49-byte 0xAA 0x55 0x2c frame of nine little-endian floats, stores wx, wy and "
             "wz as IMU_WX, IMU_WY and IMU_WZ, stores -9.8 times ax, ay and az as IMU_X_ACC, IMU_Y_ACC and "
             "IMU_Z_ACC and the three magnetometer values, then reads a 25-byte 0xAA 0x55 0x14 frame of roll, pitch "
             "and yaw in degrees, converts them to radians and stores the resulting quaternion in IMU_ORI_QUAT_X, "
             "IMU_ORI_QUAT_Y, IMU_ORI_QUAT_Z and IMU_ORI_QUAT_W before it appends one observation.",
             source="upstream_code", ref=f"{_IMU_SOURCE}:248-389"),
        Fact("The hfi-b6 parser reads 11-byte frames; it computes the acceleration only to print it, stores nothing "
             "for the angular-velocity frame, and creates an observation only on the euler frame, without setting a "
             "measurement.", source="upstream_code", ref=f"{_IMU_SOURCE}:144-246"),
        Fact("TIMUDataIndex documents the acceleration entries in the local/vehicle frame in m/s2 and the angular "
             "velocity entries in the local/vehicle frame in rad/s; the orientation quaternion entries are in the "
             "global/navigation frame.", source="upstream_code", ref=f"{_OBS_HEADER}:27-84"),
        Fact("CObservationIMU.get throws when the requested entry was not set.", source="upstream_code",
             ref=f"{_OBS_HEADER}:148-153"),
        Fact("The Python binding exposes CObservationIMU.get with a TIMUDataIndex argument.", source="upstream_code",
             ref=f"{_OBS_BINDING}:213-217"),
        Fact("The clone's Python example constructs CTaoboticsIMU, sets the serial port, calls initialize(), checks "
             "getState() against CGenericSensor.ssError, then loops doProcess() and getObservations() and reads "
             "IMU_WZ in rad/s and IMU_Z_ACC in m/s2 with obs.get(TIMUDataIndex...).", source="upstream_code",
             ref="mrpt_examples_py/hwdriver-tao-imu-usb.py:25-38"),
        Fact("The class documentation's configuration example lists process_rate 500 Hz and says it must be larger "
             "than the sensor rate, serialPort /dev/ttyUSB0, sensorModel hfi-a9, sensor-pose positions in meters and "
             "angles in degrees, and a sensorLabel.", source="upstream_code", ref=f"{_IMU_HEADER}:56-71"),
        Fact("CTaoboticsIMU declares construction, destruction, configuration, initialize, doProcess and the two "
             "parsers; this declaration has no stop, enable, motion or reset method.", source="upstream_code",
             ref=f"{_IMU_HEADER}:90-152"),
        Fact("CGenericSensor defines getState, getProcessRate, getSensorLabel, setSensorLabel and enableVerbose "
             "in this range.", source="upstream_code",
             ref="modules/mrpt_hwdrivers/include/mrpt/hwdrivers/CGenericSensor.h:97-108"),
    ]
    safe_state = (
        "The IMU is a passive sensor: it has no actuation, motion, stop or reset command, so the driver only reads "
        "observations and commands no safe state."
    )

    @action(cap="cap.sensing.imu.v1", description="Read one complete IMU observation and return the acceleration "
                                                  "and angular velocity in the requested frame, the orientation and "
                                                  "the sample time",
            input={"frame": Field("string", enum=["body", "world"],
                                  description="body is the local/vehicle frame the observation stores; world rotates "
                                              "the vectors with the reported orientation")})
    def read_imu(self, frame):
        deadline = time.monotonic() + _READ_TIMEOUT_S
        sample = None
        sampled = None
        while sample is None:
            self.check_cancelled()
            self.native.doProcess()
            for timestamp, candidate in self.native.getObservations():
                values = {name: _measurement(candidate, name) for name in _REQUIRED}
                if all(value is not None for value in values.values()):
                    sample, sampled = candidate, timestamp
            if sample is not None:
                break
            if time.monotonic() >= deadline:
                raise DriverFailed(
                    "MHS.DEVICE.PRECONDITION_UNMET",
                    "no complete IMU observation arrived within 2 s; the serial port may not be open (initialize() "
                    "records ssError without raising) or the sensor model may be hfi-b6",
                )
            time.sleep(_POLL_S)

        quaternion = None
        raw_quaternion = {name: _measurement(sample, name) for name in _QUATERNION}
        if all(value is not None for value in raw_quaternion.values()):
            quaternion = _normalize((raw_quaternion["IMU_ORI_QUAT_X"], raw_quaternion["IMU_ORI_QUAT_Y"],
                                     raw_quaternion["IMU_ORI_QUAT_Z"], raw_quaternion["IMU_ORI_QUAT_W"]))
        acceleration = [_measurement(sample, name) for name in ("IMU_X_ACC", "IMU_Y_ACC", "IMU_Z_ACC")]
        angular = [_measurement(sample, name) for name in ("IMU_WX", "IMU_WY", "IMU_WZ")]
        if frame == "world":
            if quaternion is None:
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                                   "the observation has no unit orientation quaternion, so the world frame cannot "
                                   "be derived; request frame body")
            acceleration = _rotate(quaternion, acceleration)
            angular = _rotate(quaternion, angular)
        result = {
            "linear_acceleration": acceleration,
            "angular_velocity": angular,
            "sampled_at": _rfc3339(_seconds(sampled)),
        }
        if quaternion is not None:
            result["orientation"] = {"x": quaternion[0], "y": quaternion[1], "z": quaternion[2],
                                     "w": quaternion[3]}
        return result
