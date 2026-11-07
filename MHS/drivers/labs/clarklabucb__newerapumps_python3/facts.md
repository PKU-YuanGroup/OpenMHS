# Facts and tags for gh.clarklabucb/newerapumps_python3

Every fact cites its source at commit `b8e3d0214ded43734ad22fa378b5bd408010f109`: `vendor_doc` (a text file of the
clone, here README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The upstream programs control New Era NE-500 OEM one-channel syringe pumps with 1 mL, 3 mL, 5 mL or 10 mL Becton Dickinson syringes | vendor_doc | README.md:27 |
| The pump GUI opens the serial chain at 19200 baud with a 0.2 s read timeout | upstream_code | pump_control3.py:23 |
| The GUI offers 1, 3, 5 and 10 mL BD syringes with inner diameters 4.699, 8.585, 11.99 and 14.50 mm | upstream_code | pump_control3.py:9-12 |
| Each pump on a chain is named a unique single digit integer 0-9 | vendor_doc | README.md:93 |
| A chain holds at most 10 pumps, addressed 0-9 | vendor_doc | README.md:102 |
| Flow rates are entered and displayed in uL/hour | vendor_doc | README.md:119 |
| The Prime button sets the flow rate to 10,000 uL/hr and starts the pump | vendor_doc | README.md:122 |
| The GUI sends the direction (INF or WDR) before the rate, then writes UH below 5000 and MH at 5000 or above by dividing the rate by 1000 | upstream_code | new_era3.py:47-61 |
| A rate query is sent twice: the fourth byte of the first reply is W for a withdraw, and the second reply carries the value and the UH or MH unit | upstream_code | new_era3.py:68-97 |
| The syringe diameter is set with `<n>DIA<mm>` and read with `<n>DIA` | upstream_code | new_era3.py:111-124 |
| The broadcast `*STP` stops all pumps; the per-pump stop sends `<n>STP` and then `<n>RAT0UH` | upstream_code | new_era3.py:26-41 |
| The broadcast `*RUN` starts all pumps | upstream_code | new_era3.py:20-24 |
| Prime starts one pump with `<n>RAT10.0MH` and then `<n>RUN` | upstream_code | new_era3.py:126-135 |

## Limits

Both writable parameters are `Limit.operator_required`; no text file of the clone states a numeric range for them.

| parameter | unit | limit | why |
|---|---|---|---|
| flow_rate | uL/h | operator_required | README.md:122 gives the 10,000 uL/hour prime rate, not a maximum, and no file states the NE-500 flow-rate range; the site supplies the range of its pump, syringe and tubing |
| diameter | mm | operator_required | pump_control3.py:9-12 lists four BD syringe sizes the GUI offers; that menu is a configuration choice, not a device bound, so the site supplies the range of the syringes it mounts |

`site-limits.example.json` shows an example overlay under the device id `mhs://localhost/newera-ne500`; its values
(0 to 10000 uL/h and 0.1 to 50 mm) are operator examples, not facts or limits of the device.

## Protocol and safety

The card proposed a SerialDriver, but the upstream builds every command from an address and a token
(`<n>DIRINF`, `<n>RAT<value>UH`, `<n>DIA<mm>`, `<n>STP`, `<n>RAT0UH`) in new_era3.py; it never writes a literal
command line. This package is therefore a direct Driver over the card's class `pump_control3:PumpControl`, using the
pyserial handle that class stores as `self.ser` (pump_control3.py:23). The wire syntax is the upstream's; the driver
adds no space and splits no token.

The device moves liquid, so the risk is R2 (MHS/spec/04-safety.md). The native stop is the broadcast `*STP` of
new_era3.stop_all (new_era3.py:26-30); the runtime latches first and then sends it. The safe-state action
`x-cap.clarklabucb.stop_pump.v1` sends the upstream per-pump stop `<n>STP` and then `<n>RAT0UH`
(new_era3.py:32-41). The clone documents no independent hardware e-stop, so the package relies on that safe-state
action for SAFE-045.

The package is model-authored and unreviewed. Its fake backend stands in for the pyserial handle; its start rate,
start diameter and start address are test data marked `# placeholder`, never facts or limits. No hardware backend
was run and no instrument was tried.

Tags: syringe pump, new era, ne-500, serial, fluid
