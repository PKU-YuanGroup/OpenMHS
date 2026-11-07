"""Fake backend of the IKA RET Control Visc driver: an in-memory stand-in for IKARETControlVisc.

Gate G7: every public method and property defined here exists on
``platform_server.modules.serial_labware.IKA_RET_Stirrer.IKA_RET_Control_Visc:IKARETControlVisc``.  The upstream
value replies come from ``valueanswer`` (a list of two captured strings: the number and a status code), so the
properties here return the same two-item list shape.  The starting values are test data, not facts: every one is
marked ``# placeholder`` and none is used in a Fact, a Limit or a reference.  The values never move by themselves,
so two reads give the same state.  Nothing here talks to a device.
"""


class FakeIKARETControlVisc:
    def __init__(self, **_options):
        self._medium = 21.5            # placeholder: sensor-1 process value in degC
        self._temperature_sp = 25.0    # placeholder: sensor-1 set point in degC
        self._stir_rate = 0.0          # placeholder: stirrer process value in rpm
        self._stir_rate_sp = 300.0     # placeholder: stirrer set point in rpm
        self._ph = 7.00                # placeholder: pH process value

    @property
    def temperature_pv(self):
        return ["{0:.2f}".format(self._medium), "0"]        # placeholder status code

    @property
    def temperature_sp(self):
        return ["{0:.2f}".format(self._temperature_sp), "0"]   # placeholder status code

    @temperature_sp.setter
    def temperature_sp(self, temperature):
        self._temperature_sp = float(temperature)

    @property
    def stir_rate_pv(self):
        return ["{0:.2f}".format(self._stir_rate), "0"]     # placeholder status code

    @property
    def stir_rate_sp(self):
        return ["{0:.2f}".format(self._stir_rate_sp), "0"]  # placeholder status code

    @stir_rate_sp.setter
    def stir_rate_sp(self, stir_rate):
        self._stir_rate_sp = float(int(float(stir_rate)))   # the upstream setter converts with int()

    def start_heater(self):
        return True

    def stop_heater(self):
        return True

    def start_stirrer(self):
        return True

    def stop_stirrer(self):
        return True

    def get_ph(self):
        return ["{0:.2f}".format(self._ph), "0"]            # placeholder status code
