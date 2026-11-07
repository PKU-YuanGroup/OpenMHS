"""Fake backend of the MagScope focus driver: an in-memory stand-in for PythonMicroscopeFocusMotor.

Gate G7: every public method defined here exists on ``magscope.python_microscope:PythonMicroscopeFocusMotor`` (the
adapter itself or its FocusMotorBase base in magscope/hardware.py).  The driver uses only the four motion primitives
the adapter and FocusMotorBase provide: ``move_absolute``, ``get_current_z``, ``get_is_moving`` and
``get_position_limits`` (magscope/python_microscope.py:184-220, magscope/hardware.py:201-215).  Like the adapter, the
fake does not clamp a move: the runtime enforces the declared Z bounds before a call reaches the backend.

Every starting number is test data, not a fact about any stage, and is marked ``# placeholder``.  Nothing here talks
to a device.
"""


class FakeMagscopeFocusMotor:
    """A stage axis that jumps to the commanded position; its limits are fixed test values."""

    def __init__(self, **_options):
        self._position_nm = 0.0        # placeholder: start position in the adapter's nanometre unit
        self._moving = False           # placeholder: the fake settles immediately
        self._lower_nm = -100000.0     # placeholder: lower travel bound in nanometres
        self._upper_nm = 100000.0      # placeholder: upper travel bound in nanometres

    def move_absolute(self, z):
        self._position_nm = float(z)
        self._moving = False

    def get_current_z(self):
        return self._position_nm

    def get_is_moving(self):
        return self._moving

    def get_position_limits(self):
        return (self._lower_nm, self._upper_nm)
