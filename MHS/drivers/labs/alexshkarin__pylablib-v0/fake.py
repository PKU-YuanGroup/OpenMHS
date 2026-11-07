"""Fake backend of the AWG33220A driver: an in-memory stand-in for the upstream class.

Gate G7 compares every public method defined here with ``AWG33220A`` in
``pylablib/aux_libs/devices/AgilentElectronics.py``; each one is a method of that class.  The class state is kept in
private attributes, so it adds no public member.  Every number and name below is test data, not a device fact: the
starting values are marked ``# placeholder`` and are never copied into a Fact, a Limit or the reference.  The setters
return the same read-back the upstream method returns (for example ``set_amplitude`` returns ``get_amplitude``); the
offset setter returns ``None`` like the upstream write-only SCPI command.  Nothing here talks to a device.
"""


class FakeAwg33220A:
    def __init__(self, **_options):
        self._amplitude = 0.5          # placeholder
        self._frequency = 1000.0       # placeholder
        self._offset = 0.0             # placeholder
        self._phase = 0.0              # placeholder
        self._function = "sine"        # placeholder
        self._duty_cycle = 50.0        # placeholder
        self._burst_enabled = False    # placeholder
        self._burst_mode = "trig"      # placeholder
        self._burst_ncycles = 1.0      # placeholder
        self._gate_polarity = "norm"   # placeholder
        self._output = True            # placeholder
        self._sync_output = False      # placeholder
        self._trigger_output = False   # placeholder

    # -- the methods the driver reads -------------------------------------------------------------------------
    def get_amplitude(self):
        return self._amplitude

    def get_frequency(self):
        return self._frequency

    def get_offset(self):
        return self._offset

    def get_phase(self):
        return self._phase

    def get_function(self):
        return self._function

    def get_duty_cycle(self):
        return self._duty_cycle

    def is_burst_enabled(self):
        return self._burst_enabled

    def get_burst_mode(self):
        return self._burst_mode

    def get_burst_ncycles(self):
        return self._burst_ncycles

    def get_gate_polarity(self):
        return self._gate_polarity

    def get_output(self):
        return self._output

    def is_sync_output_enabled(self):
        return self._sync_output

    def is_trigger_output_enabled(self):
        return self._trigger_output

    # -- the methods the driver writes ------------------------------------------------------------------------
    def set_amplitude(self, amplitude):
        self._amplitude = float(amplitude)
        return self.get_amplitude()

    def set_frequency(self, frequency):
        self._frequency = float(frequency)
        return self.get_frequency()

    def set_offset(self, offset):
        self._offset = float(offset)
        return None

    def set_phase(self, phase):
        self._phase = float(phase)
        return self.get_phase()

    def set_function(self, func):
        self._function = str(func)
        return self.get_function()

    def set_duty_cycle(self, dcycle):
        self._duty_cycle = float(dcycle)
        return self.get_duty_cycle()

    def enable_burst(self, enabled=True):
        self._burst_enabled = bool(enabled)
        return self.is_burst_enabled()

    def set_burst_mode(self, mode):
        self._burst_mode = str(mode)
        return self.get_burst_mode()

    def set_burst_ncycles(self, ncycles=1):
        self._burst_ncycles = float("inf") if ncycles is None or float(ncycles) > 1E37 else float(ncycles)
        return self.get_burst_ncycles()

    def set_gate_polarity(self, polarity="norm"):
        self._gate_polarity = str(polarity)
        return self.get_gate_polarity()

    def set_output(self, enabled=True):
        self._output = bool(enabled)
        return self.get_output()

    def enable_sync_output(self, enabled=True):
        self._sync_output = bool(enabled)
        return self.is_sync_output_enabled()

    def enable_trigger_output(self, enabled=True):
        self._trigger_output = bool(enabled)
        return self.is_trigger_output_enabled()
