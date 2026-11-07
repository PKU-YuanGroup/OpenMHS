"""Deterministic Modbus register fake of a Hanmatek HM supply for the labmastro TagDriver.

It answers only the holding registers the package declares, applies a write
of the output register 0x0001 to its own read-back (as power_on/power_off
followed by get_power_status do upstream) and lets the displayed voltage and
current follow the setpoints while the output is on. Every number below is
test data, not a device fact; the fake models no load, regulation, slew rate,
protection trip or Modbus exception of a real unit.
"""

from mhs.bridge.tag_fake import RecordingTagTransport

OUTPUT, VOLTAGE, CURRENT = 0x0001, 0x0010, 0x0011
VOLTAGE_SET, CURRENT_SET, OVP, OCP = 0x0030, 0x0031, 0x0020, 0x0021


class FakeHanmatek(RecordingTagTransport):
    def __init__(self, **_options):
        super().__init__("modbus")
        self.registers.update({
            ("holding", OUTPUT): 0,          # placeholder: output off
            ("holding", VOLTAGE): 0,         # placeholder display word
            ("holding", CURRENT): 0,         # placeholder display word
            ("holding", VOLTAGE_SET): 500,   # placeholder setpoint word
            ("holding", CURRENT_SET): 100,   # placeholder setpoint word
            ("holding", OVP): 600,           # placeholder protection word
            ("holding", OCP): 200,           # placeholder protection word
        })
        self.load_ohms = 50                  # placeholder resistive load for the display words

    def on_write(self, request, raw):
        self._settle()

    def _settle(self):
        """Displayed words follow the setpoints while the output is on (placeholder model, not regulation)."""
        if self.registers[("holding", OUTPUT)] == 1:
            volts_word = self.registers[("holding", VOLTAGE_SET)]
            self.registers[("holding", VOLTAGE)] = volts_word
            amps_word = min(self.registers[("holding", CURRENT_SET)], (volts_word * 10) // self.load_ohms)
            self.registers[("holding", CURRENT)] = amps_word
        else:
            self.registers[("holding", VOLTAGE)] = 0
            self.registers[("holding", CURRENT)] = 0
