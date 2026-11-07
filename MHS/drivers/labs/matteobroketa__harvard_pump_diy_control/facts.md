# Facts and tags for gh.matteobroketa/harvard_pump_diy_control

Every fact cites its source at commit `d4a888432a81d69dad963fddb9df5adf3bc94633`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| A Model 44 command is the pump address followed by the upper-case command word and optional arguments | upstream_code | refactored_pump_control/harvard_phd2000_driver.py:143-152 |
| A complete response ends in a line-framed one- or two-digit address and one state character | upstream_code | refactored_pump_control/harvard_phd2000_driver.py:44-50 |
| The prompt state characters are ':' stopped, '>' infusing, '<' withdrawing, '/' paused, '*' stalled and '^' trigger wait | upstream_code | refactored_pump_control/harvard_phd2000_driver.py:36-43 |
| The pump address is an integer from 0 to 99 | upstream_code | refactored_pump_control/harvard_phd2000_driver.py:63-71 |
| The rate unit tokens the clone sends are UH (uL/h), UM (uL/m), MH (mL/h) and MM (mL/m) | upstream_code | refactored_pump_control/harvard_phd2000_driver.py:212-225 |
| set_rate sends RAT when infusing and RFR when withdrawing, with the numeric rate and the unit token | upstream_code | refactored_pump_control/harvard_phd2000_driver.py:256-270 |
| get_rate queries RAT or RFR and returns the rate and unit parsed from the reply | upstream_code | refactored_pump_control/harvard_phd2000_driver.py:275-285 |
| set_direction sends DIR INF for infuse and DIR REF for withdraw | upstream_code | refactored_pump_control/harvard_phd2000_driver.py:287-299 |
| start sends RUN and verifies the infusing or withdrawing state | upstream_code | refactored_pump_control/harvard_phd2000_driver.py:301-314 |
| stop sends STP through the emergency transport path and confirms the stopped state | upstream_code | refactored_pump_control/harvard_phd2000_driver.py:316-330 |
| query_state sends only the address (the addressed prompt request) and returns the state | upstream_code | refactored_pump_control/harvard_phd2000_driver.py:332-333 |
| request_prompt queries the state with the address alone and never with a bare carriage return | upstream_code | refactored_pump_control/harvard_phd2000_driver.py:172-174 |
| identify sends an addressed prompt request, VER and a second addressed prompt request | upstream_code | refactored_pump_control/harvard_phd2000_driver.py:176-205 |
| get_syringe_info reads the diameter with DIA | upstream_code | refactored_pump_control/harvard_phd2000_driver.py:227-238 |
| set_diameter writes DIA with four decimals and restores the cached rates and direction around it | upstream_code | refactored_pump_control/harvard_phd2000_driver.py:240-254 |
| The canonical directions are infuse and withdraw, with aliases accepted by Direction.coerce | upstream_code | refactored_pump_control/pump_models.py:8-21 |
| The Model 44 prompt states are normalized as stopped, infusing, refilling, paused, stalled and trigger wait | vendor_doc | README.md:101-106 |
| A bare carriage return is the Model 44 chain-wide STOP ALL command, and the transports reject an empty command | vendor_doc | README.md:50-54 |
| State polling uses the addressed prompt request '<address><CR>' | vendor_doc | README.md:56 |
| Normal and emergency application stops use '<address>STP<CR>' independently for each selected pump | vendor_doc | README.md:59-60 |
| A zero flow physically stops the pump | vendor_doc | README.md:113 |
| PHD 2000 exposes the diameter through DIA and does not provide syringe manufacturer or model data | vendor_doc | README.md:124-128 |
| The recommended PHD 2000 serial framing is 9600 baud, 8 data bits, no parity and 2 stop bits | vendor_doc | README.md:33-39 |
| SerialTransport uses a carriage return as its terminator | upstream_code | refactored_pump_control/serial_transport.py:48-50 |
| SerialTransport refuses an empty command instead of transmitting a bare carriage return | upstream_code | refactored_pump_control/serial_transport.py:134-141 |
| emergency_transaction cancels queued noncritical updates and sends the stop at queue head | upstream_code | refactored_pump_control/serial_transport.py:152-155 |

Limits: the flow rate and the syringe inside diameter are `Limit.operator_required`. No text file of the clone states
a numeric rate or diameter range: the accepted range depends on the installed syringe and pump head, so the site
supplies the range of its unit (`site-limits.example.json` shows the overlay). The direction is limited to the two
canonical values `infuse` and `withdraw` that `Direction.coerce` returns.

Safety: the native stop is `<address>STP` through `SerialTransport.emergency_transaction`
(`harvard_phd2000_driver.py:316-330`, `serial_transport.py:152-155`); it is the `@estop` method. No line of the
clone documents an independent hardware e-stop, so `estop_physical_ref` is not set; the safe-state action
`x-cap.matteobroketa.stop_pump.v1` calls the same native stop and satisfies SAFE-045 for this R2 hardware driver.

Tags: syringe pump, harvard, phd 2000, serial, infusion, withdrawal
