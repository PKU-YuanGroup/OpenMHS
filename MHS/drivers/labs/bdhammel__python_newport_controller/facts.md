# Facts and tags for gh.bdhammel/python_newport_controller

Every fact cites its source at commit `1d960070435d1a47708ed42986697ac72a0ba4f3`: `vendor_doc` for a text file of
the clone (`README.md`) and `upstream_code` for `newport.py`. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The clone is a Python driver for a New Focus Picomotor motion controller over USB | vendor_doc | README.md:1 |
| The README says the script was tested with a single closed-loop Picomotor controller (model 8745) | vendor_doc | README.md:6 |
| The NewFocus command grammar is an optional one-digit driver number, a two-or-more letter mnemonic and an optional numeric parameter | upstream_code | newport.py:45 |
| parse_command builds the USB text `1>{driver} {command} {parameter}\r` from a NewFocus command | upstream_code | newport.py:178-189 |
| xPRnn moves motor x by nn steps | vendor_doc | README.md:108 |
| ST stops all motor movement | vendor_doc | README.md:107 |
| The connection check queries motor positions with `1>1 TP?` through `1>4 TP?` | upstream_code | newport.py:33-36 |
| The connect check assumes four motor channels and asks each for its motor type with `{m}QM?` | upstream_code | newport.py:129-134 |
| The motor-type reply maps 0 to no motor connected, 1 to motor unknown, 2 to 'Tiny' and 3 to 'Standard' | upstream_code | newport.py:46-51 |
| The console reads input with raw_input, which does not exist in Python 3, so start_console is not exposed as a capability | upstream_code | newport.py:255 |
| The README directs the reader to section 6.2 of an external 8745 manual for the full command list | vendor_doc | README.md:118 |
| The device is found by USB product and vendor ids through usb.core and uses its first IN and OUT endpoints | upstream_code | newport.py:90-122 |

## Limits

The two inputs of `x-cap.bdhammel.move_steps.v1` are `Limit.operator_required`:

- `axis`: no text file of the clone states how many motor channels the installed controller drives. The connect
  check polls four channels (`newport.py:129-134`), but that is an assumption of that check, not a bound of the
  device, so the site sets the installed channel range.
- `steps`: no text file of the clone states a travel range or maximum step count. The README names `xPRnn` without a
  bound and links the full command list to an external PDF manual (`README.md:118`), so the site sets the step bound.

`site-limits.example.json` is an example overlay that fills both paths; it is operator data, not a fact about any
unit. Without an overlay every move is refused `MHS.SAFETY.LIMITS_UNSET` before a native call.

## Safety

The native stop is `ST` through `newport.Controller.command()` (`README.md:107`). It is the `@estop` path and,
through `cap.motion.stop.v1` (`safe_state=True`), the safe-state action. No line of the clone documents an independent
hardware e-stop, so `estop_physical_ref` is not set; the package is R1, below the R2/R3 requirement for an
independent stop (SAFE-045).

`Controller.start_console()` is not exposed: it blocks on `raw_input` (`newport.py:255`), which does not exist in
Python 3, and an arbitrary command channel would bypass every declared bound. The package exposes only the position
read, the relative step move and the stop.

This package is model-authored (`driver.lock.json` `authored_by` kind `model`) and unreviewed (`reviewed_by` null).
The gate checks only the fake backend; the hardware backend has never been run or reviewed.

Tags: picomotor, motion, newfocus, usb
