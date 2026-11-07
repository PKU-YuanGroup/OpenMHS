# Facts and tags for gh.amsikking/zaber_x_adr130

Every fact cites its source at commit `7c5926e07929b5c40ea6049ea5bceab28609bb0e`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (a path of the clone and a line). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is a Python device adaptor for the Zaber X-ADR130 linear motor XY microscope stage | vendor_doc | README.md:1-2 |
| The adaptor writes the ASCII command '/get device.id' and reads the reply before any motion | upstream_code | zaber_X_ADR130.py:37-63 |
| Device id 50998 is recognized as an X-ADR130B100B-SAE53D12 | upstream_code | zaber_X_ADR130.py:51-52 |
| The constructor rejects an x limit outside 0 to 130 mm and a y limit outside 0 to 100 mm | upstream_code | zaber_X_ADR130.py:20-25 |
| A command is sent as '/<device address> <command>\n'; a reply begins with '@<device address>' and ends with CRLF | upstream_code | zaber_X_ADR130.py:73-94 |
| get_position_mm reads 'get pos' and converts each axis from nm to mm by 1e-6 | upstream_code | zaber_X_ADR130.py:236-244 |
| An x move is sent as '1 move abs <position in nm>' and is not sent when the target is outside the configured x limits | upstream_code | zaber_X_ADR130.py:150-166 |
| A y move is sent as '2 move abs <position in nm>' and is not sent when the target is outside the configured y limits | upstream_code | zaber_X_ADR130.py:202-218 |
| get_maxspeed reads 'get maxspeed' and converts each axis to mm/s with 1e-6 / 1.6384, rounded to three decimals | upstream_code | zaber_X_ADR130.py:260-269 |
| set_maxspeed sends '1 set maxspeed' and '2 set maxspeed' with 1e6 * 1.6384 * mm/s | upstream_code | zaber_X_ADR130.py:271-280 |
| The x axis is stopped with '1 stop' | upstream_code | zaber_X_ADR130.py:168-174 |
| The y axis is stopped with '2 stop' | upstream_code | zaber_X_ADR130.py:220-226 |

Limits (all `upstream_code`):

| parameter | limit | ref |
|---|---|---|
| x_mm (absolute XY move input) | 0 to 130 mm | zaber_X_ADR130.py:21 (the constructor asserts `0 <= x <= 130`) |
| y_mm (absolute XY move input) | 0 to 100 mm | zaber_X_ADR130.py:24 (the constructor asserts `0 <= y <= 100`) |
| x_maxspeed (writable state) | 0.01 to 750 mm/s | zaber_X_ADR130.py:277 (`assert 0.01 <= x_mmps <= 750`) |
| y_maxspeed (writable state) | 0.01 to 750 mm/s | zaber_X_ADR130.py:277 (`assert 0.01 <= y_mmps <= 750`) |

These are the values the upstream code itself accepts and checks; none is a constructor default copied into a bound.
The constructor defaults `x_limits_mm=(0, 130)`, `y_limits_mm=(0, 100)` and `maxspeed_mmps=(100, 100)` (lines 13-15)
are not used as sources: an operator may configure the controller differently, and the asserts on lines 21, 24 and
277 are the bounds the code enforces on any configured value.

Units: positions are millimetres, speeds millimetres per second. The upstream works internally in nanometres for
positions (line 161: `1e6 * x_mm`) and in `1e6 * 1.6384 * mm/s` for speeds (line 278). The read-back of the speed
is rounded to three decimals (lines 263-265), so the setter rounds to that resolution before calling the upstream
`set_maxspeed`, whose round-trip assertion on line 280 would otherwise reject a value with more decimals.

Safety: the e-stop calls the upstream stop of each axis, `_stop_x` (line 171: `1 stop`) and `_stop_y` (line 223:
`2 stop`). The upstream stop helpers assert that the reply reports the axis BUSY (lines 171 and 223); the stop
command is sent before the assertion. There is no independent hardware e-stop in the text of the clone, and this
package declares none. The device is a motorized XY stage: the driver is R1 (the card's floor and the catalogue's
motion class floor), and it claims no protection beyond the runtime's latch and the two software stop commands. The
upstream has no locking around the serial port, and the driver does not claim that its stop is safe against a
concurrent read on the wire.

Tags: zaber, x-adr130, xy stage, microscope stage, serial, ascii protocol
