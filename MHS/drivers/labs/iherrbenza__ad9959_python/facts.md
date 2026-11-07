# Facts and tags for gh.iherrbenza/ad9959_python

Every fact cites its source at commit `cd5298ec17fe7994a2c07ce9783ac88a3d194f8c`; the same facts are in
`driver.py` (`facts = [...]`) and the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The AD9959 has 4 channels with modulation and sweep capabilities | vendor_doc | README.md:10 |
| set_frequency writes a channel frequency in Hz and selects the channel with ch (0b00 to 0b11) | upstream_code | DDS_ESP32_lab/DDS_ESP32.py:554-561 |
| set_amplitude writes a 10-bit amplitude word with a maximum of 1023 | upstream_code | DDS_ESP32_lab/DDS_ESP32.py:570-573 |
| set_phase writes a phase in degrees with a maximum of 360 | upstream_code | DDS_ESP32_lab/DDS_ESP32.py:587-590 |

Limits: the amplitude word is bounded by 0 to 1023 and the phase by 0 to 360 degrees, both from the docstrings on
the cited lines.  The frequency bound is `Limit.operator_required`: the upstream docstring says
`max=clock x PLL, min=(clock x PLL)/(2^32)` (DDS_ESP32_lab/DDS_ESP32.py:557), but `clock` and `pll` are constructor
options (DDS_ESP32_lab/DDS_ESP32.py:34).  A constructor default is not a device bound, so every frequency write is
refused with `MHS.SAFETY.LIMITS_UNSET` until the operator's overlay supplies the band of the unit;
`site-limits.example.json` shows such an overlay (its numbers are an example, not a fact about any board).

Read-back: the upstream class has no getter and the ESP32 protocol has no reply for a register write, so this driver
declares no `@read`.  The runtime reports the last value written as the resource state; that is the last value the
driver sent, not a measurement of the DDS output.

Coverage: the package exposes the four-channel frequency, amplitude and phase words and a mute action.  The 2-level
modulation setters (`set_2mod_frequency`, `set_2mod_amplitude`, `set_2mod_phase`), the ramps (`ramp_*`), the memory
list (`memory_storage`, `list_*`) and `direct_spi` are not exposed.  Raw `direct_spi` text would bypass every limit.

Safety: the e-stop and the safe-state action `x-cap.iherrbenza.mute.v1` both call `set_amplitude(ch, 0, send=True)`
for channels 0 to 3.  The clone documents no independent hardware stop and the card's floor is R1, so no
`estop_physical_ref` is claimed.  The model-authored package is unreviewed.

Fake: `FakeDDS_ESP32` only implements `set_frequency`, `set_amplitude` and `set_phase` (the upstream names and
signatures); its stored values and return codes are placeholders, never facts or limits.

Tags: dds, ad9959, esp32, signal-source, rf
