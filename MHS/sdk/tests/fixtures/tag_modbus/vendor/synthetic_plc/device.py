"""Synthetic register map used only by the OpenMHS tag-bridge SDK tests (original text, never executed)."""


class SyntheticPlc:
    """A made-up heater controller: every number here is test data."""

    def __init__(self, client, unit=1):
        self.client = client
        self.unit = unit

    def heater_enabled(self):
        return self.client.read_coils(0, 1)  # coil 0: heater enable

    def set_heater(self, on):
        self.client.write_coil(0, bool(on))  # coil 0

    def door_closed(self):
        return self.client.read_discrete_inputs(10, 1)  # discrete input 10

    def temperature(self):
        return self.client.read_input_registers(100, 1)  # input register 100, signed tenths of a degree

    def set_setpoint(self, value):
        self.client.write_register(200, int(value * 10))  # holding register 200, tenths of a degree

    def counter(self):
        return self.client.read_holding_registers(300, 2)  # holding 300-301, unsigned 32-bit, high word first

    def flow(self):
        return self.client.read_input_registers(400, 2)  # input 400-401, float32, low word first

    def mode(self):
        return self.client.read_holding_registers(500, 1)  # holding register 500, mode word

    def set_mode(self, mode):
        self.client.write_register(500, mode)  # holding register 500
