# Facts and tags for gh.solgaardlab/apt_piezo

Every fact cites its source at commit `677eb8f632b6b1d7c84c1fd83a5821239331e4a5`. `vendor_doc` is documentation
text of the clone (README.md); `upstream_code` is code of the clone, cited as `path/in/clone:LINE`. The same facts
are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The clone is a Thorlabs APT controller compatibility library for the BPC-303 controller through USB | vendor_doc | README.md:3-9 |
| The README gives the move argument in microns | vendor_doc | README.md:34 |
| The README lists piezo zeroing, control-mode changes and closed-loop piezo movement | vendor_doc | README.md:16-18 |
| Module.__init__ enables closed-loop mode and sends the zero-position message | upstream_code | interface/module.py:25-27 |
| Module.move clamps the requested travel between 0 and the configured max_travel | upstream_code | interface/module.py:37-38 |
| Module.move sends message 0x0646 with a 2-byte channel word and a 2-byte output position computed from 0 to 32767 | upstream_code | interface/module.py:29-50 |
| Module.zero sends message 0x0658 with payload 0x01,0x00 to the module bay | upstream_code | interface/module.py:52-57 |
| Module.set_closed_loop sends message 0x0640 with 0x01,0x02 for closed loop and 0x01,0x01 for open loop | upstream_code | interface/module.py:59-70 |
| APT detects used bays among 10 and constructs each Module with a fixed max_travel constructor argument | upstream_code | apt.py:12-21 |
| The controller opens the FTDI device 0x0403:0xfaf0 at 115200 baud, 8 data bits, 1 stop bit and no parity | upstream_code | interface/controller.py:42-51 |

## Reading the device

The clone has no position query and no control-mode query for a module: `Module.move` and `Module.zero` only write
the framed messages, and `Controller.read_data` is used only to poll the bay-used response during `APT()`
(`apt.py:17`). The driver therefore publishes the last commanded travel and control mode and says so in the
descriptions; it never claims a measured position.

## Limits

`position` (the writable resource field) and the `position_um` input of `x-cap.solgaardlab.move_piezo.v1` are
`Limit.operator_required`. No text file of the clone states the travel of an attached piezo stage. `Module.move`
clamps to `max_travel` (`interface/module.py:37-38`), but `APT` supplies that value as a fixed constructor argument,
30 (`apt.py:21`): a library configuration, not a stage specification. The operator supplies the travel range in
`site-limits.json`; `site-limits.example.json` shows the overlay with an example range.

## Safety

The native stop and the safe-state action `x-cap.solgaardlab.zero_piezo.v1` both call `Module.zero()`
(`interface/module.py:52-57`), which sends the zero-position message for the module bay. The clone defines no
separate stop command. No line of the clone documents an independent hardware e-stop, so `estop_physical_ref` is not
set; the device is R1, so SAFE-045 does not apply, and the safe-state action gives the runtime a no-input stop path.

The hardware path (`native.py`) has never been run; it is model-authored and unreviewed. The fake is an in-memory
object that mirrors only the upstream methods `move`, `zero` and `set_closed_loop` plus the `max_travel` attribute.

Tags: piezo, thorlabs, apt, motion, actuator
