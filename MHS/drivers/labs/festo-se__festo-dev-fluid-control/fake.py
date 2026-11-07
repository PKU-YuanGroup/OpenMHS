"""Fake backend of the Festo pressure-over-liquid driver: an in-memory stand-in for FluidControlSession.

Gate G7: every public method defined here exists on
``fluid_control.cli.session:FluidControlSession`` (get_channels, get_liquid_classes, get_status,
set_pressure, aspirate, dispense, mix).  The session's ``component`` attribute exists on the upstream
class (assigned in its __init__, src/fluid_control/cli/session.py:121) and is a small stand-in for a
Dispenser/Pipettor component: it has the pressure controller, the valve controller and the status the
session delegates to.  Every number and reply below is test data for the fake, not a device fact, and
is marked ``# placeholder``; nothing here talks to hardware.
"""


class _FakePressureControl:
    """Stand-in for the PGVA pressure controller object the component owns."""

    def __init__(self):
        self._pressure = 0  # placeholder: test start pressure in mbar

    def set_output_pressure(self, pressure):
        self._pressure = int(pressure)

    def get_output_pressure(self):
        return self._pressure


class _FakeValveControl:
    """Stand-in for the VAEM valve controller object the component owns."""

    def __init__(self):
        self._selected = []  # placeholder: no valve selected at test start

    def deselect_valve(self, valve_id):
        if valve_id in self._selected:
            self._selected.remove(valve_id)


class _FakeComponent:
    """The part of Dispenser/Pipettor that FluidControlSession reads and stops."""

    def __init__(self):
        self.active_channels = [1, 2]  # placeholder: test channel set
        self.channel_count = 2  # placeholder: test channel count
        self.pressure_control = _FakePressureControl()
        self.valve_control = _FakeValveControl()
        self.fluid_control_status = 0  # placeholder: clear at test start
        self.calibration = {"water": {}, "ethylene-glycol10%": {}}  # placeholder: test liquid classes

    def get_liquid_classes(self):
        return list(self.calibration)

    def get_status(self):
        return {
            "pressure": self.pressure_control.get_output_pressure(),  # placeholder: no PGVA status word
            "valve": {"Readiness": 1},  # placeholder: canned valve status
            "fluid_control_status": self.fluid_control_status,
        }

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.pressure_control.set_output_pressure(0)  # 0 mbar is the neutral value in driver.py's Facts
        self.fluid_control_status = 0  # placeholder: clear after the safe-state exit
        return False


class FakeFestoDevFluidControl:
    """In-memory stand-in for the upstream manual-operation session."""

    def __init__(self, **_options):
        self.component = _FakeComponent()
        self.gantry = None  # placeholder: the fake has no motion gantry
        self.mount_axis_name = "Z"  # placeholder: upstream default test value

    def get_channels(self):
        return list(self.component.active_channels)

    def get_liquid_classes(self):
        return self.component.get_liquid_classes()

    def get_status(self):
        return self.component.get_status()

    def set_pressure(self, pressure_mbar):
        self.component.pressure_control.set_output_pressure(int(pressure_mbar))

    def _check_command(self, channel, volume_ul, liquid_class):
        if int(channel) not in self.component.active_channels:
            raise ValueError(f"channel {channel!r} is not an active channel")
        if float(volume_ul) < 0:
            raise ValueError("volume must be greater than or equal to zero")
        if str(liquid_class) not in self.component.get_liquid_classes():
            raise ValueError(f"liquid class {liquid_class!r} is not configured")

    def aspirate(self, channel, volume_ul, liquid_class):
        self._check_command(channel, volume_ul, liquid_class)
        self.component.fluid_control_status = 2  # placeholder: busy during the operation
        self.component.fluid_control_status = 0  # placeholder: clear after the operation
        return (0, "Aspirate complete")  # placeholder: canned OperationResult

    def dispense(self, channel, volume_ul, liquid_class):
        self._check_command(channel, volume_ul, liquid_class)
        self.component.fluid_control_status = 2  # placeholder: busy during the operation
        self.component.fluid_control_status = 0  # placeholder: clear after the operation
        return (0, "Dispense complete")  # placeholder: canned OperationResult

    def mix(self, channel, volume_ul, liquid_class, cycles):
        self._check_command(channel, volume_ul, liquid_class)
        self.component.fluid_control_status = 2  # placeholder: busy during the operation
        self.component.fluid_control_status = 0  # placeholder: clear after the operation
        return (0, f"Mix complete ({int(cycles)} cycle(s))")  # placeholder: canned OperationResult
