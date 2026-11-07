# Facts and tags for gh.asvela/dlc-control

The package wraps `dlccontrol:DLCcontrol`, a Toptica DLCpro convenience wrapper around the Toptica laser SDK.
Every fact cites the pinned clone at `eba98c139581e73dce32c0b196f41b253f6009f8` (`vendor_doc` for README text,
`upstream_code` for the Python source). The same facts are written into `driver.py` (`facts = [...]`); the reference
file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The README warns that this module controls potentially Class 4 lasers. | vendor_doc | README.md:8 |
| The README describes a convenience wrapper around the Toptica laser SDK for controlling a Toptica CTL laser with a DLCpro. | vendor_doc | README.md:6 |
| DLCcontrol controls a Toptica DLCpro over an Ethernet connection. | upstream_code | dlccontrol.py:99-100 |
| DLCcontrol builds the Toptica SDK NetworkConnection and DLCpro in __init__ and calls open() unless open_on_init is false. | upstream_code | dlccontrol.py:155-159 |
| emission, emission_button and current_enabled read the DLC emission state, the emission button and the diode current enable; the current_enabled setter is documented as controlling emission on/off. | upstream_code | dlccontrol.py:455-476 |
| The service user level prompts for interactive confirmation on stdin and uses a per-unit service password. | upstream_code | dlccontrol.py:200-215 |
| get_user_level reads the connection user level; the set_user_level docstring says 3 is normal, 2 maintenance and 1 service. | upstream_code | dlccontrol.py:185-220 |
| wavelength_actual and wavelength_setpoint read the laser wavelength; the setpoint setter checks the range queried by get_limits_from_dlc. | upstream_code | dlccontrol.py:480-506 |
| temp_actual and temp_setpoint read the diode temperature; the setpoint setter checks the range queried by get_limits_from_dlc. | upstream_code | dlccontrol.py:510-536 |
| The internal scan settings are enabled, output channel, frequency, amplitude, offset, start and end. | upstream_code | dlccontrol.py:301-309 |
| get_limits_from_dlc queries the piezo voltage, current clip, wavelength and temperature ranges; it hard-codes the scan frequency bounds 0.02 and 400 and notes that the maximum was not found in the manual. | upstream_code | dlccontrol.py:253-290 |
| The scan_frequency setter checks the value against the fmin and fmax bounds. | upstream_code | dlccontrol.py:676-681 |
| The scan range is the piezo voltage range for the PC output and the current range for the CC output; OutA and OutB have no range check. | upstream_code | dlccontrol.py:330-339 |
| freq_per_sec documents scan_freq in Hz and peak_to_peak in Vpp. | upstream_code | dlccontrol.py:741-759 |
| OutputChannel enumerates PC, CC, OutA and OutB; InputChannel enumerates Fine1, Fine2, Fast3 and Fast4. | upstream_code | dlccontrol.py:75-91 |
| set_parameters is not implemented: it raises NotImplementedError. | upstream_code | dlccontrol.py:416-421 |
| read_parameters only loads parameters from a JSON file; it does not read the instrument. | upstream_code | dlccontrol.py:405-414 |
| close() only calls self.dlc.close(). | upstream_code | dlccontrol.py:180-183 |

## Limits

- `scan_frequency`: 0.02 to 400 Hz, the wrapper's own hard-coded `fmin`/`fmax`
  (`dlccontrol.py:267-268`, checked at `dlccontrol.py:676-681`). The source comment says the maximum was not found in
  the manual, so the reason is carried on the limit.
- `wavelength_setpoint` and `temp_setpoint`: `Limit.operator_required`. The upstream wrapper queries the ranges from
  the DLC in `get_limits_from_dlc` and no text file of the clone states them; the site supplies the range of its unit.
- `scan_amplitude`, `scan_offset`, `scan_start` and `scan_end`: `Limit.operator_required`. The upstream checks them
  against the range it queries (`dlccontrol.py:330-339`, `dlccontrol.py:688-735`) and the clone states no numeric
  range; the site supplies it in the native unit of the selected scan output. The driver publishes these four values
  with unit `1` because the one upstream property is used with either the piezo voltage range (PC, V) or the current
  range (CC, mA); their descriptions say `V/mA` and the read `scan_output_channel` says which one applies.
- `current_enabled` and `scan_enabled` are booleans and carry no numeric limit.
- `site-limits.example.json` is an example overlay only. It fills the operator-required paths with example ranges and
  may only narrow the driver's limits; it is not a statement about any installed unit.

## What the driver does not expose

- `set_parameters` is not implemented upstream (`dlccontrol.py:416-421`).
- `read_parameters` only loads a JSON file and does not read the instrument (`dlccontrol.py:405-414`).
- `set_user_level` is left out because the service level prompts on stdin and needs a per-unit password
  (`dlccontrol.py:200-215`); `user_level` is exposed as a read.
- The analogue remote-control settings are not exposed: they are selected through the `remote_select` state that
  changes which of the two upstream property objects is addressed, and the driver would need to pin that selection
  for every call (`dlccontrol.py:340-360`, `dlccontrol.py:540-629`).

## Safety

- The clone has no emergency-stop method. The `current_enabled` setter is documented as the way to control emission
  on/off (`dlccontrol.py:470-476`), so both the `@estop` method and the `x-cap.asvela.emission_off.v1` safe-state
  action disable the diode current.
- The README warns about potentially Class 4 lasers (`README.md:8`), so the package declares R3, above the card's
  R1 floor. No line of the clone documents an independent hardware e-stop, so `estop_physical_ref` is not set; the
  safe-state action satisfies SAFE-045.
- The package is model-authored and unreviewed: `reviewed_by` is null in `driver.lock.json`, and the loader refuses
  the hardware backend of this R3 package until a human signs it. The gate and these notes never claim a hardware
  run.

## Tags

`laser`, `dlcpro`, `toptica`, `emission`, `scan`
