# Facts and tags for gh.samdejong86/agilent33600

Every fact cites its source at commit `262275ddb4e1486c9643587725908456d765b12b`. `vendor_doc` is a text file of
the clone; `upstream_code` is code, a comment or a macro file of the clone. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| AgilentControl.py programs an Agilent 33600A arbitrary waveform generator by sending SCPI commands via TCP | vendor_doc | README.md:8 |
| UploadArb.py uploads a specified arbitrary waveform to the device and saves it to the device's memory | vendor_doc | README.md:12 |
| AgilentControl.py opens the VISA resource 'TCPIP::<address>::INSTR' | upstream_code | AgilentControl.py:24 |
| UploadArb.py opens the same 'TCPIP::<address>::INSTR' VISA resource | upstream_code | UploadArb.py:65 |
| The control script queries '*IDN?' through the VISA session | upstream_code | AgilentControl.py:43 |
| After each macro line the control script queries 'SYST:ERR?' and treats a reply whose first two characters are '+0' as no error | upstream_code | AgilentControl.py:73-76 |
| The upload script truncates an arbitrary-waveform name to 12 characters, the maximum length allowed by the SCPI interface | upstream_code | UploadArb.py:31-34 |
| The upload script computes the sample rate as 1 divided by the mean interval between the file's time bins | upstream_code | UploadArb.py:52-54 |
| The upload script sends the waveform as a little-endian float block with pyvisa's write_binary_values | upstream_code | UploadArb.py:82 |
| After the block upload the script sets the arbitrary sample rate, offset 0, the ARB function and the amplitude | upstream_code | UploadArb.py:90-94 |
| The frequency-sweep macro selects the sine function and sets the frequency with 'SOURce1:FREQuency +50E+03' | upstream_code | freqSweep.awg:2-3 |
| The square-wave macro selects the square function and sets 20 percent duty cycle, 5000 Hz, 0.07 V high and 0 V low on channel 2 | upstream_code | squareWave.awg:1-5 |
| The triangle-wave macro selects the triangle function and sets 50 percent duty cycle, 40000 Hz, 0.50 V high and 0 V low on channel 2 | upstream_code | triangleWave.awg:1-5 |
| A stored arbitrary waveform is loaded with 'MMEMORY:LOAD:DATA1' followed by 'SOURCE1:FUNCTION ARB' and 'SOURCE1:FUNCtion:ARBitrary' | upstream_code | UploadArb.py:122-124 |

## Limits

The clone states no frequency, output-amplitude, offset or sample-rate range. README.md:10 points to an external
manual (not part of the clone), and UploadArb.py:16's pulse-height default and the macro values are examples, not
device bounds. Those four numeric inputs therefore use `Limit.operator_required`; the operator supplies a bound in
`site-limits.json` at deployment, and until then every write that sets one is refused with
`MHS.SAFETY.LIMITS_UNSET`. `site-limits.example.json` is an example overlay for the acceptance run, not a device
specification.

| parameter | command | limit | ref |
|---|---|---|---|
| frequency (Hz) | SOURCE1:FREQUENCY | operator_required | none stated in the clone |
| amplitude (V) | SOURCE1:VOLTAGE | operator_required | none stated in the clone |
| offset (V) | SOUR1:VOLT:OFFS | operator_required | none stated in the clone |
| sample_rate (Hz) | SOUR1:FUNC:ARB:SRAT | operator_required | none stated in the clone |
| function | SOURCE1:FUNC | one of SIN, SQU, TRI, ARB | freqSweep.awg:2, squareWave.awg:1, triangleWave.awg:1, UploadArb.py:93 |
| waveform | SOUR1:FUNC:ARB | at most 12 characters | UploadArb.py:31-34 |

## Safety

The e-stop writes `OUTPUT1 OFF`, the off form of the `OUTPUT1 ON` the clone's macro files send (arb.awg:11), so the
channel 1 output is switched off; the amplitude, offset and waveform settings stay.  (The first version of this
package wrote `SOURCE1:VOLTAGE 0` instead; the reviewer changed it, because the instrument clips an amplitude below its
minimum to that minimum and the DC offset this driver can set stays on the output.)  This is a software e-stop, not a
hardware safety function; MHS is not a safety-rated channel.

## Coverage gap

The binary arbitrary-waveform upload is NOT COVERED. UploadArb.py:82 sends a little-endian float block through
pyvisa's `write_binary_values`, and the declarative SCPI bridge has no binary block. The driver covers the scalar
settings around it, not the sample array. The query forms used for reads are the SCPI query form of the clone's
set commands; the clone itself only queries `*IDN?` and `SYST:ERR?`.

Tags: awg, waveform generator, agilent, keysight, 33600a, scpi
