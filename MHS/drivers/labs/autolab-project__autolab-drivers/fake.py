"""Fake backend of the Anritsu MS2830A driver: an in-memory stand-in for Driver_VISA.

Gate G7: every public method defined on ``FakeMS2830A`` exists on the upstream
anritsu_MS2830A.anritsu_MS2830A:Driver_VISA class or its base ``Driver`` (get_id and the marker powers,
anritsu_MS2830A/anritsu_MS2830A.py:31-46; the timeout, anritsu_MS2830A/anritsu_MS2830A.py:62-67; query and write,
anritsu_MS2830A/anritsu_MS2830A.py:150-153).  The ``frequency`` attribute is set by the upstream ``Driver.__init__``
(anritsu_MS2830A/anritsu_MS2830A.py:24) and the helper below mirrors the upstream ``Frequency`` methods
(anritsu_MS2830A/anritsu_MS2830A.py:166-212).  The values are test data only, not facts: every one is marked
``# placeholder``.  A value never moves by itself, so reading the state twice gives the same state.  Nothing here
talks to a device or opens a VISA resource.
"""


class _FakeController:
    """The pyvisa resource the upstream Driver_VISA stores in ``self.controller``; only its timeout is used."""

    def __init__(self):
        self.timeout = 3000.0          # placeholder: the pyvisa default the upstream constructor sets


class _FakeFrequency:
    """The upstream ``Frequency`` module: the sweep-window and point settings the driver reads and writes."""

    def __init__(self, dev):
        self.dev = dev

    def get_frequency_start(self):
        return self.dev._frequency_start

    def set_frequency_start(self, value):
        self.dev._frequency_start = float(value)

    def get_frequency_stop(self):
        return self.dev._frequency_stop

    def set_frequency_stop(self, value):
        self.dev._frequency_stop = float(value)

    def get_frequency_step(self):
        return self.dev._frequency_step

    def set_frequency_step(self, value):
        self.dev._frequency_step = float(value)

    def get_frequency_span(self):
        return self.dev._frequency_span

    def set_frequency_span(self, value):
        self.dev._frequency_span = float(value)

    def get_frequency_center(self):
        return self.dev._frequency_center

    def set_frequency_center(self, value):
        self.dev._frequency_center = float(value)
        self.dev.query("*OPC?")        # the upstream setter waits for the operation to complete

    def get_points(self):
        return self.dev._points

    def set_points(self, value):
        self.dev._points = int(value)


class FakeMS2830A:
    """An in-memory MS2830A: plain attributes, no SCPI transport and no hardware."""

    def __init__(self, **_options):
        self.controller = _FakeController()
        self.frequency = _FakeFrequency(self)
        self._idn = "Anritsu,MS2830A,0000000000,1.00"   # placeholder
        self._power_1 = -30.0                           # placeholder
        self._power_2 = -40.0                           # placeholder
        self._power_3 = -50.0                           # placeholder
        self._frequency_start = 0.1                     # placeholder, GHz
        self._frequency_stop = 1.0                      # placeholder, GHz
        self._frequency_step = 1000000.0                # placeholder, Hz
        self._frequency_span = 0.9                      # placeholder, GHz
        self._frequency_center = 0.55                   # placeholder, GHz
        self._points = 1001                             # placeholder
        self._continuous = True                         # placeholder

    def get_id(self):
        return self._idn

    def get_power_marker_1(self):
        return self._power_1

    def get_power_marker_2(self):
        return self._power_2

    def get_power_marker_3(self):
        return self._power_3

    def get_timeout(self):
        return float(self.controller.timeout)

    def set_timeout(self, value):
        self.controller.timeout = float(value)

    def query(self, command):
        if command == "*OPC?":
            return "1"                    # placeholder
        return "0"                        # placeholder: no other query is used by this package

    def write(self, command):
        if command == "INIT:CONT OFF":
            self._continuous = False
        elif command == "INIT:CONT ON":
            self._continuous = True
