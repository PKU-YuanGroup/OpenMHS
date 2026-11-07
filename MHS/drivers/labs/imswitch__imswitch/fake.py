"""Fake backend of the ImSwitch Standa rotation mount: an in-memory stand-in for StandaMotor.

The upstream class StandaMotor is the controller interface; this fake models only the members the driver uses,
and every one of them exists on StandaMotor at the pinned commit: get_pos (standamotor.py:85-90), moveabs
(standamotor.py:97-100), wait_for_stop (standamotor.py:102-103), stop_cont_rot (standamotor.py:149-150) and close
(standamotor.py:52-54).  The position is kept in degrees, the unit the upstream class publishes and accepts.

The upstream class converts degrees to steps and microsteps and talks to libximc; the fake does neither.  It has no
motion over time, no speed, no continuous rotation and no controller errors.  The commands it received are kept in
``_commands`` so a test can see that the driver reached the native stop.  Nothing here talks to a device.

The starting position is placeholder test data, not a fact about a mount.
"""


class FakeStandaMotor:
    def __init__(self, motor_index=None, lib_loc=None, steps_per_turn=None, microsteps_per_step=None, **_options):
        # placeholder: a rotation mount can be anywhere when the driver starts
        self._position_deg = 0.0
        # placeholder: the fake starts with the axis not stopped by this driver
        self._stopped = False
        self._closed = False
        self._commands = []
        # The constructor options are accepted and not used by the model.
        del motor_index, lib_loc, steps_per_turn, microsteps_per_step

    def get_pos(self):
        """Return the current angle in degrees (the upstream returns dist_translate_inv of steps and microsteps)."""
        self._commands.append("get_pos")
        return self._position_deg

    def moveabs(self, pos_move):
        """Command an absolute move; the model lands on the target immediately."""
        self._commands.append("moveabs")
        self._position_deg = float(pos_move)

    def wait_for_stop(self, interval=100):
        """The model has no motion to wait for."""
        self._commands.append("wait_for_stop")

    def stop_cont_rot(self):
        """The native stop: command_sstp in the upstream class."""
        self._commands.append("stop_cont_rot")
        self._stopped = True

    def close(self):
        self._commands.append("close")
        self._closed = True
