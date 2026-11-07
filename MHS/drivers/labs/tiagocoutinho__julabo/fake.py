"""Fake backend of the Julabo driver: an in-memory stand-in for julabo.device:JulaboCF.

Gate G7: every public method defined here exists on julabo.device:JulaboCF (BaseJulabo and BaseJulaboCirculator in
julabo/device.py), and the one other attribute the driver reaches, ``protocol``, is set by the upstream __init__
(julabo/device.py:105).  Like the upstream class on an asyncio connection, each method is a coroutine function, and
set_point_1(value=None) reads without a value and writes with one (julabo/device.py:30-34).  The starting values are
the defaults of the upstream simulator (julabo/simulator.py:39-81) and a set point is kept with two decimals like the
upstream encoder (julabo/device.py:48).  The values never move by themselves, so reading the state twice gives the
same state.  Nothing here talks to a device.
"""


class _FakeConnection:
    """The connection object a real device owns (``device.protocol.conn``); the driver only closes it."""

    def __init__(self):
        self.is_open = True

    async def close(self):
        self.is_open = False


class _FakeProtocol:
    def __init__(self):
        self.conn = _FakeConnection()


class FakeJulaboCF:
    def __init__(self, **_options):
        self.protocol = _FakeProtocol()
        self._bath = 29.45          # julabo/simulator.py:76 (PV_00)
        self._external = 28.22      # julabo/simulator.py:78 (PV_02)
        self._setpoint = 30.0       # julabo/simulator.py:46 (SP_00)
        self._channel = 1           # julabo/simulator.py:40 (MODE_01 "0" is channel 1, julabo/device.py:139)
        self._running = False       # julabo/simulator.py:44 (MODE_05 "0")

    async def bath_temperature(self):
        return self._bath

    async def external_temperature(self):
        return self._external

    async def set_point_1(self, value=None):
        if value is None:
            return self._setpoint
        self._setpoint = float(f"{float(value):.2f}")

    async def active_set_point_channel(self):
        return self._channel

    async def is_started(self):
        return self._running

    async def status(self):
        # the simulator answers a start/stop command with these two lines (julabo/simulator.py:94)
        return "03 REMOTE START" if self._running else "02 REMOTE STOP"

    async def start(self):
        self._running = True

    async def stop(self):
        self._running = False
