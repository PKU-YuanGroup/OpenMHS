# Facts, limits and tags for gh.mabl/pymso5000

The clone is a Python library and MCP server for Rigol MSO5000 series oscilloscopes over VISA
(`README.md:3-4`). This package serves one device through its high-level `pymso5000.scope:Scope` class: analog
channel 1, the shared acquisition and timebase settings, and one scalar automatic measurement.

Every fact cites its source at commit `48ebacc0317ada6d6f54a58ab03916c5d5a44e80`: `upstream_code` is a code line of
the clone, `vendor_doc` a text file of it (README.md, or the checked-in programming-guide transcription
`src/pymso5000/data/mso5000_commands.json`). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The clone is a Python library and MCP server for controlling Rigol MSO5000 series oscilloscopes over VISA | vendor_doc | README.md:3-4 |
| Scope is the high-level API and Scope.connect opens any message-based VISA resource name using the bundled SCPI definitions | upstream_code | src/pymso5000/scope.py:189-224 |
| info returns the *IDN? reply split into vendor, model, serial and firmware fields | upstream_code | src/pymso5000/scope.py:293-307 |
| run writes RUN, stop writes STOP and trigger_status reads TRIGger:STATus? (STOP, WAIT, TD, AUTO, RUN) | upstream_code | src/pymso5000/scope.py:311-329 |
| get_acquisition reads the run state and the ACQuire TYPE, AVERages, SRATe and MDEPth queries | upstream_code | src/pymso5000/scope.py:389-423 |
| set_acquisition writes ACQuire:TYPE, ACQuire:AVERages and ACQuire:MDEPth, then reads the state back | upstream_code | src/pymso5000/scope.py:477-489 |
| set_acquisition refuses acquisition writes while the acquisition is stopped, because the instrument would accept and ignore them | upstream_code | src/pymso5000/scope.py:524-542 |
| The acquisition types are NORMal, AVERages, PEAK and HRESolution | upstream_code | src/pymso5000/parameters.py:60 |
| The average count is a power of two from 2 to 65536 | upstream_code | src/pymso5000/parameters.py:63-65 |
| The settable memory depths are AUTO, 1k, 10k, 100k, 1M, 10M, 25M, 50M, 100M and 200M | upstream_code | src/pymso5000/parameters.py:85 |
| get_channel reads DISPlay, SCALe, OFFSet, UNITs, COUPling, PROBe and BWLimit of one analog channel | upstream_code | src/pymso5000/scope.py:565-603 |
| set_channel writes the channel settings and returns the read-back state with the requested values it disagrees with | upstream_code | src/pymso5000/scope.py:693-734 |
| The channel input couplings are DC, AC and GND | upstream_code | src/pymso5000/parameters.py:8 |
| The explicit bandwidth filters are OFF, 20M to 600M, and 1G to 20G | upstream_code | src/pymso5000/parameters.py:153-173 |
| The channel probe ratios accepted by the firmware definition run from 0.0001 to 50000 | upstream_code | src/pymso5000/data/scpi_mso5000/CHANnel1.xml:827-885 |
| get_timebase reads TIMebase:MODE?, TIMebase:MAIN:SCALe? and TIMebase:MAIN:OFFSet? | upstream_code | src/pymso5000/scope.py:738-746 |
| set_timebase writes TIMebase:MAIN:SCALe and TIMebase:MAIN:OFFSet and returns the read-back adjustments | upstream_code | src/pymso5000/scope.py:783-792 |
| Scope.execute validates a command and its arguments and returns the parsed reply of a query | upstream_code | src/pymso5000/scope.py:932-946 |
| MEASure:ITEM? is the immediate measurement query of one item and source; each query also registers the item on the ten-slot measurement list | upstream_code | src/pymso5000/api/measure.py:811-820 |
| The single-source waveform measurement items run from VMAX to NEDGes | upstream_code | src/pymso5000/api/measurement_models.py:54-87 |
| The programming guide gives the channel scale range as 500 uV/div to 10 V/div for a 1X probe | vendor_doc | src/pymso5000/data/mso5000_commands.json:3627 |
| The programming guide gives the channel scale range as 10 mV/div to 100 V/div for a 10X probe | vendor_doc | src/pymso5000/data/mso5000_commands.json:9692 |
| The programming guide gives the channel offset range in three vertical-scale bands, from +/-1 V to +/-100 V | vendor_doc | src/pymso5000/data/mso5000_commands.json:3546 |
| The programming guide gives the main timebase scale in YT mode per model, from 1 ns to 1000 s for the MSO5354 and 5 ns to 1000 s for the MSO5072/MSO5074 | vendor_doc | src/pymso5000/data/mso5000_commands.json:13005 |
| The programming guide leaves the timebase offset range to remarks that depend on the timebase mode and the operating status | vendor_doc | src/pymso5000/data/mso5000_commands.json:12968 |

## Limits

| parameter | unit | limit | source |
|---|---|---|---|
| acquisition_type | | one of NORMal, AVERages, PEAK, HRESolution | upstream_code: src/pymso5000/parameters.py:60 |
| memory_depth | | one of AUTO, 1k, 10k, 100k, 1M, 10M, 25M, 50M, 100M, 200M | upstream_code: src/pymso5000/parameters.py:85 |
| channel1_enabled (action input) | | boolean, no numeric bound | - |
| channel1_scale_per_div | V | operator_required: the guide states the range per probe ratio (500 uV/div to 10 V/div at 1X, 10 mV/div to 100 V/div at 10X) and the clone only refuses a value that is not above zero | operator |
| channel1_offset | V | operator_required: the guide states the range in bands that depend on the vertical scale, up to +/-100 V | operator |
| channel1_coupling (action input) | | one of DC, AC, GND | upstream_code: src/pymso5000/parameters.py:8 |
| channel1_probe_ratio (action input) | | one of 0.0001 to 50000 (27 values) | upstream_code: src/pymso5000/data/scpi_mso5000/CHANnel1.xml:827-885 |
| channel1_bandwidth_limit (action input) | | one of OFF, 20M, 25M, 50M, 70M, 100M, 150M, 200M, 250M, 300M, 350M, 500M, 600M, 1G, 2G, 4G, 5G, 10G, 20G | upstream_code: src/pymso5000/parameters.py:153-173 |
| timebase_scale_s_per_div | s | operator_required: the guide states the range per model and mode (1 ns/div to 1000 s/div at the widest) and the clone only refuses a value that is not above zero | operator |
| timebase_offset_s | s | operator_required: the guide refers to remarks that depend on the timebase mode and the operating status | operator |

The four operator-required ranges are supplied by the site in `site-limits.json`; `site-limits.example.json` shows
one overlay that narrows them for a bench. Without an overlay every write of those fields is refused with
`MHS.SAFETY.LIMITS_UNSET`. The channel-1 display, coupling, probe ratio and bandwidth filter are one extension
action (`x-cap.mabl.scope_channel_input.v1`) rather than fields of `cap.device.configure.v1`: the standard configure
tool with all ten writes was 2492 bytes, above the 2048-byte MCP tool bound, and splitting it keeps every tool below
the bound.

## Safety

* The e-stop calls the native `Scope.stop`, which writes `STOP` (`scope.py:315-320`): the acquisition is halted and
  the display is frozen. The driver sets no other actuation, and the oscilloscope does not emit energy.
* Channel 1 writes go through `Scope.set_channel`, which writes the channel sequence and returns the read-back with
  the requested values it did not apply (`scope.py:693-734`). The driver raises `MHS.DEVICE.FAULTED` instead of
  reporting a silent clamp as success.
* This is an R1 hardware package. It is model-authored and unreviewed (`driver.lock.json` `reviewed_by` is null),
  checked on the fake backend only, and never ran on hardware. The loader's unreviewed-hardware guard applies at R2
  and R3 only, so this package does not claim it.

## Not covered

* Waveform arrays: the MSO5000 waveform readout is a large array that the standard cannot carry yet. Only the
  scalar settings and the automatic measurement action are served; the waveform capture path is not exposed.
* Channels 2 to 4, the logic analyzer, the built-in generator, the trigger subsystem, decode, the front panel and
  the setup blob are not served. The driver serves analog channel 1 and the shared acquisition/timebase state; the
  measurement action can name any analog channel as its source, but their vertical settings are not read or set.
* `set_acquisition` refuses a write while the acquisition is stopped (`scope.py:524-542`); the driver leaves that
  refusal to the native call, so a stopped scope reports the upstream `ScopeUsageError` as a failed receipt.

## Tags

oscilloscope, scpi, visa, mso5000, mso5074, pymso5000
