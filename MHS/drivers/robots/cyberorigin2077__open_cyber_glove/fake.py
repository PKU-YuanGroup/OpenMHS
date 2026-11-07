"""Fake backend of the OpenCyberGlove driver: an in-memory stand-in for open_cyber_glove.sdk:OpenCyberGlove.

Gate G7: every public member defined here is a method of OpenCyberGlove in the pinned clone
(88910bec8433658ffe8e181f23fb259f5376bb88): ``start`` (sdk.py:29), ``stop`` (sdk.py:39) and ``get_data``
(sdk.py:47), with the upstream parameter names.  ``get_data`` returns a ``GloveSensorData``-shaped packet: 19
tensile values, three accelerometer values, three gyroscope values, three magnetometer values, a temperature and
a microsecond timestamp (glove.py:23-41).

What it does not do: no serial port, no background thread and no CRC or range checks of the reader
(glove.py:139-196, 369-374).  The fake ignores the deployment's left_port/right_port and the SDK's
"at least one port" check (sdk.py:17-18), because the acceptance gate constructs the fake without ports; the
driver's ``hand`` option selects the served hand.  While the reader is "running" each ``get_data`` returns a new
packet with an increasing timestamp; after ``stop`` it returns the last packet (a real glove has no fresh packets
once its reader stops).  The numbers below are placeholders, not measurements or device facts.

The public methods are only the upstream ones.  The underscore attributes are test hooks: ``_starts``,
``_stops``, ``_reads`` and ``_fail`` let ``test_driver.py`` observe the native stop and exercise a native failure.
"""


class _GloveSensorData:
    """The fields of open_cyber_glove.glove.GloveSensorData (glove.py:23-41), without importing upstream."""

    def __init__(self, tensile_data, acc_data, gyro_data, mag_data, temperature, timestamp):
        self.tensile_data = tensile_data
        self.acc_data = acc_data
        self.gyro_data = gyro_data
        self.mag_data = mag_data
        self.temperature = temperature
        self.timestamp = timestamp


# placeholder: synthetic packet values for the fake only, never a measurement
_TENSILE = tuple(index * 101 for index in range(19))       # placeholder
_ACC = (0.0, 0.0, 9.81)                                    # placeholder
_GYRO = (0.01, -0.02, 0.0)                                 # placeholder
_MAG = (24.0, -5.0, 41.0)                                  # placeholder
_TEMPERATURE = 36.5                                        # placeholder
_TIMESTAMP_STEP_US = 5000                                  # placeholder


class FakeOpenCyberGlove:
    def __init__(self, left_port=None, right_port=None, model_path=None, glove_cls=None, **options):
        self.left_port = left_port
        self.right_port = right_port
        self.model = None if model_path is None else model_path
        self._running = False
        self._last = None
        self._sequence = 0
        self._starts = 0
        self._stops = 0
        self._reads = 0
        self._fail = None

    def start(self):
        """The upstream start() opens each configured port and starts its reader (sdk.py:29-37)."""
        self._starts += 1
        self._running = True

    def stop(self):
        """The upstream stop() stops every reader (sdk.py:39-45); the fake keeps its last packet."""
        self._stops += 1
        self._running = False

    def get_data(self, hand_type):
        """The upstream get_data(hand_type) returns the selected glove's latest packet (sdk.py:47-70)."""
        if hand_type not in ("left", "right"):
            raise ValueError(f"Invalid hand type: {hand_type}")
        if self._fail is not None:
            error, self._fail = self._fail, None
            raise error
        if not self._running and self._last is None:
            raise RuntimeError("Serial port not connected.")
        if self._running:
            self._sequence += 1
            self._last = _GloveSensorData(
                tensile_data=_TENSILE,
                acc_data=_ACC,
                gyro_data=_GYRO,
                mag_data=_MAG,
                temperature=_TEMPERATURE,
                timestamp=self._sequence * _TIMESTAMP_STEP_US,   # placeholder
            )
            self._reads += 1
        return self._last

    # -- hooks for test_driver.py (not OpenCyberGlove members; never used by the driver) ------------------------
    def _fail_next_read(self, error):
        """The next get_data raises ``error`` once (a native failure the driver must not hide)."""
        self._fail = error

    def _forget_last(self):
        """Drop the held packet, as a reader that has not received anything yet."""
        self._last = None
