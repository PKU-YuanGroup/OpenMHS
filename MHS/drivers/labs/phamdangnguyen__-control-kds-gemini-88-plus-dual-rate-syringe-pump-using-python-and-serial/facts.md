# Facts and tags for gh.phamdangnguyen/control-kds-gemini-88-plus-dual-rate-syringe-pump-using-python-and-serial

Every fact cites its source at commit `ab6a02be981ea541d11f8788567030073ad2a378`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone:LINE`).  The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository controls a KDS Gemini 88 dual-rate syringe pump from Python over a serial COM port | vendor_doc | README.md:1-5 |
| The pump can infuse with one syringe and withdraw with the other, at different rates | vendor_doc | README.md:5 |
| The upstream's example command is 'condition Independent' | upstream_code | InfuseCode.py:5 |
| In the independent condition the commands take channel a, b or ab | vendor_doc | tutorial_command_basic.txt:4 |
| The tutorial lists the command forms for syringe selection, syringe volume, diameter, target time, target volume, infusion rate, run, status and stop | vendor_doc | tutorial_command_basic.txt:4-27 |
| The example syringe selection is 'syr ab sst 1' | vendor_doc | tutorial_command_basic.txt:4 |
| 'status' reports the state of the pumps | vendor_doc | tutorial_command_basic.txt:25 |
| A command is written as its bytes plus a carriage return and a line feed | upstream_code | realSerial.py:31 |
| The serial port defaults to 9600 baud, a 10 s timeout, odd parity, two stop bits and seven data bits | upstream_code | realSerial.py:6 |
| The upstream reads the reply bytes waiting on the port | upstream_code | realSerial.py:39-45 |
| The example sends the command through realSerial.writeSerial and optionally reads the reply through realSerial.readSerial | upstream_code | InfuseCode.py:9-11 |
| The README says the pump stops when it reaches the volume specified in the code | vendor_doc | README.md:30 |
| The README says the pump's display need not change when software controls it | vendor_doc | README.md:28 |
| The README names pyserial 3.5 as the serial dependency | vendor_doc | README.md:21 |

Limits: every numeric write and invoke input is `Limit.operator_required`, because no text file of the clone states
a range.  The operator supplies the installed syringe, process and tubing envelope in `site-limits.json`; without
one the runtime refuses the call `MHS.SAFETY.LIMITS_UNSET`.

| parameter / input | command | limit | why the clone states none |
|---|---|---|---|
| syringe_volume (uL) | `svolume ab {value} ul` | operator_required | the installed syringe sets the volume (tutorial_command_basic.txt:5-7) |
| diameter (mm) | `diameter ab {value}` | operator_required | the installed syringe sets the diameter (tutorial_command_basic.txt:8-10) |
| target_time (s) | `ttime ab {value} sec` | operator_required | the process sets the target time (tutorial_command_basic.txt:11-13) |
| target_volume (uL) | `tvolume ab {value} ul` | operator_required | the installed syringe and process set the volume (tutorial_command_basic.txt:14-16) |
| flow_rate (mL/min) | `irate ab {value} ml/min` | operator_required | the installed syringe, motor and tubing set the rate (tutorial_command_basic.txt:17-21) |
| x-cap.phamdangnguyen.syringe.v1 index | `syr {channel} {code} {index}` | operator_required | the pump's syringe list sets the index (tutorial_command_basic.txt:4) |

The values in `site-limits.example.json` are example operator bounds for the acceptance run; they are not device
facts and are not copied into `driver.py`.  The operator's own overlay replaces them at deployment.

Safety: the stop command `stop ab` stops both pumps in the independent condition (tutorial_command_basic.txt:26-27).
The driver sends it from the safe-state action and from the native e-stop.  There is no independent hardware e-stop
to cite in the clone, so the independent stop path is the safe-state action; no hardware was attached.

Tags: syringe pump, kds, gemini 88, serial, infuse, withdraw, dual rate
