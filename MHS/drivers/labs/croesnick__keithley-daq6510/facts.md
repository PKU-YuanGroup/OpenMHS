# Facts and tags for gh.croesnick/keithley-daq6510

Every fact cites its source at commit `4c800f325a14a1051819ad089e4b1fc918aab8d4`: `vendor_doc` (a text file of the
clone such as `README.rst`) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The package is a sample library for the Keithley DAQ6510 instrument that uses pyvisa and pyvisa-sim | vendor_doc | README.rst:23 |
| Instrument subclasses VisaInstrument | upstream_code | src/keithley_daq6510/instrument.py:9 |
| Instrument declares the SCPI query *IDN? as its idn operation | upstream_code | src/keithley_daq6510/instrument.py:10 |
| VisaInstrument.query forwards to conn.query and VisaInstrument.command forwards to conn.write | upstream_code | src/keithley_daq6510/visa_instrument.py:24-28 |
| Operation sends a command ending in '?' through query and every other command through command | upstream_code | src/keithley_daq6510/scpi/operation/__init__.py:121 |
| The upstream pyvisa-sim fixture declares an *IDN? dialogue with a Keithley Instruments reply | upstream_code | tests/fixtures/devices.yml:9-10 |
| The upstream test asserts that Instrument.idn() returns the fixture identity reply | upstream_code | tests/test_instrument.py:16-17 |
| The upstream pyvisa-sim fixture also declares a :STATus:CLEar command with no reply | upstream_code | tests/fixtures/devices.yml:11 |

## Limits

The package declares no numeric write and no numeric action input, so there is no Limit and no
`Limit.operator_required` path. The clone states no measurement range, channel count, sample rate or output bound, and
this driver does not invent one. `site-limits.example.json` is therefore absent: there is nothing to narrow.

## Coverage

The clone binds only the identity query. `x-cap.croesnick.identity.v1` returns the `*IDN?` reply as a read capability;
the same reply is exposed as the read-only state field `idn`. No measurement, channel, trigger, range, status or output
command is declared by the clone, so none is offered. `:STATus:CLEar` appears only as a pyvisa-sim dialogue with no
reply and is not exposed.

Safety: the driver is R0. It reads a string and writes no device state; the clone has no stop command, no output and no
actuator. No hardware e-stop is claimed and none is needed at R0. The hardware backend has never been run.

The fake is a package-local transport stand-in, not the upstream simulator: importing or running clone code is not
allowed here. Its identity reply is placeholder test data from the clone's fixture, not a fact about an attached
instrument.

Tags: keithley, daq6510, data acquisition, scpi, visa, identity
