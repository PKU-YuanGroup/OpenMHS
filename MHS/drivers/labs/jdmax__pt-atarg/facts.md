# Facts and tags for gh.jdmax/pt-atarg

Every fact cites its source at commit `476a6a21a7a31d0a457fcb5519a18214cc2b19e0` (`upstream_code` is a Python or
configuration file of the clone). The same facts are written into `driver.py` (`facts = [...]`); the reference
file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| DeviceConnection is the Lake Shore Model 218 connection class; it handles the instrument over serial over Ethernet | upstream_code | devices/ls218.py:22-27 |
| read_all writes the ASCII command KRDG? 0 followed by a newline, reads one line, and returns the decimal numbers its regular expression finds | upstream_code | devices/ls218.py:29-35 |
| The written command is KRDG? 0, where the comment says 0 means all channels | upstream_code | devices/ls218.py:32 |
| The Device class creates one softioc analog-input record per configured channel and creates a DeviceConnection from the ip, port and timeout settings | upstream_code | devices/ls218.py:9-19 |
| The sample settings file configures the lakeshore_218 IOC with module devices.ls218 and port 23, channel 1 of a serial-to-Ethernet adapter, with a 2 s timeout | upstream_code | settings.yaml:9-15 |
| The sample settings file lists eight channel slots for the 218 and publishes only Test_TI, with EGU set to K | upstream_code | settings.yaml:17-37 |
| TelnetConnection opens telnetlib.Telnet(host, port, timeout) and stores it as self.tn; it defines no close, stop, abort or disable method | upstream_code | devices/telnet_base.py:27-38 |
| The IOC host imports the device module, constructs module.Device(device_name, ioc_settings), calls connect() and then repeatedly awaits device.do_reads() | upstream_code | master_ioc.py:50-76 |
| DeviceConnection has no stop path: the class body is its constructor and read_all, and its base TelnetConnection has only the constructor | upstream_code | devices/ls218.py:22-38 |

Limits: none. The package exposes no writable parameter and no numeric action input, so no bound is needed and no
`Limit` is declared. The array length is not fixed: the query asks for all channels and the clone does not state a
channel count as a device property (the sample settings merely list eight channel slots, settings.yaml:17-27).

Safety: the Model 218 is a temperature monitor with no actuator and the native class has no stop, close or disable
method (devices/ls218.py:22-38, devices/telnet_base.py:27-38). The safety binding calls `read_all`, which writes a
fresh `KRDG? 0` query. It neither drains nor cancels an in-flight read; it changes no actuator state, and the
runtime latch is the only command protection. Observational reads remain available while latched. No physical
e-stop, interlock or independent hardware stop is claimed. The native read uses a 2 s `read_until` timeout
(devices/ls218.py:33), which can exceed the runtime's default 1 s e-stop budget; failure then remains latched.

The state and read action require at least one parsed number, so an empty/malformed reply that the upstream
regular expression turns into `[]` is refused instead of reported as a successful measurement. A nonempty
array still does not prove a complete reply or correct channel count: the upstream parser accepts its matching
substrings without checking a full reply (devices/ls218.py:27-35). The fake does not model that parser, partial
replies, socket contention or timing. The e-stop and reads share the same upstream socket with no native
serialization (devices/ls218.py:29-38); replies can be interleaved. Upstream connection/read failures print to
stdout before raising or returning (devices/telnet_base.py:35-38, devices/ls218.py:36-38), which needs isolation
for a stdio deployment. Even DeviceConnection imports the softioc-dependent module chain; the required
pythonSoftIOC dependencies remain part of deployment. No upstream code was imported or run in this review.
The validation interpreter is Python 3.14.7 and has no `telnetlib` module (checked without importing upstream).
The upstream transport imports `telnetlib`, so hardware deployment also requires a compatible Python runtime;
the successful fake check does not establish hardware availability in this environment.

Units: the clone states no engineering unit for the readings. The sample settings publish one softioc record with
`EGU: 'K'` (settings.yaml:35), which is a configuration of that IOC, not a statement that every `KRDG?` reply is in
kelvin for every probe. The read state and the action output therefore carry no unit.

Tags: lakeshore, temperature, thermometer, serial-over-ethernet, read-only
