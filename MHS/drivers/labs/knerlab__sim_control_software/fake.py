"""Fake backend of the knerlab motorized polarizer: an in-memory stand-in for the upstream A8MRU class.

The upstream A8MRU class (motorized_pol_v2.py:23) is the controller wrapper; this fake implements only the members
the driver uses, and every one of them exists on A8MRU at the pinned commit: getCurPos (motorized_pol_v2.py:101-105),
MoveAbs (motorized_pol_v2.py:64-69), Stop (motorized_pol_v2.py:133-135) and close (motorized_pol_v2.py:92-94).

The upstream class sends USMC_Start and USMC_Stop through USMCDLL.dll; the fake does neither and keeps the angle in
degrees, the unit the upstream class publishes and accepts.  It has no motion over time, no speed, no limit switches
and no controller errors.  The calls it received are kept in ``_commands`` so a test can see that the driver reached
the native stop.  Nothing here talks to a device.

The starting position and the recorded calls are placeholder test data, not facts about a polarizer.
"""


class FakeA8MRU:
    def __init__(self, **_options):
        # placeholder: the polarizer can be anywhere when the driver starts
        self._position_deg = 0.0
        # placeholder: the fake starts with motion stopped and the connection open
        self._stopped = False
        self._closed = False
        self._commands = []

    def getCurPos(self):
        """Return the current angle in degrees (the upstream converts the controller's CurPos)."""
        self._commands.append("getCurPos")
        return self._position_deg

    def MoveAbs(self, pos):
        """Command an absolute move in degrees; the model lands on the target immediately."""
        self._commands.append(("MoveAbs", float(pos)))
        self._position_deg = float(pos)

    def Stop(self):
        """The native stop: USMC_Stop in the upstream class."""
        self._commands.append("Stop")
        self._stopped = True

    def close(self):
        self._commands.append("close")
        self._closed = True
