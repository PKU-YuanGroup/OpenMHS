"""Fake backend of the Runze ZSB-SY01B package: an in-memory stand-in for the upstream SY01B.

Gate G7: every public method here exists on
``runze_control.multichannel_syringe_pump:SY01B`` (its own methods plus
``MultiChannelSyringePump``, ``SyringePump`` and ``RunzeDevice``), and so does
every public attribute the driver touches.  The state values are test data,
not facts about any pump, and every one of them is marked ``# placeholder``.
Nothing here opens a serial port or talks to a device.
"""


class FakeSY01B:
    def __init__(self, **_options):
        self.ser = None
        self.syringe_volume_ul = 5000            # placeholder
        self.max_position_steps = 6000           # placeholder
        self.max_speed_rpm = 450                 # placeholder
        self.driver_steps = 0                    # placeholder
        self.syringe_speed_percent = 60.0        # placeholder
        self._valve_position = 1                 # placeholder
        self._motor_status = 0                   # placeholder

    # -- reads ------------------------------------------------------------------------------------------------
    def get_position_steps(self):
        return self.driver_steps

    def get_position_ul(self):
        return self.driver_steps * self.syringe_volume_ul / self.max_position_steps

    def get_position_percent(self):
        return self.driver_steps * 100.0 / self.max_position_steps

    def get_address(self):
        return 0                                 # placeholder

    def get_rs232_baudrate(self):
        return 9600                              # placeholder

    def get_firmware_version(self):
        return 0.0                               # placeholder

    def get_motor_status(self):
        return self._motor_status

    def is_busy(self):
        return False

    def get_speed_percent(self):
        return self.syringe_speed_percent

    # -- plunger movement -------------------------------------------------------------------------------------
    def reset_syringe_position(self):
        self.set_speed_percent(60.0)             # placeholder
        self.driver_steps = 0

    def aspirate(self, microliters):
        steps = round(microliters * self.max_position_steps / self.syringe_volume_ul)
        self.aspirate_steps(steps)

    def aspirate_steps(self, steps):
        self.driver_steps += steps

    def dispense(self, microliters):
        steps = round(microliters * self.max_position_steps / self.syringe_volume_ul)
        self.dispense_steps(steps)

    def dispense_steps(self, steps):
        self.driver_steps -= steps

    def move_absolute_in_steps(self, steps):
        self.driver_steps = steps

    def move_absolute_in_percent(self, percent):
        self.driver_steps = round(percent / 100.0 * self.max_position_steps)

    def set_speed_percent(self, percent):
        if percent > 100 or percent < 0:
            raise ValueError("speed percent out of range")
        self.syringe_speed_percent = percent

    # -- valve and stop ---------------------------------------------------------------------------------------
    def move_valve_to_position(self, position):
        self._valve_position = position

    def force_stop(self):
        self._motor_status = 0                   # placeholder
