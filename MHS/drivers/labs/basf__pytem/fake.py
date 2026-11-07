"""Fake backend of the pyTEM driver: an in-memory stand-in for pyTEM.Interface:Interface.

Gate G7: every public method defined here is a method of the upstream Interface class, inherited from one of its
mixins (StageMixin, BeamBlankerMixin, ScreenMixin, VacuumMixin, ModeMixin) and reached through Interface.py:34-43.
The fake keeps the same public method names and argument names as the upstream, returns the same value shapes, and
never imports pyTEM or touches a device.  All starting values are test data (# placeholder): the clone does not state
a particular stage position, vacuum pressure or screen state, and none of them appears in a Fact or a Limit.
"""

import math


class FakeInterface:
    def __init__(self, **_options):
        self._x = 12.5                      # placeholder
        self._y = -8.0                      # placeholder
        self._z = 4.0                       # placeholder
        self._alpha = 1.5                   # placeholder
        self._beta = -0.5                   # placeholder
        self._beam_blanked = False          # placeholder
        self._screen_position = "retracted"  # placeholder
        self._column_valve_open = True      # placeholder
        self._mode = "TEM"                  # placeholder
        self._projection_mode = "imaging"   # placeholder
        self._illumination_mode = "microprobe"  # placeholder
        self._column_vacuum_pa = 1.0e-5     # placeholder
        self._accelerator_vacuum_pa = 2.0e-6  # placeholder

    # -- stage (StageMixin) ---------------------------------------------------------------------------------------
    def get_stage_position_x(self):
        return self._x

    def set_stage_position_x(self, x, speed=1.0, movement_type="go"):
        self._x = float(x)

    def get_stage_position_y(self):
        return self._y

    def set_stage_position_y(self, y, speed=1.0, movement_type="go"):
        self._y = float(y)

    def get_stage_position_z(self):
        return self._z

    def set_stage_position_z(self, z, speed=1.0, movement_type="go"):
        self._z = float(z)

    def get_stage_position_alpha(self):
        return self._alpha

    def set_stage_position_alpha(self, alpha, speed=1.0, movement_type="go"):
        self._alpha = float(alpha)

    def get_stage_position_beta(self):
        return self._beta

    def set_stage_position_beta(self, beta, speed=1.0, movement_type="go"):
        self._beta = float(beta)

    def reset_stage_position(self):
        self._x = 0.0
        self._y = 0.0
        self._z = 0.0
        self._alpha = 0.0
        self._beta = 0.0

    def stage_is_home(self, threshold=0.1):
        # threshold is the upstream default (StageMixin.py:404); the comparison mirrors StageMixin.py:413-415,
        # including its use of < instead of abs().
        return (self.get_stage_position_x() < threshold and self.get_stage_position_y() < threshold
                and self.get_stage_position_z() < threshold and self.get_stage_position_alpha() < threshold
                and self.get_stage_position_beta() < threshold)

    # -- beam blanker (BeamBlankerMixin) --------------------------------------------------------------------------
    def beam_is_blank(self):
        return self._beam_blanked

    def blank_beam(self):
        self._beam_blanked = True

    # -- screen (ScreenMixin) -------------------------------------------------------------------------------------
    def get_screen_position(self):
        return self._screen_position

    def insert_screen(self):
        self._screen_position = "inserted"

    # -- vacuum (VacuumMixin) -------------------------------------------------------------------------------------
    def get_column_valve_position(self):
        return "open" if self._column_valve_open else "closed"

    def close_column_valve(self):
        self._column_valve_open = False

    @staticmethod
    def _as_pressure(units, pascals, log_value):
        units = str(units).lower()
        if units in {"pascal", "pascals"}:
            return pascals
        if units in {"log", "logs"}:
            return log_value
        return math.nan

    def get_column_vacuum(self, units="log"):
        log_value = math.log10(self._column_vacuum_pa) if self._column_vacuum_pa > 0 else -math.inf
        return self._as_pressure(units, self._column_vacuum_pa, log_value)

    def get_accelerator_vacuum(self, units="log"):
        log_value = math.log10(self._accelerator_vacuum_pa) if self._accelerator_vacuum_pa > 0 else -math.inf
        return self._as_pressure(units, self._accelerator_vacuum_pa, log_value)

    # -- modes (ModeMixin) ----------------------------------------------------------------------------------------
    def get_mode(self):
        return self._mode

    def get_projection_mode(self):
        return self._projection_mode

    def get_illumination_mode(self):
        return self._illumination_mode

    # -- the native safe state (Interface.make_safe) --------------------------------------------------------------
    def make_safe(self):
        self.close_column_valve()
        self.blank_beam()
        self.insert_screen()
