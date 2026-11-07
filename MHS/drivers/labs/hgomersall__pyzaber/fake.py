"""Fake backend of the pyzaber driver: an in-memory stand-in for ``pyzaber.linear_slides:multiaxis_linear_slides``.

Gate G7: every public method defined here (``get_current_position``, ``move_absolute``, ``home`` and
``emergency_stop``) is a command of the upstream class (``pyzaber/zaber_device.py:163-196`` resolves the generated
commands and ``389-405`` defines the stop), and the driver touches nothing else.  The fake keeps the three axis
positions in memory and applies a move or a home to them, so the change is visible to the next position read and the
runtime's state hash changes.

The clone has no simulator for this class that can serve the driver: its ``dummy_linear_slides.py`` has
``get_current_position`` and ``move_absolute`` but no ``home`` and no ``emergency_stop`` (``dummy_linear_slides.py:9-29``),
so a package fake is used.  Every number below is test data (# placeholder), not a fact about a stage.  Nothing here
opens a serial port or moves anything.
"""

#: Test start positions in millimetres (# placeholder: not a fact of the device).
START_POSITIONS = {"x": 10.0, "y": 20.0, "z": 30.0}  # placeholder

#: Test home position in millimetres (# placeholder: the Zaber home switch sets the real reference).
HOME_POSITIONS = {"x": 0.0, "y": 0.0, "z": 0.0}  # placeholder


class FakePyzaber:
    def __init__(self, **_options):
        self._positions = dict(START_POSITIONS)  # placeholder
        self._stop_calls = 0  # placeholder: no stop was sent yet

    # -- position ------------------------------------------------------------------------------------------------
    def get_current_position(self):
        return dict(self._positions)

    def move_absolute(self, positions, blocking=False):
        for axis, value in positions.items():
            if axis not in self._positions:
                raise KeyError(axis)
            self._positions[axis] = float(value)
        return None

    def home(self):
        for axis in self._positions:
            self._positions[axis] = float(HOME_POSITIONS[axis])  # placeholder: the reference position
        return None

    # -- safety --------------------------------------------------------------------------------------------------
    def emergency_stop(self):
        self._stop_calls += 1
        return None
