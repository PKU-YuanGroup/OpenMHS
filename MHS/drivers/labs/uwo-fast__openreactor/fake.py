"""Fake backend of the RLHT heater driver: an in-memory stand-in for openreactor.rlht:RlhtSlice.

Gate G7: every public method defined here exists on
``openreactor.rlht:RlhtSlice`` -- ``status``, ``set_setpoint`` and
``send_safe``.  The upstream class holds the wanted setpoints in
``setpoints_deci`` (tenths of a degree), and ``status()`` reports them as
``desired_c`` together with the slice state and both outputs
(src/openreactor/rlht.py:410-467).  The values below are test data, not
facts about any board: they are marked ``# placeholder`` and move only when
a setpoint is written or the safe state is sent.  Nothing here opens a bus
or talks to a device.
"""


class _Output:
    """One heater output as SliceStatus reports it (src/openreactor/rlht.py:104-118)."""

    def __init__(self, output, tc, temperature_c, setpoint_c, on_ms, period_ms):
        self.output = output
        self.channel = None
        self.tc = tc
        self.temperature_c = temperature_c
        self.setpoint_c = setpoint_c
        self.on_ms = on_ms
        self.period_ms = period_ms


class _Watchdog:
    """The watchdog fields SliceStatus carries (src/openreactor/rlht.py:121-126)."""

    def __init__(self):
        self.armed = True       # placeholder
        self.timeout_ms = 5000  # placeholder
        self.tripped = False    # placeholder
        self.trip_count = 0     # placeholder


class _Status:
    """The fields the driver reads from SliceStatus (src/openreactor/rlht.py:129-143)."""

    def __init__(self, name, address, state, version, caps, mode, estop, outputs, watchdog, desired_c):
        self.name = name
        self.address = address
        self.state = state
        self.version = version
        self.caps = caps
        self.mode = mode
        self.estop = estop
        self.outputs = outputs
        self.watchdog = watchdog
        self.desired_c = desired_c


class FakeRlhtSlice:
    def __init__(self, **_options):
        self.name = "heater"             # placeholder
        self.address = 0x0A              # placeholder
        self.state = "ok"                # placeholder
        self.version = "RLHT 1.0.0, CRUMBS 0.15.0"  # placeholder
        self.caps = 0x7F                 # placeholder
        self.mode = "closed loop"        # placeholder
        self.estop = False               # placeholder
        # The backend factory starts the slice, whose start-up leaves the
        # wanted setpoints at zero (src/openreactor/rlht.py:320, 404).
        self._setpoints = [0.0, 0.0]     # placeholder
        self._outputs = [
            _Output(1, 1, 21.5, 0.0, 0, 1000),  # placeholder
            _Output(2, 2, 20.8, 0.0, 0, 1000),  # placeholder
        ]
        self._watchdog = _Watchdog()

    def status(self, why=None):
        return _Status(
            self.name,
            self.address,
            why if why is not None else self.state,
            self.version,
            self.caps,
            self.mode,
            self.estop,
            tuple(self._outputs),
            self._watchdog,
            (self._setpoints[0], self._setpoints[1]),
        )

    def set_setpoint(self, output, deci):
        if output not in (1, 2):
            raise ValueError(f"RLHT output must be 1 or 2, got {output!r}")
        value = deci / 10
        self._setpoints[output - 1] = value
        self._outputs[output - 1].setpoint_c = value

    def send_safe(self):
        self._setpoints = [0.0, 0.0]
        for output in self._outputs:
            output.setpoint_c = 0.0
            output.on_ms = 0
