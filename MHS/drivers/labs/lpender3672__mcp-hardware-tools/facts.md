# Facts and tags for gh.lpender3672/mcp-hardware-tools

This package covers the card's second entry symbol, `hwtools.drivers.joyit.jds6600:JDS6600` (the Joy-IT JDS6600
DDS signal generator).  The card also lists the scope `hwtools.drivers.rigol.ds1054z:DS1054Z`; the OpenMHS layout
serves one device per package, so the scope is left for a separate card.

Every fact cites its source at commit `e13d9cd83962cc1bb80b3f25f0daa2fce52eb0f5`.  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The JDS6600 speaks a 115200 8N1 USB-CDC serial line protocol, one command per line framed ':<op><fn>=<data>.' with CRLF, where 'w' writes and 'r' reads | upstream_code | src/hwtools/drivers/joyit/jds6600.py:4-7 |
| Frequency is encoded in centi-Hz with unit code 0 ('round(hz*100)'), so a 1 MHz setting reads 100000000,0 | upstream_code | src/hwtools/drivers/joyit/jds6600.py:13-15 |
| Amplitude is millivolt peak-to-peak, offset is hundredths of a volt biased so 1000 is 0 V, duty is tenths of a percent and phase is tenths of a degree | upstream_code | src/hwtools/drivers/joyit/jds6600.py:16-19 |
| Function code 20 is the shared both-channels output-enable register written as 'a,b'; codes 21/22 waveform, 23/24 frequency, 25/26 amplitude, 27/28 bias, 29/30 duty are per channel, and 31 is the channel-2-versus-channel-1 phase | upstream_code | src/hwtools/drivers/joyit/jds6600.py:21-24 |
| The driver's capability table records 15 MHz as the JDS6600-15 frequency maximum, 20 Vpp as the amplitude maximum and 9.99 V as the symmetric offset maximum | upstream_code | src/hwtools/drivers/joyit/jds6600.py:83-87 |
| The upstream model validates frequency > 0, amplitude >= 0 and duty between 0 and 100 percent | upstream_code | src/hwtools/model/siggen.py:66-69 |
| The JDS6600-15 provides two channels, seventeen built-in waveforms, 60 arbitrary slots of 2048 points with 12-bit codes | upstream_code | src/hwtools/drivers/joyit/jds6600.py:51-91 |
| The native set_phase_deg accepts 0 to 360 degrees and rejects anything outside that range | upstream_code | src/hwtools/drivers/joyit/jds6600.py:215-217 |
| read_channel queries the waveform, frequency, amplitude, offset, duty and output-enable state of one channel | upstream_code | src/hwtools/drivers/joyit/jds6600.py:251-271 |
| enable_output reads the shared output pair, flips only the requested channel's bit and writes it back | upstream_code | src/hwtools/drivers/joyit/jds6600.py:205-213 |
| idn reads function codes 00 and 01 and formats JDS6600-<model> SN:<serial> | upstream_code | src/hwtools/drivers/joyit/jds6600.py:159-163 |
| The arbitrary-waveform path uses 60 slots of exactly 2048 points with 12-bit codes, and a channel plays slot N as waveform code 100 + N | upstream_code | src/hwtools/drivers/joyit/jds6600.py:72-79 |
| When an arbitrary slot is selected, read_channel returns its slot and uses SINE as a don't-care built-in waveform field | upstream_code | src/hwtools/drivers/joyit/jds6600.py:251-271 |

## Limits

| field | limit | source | ref |
|---|---|---|---|
| ch1/ch2 frequency | 0 to 15e6 Hz | upstream_code | src/hwtools/model/siggen.py:66 (positive) and src/hwtools/drivers/joyit/jds6600.py:85 (15 MHz) |
| ch1/ch2 amplitude | 0 to 20 Vpp | upstream_code | src/hwtools/model/siggen.py:67 (non-negative) and src/hwtools/drivers/joyit/jds6600.py:86 (20 Vpp) |
| ch1/ch2 offset | -9.99 to 9.99 V | upstream_code | src/hwtools/drivers/joyit/jds6600.py:17 |
| ch1/ch2 duty | 0 to 100 percent | upstream_code | src/hwtools/model/siggen.py:69 |
| phase action `degrees` | 0 to 360 degrees | upstream_code | src/hwtools/drivers/joyit/jds6600.py:216 |

The frequency lower bound is the upstream model's `gt=0`; the OpenMHS closed bound is 0, so a zero setting is
refused by the driver before a native configuration write. The frequency and amplitude limits name their lower
bound citations in `reason` and the device-maximum citations in `ref`; both source ranges were read in this model
review. No operator-required bound is needed, so this
package ships no `site-limits.example.json`.

## Safety

- The e-stop (`stop_outputs`) calls the native `enable_output(1, False)` and `enable_output(2, False)`: the shared
  output-enable register is requested as `0,0` (jds6600.py:205-213). Both calls are attempted even if one raises,
  and both flags are read back through `output_enabled` (273-279). Any failed exchange or enabled flag fails the
  stop with `SAFE_STATE_UNREACHED`; the latch remains held. The physical output signal is not measured.
- Serial exchanges have the factory's default 1 s read timeout each; the stop makes up to six exchanges, so a
  slow device can exceed the endpoint's default 1 s stop budget and remain unconfirmed. The upstream serial
  constructor does not set a write timeout (141-146), and other clients can change the shared output register.
  These timing and concurrency gaps require deployment assessment; the fake supplies no physical evidence.
- The signal generator is a bench stimulus source (up to 20 Vpp, ±9.99 V offset), not a laser, motion, heating or
  pumping device; the package is R1, at the card's floor.  No independent hardware e-stop is cited because no
  vendor text of the clone documents one, and the card's floor is R1.
- Model-authored and unreviewed: the fake backend is the only backend exercised here; no hardware run is claimed.

## Not covered

- `upload_arbitrary` / `read_arbitrary`: the arbitrary waveform sample array (60 slots × 2048 points × 12-bit) is
  not exposed.  The standard waveform, frequency, amplitude, offset, duty, phase and enable controls are.
- `ch1_arbitrary_slot` and `ch2_arbitrary_slot` report the selected stored slot, with 0 meaning a built-in shape.
  While a slot is active the upstream built-in waveform field is a SINE fallback (251-257). A built-in waveform
  write clears `arb_slot`; other setting writes preserve it. The fake preserves the same metadata.
- The DS1054Z scope entry symbol in the card is not covered by this package.

Tags: signal-generator, waveform, dds, serial
