"""OpenMHS driver for gh.cyberorigin2077/open_cyber_glove: the OpenCyberGlove data glove.

A direct Driver over ``open_cyber_glove.sdk:OpenCyberGlove`` (sdk.py:7).  The SDK manages one or two gloves,
each a ``Glove`` with a background serial reader (sdk.py:11-45), and ``get_data(hand_type)`` returns the latest
parsed packet of the selected hand (sdk.py:47-70, glove.py:259-262).  One OpenMHS device serves one configured
glove; the deployment selects ``hand`` (``left`` or ``right``) and the matching serial port.

The packet has 19 int32 tensile values, a 3-axis accelerometer, gyroscope and magnetometer, a temperature and
a microsecond timestamp (glove.py:29-41, 242-247).  The driver exposes them as:

* read state: the last packet of the configured glove (``tensile``, ``accelerometer``, ``gyroscope``,
  ``magnetometer``, ``temperature``, ``packet_timestamp_us``), the configured ``hand`` and whether the reader is
  ``acquisition`` running or stopped;
* ``cap.sensing.read.v1``: capture one fresh packet and return the requested channels; the class example
  ``fields: ["temperature"]`` selects one channel, and an omitted or empty list returns every channel.  After an
  e-stop the capture returns the held last packet with ``acquisition: "stopped"`` rather than restarting a reader;
* the native stop ``OpenCyberGlove.stop`` (sdk.py:39-45, which stops each glove's reader) is the e-stop.  The
  device is input-only and provides no haptic feedback (docs/safety_en.md:25), so stopping its readers is its
  safe state.  An e-stop latches and stops acquisition; the SDK has no separate resume and the driver does not
  restart a stopped reader on its own, so the device is reopened after a stop.

Every Fact cites the pinned clone at 88910bec8433658ffe8e181f23fb259f5376bb88.  The upstream calibration
``Glove.calibrate`` and ``Glove.advanced_calibrate`` are interactive: they print a pose prompt and wait on
``input()`` (glove.py:264-284, 303-325), so this server driver does not expose ``cap.device.calibrate.v1``; a
calibration is a bench procedure, not a remote command.  ``get_angles`` is not exposed either: the linear path
raises NotImplementedError and the model path needs an ONNX model (glove.py:376-397).

This package is model-authored and unreviewed.  It is checked on the fake backend only; the hardware backend was
never opened and this is not a hardware run.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, action, estop, read

#: The upstream SDK module and the Glove module, relative to the clone root.
SDK = "open_cyber_glove/sdk.py"
GLOVE = "open_cyber_glove/glove.py"
#: The vendor documentation of the glove and its safety rules.
README = "README.md"
USER_GUIDE = "docs/setup/user_guide_en.md"
SAFETY = "docs/safety_en.md"

class OpenCyberGloveSensor(Driver):
    device_id = "open-cyber-glove"
    device_kind = "sensor"
    mode = "hardware"
    risk = "R1"
    native = "open_cyber_glove.sdk:OpenCyberGlove"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeOpenCyberGlove"}
    vendor, model = "CyberOrigin", "OpenCyberGlove data glove (one hand)"
    display_name = "OpenCyberGlove data glove (OpenCyberGlove SDK)"
    tags = ["data glove", "wearable sensor", "tensile sensors", "imu", "hand motion capture", "serial"]
    facts = [
        Fact("The README states that the SDK connects to one or two data gloves over a serial port at 1 Mbps and "
             "samples at 120 Hz", source="vendor_doc", ref=f"{README}:20-21"),
        Fact("The README lists 19 tensile sensors", source="vendor_doc", ref=f"{README}:23"),
        Fact("The README documents tensile_data as 19 integers in the range 0-16384 and marks acc_data, gyro_data "
             "and mag_data as 'To be added'", source="vendor_doc", ref=f"{README}:114-117"),
        Fact("The user guide lists 19 sensors, a 120 Hz frequency and a sensor value range of 0 - 16380",
             source="vendor_doc", ref=f"{USER_GUIDE}:26-32"),
        Fact("The SDK constant SENSOR_MAX_VALUE is 8192 * 2", source="upstream_code", ref=f"{GLOVE}:72"),
        Fact("The reader skips a packet whose tensile values are not all within 0..SENSOR_MAX_VALUE",
             source="upstream_code", ref=f"{GLOVE}:169"),
        Fact("The SDK's DEFAULT_BAUDRATE is 1000000", source="upstream_code", ref=f"{GLOVE}:73"),
        Fact("GloveSensorData documents the packet units: accelerometer in m/s2, gyroscope in rad/s, magnetometer "
             "in uT, temperature in Celsius and timestamp in microseconds", source="upstream_code",
             ref=f"{GLOVE}:29-34"),
        Fact("The packet is 132 bytes: 19 int32 tensile values, three float accelerometer values, three float "
             "gyroscope values, three float magnetometer values, one float temperature and one uint32 timestamp",
             source="upstream_code", ref=f"{GLOVE}:55-68"),
        Fact("parse_raw_data unpacks exactly those fields from the packet offsets", source="upstream_code",
             ref=f"{GLOVE}:242-247"),
        Fact("The reader validates a packet with a CRC-32 over the first 120 bytes", source="upstream_code",
             ref=f"{GLOVE}:369-374"),
        Fact("get_raw_data waits, with no timeout, until the queue has a packet and returns only the most recent "
             "one after draining the queue", source="upstream_code", ref=f"{GLOVE}:212-222"),
        Fact("get_data reads the most recent raw packet and parses it", source="upstream_code",
             ref=f"{GLOVE}:259-262"),
        Fact("OpenCyberGlove refuses construction unless at least one of left_port and right_port is provided",
             source="upstream_code", ref=f"{SDK}:17-18"),
        Fact("start connects each configured glove and starts its background reader", source="upstream_code",
             ref=f"{SDK}:29-37"),
        Fact("stop stops the readers of all configured gloves", source="upstream_code", ref=f"{SDK}:39-45"),
        Fact("get_data(hand_type) returns the packet of the requested glove and raises RuntimeError when that "
             "glove is not configured", source="upstream_code", ref=f"{SDK}:47-70"),
        Fact("stop_reader clears the reader event and joins the reader thread without a timeout",
             source="upstream_code", ref=f"{GLOVE}:127-137"),
        Fact("stop_reader does not close the serial port and does not clear the data queue, so packets already "
             "queued remain after a stop", source="upstream_code", ref=f"{GLOVE}:94-137"),
        Fact("connect opens the serial port with a one-second read timeout", source="upstream_code",
             ref=f"{GLOVE}:111"),
        Fact("calibrate prints a pose prompt and waits on input() before its min/max samples, then prompts again "
             "for the static-average samples", source="upstream_code", ref=f"{GLOVE}:264-284"),
        Fact("advanced_calibrate collects each pose through data_collection, which also waits on input()",
             source="upstream_code", ref=f"{GLOVE}:303-325"),
        Fact("inference raises NotImplementedError for method='linear'; method='model' requires an ONNX model",
             source="upstream_code", ref=f"{GLOVE}:376-397"),
        Fact("The safety guide states that the glove is an input-only device and does not provide haptic feedback "
             "or collision protection", source="vendor_doc", ref=f"{SAFETY}:25"),
        Fact("The safety guide states that an integrator controlling robots or mechanical arms is responsible for "
             "collision detection, limit switches and emergency stops in the controlled system",
             source="vendor_doc", ref=f"{SAFETY}:26"),
        Fact("The safety guide asks for a safety officer and immediate access to the emergency stop button when "
             "operating physical equipment", source="vendor_doc", ref=f"{SAFETY}:27"),
    ]
    safe_state = ("the glove readers are stopped (OpenCyberGlove.stop): no further packets are acquired; the "
                  "device is input-only, so no actuator remains energised")
    # The native stop is software (serial reader threads); the glove documents no hardware e-stop of its own.
    # At R1 no independent physical stop is required, and the safety guide puts the controlled system's e-stop
    # on the integrator (docs/safety_en.md:26-27).

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        hand = self.options.get("hand", "left")
        if hand not in ("left", "right"):
            raise ValueError(f"the 'hand' option must be 'left' or 'right', got {hand!r}")
        self._hand = hand
        self._acquiring = False
        self._sample = None
        self._sample_ctx = None

    # -- lifecycle -------------------------------------------------------------------------------------------------
    def setup(self):
        """Open the configured glove and hold the first packet (the SDK's start opens the serial port)."""
        self.native.start()
        self._acquiring = True
        self._sample = self._read_packet()
        self._sample_ctx = None

    def teardown(self):
        try:
            self.native.stop()
        finally:
            self._acquiring = False

    def _read_packet(self):
        try:
            return self.native.get_data(self._hand)
        except ValueError as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the glove packet could not be parsed: {exc}") from exc
        except RuntimeError as exc:
            raise DriverFailed("MHS.DEVICE.NOT_READY",
                               f"the glove reader is not available: {exc}") from exc

    def _latest(self, ctx=None):
        """The packet for this read request: one fresh packet per request while the reader runs.

        Every getter of one ``mhs.resource.read`` receives the same ``ctx`` object, so the fields of one state
        document come from one packet.  After an e-stop the reader is stopped and the last held packet is returned
        instead of calling the blocking getter of a stopped reader.
        """
        if self._acquiring and ctx is not self._sample_ctx:
            self._sample = self._read_packet()
            self._sample_ctx = ctx
        if self._sample is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "no glove packet has been received yet")
        return self._sample

    # -- stable state ----------------------------------------------------------------------------------------------
    @read("hand", type="string", description="The hand this device serves: left or right")
    def hand(self):
        return self._hand

    @read("acquisition", type="string",
          description="'running' while the background reader acquires packets, 'stopped' after an e-stop")
    def acquisition(self):
        return "running" if self._acquiring else "stopped"

    # -- packet values ---------------------------------------------------------------------------------------------
    @read("tensile", type="array", items="integer", length=19, unit="1",
          description="Raw tensile values of the 19 sensors, in the packet order")
    def tensile(self, ctx=None):
        return [int(value) for value in self._latest(ctx).tensile_data]

    @read("accelerometer", type="array", items="number", length=3, unit="m/s2",
          description="Accelerometer x, y and z in m/s2")
    def accelerometer(self, ctx=None):
        return [float(value) for value in self._latest(ctx).acc_data]

    @read("gyroscope", type="array", items="number", length=3, unit="rad/s",
          description="Gyroscope x, y and z in rad/s")
    def gyroscope(self, ctx=None):
        return [float(value) for value in self._latest(ctx).gyro_data]

    @read("magnetometer", type="array", items="number", length=3, unit="uT",
          description="Magnetometer x, y and z in uT")
    def magnetometer(self, ctx=None):
        return [float(value) for value in self._latest(ctx).mag_data]

    @read("temperature", unit="Cel", description="Glove temperature in Celsius")
    def temperature(self, ctx=None):
        return float(self._latest(ctx).temperature)

    @read("packet_timestamp_us", type="integer", unit="us",
          description="Microsecond timestamp of the packet (the SDK's uint32 field)")
    def packet_timestamp_us(self, ctx=None):
        return int(self._latest(ctx).timestamp)

    # -- measurement capability ------------------------------------------------------------------------------------
    @action(cap="cap.sensing.read.v1",
            description="Capture one glove packet and return the requested sensor channels; after an e-stop it returns "
                        "the held last packet with acquisition='stopped'",
            input={"fields": Field(
                "array", items="string",
                description="Channel names to return: tensile, accelerometer, gyroscope, magnetometer, temperature, "
                             "packet_timestamp_us, hand or acquisition; omit or leave empty for all of them")})
    def read_sensors(self, fields=None):
        if self._acquiring:
            # A stopped reader has no fresh packet; its last held packet is returned with acquisition="stopped".
            self._sample = self._read_packet()
            self._sample_ctx = None
        if self._sample is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "no glove packet has been received yet")
        values = self._values(self._sample)
        if fields:
            values = {name: values[name] for name in fields if name in values}
        return {"values": values}

    def _values(self, packet):
        return {
            "tensile": [int(value) for value in packet.tensile_data],
            "accelerometer": [float(value) for value in packet.acc_data],
            "gyroscope": [float(value) for value in packet.gyro_data],
            "magnetometer": [float(value) for value in packet.mag_data],
            "temperature": float(packet.temperature),
            "packet_timestamp_us": int(packet.timestamp),
            "hand": self._hand,
            "acquisition": "running" if self._acquiring else "stopped",
        }

    # -- stop ------------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """Stop acquisition first locally, then through the SDK's own stop (stops every glove reader)."""
        self._acquiring = False
        self.native.stop()
