# Facts and tags for gh.ledger-donjon/pypdm

Every fact cites its source at commit `a059c30e5054a9e1276769c18c4f13e56a404a6a`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| PyPDM controls AlphANOV PDM laser sources, supports PDM protocol version 3.4 to 3.7 and lets daisy-chained devices share one serial link | vendor_doc | README.md:4 |
| The documentation lists the PDM properties that can be read or changed: sync source, delay line type, frequency, pulse width, delay, offset current, current percentage, current, temperature, maximum current, current source, interlock status, activation and mode | vendor_doc | docs/getting_started.rst:72-89 |
| The link opens the serial port at 125000 baud and frames a command as length, address, command id, data and a checksum | upstream_code | pypdm/pdm.py:169-233 |
| The checksum is the XOR of the frame bytes minus one, modulo 256 | upstream_code | pypdm/pdm.py:188-197 |
| A response is a length byte, a status byte, the data and a checksum; a status other than OK raises StatusError | upstream_code | pypdm/pdm.py:199-218 |
| The PDM constructor validates the protocol version: major 3 and minor 4 to 7 | upstream_code | pypdm/pdm.py:278-288 |
| The class states its bounds: MAX_DELAY 15000 ps, MAX_PULSE_WIDTH 1275000 ps and MAX_FREQUENCY 250000000 Hz | upstream_code | pypdm/pdm.py:255-260 |
| The offset current setter refuses a value below 0 or above 150 mA | upstream_code | pypdm/pdm.py:443-445 |
| The current percentage setter refuses a value below 0 or above 100 | upstream_code | pypdm/pdm.py:462-465 |
| The current in mA is current_percentage times maximum_current divided by 100 | upstream_code | pypdm/pdm.py:470-483 |
| The maximum pulse current and the maximum mean current are read from the device and cached | upstream_code | pypdm/pdm.py:501-534 |
| InterlockStatus.CLOSED is 0 (the laser can pulse) and InterlockStatus.OPEN is 1 (it cannot pulse) | upstream_code | pypdm/pdm.py:89-93 |
| The mode command reads the continuous or pulsed hardware switch: 0 for pulsed and 1 for continuous | upstream_code | pypdm/pdm.py:579-592 |
| The activation is a boolean instruction and apply() makes the pending instructions effective | upstream_code | pypdm/pdm.py:563-578 |
| apply() sends the APPLY_ALL_INSTRUCTIONS command, which makes all settings in volatile memory effective | upstream_code | pypdm/pdm.py:601-606 |
| The destructor sets the activation to False and calls apply() for safety | upstream_code | pypdm/pdm.py:294-299 |
| The synchronization sources are EXTERNAL_TTL_LVTTL 0, EXTERNAL_LVDS 1 and INTERNAL 2; the delay line types are NONE 0 and INTERNAL 1; the current sources are ANALOG 0 and NUMERIC 1 | upstream_code | pypdm/pdm.py:131-157 |

Limits: the frequency input is `Limit(min=1, max=250000000, ref="pypdm/pdm.py:260-397")`, the current percentage
`Limit(min=0, max=100, ref="pypdm/pdm.py:462-465")` and the offset current
`Limit(min=0, max=150, ref="pypdm/pdm.py:443-445")`; all three cite the upstream code that states or enforces the bound.
No operator overlay is needed.

Safety: the e-stop and the safe-state action `x-cap.ledger-donjon.disable_emission.v1` both clear the activation
instruction and call the native `apply()` as the upstream destructor does (pypdm/pdm.py:294-299). The driver is
R2 (a laser above class 1, MHS/spec/04-safety.md; a model review raised it, and a class 3B or 4 source is R3); the
safe-state action is its independent stop, and the clone documents no hardware e-stop on this link.

Tags: laser, pulsed-laser, laser-diode, serial, binary-protocol
