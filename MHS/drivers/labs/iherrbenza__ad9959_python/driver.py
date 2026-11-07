"""OpenMHS driver for gh.iherrbenza/ad9959_python: an AD9959 DDS behind an ESP32 over TCP.

A direct Driver (decorated methods) over the upstream plain-object class
``DDS_ESP32_lab.DDS_ESP32:DDS_ESP32``.  The upstream class builds the SPI words of the AD9959 in Python and sends
the resulting hexadecimal text to an ESP32 over a TCP socket; the ESP32 performs the SPI transfers
(DDS_ESP32_lab/DDS_ESP32.py:46-54, 554-568).  There is no getter in the class and the protocol has no reply for a
register write, so the driver declares no ``@read``: the resource state is the last value the runtime wrote, which
is also the last value the driver sent to the device.

* writes: one four-element array per parameter -- the frequency in Hz, the 10-bit amplitude word and the phase in
  degrees -- for channels 0 to 3; each channel is one native call with ``send=True``;
* the frequency range is not a fixed bound: the upstream docstring gives ``max=clock x PLL``, and ``clock`` and
  ``pll`` are constructor options (DDS_ESP32_lab/DDS_ESP32.py:557), so the site supplies the core clock with
  ``site-limits.example.json`` (``Limit.operator_required``);
* the amplitude word is bounded by the 10-bit register (0 to 1023, DDS_ESP32_lab/DDS_ESP32.py:573) and the phase by
  0 to 360 degrees (DDS_ESP32_lab/DDS_ESP32.py:590);
* the e-stop and the safe-state action set every channel amplitude word to 0 (``set_amplitude(..., send=True)``).

Every Fact cites a line of the clone at the pinned commit (cd5298ec17fe7994a2c07ce9783ac88a3d194f8c).  This
package is model-authored and unreviewed; it is checked on the fake backend only.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, write

# The upstream docstring gives the frequency bound as clock x PLL; both are constructor options of the class, so the
# bound of a particular unit is an operator input, not a library default.
_FREQUENCY_LIMIT = Limit.operator_required(
    "the upstream docstring gives max = clock x PLL and min = (clock x PLL) / 2**32, but clock and pll are "
    "constructor options of DDS_ESP32 (50E6 and 10 by default); the site states the core clock of its unit and the "
    "band it may drive")

# The amplitude word and the phase word are fixed by the register widths in the upstream code.
_AMPLITUDE_LIMIT = Limit(min=0, max=1023, source="upstream_code", ref="DDS_ESP32_lab/DDS_ESP32.py:573")
_PHASE_LIMIT = Limit(min=0, max=360, source="upstream_code", ref="DDS_ESP32_lab/DDS_ESP32.py:590")


class AD9959(Driver):
    device_id = "ad9959"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "DDS_ESP32_lab.DDS_ESP32:DDS_ESP32"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeDDS_ESP32"}
    vendor, model = "Analog Devices / iherrbenza", "AD9959 DDS via ESP32"
    display_name = "AD9959 four-channel DDS (DDS_ESP32_lab.DDS_ESP32)"
    tags = ["dds", "ad9959", "esp32", "signal-source", "rf"]
    facts = [
        Fact("The AD9959 has 4 channels with modulation and sweep capabilities", source="vendor_doc",
             ref="README.md:10"),
        Fact("set_frequency writes a channel frequency in Hz and selects the channel with ch (0b00 to 0b11)",
             source="upstream_code", ref="DDS_ESP32_lab/DDS_ESP32.py:554-561"),
        Fact("set_amplitude writes a 10-bit amplitude word with a maximum of 1023", source="upstream_code",
             ref="DDS_ESP32_lab/DDS_ESP32.py:570-573"),
        Fact("set_phase writes a phase in degrees with a maximum of 360", source="upstream_code",
             ref="DDS_ESP32_lab/DDS_ESP32.py:587-590"),
    ]
    safe_state = "all four channel amplitude words at 0"

    # -- state written to the device ---------------------------------------------------------------------------
    # The upstream class has no getter and the ESP32 protocol has no register read: a @read would have to invent a
    # measurement.  The runtime therefore reports the last value of each write as the resource state.

    @write("frequency", type="array", items="number", length=4, unit="Hz",
           description="Frequency sent to channels 0 to 3 (one value per channel)",
           limit=_FREQUENCY_LIMIT)
    def set_frequency(self, value):
        for channel, frequency in enumerate(value):
            self.native.set_frequency(channel, float(frequency), send=True)

    @write("amplitude", type="array", items="integer", length=4, unit="1",
           description="10-bit amplitude word sent to channels 0 to 3 (0 to 1023 per channel)",
           limit=_AMPLITUDE_LIMIT)
    def set_amplitude(self, value):
        for channel, amplitude in enumerate(value):
            self.native.set_amplitude(channel, int(amplitude), send=True)

    @write("phase", type="array", items="number", length=4, unit="deg",
           description="Phase in degrees sent to channels 0 to 3 (0 to 360 per channel)",
           limit=_PHASE_LIMIT)
    def set_phase(self, value):
        for channel, phase in enumerate(value):
            self.native.set_phase(channel, float(phase), send=True)

    # -- actions ------------------------------------------------------------------------------------------------
    @action(name="x-cap.iherrbenza.mute.v1", safe_state=True,
            description="Set every channel amplitude word to 0 (the safe state); it takes no input",
            output={"amplitude": Field("array", items="integer", length=4, unit="1",
                                       description="Amplitude words sent, one per channel")})
    def mute(self):
        self._mute()
        return {"amplitude": [0, 0, 0, 0]}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop used by the e-stop: set every channel amplitude word to 0."""
        self._mute()

    def _mute(self):
        for channel in range(4):
            self.native.set_amplitude(channel, 0, send=True)
