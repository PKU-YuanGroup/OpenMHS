# Facts and limits for gh.scopefoundry/hw_acton_spec

Every fact cites its source at commit `a4e112406b7fd275a8d23048631a21f0a82758e7`.  The same facts are in
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The clone is a Princeton Instruments / Acton 2300i spectrometer plug-in that uses the RS-232 or USB-serial interface and was tested with Acton 2300i and 300 series spectrometers | vendor_doc | README.md:4-8 |
| The serial interface opens the port at 9600 baud, 8 data bits, no parity and one stop bit with a 5.0 s timeout | upstream_code | acton_spec_interface.py:16-17 |
| A command is written as ASCII followed by CR (\r) | upstream_code | acton_spec_interface.py:171-172 |
| A reply is accepted only when it ends with ' ok\r\n' | upstream_code | acton_spec_interface.py:200 |
| read_done_status sends MONO-?DONE and returns the reply as a boolean | upstream_code | acton_spec_interface.py:29-31 |
| read_wl sends ?NM and parses the first token of the reply as a float in nm | upstream_code | acton_spec_interface.py:33-37 |
| write_wl sends '<wavelength> NM', write_wl_fast sends '<wavelength> GOTO' and write_wl_nonblock sends '<wavelength> >NM', each with three decimals | upstream_code | acton_spec_interface.py:39-53 |
| read_grating_info sends ?GRATINGS and parses one (number, name) line per grating; read_grating sends ?GRATING and returns the current number; read_grating_name returns the entry of the current grating | upstream_code | acton_spec_interface.py:55-106 |
| write_grating requires 0 < grating < 10 and sends '<grating> GRATING' | upstream_code | acton_spec_interface.py:108-110 |
| read_turret sends ?TURRET and returns an integer; write_turret only asserts a turret of 1, 2 or 3 and sends no command | upstream_code | acton_spec_interface.py:90-97 |
| read_exit_mirror sends 'EXIT-MIRROR ?MIRROR'; write_exit_mirror accepts FRONT or SIDE and sends 'EXIT-MIRROR <pos>' | upstream_code | acton_spec_interface.py:112-120 |
| read_entrance_slit sends 'SIDE-ENT-SLIT ?MICRONS', reports -1 for 'no motor' or 'no slit'; write_entrance_slit accepts 5 to 3000 um and sends 'SIDE-ENT-SLIT <n> MICRONS' | upstream_code | acton_spec_interface.py:122-137 |
| read_exit_slit sends 'SIDE-EXIT-SLIT ?MICRONS', reports -1 for 'no motor' or 'no slit'; write_exit_slit accepts 5 to 3000 um and sends 'SIDE-EXIT-SLIT <n> MICRONS' | upstream_code | acton_spec_interface.py:145-157 |
| home_entrance_slit is a TODO that only holds the string 'SIDE-ENT-SLIT SHOME' and sends no command | upstream_code | acton_spec_interface.py:140-142 |
| The ScopeFoundry component connects center_wl to read_wl/write_wl_fast, grating_id to read_grating/write_grating, grating_name to read_grating_name, entrance_slit and exit_slit to their read/write methods and exit_mirror to read_exit_mirror/write_exit_mirror | upstream_code | acton_spec.py:74-102 |
| The ScopeFoundry component declares center_wl in nm with vmin=-100 and vmax=2000 (a setting range, not a stated instrument range) | upstream_code | acton_spec.py:30-40 |
| The HardwareComponent computes a per-pixel wavelength calibration in get_wl_calibration/wl_p_calib from the grating_calibrations setting; it is a pure calculation on the component, not a method of the serial interface | upstream_code | acton_spec.py:121-152 |
| close() closes the serial port | upstream_code | acton_spec_interface.py:217-218 |

## Limits

| field | rule | source | ref |
|---|---|---|---|
| `center_wl` | `Limit.operator_required`: no text of the clone states the wavelength range of a spectrometer; the only wavelength range in the clone is the ScopeFoundry center_wl setting vmin=-100 vmax=2000, a component default rather than an instrument specification | operator | site-limits.json |
| `grating_id` | allowed 1 to 9 (`write_grating` asserts 0 < grating < 10) | upstream_code | acton_spec_interface.py:109 |
| `entrance_slit` | 5 to 3000 um (`write_entrance_slit` assertion) | upstream_code | acton_spec_interface.py:136 |
| `exit_slit` | 5 to 3000 um (`write_exit_slit` assertion) | upstream_code | acton_spec_interface.py:156 |
| `exit_mirror` | allowed FRONT or SIDE (`write_exit_mirror` assertion) | upstream_code | acton_spec_interface.py:119 |

`site-limits.example.json` fills `center_wl` with an example range; it is an example for a site, not a statement
about a particular instrument.  The driver refuses every `center_wl` write with `MHS.SAFETY.LIMITS_UNSET` until an
operator supplies that range.

## Safety

R1.  The e-stop is the native `close()` (acton_spec_interface.py:217-218): the clone has no stop or abort command, so
the driver closes the serial link and sends no further commands; a move already executing in the instrument is not
halted by this.  No line of the clone documents an independent hardware e-stop, so `estop_physical_ref` is not set
(R1 does not require it).  The upstream `write_turret` (acton_spec_interface.py:95-97) and `home_entrance_slit`
(acton_spec_interface.py:140-142) send no command and are not exposed.

Tags: spectrometer, monochromator, acton, princeton-instruments, serial, grating, slit
