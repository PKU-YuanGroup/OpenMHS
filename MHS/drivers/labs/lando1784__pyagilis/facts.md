# Facts and tags for gh.lando1784/pyagilis

Every fact cites the clone at commit `7d27bd1571aa6b4187e2e0d40c9f34feb45456f2`; the same facts are written into
`driver.py` (`facts = [...]`).  The reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The package is a Python library for Newport Agilis piezo motion controllers (agUC2 and agUC8) | vendor_doc | README.md:2 |
| AGUC2 resets with 'MR' and then installs axis 1 and axis 2 | upstream_code | pyagilis/controller.py:30-33 |
| AGUC2.move jogs axis 1 and waits until it is still, then jogs axis 2 and waits | upstream_code | pyagilis/controller.py:41-46 |
| goToZero reads both axis counters and jogs each axis by the negative of its counter | upstream_code | pyagilis/controller.py:81-89 |
| setZero resets the counter of both axes | upstream_code | pyagilis/controller.py:92-95 |
| A jog of n steps sends '<axis>PR<n>' | upstream_code | pyagilis/channel.py:75-83 |
| The stop command of an axis is '<axis>ST' | upstream_code | pyagilis/channel.py:45-48 |
| queryCounter sends '<axis>TP' and returns the accumulated steps since power-on or the last reset | upstream_code | pyagilis/channel.py:64-67 |
| amIatMyLimit reads the 'PH' limit-switch status | upstream_code | pyagilis/channel.py:59-62 |
| A counter reset sends '<axis>ZP' | upstream_code | pyagilis/channel.py:69-72 |
| The serial port is opened at 921600 baud with 8 data bits, no parity and one stop bit | upstream_code | pyagilis/agPort.py:38 |
| The step amplitude of an axis is stated as 0 to 50 | upstream_code | pyagilis/channel.py:24 |

## Native interface confirmed by recon

| native member | kind | what it does | ref |
|---|---|---|---|
| `AGUC2.__init__` | constructor | opens the serial port, sends `MR`, installs axis 1 and axis 2 | pyagilis/controller.py:21-33 |
| `AGUC2.move(d1, d2)` | action | relative jog of both axes; waits for each to stop | pyagilis/controller.py:41-46 |
| `AGUC2.goToZero()` | action | jogs each axis back by its counter | pyagilis/controller.py:81-89 |
| `AGUC2.setZero()` | action | resets both counters | pyagilis/controller.py:92-95 |
| `AGUC2.stop()` | action | upstream stop; the wrapper in native.py sends `ST` per axis because line 100 uses the removed `Thread.isAlive` | pyagilis/controller.py:98-105, pyagilis/channel.py:45-48 |
| `Axis.queryCounter()` | read | returns accumulated steps from the `TP` reply | pyagilis/channel.py:64-67 |
| `Axis.amIatMyLimit()` | read | reads the `PH` limit-switch reply | pyagilis/channel.py:59-62 |
| `Axis.whatDidIdo()` | read | returns the last operation string | pyagilis/channel.py:40-43 |
| `Axis.jog(n)` | write (wire) | sends `<axis>PR<n>`; there is no bound in the clone | pyagilis/channel.py:75-83 |
| `Axis.stop()` | write (wire) | sends `<axis>ST` | pyagilis/channel.py:45-48 |

The wire syntax is assembled by the upstream class (`name+'PR'+str(int(steps))`, `name+'ST'`, `name+'TP'`), so a
SerialDriver command table cannot reproduce it; the package uses a direct Driver over the upstream object.  The
hardware factory is `native.py` (never imported by the gate); the fake is `fake.py`.

## Limits

| field | limit | ref |
|---|---|---|
| `x-cap.lando1784.jog.v1.x_steps` | `Limit.operator_required`: the clone states no travel or step bound | pyagilis/channel.py:75-83 (no bound in the docstring or the command) |
| `x-cap.lando1784.jog.v1.y_steps` | `Limit.operator_required`: the clone states no travel or step bound | pyagilis/channel.py:75-83 (no bound in the docstring or the command) |

`site-limits.example.json` shows the operator overlay that fills these two paths; its values are illustrative and
must be replaced with the travel of the installed stage.  Nothing in the clone states a per-move step range, so no
number is presented as a device fact.

## Safety

The device is a two-axis piezo motion controller.  The package declares R1 (the card floor is R0; the catalogue's
single-axis motion capabilities are R1).  The e-stop is the upstream stop path: `@estop` calls `self.native.stop()`,
which the hardware wrapper implements as `Axis.stop()` on each axis (`ST`).  The safe-state action is
`x-cap.lando1784.stop.v1`, also calling the native stop.  There is no independent hardware e-stop cited in the clone,
so none is invented; R1 does not require one.

The upstream `AGUC2.stop()` itself calls `Thread.isAlive` (`pyagilis/controller.py:100`); that attribute no longer
exists in Python 3.9 and later.  The hardware factory wraps the controller and implements `stop` by sending `ST` to
each axis, so the safe state does not depend on the removed API.  This is a hardware-path detail only; the fake
implements `stop` directly.

Tags: newport, agilis, piezo, motion-controller, serial
