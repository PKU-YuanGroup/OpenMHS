"""Fake backend of the IKA RET control-visc driver: an in-memory stand-in for IKARETControlVisc.

Gate G7: every public method and property defined here exists on
``Stirrer.IKA_RET_Control_Visc:IKARETControlVisc`` (including the inherited ``SerialDevice`` members).  The class
mirrors the upstream shape: each numeric answer is a ``(value, status)`` pair like the ``valueanswer`` pattern
produces (``Stirrer/IKA_RET_Control_Visc.py:79``), the temperature and stirrer set points are properties with a
setter (``Stirrer/IKA_RET_Control_Visc.py:127-157`` and ``:165-187``), and the start/stop functions are plain
methods.  The values never move by themselves; the state changes only through the setters and commands, so reading
twice gives the same state.  Nothing here talks to a device.

Every number below is test data, not a fact about the instrument; each line is marked ``# placeholder``.
"""


class FakeIKARETControlVisc:
    def __init__(self, **_options):
        self._medium_temperature = 25.0         # placeholder
        self._hot_plate_temperature = 24.0      # placeholder
        self._medium_setpoint = 25.0            # placeholder
        self._hot_plate_setpoint = 25.0         # placeholder
        self._heat_transfer_setpoint = 25.0     # placeholder
        self._safety_setpoint = 50.0            # placeholder
        self._stir_rate = 0.0                   # placeholder
        self._stir_rate_setpoint = 0.0          # placeholder
        self._ph = 7.0                          # placeholder
        self._weight = 0.0                      # placeholder
        self._heater_running = False            # placeholder
        self._stirrer_running = False           # placeholder
        self._ph_meter_running = False          # placeholder
        self._weighing_running = False          # placeholder
        self._closed = False                    # placeholder

    # -- sensor 1 (medium / external temperature) ---------------------------------------------------------------
    @property
    def temperature_pv(self):
        return (f"{self._medium_temperature:.2f}", "0")     # placeholder

    @property
    def temperature_sp(self):
        return (f"{self._medium_setpoint:.2f}", "0")        # placeholder

    @temperature_sp.setter
    def temperature_sp(self, value):
        self._medium_setpoint = float(value)

    # -- stirrer -------------------------------------------------------------------------------------------------
    @property
    def stir_rate_pv(self):
        return (f"{self._stir_rate:.2f}", "0")              # placeholder

    @property
    def stir_rate_sp(self):
        return (f"{self._stir_rate_setpoint:.2f}", "0")     # placeholder

    @stir_rate_sp.setter
    def stir_rate_sp(self, value):
        self._stir_rate_setpoint = float(int(value))

    # -- sensor 2 (hot plate) and heat-transfer medium -----------------------------------------------------------
    @property
    def temperature_hot_plate_pv(self):
        return (f"{self._hot_plate_temperature:.2f}", "0")  # placeholder

    @property
    def temperature_hot_plate_sp(self):
        return (f"{self._hot_plate_setpoint:.2f}", "0")     # placeholder

    @temperature_hot_plate_sp.setter
    def temperature_hot_plate_sp(self, value):
        self._hot_plate_setpoint = float(value)

    @property
    def temperature_heat_transfer_medium_sp(self):
        return (f"{self._heat_transfer_setpoint:.2f}", "0")  # placeholder

    @property
    def temperature_hot_plate_safety_sp(self):
        return (f"{self._safety_setpoint:.2f}", "0")        # placeholder

    # -- pH and weighing -----------------------------------------------------------------------------------------
    def get_ph(self):
        return (f"{self._ph:.2f}", "0")                     # placeholder

    def get_weight(self):
        return (f"{self._weight:.2f}", "0")                 # placeholder

    # -- commands ------------------------------------------------------------------------------------------------
    def start_heater(self):
        self._heater_running = True
        return True

    def stop_heater(self):
        self._heater_running = False
        return True

    def start_stirrer(self):
        self._stirrer_running = True
        return True

    def stop_stirrer(self):
        self._stirrer_running = False
        return True

    def start_ph_meter(self):
        self._ph_meter_running = True
        return True

    def stop_ph_meter(self):
        self._ph_meter_running = False
        return True

    def start_weighing(self):
        self._weighing_running = True
        return True

    def stop_weighing(self):
        self._weighing_running = False
        return True

    def reset_hot_plate(self):
        self._medium_setpoint = 25.0            # placeholder
        self._hot_plate_setpoint = 25.0         # placeholder
        self._stir_rate_setpoint = 0.0          # placeholder
        return True

    def close_connection(self):
        self._closed = True
        return True
