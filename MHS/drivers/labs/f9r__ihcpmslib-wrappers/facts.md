# Facts and tags for gh.f9r/ihcpmslib-wrappers

Every fact cites its source at commit `3e6bd4c47f395bc37122e0e814184c540a99dd4e`: `upstream_code` is a code,
docstring or comment line of the clone; `vendor_doc` is a text file of the clone. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package models one of the two devices the clone wraps: the INHECO SCILA CO2 incubator
(`src/ihcWrappers/scila.py:36`). The ODTC thermal cycler (`src/ihcWrappers/odtc.py:28`) is not bound; its methods
are not part of this driver.

## Facts

| fact | source | ref |
|---|---|---|
| ScilaWrapper is the SCILA device wrapper; it extends DeviceWrapper and registers a status event | upstream_code | src/ihcWrappers/scila.py:36-40 |
| The wrapper loads the vendor IHC_PMS_Lib.Scila assembly through pythonnet | upstream_code | src/ihcWrappers/scila.py:7-9 |
| GetTemperature returns the current temperature, the target temperature and the temperature-control flag | upstream_code | src/ihcWrappers/responseDataGetTemperature.py:8-18 |
| SetTemperature takes a target temperature and a temperature-control flag and passes a None target through as None | upstream_code | src/ihcWrappers/scila.py:286-295 |
| GetAutoBoostCo2 returns the auto-boost flag and the boost-state string | upstream_code | src/ihcWrappers/responseDataGetAutoBoostCo2.py:8-14 |
| SetAutoBoostCo2 writes the CO2 auto-boost flag | upstream_code | src/ihcWrappers/scila.py:260-262 |
| GetCo2FlowStatus returns the CO2 flow status string | upstream_code | src/ihcWrappers/responseDataGetCo2FlowStatus.py:8-10 |
| SetCo2NormalFlow writes the normal CO2 flow flag | upstream_code | src/ihcWrappers/scila.py:273-275 |
| GetDoorStatus returns the four drawer status strings | upstream_code | src/ihcWrappers/responseDataGetDoorStatus.py:8-22 |
| GetLiquidLevel returns the liquid-level string | upstream_code | src/ihcWrappers/responseDataGetLiquidLevel.py:8-10 |
| GetValveStatus returns the Gas_Boost, Gas_Normal and H2O valve status strings | upstream_code | src/ihcWrappers/responseDataGetValveStatus.py:8-18 |
| GetStatus returns a StatusWrapper whose State and Locked properties are the SiLA state and the lock flag | upstream_code | src/ihcWrappers/status.py:18-28 |
| GetDeviceIdentification returns a DeviceIdentificationWrapper with the device name, firmware version, manufacturer and serial number | upstream_code | src/ihcWrappers/deviceIdentification.py:8-22 |
| Abort is a mandatory SiLA command on DeviceWrapper | upstream_code | src/ihcWrappers/device.py:117-128 |
| The example application sets the SCILA temperature to 37 and enables control, and reads the current temperature, target temperature and control flag | upstream_code | app/main.py:169-200 |
| The example application enables the CO2 auto boost and the normal CO2 flow and reads their statuses | upstream_code | app/main.py:136-198 |
| The example configuration enables the SCILA wrapper | upstream_code | app/config.ini:3 |
| The clone states no temperature unit and no numeric temperature range; the example method set gives 27 and 110 without a unit | upstream_code | data/methodSet-example.xml:5-6 |
| The vendor libraries require .NET Framework 4.8 or Mono and are not publicly downloadable | vendor_doc | README.md:3-9 |

## Limits

- `cap.thermal.setpoint.v1` input `target_temperature` is `Limit.operator_required`: no text file of the clone
  states a temperature range, and the wrapper passes the value to the vendor assembly. Every set-point call is
  refused `MHS.SAFETY.LIMITS_UNSET` until the operator overlay supplies the range. `site-limits.example.json` shows
  an example range; it is an example, not a statement about any unit.
- The one writable state field is the boolean `auto_boost_co2`, so it needs no numeric bound. `temperature_control`
  is a read-only state field; temperature control is enabled only by the bounded set-point action, so an agent cannot
  enable heating without supplying a bounded target temperature.
- The unit `Cel` on the temperature reads and on the two catalogue temperature actions comes from the catalogue
  classes (`cap.measure.temperature.v1` and `cap.thermal.setpoint.v1`); the clone states no unit for the wrapper's
  numbers. The driver passes the wrapper's value through unchanged and does not convert it. This limitation is
  recorded in RESULT.json notes.

## Safety

The device heats and controls CO2, so the driver is R2. The native stop is the mandatory SiLA `Abort` command
inherited from `DeviceWrapper` (`src/ihcWrappers/device.py:117-128`): the runtime latches first and then calls it.
The independent safe-state action `x-cap.f9r.stop_incubation.v1` calls `SetTemperature(None, False)`,
`SetAutoBoostCo2(False)` and `SetCo2NormalFlow(False)` (`src/ihcWrappers/scila.py:286-295`, `:260-262` and
`:273-275`) and reads the state back. The clone does not describe a dedicated stop command or a hardware e-stop, so
`estop_physical_ref` is not set; the safe-state action is the independent stop SAFE-045 asks of R2 hardware.

The package is model-authored and unreviewed: `driver.lock.json` `reviewed_by` is null. The R2 hardware backend is
refused by the loader until a human sets it, and nothing here was run on hardware.

## Scope and fake

The ODTC wrapper (`src/ihcWrappers/odtc.py:28`), the finders, the FTP downloaders, `SetConfiguration`,
`SetParameters`, `BoostCo2`, `Dispose` and the door/position methods are not bound. They include raw XML or
positional commands whose arguments and ranges the clone does not describe.

The upstream has no simulator or recording. The package fake is an in-memory object whose public methods are the
wrapper methods above (gate G7); its values are placeholder test data marked `# placeholder` in `fake.py`, not facts,
limits or a recording. The hardware path (`native.py`) was never run.

Tags: incubator, co2, temperature-control, inheco, pythonnet
