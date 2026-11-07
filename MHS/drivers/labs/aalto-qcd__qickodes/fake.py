"""Fake backend of the QICKoDeS driver: a source-shaped stand-in for qickodes.instrument_v2:QickInstrument.

The upstream constructor stores one QCoDeS Parameter under each of ``hard_avgs``, ``soft_avgs``, ``final_delay``,
``final_wait`` and ``initial_delay`` (instrument_v2.py:155-192), and one ``Ddr4Buffer`` module under
``ddr4_buffer`` (instrument_v2.py:141).  This fake stores a small stand-in object under each of those names and
implements only the calls the driver makes: ``SweepableParameter.get_raw``/``set_raw`` for the delays,
``ManualParameter.get``/``set`` for the counts, ``Ddr4Buffer.arm``, ``set_macro_list`` and ``get_idn``.  Nothing here
imports QCoDeS, QICK or Pyro4 and nothing opens a network connection.

Every value below is a placeholder chosen for the behavioural tests; none is a fact about a board or a site.  The
fake does not model the tProc program, the QICK proxy, the DAC/ADC channel layout or the DDR4 transfer itself.  A
write is accepted without the upstream validator, a read returns the stored number, and ``arm`` only counts calls.
The timing and the real board behaviour require a supervised hardware run.
"""


class _FakeSweepableParameter:
    """Stand-in for SweepableParameter: the scalar path of get_raw/set_raw, without a sweep registration."""

    def __init__(self, value):
        self._value = value

    def get_raw(self):
        return self._value

    def set_raw(self, value):
        self._value = value

    def get(self):
        return self.get_raw()

    def set(self, value):
        self.set_raw(value)


class _FakeManualParameter:
    """Stand-in for ManualParameter: an in-memory value with get() and set(value)."""

    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class _FakeDdr4Buffer:
    """Stand-in for Ddr4Buffer: the configured channel, transfer count and the arm() call."""

    def __init__(self):
        self.selected_adc_channel = _FakeManualParameter(0)       # placeholder
        self.num_transfers = _FakeManualParameter(1)              # placeholder
        self.wired_adc_channels = [0]                             # placeholder
        self.samples_per_transfer = 128                           # placeholder
        self.arm_calls = 0

    def arm(self):
        """Record one arm call; the real method calls parent.soc.arm_ddr4."""
        self.arm_calls += 1


class _FakeSoc:
    """Stand-in for the Pyro4 QickSoc proxy: the fake keeps no board state."""

    def arm_ddr4(self, selected_adc_channel, num_transfers):
        self.last_arm = (selected_adc_channel, num_transfers)     # placeholder


class FakeQickodes:
    def __init__(self, **_options):
        self.final_delay = _FakeSweepableParameter(1e-6)          # placeholder, seconds
        self.final_wait = _FakeSweepableParameter(0.0)            # placeholder, seconds
        self.initial_delay = _FakeSweepableParameter(1e-6)        # placeholder, seconds
        self.hard_avgs = _FakeManualParameter(1000)               # placeholder
        self.soft_avgs = _FakeManualParameter(1)                  # placeholder
        self.macro_list = []                                      # placeholder, the upstream starts with no macro
        self.macro_name_counter = {}
        self.ddr4_buffer = _FakeDdr4Buffer()
        self.soc = _FakeSoc()
        self.swept_params = set()
        self.soccfg = {"board": "fake-board"}                     # placeholder

    def get_idn(self):
        """The identity fields of the upstream get_idn; the fake board name is a placeholder."""
        return {
            "vendor": "Xilinx",
            "model": self.soccfg["board"],
            "serial": None,
            "firmware": "placeholder fake firmware",
        }

    def set_macro_list(self, macro_list):
        """Replace the macro list; the driver's e-stop calls this with an empty list."""
        self.macro_list = list(macro_list)
