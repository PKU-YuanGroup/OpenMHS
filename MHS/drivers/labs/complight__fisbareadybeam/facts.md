# Facts, limits and tags for gh.complight/fisbareadybeam

The clone is one Python module, `FisbaReadyBeam/__init__.py`, that drives a Fisba ReadyBeam multicolor laser module
over a framed serial protocol (MeCom): a command carries an address, a sequence number, a parameter id, an instance
and a CRC16 checksum (FisbaReadyBeam/__init__.py:125-193). This package is a direct Driver over that class; the
card's SerialDriver cannot express the frames ("DEVIATION FROM THE CARD" in RESULT.json).

Every fact cites its source at commit `65b73a79aa1fe3eb10c809246a40e44449780492`: `upstream_code` is a code or
docstring line of the clone, `vendor_doc` a text file of it. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| A command is framed as '#' + address + sequence + '?VR' (query) or 'VS' (set) + parameter id + instance + parameter; the parameter is eight hex digits (an IEEE-754 float or an integer) | upstream_code | FisbaReadyBeam/__init__.py:160-193 |
| The frame carries the address, a sequence number modulo 0x10000 and a CRC16 XMODEM checksum over the text, and ends with CR | upstream_code | FisbaReadyBeam/__init__.py:125-136 |
| The three channel instances are red 1, green 2 and blue 3 | upstream_code | FisbaReadyBeam/__init__.py:171 |
| set_brightness takes a list of powers in percent, one per channel, and sends for each channel a channel-switch command (parameter 7006) and a power command (parameter 7013) | upstream_code | FisbaReadyBeam/__init__.py:209-217 |
| A channel is switched on when its power is greater than 0 and off otherwise | upstream_code | FisbaReadyBeam/__init__.py:210-213 |
| Laser powers are set in percentage using floating numbers and the maximum percentage is 100.5 | upstream_code | FisbaReadyBeam/__init__.py:203 |
| The device status is read from parameter 104 and the class lists Init, Ready, Run, Error, Bootloader and Pending Reset | upstream_code | FisbaReadyBeam/__init__.py:22-29 |
| The device type is read from parameter 100 and should answer 1171, which means RGB-1171 | upstream_code | FisbaReadyBeam/__init__.py:248-253 |
| open() enables digital control by setting parameter 7000 to 1; close() disables it with 7000 set to 0 and closes the port | upstream_code | FisbaReadyBeam/__init__.py:60-87 |
| The device error codes 1 to 9 are Command not available, Device is busy, General communication error, Format error, Parameter not available, Parameter is read-only, Value is out of range, Instance is not available, and Parameter general error | upstream_code | FisbaReadyBeam/__init__.py:11-21 |
| The library controls Fisba ReadyBeam laser light sources and was only tested on Ubuntu 22.04 | vendor_doc | README.md:2-4 |

## Limits

| parameter | unit | limit | source |
|---|---|---|---|
| brightness (list of 3 numbers, red/green/blue) | % | 0 to 100.5 per channel | upstream_code: FisbaReadyBeam/__init__.py:203-213 |

The range comes from two lines of `set_brightness`: its docstring states the maximum percentage of 100.5 (line 203),
and its code switches a channel off when the power is not greater than 0 (lines 210-213), so 0 is the lower end. The
class itself does not validate the value; the runtime enforces this bound before the native call.

No other parameter is writable, so there is no operator-required bound and no `site-limits.example.json` need; the
example file in this package narrows the brightness range for one bench.

## Safety

* The e-stop calls the native `set_brightness` with three zeros: `set_brightness` switches the channel switch
  (parameter 7006) off for a power that is not greater than 0, so every laser goes off. The upstream test itself
  calls `set_brightness([0, 0, 0])` before closing the module (test/test_on_off.py:24-26).
* The clone does not state the laser safety class of the module or any hardware interlock; the site's laser safety
  measures stay authoritative, and the physical laser interlock is not modelled by this package.
* The e-stop and the safe state are the same native call, so a latched e-stop leaves the module with all channels at
  0 percent until an operator resets it.
* Hardware is never attached in the acceptance run; the package's hardware backend (`native.py`) was never opened.

## Tags

laser, light source, multicolor, rgb, serial, mecom, fisba, readybeam
