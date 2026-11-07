# Facts and tags for gh.alphatra/vacuum-instrument-monitor

Every fact cites its source at commit `838275818a2f48b0fbb46ea5a35cbaa857396a7e`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The serial client sends a command plus its line terminator as ASCII and returns the stripped reply line | upstream_code | collectors/serial_client.py:34-47 |
| The RS-232 module command DS IG returns the ion-gauge pressure; the documented reply example is 1.20E-07 | vendor_doc | README.md:137 |
| The upstream GP350 parser accepts a pressure reply written X.XXE+XX and returns the value in Torr | upstream_code | simulators/parser.py:85-88 |
| 9.90E+09 is not a real pressure: the controller uses it when there is no valid reading, for example when the ion gauge is off | vendor_doc | docs/operations/gp350-wiring.md:175-176 |
| DGS returns the degas status as 1 or 0 | vendor_doc | README.md:140 |
| DG ON and DG OFF control degas and answer OK or INVALID | vendor_doc | README.md:138 |
| At high pressure DG ON can answer OK while DGS still reports degas off | vendor_doc | README.md:139 |
| IG1 ON/OFF controls filament 1 and IG2 ON/OFF controls filament 2 | vendor_doc | README.md:141-142 |
| IGB returns a two-digit filament status; the documented values are 00, 01, 10 and 11 | vendor_doc | docs/development/dzialanie.md:33 |
| The upstream simulator encodes IGB as 01 when filament 1 is on, 10 when filament 2 is on and 11 when both are on | upstream_code | simulators/simulator.py:303-312 |
| The upstream simulator answers INVALID when a filament or degas switch already has the requested state | upstream_code | simulators/simulator.py:365-379 |

## Limits

The package declares no numeric Limit. It writes only booleans (filament 1, filament 2 and degas), so there is no
numeric range to bound, and the boolean schema itself is the allowed set. The pressure read is read-only. The
constructor defaults of `SerialClient` (baudrate, byte size, parity, stop bits, terminator, timeouts) are not device
limits: they depend on the module fitted to the controller and are options of the hardware backend, not bounds of
a capability.

## Safety

- The controller energises two hot-cathode ion-gauge filaments and a degas cycle: IG1/IG2 switch the filaments and
  DG switches degas (README.md:138-142). Both are heating elements, so the package declares **R2**.
- The clone states no independent hardware e-stop, so `estop_physical_ref` is not set. The independent stop is the
  `x-cap.alphatra.safe_state.v1` action with `safe_state=True` (SAFE-045); it and the `@estop` method send
  `IG1 OFF`, `IG2 OFF` and `DG OFF` over the same serial line. This is a software stop over the controller's own
  interface, not a physical e-stop, and the package does not claim otherwise.
- A safety command is accepted when the controller answers `OK` or `INVALID`: on the clone's model `INVALID` is the
  reply for a switch that already has the requested state (simulators/simulator.py:365-379). Any other reply raises
  instead of being reported as applied.
- This package is model-authored and unreviewed. The loader refuses the hardware backend of an unreviewed
  model-written package at R2 and R3; the package was checked on the fake backend only, and no hardware was attached.

## Not covered

- The INFICON VGC402 profile of the same repository uses an ACK/ENQ handshake
  (collectors/serial_client.py:50-70) that this GP350 package does not drive; it is a different controller with a
  different reply format. The analog-output/ADS1115 profile is also not covered.
- The RS-485 addressed form (`#AA` prefix) is not exposed: the package sends the plain RS-232 command.
- The fake does not reproduce the `9.90E+09` no-reading sentinel when both filaments are off, nor the high-pressure
  `DG ON` case where `DGS` still reports degas off; the driver rejects both at runtime.

Tags: vacuum, pressure, ion gauge, gp350, serial, rs-232
