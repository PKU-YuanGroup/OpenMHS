# Facts and tags for gh.feifanphys/instrumentdriver

Every fact cites its source at commit `749c845066b5a0e5ac30a1f9f55ff36e76ca24e1`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The KeysightN5182B.reset method writes '*RST' | upstream_code | drivers/SignalGenerator/KeysightN5182B.py:9-10 |
| The KeysightN5182B.set_frequency method writes 'FREQ {hz}' | upstream_code | drivers/SignalGenerator/KeysightN5182B.py:12-13 |
| The KeysightN5182B.set_power method writes 'POW {dbm}DBM' | upstream_code | drivers/SignalGenerator/KeysightN5182B.py:15-16 |
| The KeysightN5182B.output_on and output_off methods write 'OUTP ON' and 'OUTP OFF' | upstream_code | drivers/SignalGenerator/KeysightN5182B.py:18-22 |
| The upstream mock answers '*IDN?', 'FREQ?', 'POW?' and 'OUTP?' | upstream_code | drivers/SignalGenerator/KeysightN5182B.py:75-86 |
| The upstream mock identity starts 'Keysight Technologies,N5182B,' | upstream_code | drivers/SignalGenerator/KeysightN5182B.py:31 |
| The upstream mock accepts 'FREQ ', 'POW ' with an optional DBM suffix, and 'OUTP ON'/'OUTP OFF' | upstream_code | drivers/SignalGenerator/KeysightN5182B.py:53-70 |
| The upstream README example resets the generator, sets frequency and power, and turns the output on | vendor_doc | README.md:131-134 |
| ScpiTransport writes a command plus its terminator and the default terminator is a newline | upstream_code | transport/ScpiTransport.py:6-18 |

## Limits

The clone states no numeric frequency or power range: it sends whatever value the caller passes
(`drivers/SignalGenerator/KeysightN5182B.py:12-16`), and the mock stores it without a check
(`drivers/SignalGenerator/KeysightN5182B.py:53-63`). The driver therefore declares both as
`Limit.operator_required`; until the operator supplies a bound in `site-limits.json`, every write that sets the field
is refused with `MHS.SAFETY.LIMITS_UNSET`. `site-limits.example.json` is an example overlay with operator-chosen
values; it is not a device bound and does not widen anything.

The output state is a boolean (`OUTP ON` / `OUTP OFF`, `drivers/SignalGenerator/KeysightN5182B.py:18-22`) and needs no
numeric limit.

## Safety

- E-stop: software, latching, native stop `OUTP OFF` (`safety_bindings["estop"]`).
- Safe state: RF output disabled (`OUTP OFF`).
- Risk R1: a wrong setting is recoverable by turning the output off; the package adds no protection the SDK does not
  give. OpenMHS is not a safety certification and not a safety-rated channel; the physical e-stop stays
  authoritative.
- The package is model-authored and unreviewed. It was checked on the fake backend only; no hardware was used.

## Licence note

The clone's README says "MIT License" (`README.md:202`), but the clone contains no `LICENSE` file. The lock keeps the
task card's `license_spdx` `NOASSERTION` and `license_class` `unknown`; this is a recon note, not a claim about the
upstream.

Tags: signal generator, rf source, keysight, n5182b, scpi.
