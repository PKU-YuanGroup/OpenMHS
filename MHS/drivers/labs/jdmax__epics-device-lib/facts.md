# Facts, limits and deployment notes for gh.jdmax/epics-device-lib

Every fact cites the upstream clone at commit `370b8e3d94224db70ee2a1f51bd28c5d305daefe`. The same facts are written
into `driver.py`; `reference.json` and `REFERENCE.md` are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The README identifies instruments/ls336.py as the Lake Shore Model 336 temperature controller | vendor_doc | README.md:26 |
| The README lists the ls336 driver as a Telnet (RS-232) device exposing temperature/heater inputs and setpoint/PID outputs | vendor_doc | README.md:52 |
| The README's inheritance tree lists the repository's other device modules, among them the Rigol DP832 power supply (dp832.py) and the Zaber ASCII motor controller (zaber_motor.py) | vendor_doc | README.md:11-33 |
| For each configured channel whose name does not contain _TI, the Device class creates _TI, _Heater, _Manual, _kP, _kI, _kD, _SP, _Mode and _Range PVs, the _Mode and _Range PVs as mbbOut records built from mode_list and range_list; a _TI channel gets only its temperature PV | upstream_code | instruments/ls336.py:20-35 |
| Device._create_connection passes settings['ip'], settings['port'] and settings['timeout'] to DeviceConnection | upstream_code | instruments/ls336.py:37-42 |
| do_sets passes a _Mode PV's new value to set_outmode(chan, new_value, chan, 0), the channel as first and third argument, and a _Range PV's new value to set_range(chan, new_value) | upstream_code | instruments/ls336.py:62-65 |
| The output-mode menu names Off, Closed Loop, Zone and Open Loop in that order | upstream_code | instruments/ls336.py:17 |
| The heater-range menu names Off, Low, Med and High in that order | upstream_code | instruments/ls336.py:18 |
| do_reads sets channel i's temperature PV from temps[i] and, for a channel without _TI in its name, reads heater, PID, output mode, range, setpoint and manual output for channel i+1 | upstream_code | instruments/ls336.py:75-91 |
| read_temps sends KRDG? 0 and parses four comma-separated floats; the comment calls KRDG a Kelvin reading | upstream_code | instruments/ls336.py:107-120 |
| The set_pid and read_pid docstrings name channel 1 or 2; set_pid sends PID <channel>,<P>,<I>,<D> and then PID?, and read_pid sends PID? without its channel argument | upstream_code | instruments/ls336.py:126-147 |
| read_heater sends HTR? <channel> and read_man_heater sends MOUT? <channel> | upstream_code | instruments/ls336.py:153-173 |
| The manual-heater docstrings name output percentages, and set_man_heater sends MOUT <channel>,<value> then MOUT? <channel> | upstream_code | instruments/ls336.py:166-187 |
| set_outmode sends OUTMODE <channel>,<mode>,<in_channel>,<powerup_on> and then OUTMODE? <channel> and returns the first number of the reply; read_outmode sends OUTMODE? <channel> | upstream_code | instruments/ls336.py:193-218 |
| set_range sends RANGE <channel>,<range> and reads RANGE? <channel> back | upstream_code | instruments/ls336.py:220-245 |
| set_setpoint sends SETP <channel>,<value> and reads SETP? <channel> back; read_setpoint sends SETP? | upstream_code | instruments/ls336.py:247-272 |
| Each method from read_temps to read_setpoint reads one line with read_until(b'\n', timeout=2), parses it with a regex search and, on any Exception (a reply the regex does not match included), prints the error and raises OSError | upstream_code | instruments/ls336.py:113-272 |
| TelnetConnection's constructor stores host, port and timeout and creates a TelnetSocket to host:port as self.tn; an exception from that is printed, not raised | upstream_code | telnet_base.py:27-38 |
| TelnetSocket.read_until returns whatever has arrived when the timeout or EOF comes instead of raising | upstream_code | telnet_socket.py:69-78 |

## Scope

The clone is a library of EPICS soft-IOC device modules meant to be mounted as the package `devices` of a deployment
(README.md:3-6). This package serves one of them, the Lake Shore Model 336 temperature controller
(`instruments/ls336.py`, `DeviceConnection` at line 99), one configured heater output per instance. The card's other
entry symbols, `instruments.dp832:DeviceConnection` (Rigol DP832 power supply) and
`instruments.zaber_motor:DeviceConnection` (Zaber motor controller), and the README's other modules (Datexel Modbus
modules, AMI 136 and LM-500 level monitors, Cryomagnetics 4G and CS-4 magnet supplies, Lakeshore 218, MKS 937B,
SI-9700, Pfeiffer TPG 26x, Vaunix LMS, `ioc_load`; README.md:11-33) are other devices and are not served here. The
soft-IOC `Device` and PV layer of `ls336.py` is not used either.

## Limits

| field | bound | why |
|---|---|---|
| `setpoint` (Cel) | `Limit.operator_required` | No text file of the clone states the SETP range. The controller's preferred unit and the safe sample range are per-installation, so the operator supplies it in `site-limits.json`. |
| `cap.thermal.setpoint.v1.target_temperature` (Cel) | `Limit.operator_required` | Same SETP range question. |
| `manual_heater` (%) | `Limit.operator_required` | MOUT is documented only as a percentage; no 0-100 bound is stated in the clone. |
| `heater_range` | `allowed` = Off, Low, Med, High | The range menu at `instruments/ls336.py:18`; `do_sets` passes the `_Range` PV's new value to `set_range` at `instruments/ls336.py:65`. |

`site-limits.example.json` is an example overlay only. It supplies a 15 to 60 Cel setpoint range, a 0 to 100 %
manual-heater range and the same 15 to 60 Cel input bound for `cap.thermal.setpoint.v1`; these are operator data,
not device limits.

The Celsius bounds hold only when the `setpoint_unit` option names the unit the controller uses for the control
input: SETP is sent in that unit. With a wrong unit the controller gets another temperature than the one the envelope
checked (30 Cel is sent as 303.15 under `K`, which a controller set to Celsius takes as 303.15 Cel). The clone does not
state the unit, so the hardware backend has no default: every setpoint read and write, and the thermal action, fail
`MHS.DEVICE.PRECONDITION_UNMET` until the option is set. The fake keeps Kelvin, the unit of its placeholder setpoints.

## Safety and stop path

- The e-stop (`stop`, `@estop(native="set_outmode")`) sends `OUTMODE <channel>,0,<channel>,0`: the first output-mode
  menu entry is `Off` (`instruments/ls336.py:17`), and the upstream's own `do_sets` sends the `_Mode` PV's value the
  same way, with the channel as output and control input and powerup 0 (`instruments/ls336.py:62-63`). That the
  value of an `mbbOut` record is the zero-based position of the selected menu entry is pythonSoftIOC/EPICS record
  semantics, outside the clone. The upstream `set_outmode` then sends `OUTMODE? <channel>` and waits up to 2 s for
  the reply (`instruments/ls336.py:193-205`); the stop fails (`MHS.SAFETY.SAFE_STATE_UNREACHED`) unless the parsed
  mode is 0, and an unmatched or missing reply fails it with the upstream's `OSError`.
- `x-cap.jdmax.heater_off.v1` is the `safe_state=True` action, which the runtime runs after the native stop (or once
  the 1000 ms default e-stop budget is spent while the native stop is still waiting). It sends the same OUTMODE
  command and raises `MHS.SAFETY.SAFE_STATE_UNREACHED` unless a fresh `OUTMODE?` reads back mode 0. It satisfies
  SAFE-045 because the clone documents no independent hardware e-stop. The command is idempotent, so the second send
  and the background retries are harmless.
- What the stop leaves: the configured output in output mode Off. The same command sets that output's control input
  to input `<channel>` and its powerup enable to 0, whatever they were before. The heater range, setpoint and manual
  output are kept. The other heater output is not commanded and keeps heating if it was on; nothing cools the sample.
- `x-cap.jdmax.enable_heater.v1` is the input-free `reenable=True` action. It sends
  `OUTMODE <channel>,<reenable_mode>,<channel>,0` (default Closed Loop) and raises `MHS.DEVICE.FAULTED` if the
  readback differs. Heating then resumes toward the setpoint (Closed Loop, Zone) or manual output (Open Loop) stored
  in the controller, which the envelope checked only if it was written through this package; the control input is
  input `<channel>`. No `@reset` hook exists, so a reset only releases the latch (the e-stop case in `test_driver.py`
  shows the output staying Off after the reset). The stop is not terminal: the re-enable undoes it on the same
  endpoint.
- The fake answers at once. On hardware each upstream call waits up to 2 s for its reply line, so a silent controller
  makes the native stop and the safe-state action fail after the e-stop budget, with the latch held and the
  background retry running.

## Upstream transport behaviour (read before a hardware run)

- One `TelnetSocket` (a raw TCP socket to a serial-to-Ethernet adapter port) carries every command, and it has no
  lock. The SDK runs reads, the `@estop` method and safe-state actions without the driver lock, so two callers can
  share the socket at once and read each other's reply lines. The stop command itself is always written before any
  read, so a crossed reply cannot hold it back; a crossed reply fails the stop's or the safe-state action's check
  (only an `OUTMODE?` reply matches its pattern), keeping the latch. Ordinary reads are less protected: SETP?, HTR? and
  MOUT? replies match one another's pattern, and the RANGE? pattern takes the first digit of any reply, so a crossed
  reply can be returned as a plausible wrong value.
- `read_until` returns what it has after 2 s and drops it (`telnet_socket.py:69-78`, `:121-124`); a reply that
  arrives later stays in the socket and is read by the next command, so after one late reply every later command can
  read the reply of the command before it. Nothing in the clone resynchronises the stream.
- `TelnetConnection` and every `DeviceConnection` method print failures to stdout (`telnet_base.py:37-38`,
  `instruments/ls336.py:113-272`). An MHS endpoint served over stdio would get those lines in its protocol stream.
- The driver never reconnects. After the adapter drops the connection every command fails, the e-stop included
  (`SAFE_STATE_UNREACHED`, latch held), until the endpoint is restarted; the physical stop is the way to stop the
  heater then.
- The factory does not check which instrument answers on `host:port`: an adapter port wired to another instrument
  receives the LS336 commands.

## Native interface and fake

- Native reads the driver uses: `read_temps`, `read_pid`, `read_heater`, `read_man_heater`, `read_outmode`,
  `read_range`, `read_setpoint`.
- Native writes the driver uses: `set_setpoint`, `set_man_heater`, `set_range`, `set_outmode` (also the stop and
  re-enable path).
- `read_pid` sends `PID?` without the output number (`instruments/ls336.py:143`), so the `pid` read is whatever the
  controller answers to that query; the clone does not say which output's gains it carries.
- `fake.py:FakeLs336` is a plain in-memory stand-in, not a recording and not the upstream simulator. All of its
  values are test data marked `# placeholder` in the source; it has no plant model and no timestamps. The upstream
  provides no simulator or test fixture for this class, so the mock strategy is a package fake.
- The fake exposes eleven of the twelve public methods of `DeviceConnection` (not `set_pid`, which the driver never
  calls) with the upstream signatures and return types (the mode and range readbacks are floats, as the upstream
  parses them). Its `read_pid` ignores the channel, as the upstream does, and its `set_outmode` keeps the control
  input and powerup flag it is sent. It does not model the 2 s timeout, late or crossed replies, or the stdout
  messages.
- NOT COVERED: writing PID gains, the second heater output, ramp/wait behaviour, the soft-IOC `Device`/PV layer, and
  the controller's sensor curves. PID is read only because the clone states no gain units or ranges.

## Licence

The clone has no licence file and no licence or copyright statement in any file at the pinned commit; the card says
`NOASSERTION` and `publish_review: required`, so the owner decides before publication.

## Deployment assumptions and hardware status

- The hardware factory is `.native:connect`. It imports `devices.instruments.ls336:DeviceConnection`; the clone must
  be mounted as the package `devices` (README.md:5, README.md:102-119). The clone's modules import `softioc`
  (`instruments/ls336.py:2`, `base_device.py:3`), which the card's install block does not install: the deployment
  must provide pythonSoftIOC, which is then imported into the MHS process (nothing here starts an IOC).
- The driver reads `channel` (1 or 2, default 1), `setpoint_unit` (`K`, `Cel` or `[degF]`; required with the hardware
  backend) and `reenable_mode` (`Closed Loop`, `Zone` or `Open Loop`, default `Closed Loop`) from its options. The
  clone does not state the channel or the SETP unit, so these are deployment choices; the driver publishes setpoints
  in Celsius and converts with `mhs.units`. One instance controls one output: a second heater output needs its own
  instance and is not stopped by this one's e-stop. Do not run the instance beside the upstream soft-IOC on the same
  adapter port.
- The hardware factory has never been run. The package is model-authored and unreviewed, so the loader refuses its
  hardware backend at R2 until a human signs `reviewed_by`; fake evidence is not a hardware run.
