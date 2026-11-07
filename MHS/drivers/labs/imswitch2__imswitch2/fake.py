"""Fake backend of the ImSwitch2 Standa rotation mount: an in-memory stand-in for StandaRotatorManager.

Gate G7: every public member defined here exists on
``imswitch.imcontrol.model.managers.rotators.StandaRotatorManager:StandaRotatorManager`` at the pinned commit:
``get_pos`` (StandaRotatorManager.py:29-30), ``move_abs`` (StandaRotatorManager.py:36-38), ``stop_cont_rot``
(StandaRotatorManager.py:50-51), ``close`` (StandaRotatorManager.py:68-69) and the inherited ``position`` property
(RotatorManager.py:27-30).  The fake keeps the manager's published state: ``get_pos`` returns ``None`` like the
upstream method and the position is read through the property; the position is in degrees, the unit the upstream
manager receives from the motor (StandaRotatorManager.py:29-30) and the widget documents
(RotatorWidget.py:80-91).

The upstream manager talks to a StandaMotor and libximc; the fake does neither and has no motion over time, no
speed, no continuous rotation and no controller errors.  The native stop is recorded in ``_commands`` so a test
can see that the driver reached it.  Nothing here talks to a device.

The starting position is placeholder test data, not a fact about a mount.
"""


class FakeStandaRotator:
    def __init__(self, rotatorInfo=None, name="rotator", *args, **_options):
        # placeholder: a rotation mount can be anywhere when the driver starts
        self._position = 0.0
        # placeholder: the fake starts with the axis not stopped by this driver
        self._stopped = False
        self._closed = False
        self._commands = []
        # The constructor arguments are accepted for the manager's signature and not used by the model.
        del rotatorInfo, name, args

    @property
    def position(self):
        """The position the upstream base class returns (RotatorManager.py:27-30)."""
        return self._position

    def get_pos(self):
        """Refresh the position from the motor; the upstream manager returns None (StandaRotatorManager.py:29-30)."""
        self._commands.append("get_pos")
        return None

    def move_abs(self, move_pos):
        """Command an absolute move; the model lands on the target immediately (StandaRotatorManager.py:36-38)."""
        self._commands.append("move_abs")
        self._position = float(move_pos)

    def stop_cont_rot(self):
        """The native stop: command_sstp in the upstream StandaMotor (StandaRotatorManager.py:50-51)."""
        self._commands.append("stop_cont_rot")
        self._stopped = True

    def close(self):
        """Close the controller (StandaRotatorManager.py:68-69)."""
        self._commands.append("close")
        self._closed = True
