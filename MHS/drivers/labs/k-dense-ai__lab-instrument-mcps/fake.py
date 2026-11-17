"""Fake backend of the JULABO driver: an in-memory stand-in for labmcp_julabo.driver:JulaboCirculator.

Gate G7: every public method defined here exists on JulaboCirculator in
servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py.  The method names and
arguments follow the upstream object: the reads query the same in_pv_* / in_sp_00 /
in_mode_05 values, set_setpoint writes out_sp_00, start and stop write out_mode_05 1/0
and stop reports whether in_mode_05 confirms it.  This is not a recording and not the
upstream simulator: it holds a fixed state and never moves by itself, so two reads
return the same values.  Every number and canned reply below is test data, marked
``# placeholder``; none is a fact or a limit.  ``stop_confirmed=False`` is a test
option that models a device which never confirms ``out_mode_05 0``.
"""


class _FakeStatus:
    """The attributes of the upstream Status object that a caller of this fake can see."""

    def __init__(self, code: int, text: str, kind: str = "state", meaning: str = "") -> None:
        self.code = code
        self.text = text
        self.kind = kind
        self.meaning = meaning

    @property
    def label(self) -> str:
        return f"{self.code:03d} {self.text}" if self.code < 0 else f"{self.code:02d} {self.text}"


class FakeJulaboCirculator:
    def __init__(self, **_options):
        self._temperature_c = 21.5       # placeholder: a bath temperature in Cel
        self._heating_power_pct = 0.0    # placeholder: actuating variable in percent
        self._safety_sensor_c = 21.8     # placeholder: safety-sensor temperature in Cel
        self._excess_protection_c = 120.0  # placeholder: high-temperature protection setting in Cel
        self._setpoint_c = 20.0          # placeholder: the stored set point in Cel
        self._running = False            # placeholder: temperature control stopped
        self._closed = False
        # test hook: False models a circulator that never confirms out_mode_05 0
        self._stop_confirmed = bool(_options.get("stop_confirmed", True))

    # -- identity / status ---------------------------------------------------------------------------------------
    def version(self) -> str:
        return "JULABO MAGIO MS-1000F VERSION 1.1.2"  # placeholder: canned firmware string

    def query(self, cmd: str, timeout: float | None = None) -> str:
        cmd = cmd.strip().lower()
        if cmd == "status":
            return "03 REMOTE START" if self._running else "02 REMOTE STOP"  # placeholder: canned status line
        raise ValueError(f"the fake does not answer {cmd!r}")  # placeholder: an unsupported command

    # -- readings ------------------------------------------------------------------------------------------------
    def bath_temperature_c(self) -> float:
        return self._temperature_c

    def heating_power_pct(self) -> float:
        return self._heating_power_pct

    def safety_sensor_temperature_c(self) -> float:
        return self._safety_sensor_c

    def excess_temperature_protection_c(self) -> float:
        return self._excess_protection_c

    def setpoint_c(self) -> float:
        return self._setpoint_c

    def is_running(self) -> bool:
        return self._running

    # -- control -------------------------------------------------------------------------------------------------
    def set_setpoint(self, celsius: float) -> _FakeStatus:
        self._setpoint_c = round(float(celsius), 2)
        return _FakeStatus(3 if self._running else 2,  # placeholder: canned status codes and text
                           "REMOTE START" if self._running else "REMOTE STOP")

    def start(self) -> _FakeStatus:
        self._running = True
        return _FakeStatus(3, "REMOTE START")  # placeholder: canned status text

    def stop(self) -> bool:
        if not self._stop_confirmed:
            return False
        self._running = False
        return True

    def close(self) -> None:
        self._closed = True
