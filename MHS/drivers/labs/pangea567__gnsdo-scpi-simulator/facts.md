# Facts and tags for gh.pangea567/gnsdo-scpi-simulator

Every fact cites its source at commit `a2d57a9759ab72fcfa42578a505d8ca4248bc0a4`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone.py:LINE`). The table mirrors the `facts` list of `driver.py`; the generated
reference is built from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The upstream repository is a Linux serial-port simulator of the SCPI behaviour of a Low Noise Rubidium GNSDO, a GPS/GNSS-disciplined rubidium time-frequency reference; it is not a client library. | vendor_doc | README.md:3-5 |
| The serial port is 8N1 at 115200 baud. | vendor_doc | README.md:53 |
| A client writes a command line ending in CRLF (the README shows b'*IDN?\r\n'). | vendor_doc | README.md:143 |
| The simulator writes a response followed by CRLF. | upstream_code | src/gnsdo_simulator/serial_server.py:124 |
| Command matching is case-insensitive: normalize_command strips the line ends and returns text.upper(). | upstream_code | src/gnsdo_simulator/scpi_parser.py:52-76 |
| A command with a value is split at the first space into a command prefix and its value. | upstream_code | src/gnsdo_simulator/scpi_parser.py:169 |
| The identity reply is 'Jackson Labs, LN Rb GPSDO (PRE), Firmware Rev <firmware>'. | upstream_code | src/gnsdo_simulator/commands/system.py:42-43 |
| SYNC:LOCKED? answers '1' when the oscillator is locked and '0' when it is not. | upstream_code | src/gnsdo_simulator/commands/sync.py:81-85 |
| SYNC:TINT? is the time interval error in seconds, printed in scientific notation. | upstream_code | src/gnsdo_simulator/commands/sync.py:90-116 |
| SYNC:HEALTH? is a hexadecimal bit mask: 0x4 is a TINT above 210 ns, 0x8 a runtime below 200 s, 0x10 a holdover above 60 s and 0x400 a hardware fault. | upstream_code | src/gnsdo_simulator/commands/sync.py:121-158 |
| SYNC:HOLD:INIT sets holdover, clears the lock and records the holdover start; SYNC:HOLD:REC:INIT clears holdover, restores the lock and clears the start. | upstream_code | src/gnsdo_simulator/commands/sync.py:184-210 |
| SYNC:SOUR:MODE <value> stores any non-empty value as the synchronization source mode. | upstream_code | src/gnsdo_simulator/commands/sync.py:216-225 |
| SYNC:HOLD:DUR? answers two comma-separated numbers: the holdover duration in seconds and 1 while in holdover or 0 otherwise. | upstream_code | src/gnsdo_simulator/commands/sync.py:163-179 |
| GPS:SAT:TRAC:COUN? and GPS:SAT:VIS:COUN? answer the tracked and visible satellite counts. | upstream_code | src/gnsdo_simulator/commands/gps.py:173-186 |
| MEAS:TEMP? returns the PCB temperature. | upstream_code | src/gnsdo_simulator/commands/measure.py:31-35 |
| MEAS:VOLT? returns the TCXO adjustment voltage, not the power-supply voltage; the comment gives about 1.6 to 1.7 V from a real device output. | upstream_code | src/gnsdo_simulator/device_state.py:123-129 |
| MEAS:POW? returns the power-supply input voltage; the comment gives about 11.7 to 11.74 V from a real device output. | upstream_code | src/gnsdo_simulator/device_state.py:160-162 |
| CSAC:STATUS? answers 0 when the atomic clock module is healthy and 1 when it is not. | upstream_code | src/gnsdo_simulator/commands/csac.py:22-33 |
| CSAC:TEMP?, CSAC:SN? and CSAC:LIFE? answer the module temperature, serial number and lifetime hours. | upstream_code | src/gnsdo_simulator/commands/csac.py:38-59 |
| PTIME:OUTPUT? answers 1 or 0, while the PTIME:OUTPUT setter accepts ON or OFF. | upstream_code | src/gnsdo_simulator/commands/ptime.py:61-87 |
| PTIME:LEAP:ACC? answers the accumulated GPS-UTC leap seconds. | upstream_code | src/gnsdo_simulator/commands/ptime.py:90-94 |
| DIAG:LIFE:COUN? answers the lifetime in hours, increased by the simulator's runtime. | upstream_code | src/gnsdo_simulator/commands/diagnostic.py:26-32 |
| The simulator considers the oscillator locked only when at least four satellites are tracked. | upstream_code | src/gnsdo_simulator/device_state.py:230-236 |
| The GPS survey variance limit is 150000 in the simulator state. | upstream_code | src/gnsdo_simulator/device_state.py:79 |
| The atomic-lock warmup time is 120 s, from the manual's 'less than 2 minutes warmup time to atomic lock' comment. | upstream_code | src/gnsdo_simulator/device_state.py:226-228 |

Tags (short lowercase keywords): gnsdo, gpsdo, gnss, rubidium, oscillator, time reference, serial, scpi.

## Controlled fake time

The package fake uses a fixed placeholder clock. Reads, e-stop and reset do not advance it; a test may call the fake-only `advance_time(seconds)` helper to exercise time and holdover-duration changes. Date/time, health and holdover transitions remain observable under explicit progression. The fake clock is not the host clock or a fact about the upstream simulator, GPS synchronization, oscillator drift or hardware timing. This removes an ambient-second race in the fake gate without changing the runtime, safety checks, declared capabilities, source facts or native behavior.
