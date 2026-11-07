"""Fake backend of the ADwin Gold II driver: an in-memory stand-in for the QCoDeS ADwin_Gold2 instrument.

The upstream class exposes the controls this driver uses as ordinary methods (ADwin_Gold2.py:742-930), and the
driver calls those names only.  This fake implements the same public methods with the same scalar behavior:

* ``set_mode`` / ``get_mode``, ``set_ramp_size`` / ``get_ramp_size``, ``set_subsampling`` / ``get_subsampling``,
  ``set_output_mask`` / ``get_output_mask`` and ``set_input_mask`` / ``get_input_mask`` keep the settings in plain
  attributes;
* ``set_outputs`` builds the same five-field FIFO header and appends the targets (ADwin_Gold2.py:754-779);
  ``set_outputs_one_cycle`` sends it with a one-point ramp and ``launch_measurement`` sends it with the configured
  ramp (ADwin_Gold2.py:783-794);
* ``read_inputs`` returns canned ADC codes and ``go_to_zero`` commands 0 V on all eight outputs and clears both
  FIFOs (ADwin_Gold2.py:796-812);
* ``volt_to_binary`` and ``binary_to_volt`` repeat the upstream 16-bit DAC and 24-bit ADC conversions
  (ADwin_Gold2.py:742-752).

Nothing here imports QCoDeS, ADwin, numpy or PyVISA, opens a device or talks to hardware.  The starting settings,
the canned ADC codes and every output value kept here are placeholders chosen for the tests, never facts about an
ADwin.  The fake sends a FIFO without the upstream's ``time.sleep`` calls: it records the call and the
commanded DAC codes, so a test can see the effect without waiting.

Fidelity gap: the upstream methods reach the real-time process through ``self.device.Fifo_Clear``,
``self.device.SetFifo_Long`` and ``self.device.GetFifo_Long`` (ADwin_Gold2.py:787, 793, 810-817); the fake neither
models the ADwin FIFO semantics nor the process that consumes it.  The QCoDeS Parameter validators and the
``outputs`` / ``inputs`` parsers are bypassed, because the driver calls the methods directly.
"""

# Upstream mode bits, ADwin_Gold2.py:15-17; not device-specific values.
_LOCKIN_MODE = 0x10
_LOCKIN_2_MODE = 0x40000
_LOCKIN_2_INV_MODE = 0x80000


class FakeADwinGold2:
    def __init__(self, **_options):
        self._adwin_mode = 0                                       # placeholder, bit pattern
        self._ramp_size = 1000                                     # placeholder, process points
        self._subsampling = 1                                      # placeholder, process durations
        self._output_mask = 0b1                                    # placeholder
        self._input_mask = 0b1                                     # placeholder
        self.process_duration = 10e-6                              # placeholder, 10 us (upstream: 727-736)
        self._fifo_list = []
        self._sent = []
        self._last_targets = []                                    # placeholder DAC codes of the last FIFO
        self._raw_inputs = [2 ** 23, 2 ** 23 + 2 ** 20, 2 ** 23 - 2 ** 20]  # placeholder ADC codes
        self._zeroed = 0
        self._cleared = 0

    # -- scalar settings ------------------------------------------------------------------------------------------
    def set_mode(self, mode):
        if type(mode) is int:
            self._adwin_mode = mode
            return
        if mode == "normal":
            self._adwin_mode = 0
        elif mode == "lockin":
            self._adwin_mode = _LOCKIN_MODE
        elif mode == "lockin2":
            self._adwin_mode = _LOCKIN_2_MODE + _LOCKIN_MODE
        elif mode == "lockin2_inv":
            self._adwin_mode = _LOCKIN_2_INV_MODE + _LOCKIN_MODE
        else:
            raise ValueError(f"Invalid mode {mode}")

    def get_mode(self):
        return self._adwin_mode

    def set_ramp_size(self, ramp_size):
        self._ramp_size = ramp_size

    def get_ramp_size(self):
        return self._ramp_size

    def set_subsampling(self, subsampling):
        self._subsampling = subsampling

    def get_subsampling(self):
        return self._subsampling

    def set_output_mask(self, indexes):
        if type(indexes) is int:
            self._output_mask = indexes
        else:
            self._output_mask = sum([2 ** (index - 1) for index in indexes])

    def get_output_mask(self):
        return self._output_mask

    def set_input_mask(self, indexes):
        if type(indexes) is int:
            self._input_mask = indexes
        else:
            self._input_mask = sum([2 ** (index - 1) for index in indexes])

    def get_input_mask(self):
        return self._input_mask

    # -- FIFO staging and sending ---------------------------------------------------------------------------------
    def set_outputs(self, targets):
        self._fifo_list = [
            self.get_mode(),
            self.get_input_mask(),
            self.get_output_mask(),
            self.get_ramp_size(),
            self.get_subsampling(),
        ]
        for target in targets:
            self._fifo_list.append(int(target))

    def set_outputs_one_cycle(self):
        if not self._fifo_list:
            raise RuntimeError("set_outputs must build the FIFO before it is sent")
        old_ramp = self._fifo_list[3]
        self._fifo_list[3] = 1
        self._send_fifo()
        self._fifo_list[3] = old_ramp

    def launch_measurement(self):
        if not self._fifo_list:
            raise RuntimeError("set_outputs must build the FIFO before it is sent")
        self._send_fifo()

    def _send_fifo(self):
        self._sent.append(list(self._fifo_list))
        self._last_targets = list(self._fifo_list[5:])

    def go_to_zero(self):
        old_mask = self.get_output_mask()
        self.set_output_mask(0b11111111)
        self.set_outputs([self.volt_to_binary(0.0)] * 8)
        self.set_outputs_one_cycle()
        self.set_output_mask(old_mask)
        self.clear_fifos()
        self._zeroed += 1

    def read_inputs(self):
        return list(self._raw_inputs)

    def clear_fifos(self):
        self._fifo_list = []
        self._cleared += 1

    # -- conversions ----------------------------------------------------------------------------------------------
    def volt_to_binary(self, voltage):
        return int(voltage / 10 * 2 ** 15 + 2 ** 15)

    def binary_to_volt(self, binary):
        return (binary - 2 ** 23) / 2 ** 23 * 10
