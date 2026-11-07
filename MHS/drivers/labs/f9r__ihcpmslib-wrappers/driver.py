"""OpenMHS driver for gh.f9r/ihcpmslib-wrappers: an INHECO SCILA CO2 incubator.

A direct Driver over ``ihcWrappers.scila:ScilaWrapper``, the Python wrapper that a host builds with
``PmsWrapper.Create`` around the vendor ``IHC_PMS_Lib.Scila`` assembly (``src/ihcWrappers/scila.py:8-9``,
``src/ihcWrappers/scila.py:36-40`` and ``src/ihcWrappers/pms.py:88-96``).  The wrapper methods are synchronous:
each one calls the .NET object and returns a response wrapper, so every method here is a plain ``def``.

* reads: device name, firmware version, SiLA state, current and target temperature, the temperature-control flag,
  the CO2 auto-boost flag and boost state, the CO2 flow status, the liquid level, the four drawer statuses and the
  three valve statuses;
* one write: the CO2 auto-boost flag (``SetAutoBoostCo2``), a boolean.  Temperature control is enabled only by the
  bounded set-point action below, never by a separate write;
* actions: the catalogue temperature measurement, the catalogue thermal set point (target temperature and enable
  control) and ``x-cap.f9r.stop_incubation.v1``, the safe-state action that turns temperature control and both CO2
  flow paths off;
* the native stop is the mandatory SiLA ``Abort`` command inherited from ``DeviceWrapper``; the runtime latches and
  then calls it, and the safe-state action runs afterwards.

No text file of the clone states a temperature unit or a numeric temperature range.  The catalogue classes fix the
unit ``Cel`` for the two temperature actions, and the driver passes the wrapper's number through unchanged.  The set
point range is therefore ``Limit.operator_required``: every set-point call is refused ``MHS.SAFETY.LIMITS_UNSET``
until the operator overlay supplies the range of its unit (``site-limits.example.json`` shows the overlay).

Every Fact cites a line of the clone at the pinned commit
(3e6bd4c47f395bc37122e0e814184c540a99dd4e).  This package is model-authored and unreviewed: it is checked on the
fake backend only, and the hardware backend is refused until a human sets ``reviewed_by`` in ``driver.lock.json``.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

_TARGET_LIMIT = Limit.operator_required(
    "no text file of the clone states the SCILA temperature range; the wrapper passes the value to the vendor "
    "assembly, so the site must supply the range of its unit")


def _ok(response):
    """Raise when a wrapper response reports failure instead of swallowing it."""
    if not bool(getattr(response, "Success", True)):
        raise DriverFailed("MHS.DEVICE.FAULTED", str(getattr(response, "Message", "the wrapper reported a failure")))
    return response


def _check_return(result):
    """Check a SiLAReturnValue, or the first item of a ``(return value, payload)`` tuple (the app asserts code 1)."""
    value = result[0] if isinstance(result, tuple) else result
    if getattr(value, "ReturnCode", 1) != 1:
        raise DriverFailed("MHS.DEVICE.FAULTED", str(getattr(value, "Message", "the wrapper reported a failure")))
    return result


class Scila(Driver):
    device_id = "scila"
    device_kind = "instrument.incubator"
    mode = "hardware"
    risk = "R2"
    native = "ihcWrappers.scila:ScilaWrapper"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeScila"}
    vendor, model = "INHECO", "SCILA"
    display_name = "INHECO SCILA CO2 incubator (ihcWrappers.scila.ScilaWrapper)"
    tags = ["incubator", "co2", "temperature-control", "inheco", "pythonnet"]
    facts = [
        Fact("ScilaWrapper is the SCILA device wrapper; it extends DeviceWrapper and registers a status event",
             source="upstream_code", ref="src/ihcWrappers/scila.py:36-40"),
        Fact("The wrapper loads the vendor IHC_PMS_Lib.Scila assembly through pythonnet",
             source="upstream_code", ref="src/ihcWrappers/scila.py:7-9"),
        Fact("GetTemperature returns the current temperature, the target temperature and the temperature-control "
             "flag", source="upstream_code", ref="src/ihcWrappers/responseDataGetTemperature.py:8-18"),
        Fact("SetTemperature takes a target temperature and a temperature-control flag and passes a None target "
             "through as None", source="upstream_code", ref="src/ihcWrappers/scila.py:286-295"),
        Fact("GetAutoBoostCo2 returns the auto-boost flag and the boost-state string",
             source="upstream_code", ref="src/ihcWrappers/responseDataGetAutoBoostCo2.py:8-14"),
        Fact("SetAutoBoostCo2 writes the CO2 auto-boost flag", source="upstream_code",
             ref="src/ihcWrappers/scila.py:260-262"),
        Fact("GetCo2FlowStatus returns the CO2 flow status string", source="upstream_code",
             ref="src/ihcWrappers/responseDataGetCo2FlowStatus.py:8-10"),
        Fact("SetCo2NormalFlow writes the normal CO2 flow flag", source="upstream_code",
             ref="src/ihcWrappers/scila.py:273-275"),
        Fact("GetDoorStatus returns the four drawer status strings", source="upstream_code",
             ref="src/ihcWrappers/responseDataGetDoorStatus.py:8-22"),
        Fact("GetLiquidLevel returns the liquid-level string", source="upstream_code",
             ref="src/ihcWrappers/responseDataGetLiquidLevel.py:8-10"),
        Fact("GetValveStatus returns the Gas_Boost, Gas_Normal and H2O valve status strings",
             source="upstream_code", ref="src/ihcWrappers/responseDataGetValveStatus.py:8-18"),
        Fact("GetStatus returns a StatusWrapper whose State and Locked properties are the SiLA state and the lock "
             "flag", source="upstream_code", ref="src/ihcWrappers/status.py:18-28"),
        Fact("GetDeviceIdentification returns a DeviceIdentificationWrapper with the device name, firmware version, "
             "manufacturer and serial number", source="upstream_code",
             ref="src/ihcWrappers/deviceIdentification.py:8-22"),
        Fact("Abort is a mandatory SiLA command on DeviceWrapper", source="upstream_code",
             ref="src/ihcWrappers/device.py:117-128"),
        Fact("The example application sets the SCILA temperature to 37 and enables control, and reads the current "
             "temperature, target temperature and control flag", source="upstream_code", ref="app/main.py:169-200"),
        Fact("The example application enables the CO2 auto boost and the normal CO2 flow and reads their statuses",
             source="upstream_code", ref="app/main.py:136-198"),
        Fact("The example configuration enables the SCILA wrapper", source="upstream_code", ref="app/config.ini:3"),
        Fact("The clone states no temperature unit and no numeric temperature range; the example method set gives "
             "27 and 110 without a unit", source="upstream_code", ref="data/methodSet-example.xml:5-6"),
        Fact("The vendor libraries require .NET Framework 4.8 or Mono and are not publicly downloadable",
             source="vendor_doc", ref="README.md:3-9"),
    ]
    safe_state = ("temperature control off, CO2 auto boost off and normal CO2 flow off "
                  "(SetTemperature(None, False), SetAutoBoostCo2(False), SetCo2NormalFlow(False))")

    def _temperature(self):
        return _ok(self.native.GetTemperature()).ResponseData

    # -- reads ------------------------------------------------------------------------------------------------
    @read("device_name", type="string", description="Device name reported by GetDeviceIdentification")
    def device_name(self):
        value, identification = self.native.GetDeviceIdentification()
        _check_return(value)
        return str(identification.DeviceName)

    @read("firmware_version", type="string", description="Device firmware version reported by GetDeviceIdentification")
    def firmware_version(self):
        value, identification = self.native.GetDeviceIdentification()
        _check_return(value)
        return str(identification.DeviceFirmwareVersion)

    @read("state", type="string", description="SiLA device state reported by GetStatus")
    def state(self):
        value, status = self.native.GetStatus()
        _check_return(value)
        return str(status.State)

    @read("current_temperature", unit="Cel", description="Current chamber temperature reported by GetTemperature")
    def current_temperature(self):
        return float(self._temperature().CurrentTemperature)

    @read("target_temperature", unit="Cel", description="Target temperature reported by GetTemperature")
    def target_temperature(self):
        return float(self._temperature().TargetTemperature)

    @read("temperature_control", type="boolean", description="True while GetTemperature reports temperature control")
    def temperature_control(self):
        return bool(self._temperature().TemperatureControl)

    @read("auto_boost_co2", type="boolean", description="True while GetAutoBoostCo2 reports CO2 auto boost")
    def auto_boost_co2(self):
        return bool(_ok(self.native.GetAutoBoostCo2()).ResponseData.AutoBoostCO2)

    @read("boost_state", type="string", description="CO2 boost state string reported by GetAutoBoostCo2")
    def boost_state(self):
        return str(_ok(self.native.GetAutoBoostCo2()).ResponseData.BoostState)

    @read("co2_flow_status", type="string", description="CO2 flow status string reported by GetCo2FlowStatus")
    def co2_flow_status(self):
        return str(_ok(self.native.GetCo2FlowStatus()).ResponseData.CO2FlowStatus)

    @read("liquid_level", type="string", description="Liquid-level string reported by GetLiquidLevel")
    def liquid_level(self):
        return str(_ok(self.native.GetLiquidLevel()).ResponseData.LiquidLevel)

    @read("door_status", type="string", description="Drawer 1 to 4 status strings reported by GetDoorStatus")
    def door_status(self):
        data = _ok(self.native.GetDoorStatus()).ResponseData
        return f"drawer1={data.Drawer1}; drawer2={data.Drawer2}; drawer3={data.Drawer3}; drawer4={data.Drawer4}"

    @read("valve_status", type="string",
          description="Gas_Boost, Gas_Normal and H2O valve status strings reported by GetValveStatus")
    def valve_status(self):
        data = _ok(self.native.GetValveStatus()).ResponseData
        return f"gas_boost={data.Gas_Boost}; gas_normal={data.Gas_Normal}; h2o={data.H2O}"

    # -- writes -----------------------------------------------------------------------------------------------
    @write("auto_boost_co2", type="boolean", description="Enable or disable the CO2 auto boost (SetAutoBoostCo2)")
    def set_auto_boost_co2(self, value):
        _ok(self.native.SetAutoBoostCo2(bool(value)))
        return bool(_ok(self.native.GetAutoBoostCo2()).ResponseData.AutoBoostCO2)

    # -- actions ----------------------------------------------------------------------------------------------
    @action(cap="cap.measure.temperature.v1",
            description="Measure the SCILA chamber temperature (GetTemperature)",
            input={
                "probe": Field("string", description="Optional probe label; the SCILA has one chamber sensor"),
                "location": Field("string", description="Optional location label; the SCILA has one chamber sensor"),
            })
    def measure_temperature(self, probe=None, location=None):
        return {"temperature": float(self._temperature().CurrentTemperature)}

    @action(cap="cap.thermal.setpoint.v1",
            description="Set the SCILA target temperature and enable temperature control",
            input={"target_temperature": Field(
                description="Target temperature of the SCILA chamber", limit=_TARGET_LIMIT)})
    def set_temperature(self, target_temperature):
        _ok(self.native.SetTemperature(target_temperature, True))
        data = self._temperature()
        return {"setpoint": float(data.TargetTemperature),
                "actual_temperature": float(data.CurrentTemperature)}

    @action(name="x-cap.f9r.stop_incubation.v1", safe_state=True,
            description="Stop temperature control and both CO2 flow paths (the safe state); it takes no input",
            output={
                "temperature_control": Field("boolean", description="False after the safe-state setters ran"),
                "auto_boost_co2": Field("boolean", description="False after the safe-state setters ran"),
                "co2_flow_status": Field("string", description="CO2 flow status read back after the setters ran"),
            })
    def stop_incubation(self):
        _ok(self.native.SetTemperature(None, False))
        _ok(self.native.SetAutoBoostCo2(False))
        _ok(self.native.SetCo2NormalFlow(False))
        return {
            "temperature_control": bool(self._temperature().TemperatureControl),
            "auto_boost_co2": bool(_ok(self.native.GetAutoBoostCo2()).ResponseData.AutoBoostCO2),
            "co2_flow_status": str(_ok(self.native.GetCo2FlowStatus()).ResponseData.CO2FlowStatus),
        }

    # -- safety -----------------------------------------------------------------------------------------------
    @estop(native="Abort")
    def stop(self):
        """The native stop: the mandatory SiLA Abort command; the safe-state action follows in the runtime."""
        _ok(self.native.Abort())

    def teardown(self):
        self.native.Dispose()
