# Facts and tags for gh.drkirkm/syringepump

Every fact cites its source at commit `6a39723535c339f24b0eeb7332c2dfe96e5a7afb`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`).  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository controls and operates Harvard Apparatus OEM model syringe pumps from a desktop program | vendor_doc | README.md:4 |
| The program is set up to control up to 3 pumps, each with its own address 00, 01 or 02 | vendor_doc | README.md:8 |
| The program uses pyserial 3.5 and PyQt5 5.9.7, and its serial port defaults to COM1 | vendor_doc | README.md:5-6 |
| Pumps is a QMainWindow desktop GUI class, not a device transport | upstream_code | pumpcontroller.py:15 |
| The module's only runtime entry creates a QApplication, instantiates Pumps and enters the Qt event loop | upstream_code | pumpcontroller.py:412-416 |
| Every command opens the serial line at 9600 baud, 8 data bits, no parity and a 0.5 s timeout | upstream_code | pumpcontroller.py:229 |
| A diameter command is the bytes 'MMD ', the entered text and a carriage return | upstream_code | pumpcontroller.py:231 |
| Flow-rate commands are 'MLH ', 'ULH ' or 'ULM ' followed by the entered text and a carriage return | upstream_code | pumpcontroller.py:240-258 |
| The first pump group sends the unprefixed RUN and STP commands | upstream_code | pumpcontroller.py:264-278 |
| The second pump group prefixes the same commands with 01: 01MLH, 01MMD, 01RUN and 01STP | upstream_code | pumpcontroller.py:270-301 |
| The third pump group prefixes the same commands with 02: 02MLH, 02MMD, 02RUN and 02STP | upstream_code | pumpcontroller.py:325-367 |
| The stop-all handler writes STP, 01STP and 02STP | upstream_code | pumpcontroller.py:373-377 |
| The close handler writes STP, 01STP and 02STP to stop all pumps before exit | upstream_code | pumpcontroller.py:404-407 |
| The diameter handler writes the command and closes the port without reading a reply | upstream_code | pumpcontroller.py:232-235 |
| The GUI lists the diameters 4.78, 8.66, 12.06, 14.5, 19.13 and 21.7 mm for 1, 3, 5, 10, 20 and 30 mL syringes | upstream_code | pumpcontroller.py:139 |
| The third pump's uL/min handler writes 02ULH instead of 02ULM | upstream_code | pumpcontroller.py:355-358 |

## Shape of this package (a card deviation, not a fact)

The card's family-config / SerialDriver shape was replaced by a direct `Driver` with `native.py`, because the
upstream is a Qt main window whose handlers each write one line, while a run is the sequence "set the rate" and
`RUN` and the safe state is the sequence `STP`, `01STP`, `02STP` (`pumpcontroller.py:240-278`, `373-377`).  A
command table could bind one line per capability but not those sequences.  The driver still writes exactly the
clone's bytes; it calls the upstream handler names through a fake or the injected-port hardware object.

The address is a driver option (`00` by default, `01` and `02` are the other prefixes of the clone).  The
unprefixed handler group is used for `00`, the `01` group for `01` and the `02` group for `02`; no wire syntax is
changed.  The fake is a recording stand-in, not a transcript: the clone contains no recorded exchange and never
reads a reply, so there is nothing to replay.

## Limits and commanded state

No text file of the clone states a flow-rate range or a diameter range.  Both numeric writes are therefore
`Limit.operator_required`; the operator supplies the installed syringe, motor and tubing envelope in
`site-limits.json`, and without one the runtime refuses the write `MHS.SAFETY.LIMITS_UNSET`.  The diameters the
GUI prints are examples of syringe sizes, not a closed set of accepted values.

The values in `site-limits.example.json` are example operator bounds for the acceptance run; they are not device
facts and are not copied into `driver.py`.  The operator's own overlay replaces them at deployment.

The upstream never reads a reply from the pump (`pumpcontroller.py:232-235`), so the reads `flow_rate`, `diameter`
and `pumping` report the last values this driver commanded, not measurements.  A restart of the process starts them
at zero/false; the pump's own state is not queried.

## Safety

The pump dispenses liquid, so the driver is R2 even though the card's floor is R0.  The safe-state action sends
`STP`, `01STP` and `02STP` (the clone's stop-all handler, `pumpcontroller.py:373-377`); the native e-stop sends the
stop handler of the configured address (`pumpcontroller.py:278`, `285`, `333`).  The clone has no independent
hardware e-stop to cite, so the independent stop path is the safe-state action.  No hardware was attached and the
hardware backend was never run.

Tags: syringe pump, harvard apparatus, serial, infuse, dispense
