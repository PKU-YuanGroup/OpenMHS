"""Fake backend of the WIL Pycro stage driver: an in-memory stand-in for hardware.stage.

The upstream entry is a module of synchronous functions
(``WIL_Pycro_Control_App/hardware/stage.py#*``), so this fake is a class whose public methods
carry the same names and call shapes: get_x_position/get_y_position/get_z_position take no
argument, set_x_position/set_y_position/set_z_position take one coordinate, wait_for_xy_stage
and wait_for_z_stage take no argument, and reset_stage takes no argument.  Gate G7 checks each
public method against the pinned module.

As upstream, set_x_position and set_y_position truncate the target to int (stage.py:225, 237),
set_z_position keeps it unchanged (stage.py:258) and every read truncates (stage.py:263-293).
The driver never calls reset_stage (model review, 2026-11-05): the e-stop sends nothing, so the
stand-in stays here only to show, in the package tests, that no RESET reaches the backend.

The starting coordinates and the post-RESET coordinates are test data, not device facts.
Nothing here talks to a device, and no motion is simulated beyond an immediate coordinate change.
"""


class FakeStage:
    def __init__(self, **_options):
        # placeholder: arbitrary test starting coordinates
        self._x = 0                 # placeholder
        self._y = 0                 # placeholder
        self._z = 0                 # placeholder

    def get_x_position(self):
        return int(self._x)

    def get_y_position(self):
        return int(self._y)

    def get_z_position(self):
        return int(self._z)

    def set_x_position(self, x_pos):
        self._x = int(x_pos)

    def set_y_position(self, y_pos):
        self._y = int(y_pos)

    def set_z_position(self, z_pos):
        self._z = z_pos

    def wait_for_xy_stage(self):
        return None

    def wait_for_z_stage(self):
        return None

    def reset_stage(self):
        # placeholder: the docstring says RESET resets the origin to the current position
        # (stage.py:323-325), so this stand-in reads 0 afterwards without moving
        self._x = 0                 # placeholder
        self._y = 0                 # placeholder
        self._z = 0                 # placeholder
