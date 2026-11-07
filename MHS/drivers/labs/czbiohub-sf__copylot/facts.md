# Facts and tags for gh.czbiohub-sf/copylot

Every fact cites its source at commit `eac4fdbf6ee49130d25764a486acb35a48d999db`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or
`upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

The package serves one device of the repository: the Vortran Stradus laser wrapper
`copylot/hardware/lasers/vortran/vortran.py:VortranLaser` (a direct Driver, see the deviation note in `driver.py`).

| fact | source | ref |
|---|---|---|
| The wrapper drives a Vortran Stradus laser over RS-232/COM | upstream_code | copylot/hardware/lasers/vortran/vortran.py:1-9 |
| Every command must terminate with a carriage return '\r' or 0x0D to be processed | upstream_code | copylot/hardware/lasers/vortran/vortran.py:173-174 |
| A command with a value is sent as 'CMD=value' and a command without one as 'CMD', both plus the carriage return | upstream_code | copylot/hardware/lasers/vortran/vortran.py:187-192 |
| A reply is parsed as the command name, '=', and the values separated by ', ' | upstream_code | copylot/hardware/lasers/vortran/vortran.py:225-228 |
| All replies to commands are in upper case | upstream_code | copylot/hardware/lasers/vortran/vortran.py:217 |
| The command vocabulary is the four lists GLOBAL_CMD, GLOBAL_QUERY, LASER_CMD and LASER_QUERY | upstream_code | copylot/hardware/lasers/vortran/vortran.py:20-48 |
| Emission is switched with LE: 1 = on, 0 = off; the setter sends 'LE=<value>' | upstream_code | copylot/hardware/lasers/vortran/vortran.py:325-340 |
| turn_on and turn_off are aliases that set the emission toggle to 1 and 0 | upstream_code | copylot/hardware/lasers/vortran/vortran.py:342-356 |
| The emission delay is a 5 second delay toggled with DELAY: 1 = on, 0 = off | upstream_code | copylot/hardware/lasers/vortran/vortran.py:276-291 |
| Laser power is set with LP and read with ?LP; it requires pulse mode to be off | upstream_code | copylot/hardware/lasers/vortran/vortran.py:358-379 |
| The power setter clamps the requested value to the maximum power read from the head | upstream_code | copylot/hardware/lasers/vortran/vortran.py:373-377 |
| Maximum laser power is queried with ?MAXP | upstream_code | copylot/hardware/lasers/vortran/vortran.py:413-419 |
| Pulse mode is toggled with PUL: 1 = on | upstream_code | copylot/hardware/lasers/vortran/vortran.py:398-411 |
| The status query returns a fault code (?FC) and a fault description (?FD) | upstream_code | copylot/hardware/lasers/vortran/vortran.py:425-434 |
| The wrapper identifies the head with ?LI: the serial number and the head's data fields | upstream_code | copylot/hardware/lasers/vortran/vortran.py:240-251 |
| The wrapper opens the port with a default baud rate of 19200 | upstream_code | copylot/hardware/lasers/vortran/vortran.py:50 |

Limits: no text file of the clone states a power range. The maximum power is a property of the head (read with
`?MAXP` at connect) and the upstream setter clamps to it, so it is not a fixed bound of the device; the power set
point is therefore `Limit.operator_required` and the operator overlay (`site-limits.json`, see
`site-limits.example.json`) supplies the operating range. The emission delay and the pulse mode are flags: no numeric
bound applies.

Safety: the laser emission is the one actuation this driver switches; the e-stop calls the upstream `turn_off`
alias (the emission toggle goes to 0, `LE=0`), and the same command is the safe-state action. The clone states no
laser safety class and no power range; a Stradus head is a laser above class 1, so a model review raised the risk to R2
(MHS/spec/04-safety.md), and a class 3B or 4 head is R3. The 5 second emission delay is a device feature the driver exposes
but does not enforce.

Units: the clone names no unit for the laser power, the pulse power or the current control (only the garbled comments
of `_identify_laser` at vortran.py:248-249 mention nm and mW for other fields), so the power fields are declared
dimensionless (`1`) and their descriptions say so.

Tags: laser, vortran, stradus, emission, serial
