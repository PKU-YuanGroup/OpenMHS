# Facts and tags for gh.bennomeier/cetoni

Every fact cites its source at commit `b957067d56c2698ca4b77bfe2b445af4b1d92045`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The module controls Cetoni Nemesys V4 syringe pumps over a serial port | vendor_doc | README.md:2 |
| The syringe volume is a constructor option in uL; a second syringe shares the serial object of the first and gets its own node id | upstream_code | cetoniSerial.py:42-50 |
| A frame is DLE (0x90), STX (0x02), a little-endian payload and a CRC-16, with byte stuffing (DLE doubled) | upstream_code | cetoniSerial.py:203-219 |
| read() sends opcode 0x60 with node id, object index, subindex and word count | upstream_code | cetoniSerial.py:259-268 |
| write() sends opcode 0x68 with node id, object index, subindex, word count and a packed value | upstream_code | cetoniSerial.py:292-304 |
| readStatus reads the state register 0x6041 | upstream_code | cetoniSerial.py:318-319 |
| readCurrentPosition reads 0x6064 and readTargetPosition reads 0x607a as signed 32-bit values; writeTargetPosition writes 0x607a | upstream_code | cetoniSerial.py:358-365 |
| readVelocity reads 0x6081 and setVelocity accepts only 0 < velocity <= maxProfileVelocity | upstream_code | cetoniSerial.py:348-356 |
| setFlowRate converts uL/s to the profile velocity register and asserts 0 <= flowRate <= maxVolperS | upstream_code | cetoniSerial.py:455-464 |
| aspirate applies -volume and dispense +volume; both execute the relative move and wait until the state register reads 1079 | upstream_code | cetoniSerial.py:424-444 |
| The constructor asserts that the safety stop input (bit 28 of digital input 0x60fd) is off | upstream_code | cetoniSerial.py:136-139 |
| The constructor shuts the drive down with control word 0x06 and enables it with 0x0f through control register 0x6040 | upstream_code | cetoniSerial.py:149-155 |
| toInput calls switchValves(1,0) and toOutput calls switchValves(0,1); switchValves drives 0x60fe and caches the bits in physicalOutputs | upstream_code | cetoniSerial.py:321-346 |
| The minimum position limit and the safety margin come from 0x607D subindex 1 and subindex 2 | upstream_code | cetoniSerial.py:96-101 |
| The maximum profile velocity is read from 0x607F and maxVolperS is derived from it (maxProfileVelocity*0.001 = maxRPM) | upstream_code | cetoniSerial.py:107-114 |
| The cross-section is volume/60 (all units mm and uL) and the position conversion factor is encoderResolution*gearFactor | upstream_code | cetoniSerial.py:72-90 |

Limits: every numeric write and every numeric action input is `Limit.operator_required`. The drive reads its travel
range from 0x607D and its maximum profile velocity from 0x607F at connect, and the flow-rate ceiling and the usable
volume also depend on the syringe, which is a constructor option (cetoniSerial.py:42, 96-114). No text of the clone
states a numeric bound for a configured pump, so the site supplies the ranges in `site-limits.example.json`. The valve
position is the only sourced limit: the allowed set is the two valve methods of the clone (cetoniSerial.py:342-346).

Safety: the e-stop and the safe-state action `x-cap.bennomeier.stop_pump.v1` both write control word 0x06 (shutdown) to
0x6040 (cetoniSerial.py:149-155). The constructor also checks the drive's safety stop input (bit 28 of 0x60fd,
cetoniSerial.py:136-139), but the clone does not document it as an independent physical e-stop, so no
`estop_physical_ref` is claimed; the safe-state action is the independent stop this R2 package declares. No line of
the clone documents clearing the fault state, so the driver does not reset it.

The flow rate read is derived from the velocity register with the inverse of the upstream `setFlowRate` conversion
(cetoniSerial.py:455-464); it therefore reports what the drive stored after the upstream integer rounding.

Tags: syringe pump, cetoni, nemesys, serial, fluid
