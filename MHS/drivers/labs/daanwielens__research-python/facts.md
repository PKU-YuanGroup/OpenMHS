# Facts and tags for gh.daanwielens/research-python

This package binds one device of the upstream repository: the Lake Shore Model 332 temperature controller
(`Lake.py`, the `*Lake*` section of `README.md:37-45`). The other entry symbols are different instruments (the SR830
lock-in amplifier and the Oxford IPS120/ITC503 controllers) and are not covered by this driver.

Every fact cites its source at commit `c17811c9b43bc581f5523f1e9eafd9dce1fdb9d2`. The facts are also written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The upstream program controls the Lake Shore 332 temperature controller and its PID loop | vendor_doc | README.md:39-41 |
| The upstream programs reach the instruments through PyVISA and NI-VISA | vendor_doc | README.md:5 |
| The Lake Shore is opened as the VISA resource GPIB0::12::INSTR | upstream_code | Lake.py:47 |
| The control-loop temperature is read with KRDG? and the Celsius reading with CRDG? | upstream_code | Lake.py:48-49 |
| The heater range is read with RANGE? and the heater output with HTR? | upstream_code | Lake.py:50-51 |
| Setpoint 1 is read with SETP? 1 | upstream_code | Lake.py:52 |
| The setpoint entry is labelled with kelvin | upstream_code | Lake.py:118 |
| Setpoint 1 is written as SETP 1,<value> | upstream_code | Lake.py:177 |
| Loop 1 PID is read with PID? 1 | upstream_code | Lake.py:85 |
| Loop 1 PID is written as PID 1,<p>,<i>,<d> | upstream_code | Lake.py:179 |
| Manual output 1 is read with MOUT? 1 | upstream_code | Lake.py:86 |
| Manual output is written as MOUT 1,<value> | upstream_code | Lake.py:178 |
| The heater range is written as RANGE <index> | upstream_code | Lake.py:180 |
| Heater range 0 is Off; ranges 1, 2 and 3 are low (0.5 W), medium (5 W) and high (50 W) | upstream_code | Lake.py:33 |
| The setpoint entry is labelled 4.5 to 280 | upstream_code | Lake.py:119 |
| The P and I entries are labelled 0.1 to 1000 | upstream_code | Lake.py:124-129 |
| The D entry is labelled 0 to 200 | upstream_code | Lake.py:134 |
| The manual output entry is labelled 0.0 to 100.0 | upstream_code | Lake.py:139 |
| The manual output is displayed in percent | upstream_code | Lake.py:247 |
| The controller temperature is displayed in kelvin and the Celsius reading with a degree-Celsius suffix | upstream_code | Lake.py:54-55 |
| The heater output is displayed in percent | upstream_code | Lake.py:57 |
| Importing the upstream file builds the Tk window, so this package does not import it | upstream_code | Lake.py:191 |

Limits (all `upstream_code`):

| parameter | command | limit | ref |
|---|---|---|---|
| setpoint (K) | SETP 1,<value> | 4.5 to 280 | Lake.py:119 |
| heater_range | RANGE <index> | one of 0, 1, 2, 3 | Lake.py:33 |
| manual_output (%) | MOUT 1,<value> | 0.0 to 100.0 | Lake.py:139 |
| PID p | PID 1,<p>,<i>,<d> | 0.1 to 1000 | Lake.py:124 |
| PID i | PID 1,<p>,<i>,<d> | 0.1 to 1000 | Lake.py:129 |
| PID d | PID 1,<p>,<i>,<d> | 0 to 200 | Lake.py:134 |

The upstream file is a Tkinter program, not an importable class: the callbacks open the VISA resource themselves
(`Lake.py:47-53, 84-87, 175-181`) and the module builds its window at import (`Lake.py:191, 266-269`). The
`ScpiDriver` card is therefore the right shape: the wire commands occur verbatim in the clone and the SCPI bridge
opens the instrument itself; the clone is never imported by this package.

Safety: the e-stop and the `x-cap.daanwielens.heater_off.v1` safe-state action write `RANGE 0`, the upstream's
first heater range (Off). The declared risk is R2 because the controller drives a heater whose high range is 50 W
(`Lake.py:33`); the upstream text shows no independent hardware e-stop, so the safe-state action is the declared
independent stop path for this unreviewed package. This package is model-authored and unreviewed, and its hardware
backend must not be used until a human signs `reviewed_by`. No hardware run was performed.

The fake is not a recording: the clone has no simulator, mock or session. It is a stateful line transport for the
commands the upstream program uses, and each canned value is marked `# placeholder` in `fake.py`, not copied into a
fact, a limit or the reference.

Tags: temperature controller, lakeshore, model 332, pid, scpi, gpib
