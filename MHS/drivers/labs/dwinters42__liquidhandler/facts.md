# Facts and tags for gh.dwinters42/liquidhandler

Every fact cites its source at commit `45e303634e7921633dde36a0466962a3a300543f`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The constructor opens the serial port with rtscts=0, xonxoff=0 and timeout=0 | upstream_code | liquidhandler.py:44-45 |
| The constructor initializes every arm with PI, SP0 and SA and every pump with Z1 0 R | upstream_code | liquidhandler.py:47-59 |
| armaddr is [18, 28] for the two arms and pumpaddr is [11] for the syringe pump | upstream_code | liquidhandler.py:32-38 |
| Move formats the arm command PA x y z, sends it to armaddr[armnum-1] and stores the position in curpos | upstream_code | liquidhandler.py:89-93 |
| MoveAxis formats the command XA, YA or ZA with an integer position and updates curpos | upstream_code | liquidhandler.py:95-100 |
| AddPosition stores coordinates [x, y, z] under a name in locations | upstream_code | liquidhandler.py:77-79 |
| ShowPosition returns the stored curpos of an arm | upstream_code | liquidhandler.py:102-103 |
| Draw takes bottle or sample as source, refuses a draw above 2000 units of syringe content and calls Pump twice | upstream_code | liquidhandler.py:116-130 |
| Dispense refuses more units than the tracked syringe content and calls Pump twice | upstream_code | liquidhandler.py:107-114 |
| Pump refuses a speed below 0 or above 20, a position below 0 or above 2000, and a direction other than in or out, then sends S<speed> A<position> <I\|O> R | upstream_code | liquidhandler.py:132-147 |
| The protocol frames each message as 0xFF 0x02 <message> 0x03 <checksum> 0x0D | vendor_doc | Protocol.md:23-26 |
| The protocol lists PI, SP0, SA and PA for arms and Sx Ay d R for syringe pumps, with no stop or halt command | vendor_doc | Protocol.md:55-65 |
| The protocol addresses arm 1 as 18, arm 2 as 28, syringe 1 as 11 and syringe 2 as 12 | vendor_doc | Protocol.md:39-48 |
| The protocol return codes are @ accepted, A error, Q execution in progress and Y finished | vendor_doc | Protocol.md:70-79 |
| The README describes a library and GUI for Waters 2700-compatible liquid handlers with 1-2 arms, attached syringes and one 6-port valve | vendor_doc | Readme.md:4-7 |
| The README lists moving up to two arms and drawing or dispensing with the syringe pump and 6-port valve | vendor_doc | Readme.md:9-15 |
| The example calls Move, AddPosition, Goto, Draw and Dispense | vendor_doc | examples/simple.py:5-15 |

Limits: the syringe speed has the 1 to 20 bound stated by the protocol (`Protocol.md:64`). The arm travel, the
syringe volume, the pump position and the arm/pump/axis counts are constructor configuration, not stated device
bounds, so they are `Limit.operator_required`; `site-limits.example.json` shows the operator overlay that fills them.

Safety: the clone documents no stop or halt command (`Protocol.md:55-65`). The e-stop and the safe-state action
`x-cap.dwinters42.stop_pump.v1` both command every syringe pump to zero speed at its tracked position, which the native
`Pump` accepts (the code refuses only speeds below 0 or above 20, `liquidhandler.py:132-134`), and the runtime latch
refuses further commands. No text documents an independent hardware e-stop, so `estop_physical_ref` is not set; this
is a software safe state, not a hardware stop.

Tags: liquid-handler, syringe-pump, robot-arm, serial, framed-protocol
