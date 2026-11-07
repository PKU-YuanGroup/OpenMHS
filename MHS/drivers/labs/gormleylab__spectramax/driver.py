"""OpenMHS driver for gh.gormleylab/spectramax: a Molecular Devices SpectraMax plate reader.

A direct Driver (decorated methods) over the upstream class spectramax:Spectramax, the Python wrapper around the
SoftMax Pro Automation API (spectramax.py:41).  The upstream object is a Python object: get_data() and
get_instrument_status() read state, set_temperature() writes the incubator set point, and read_UVVis() runs a
method file and writes result files.  The card names PythonObjectDriver, but a config-only result mapping cannot
build the three result paths read_UVVis writes from its two string arguments, so this package uses a direct Driver
(DEVIATION FROM THE CARD, recorded in RESULT.json notes).

* reads: the last instrument status and the current plate data (a tab-delimited string);
* x-cap.gormleylab.set_incubator_temperature.v1: set the incubator temperature.  The clone says only that 0 turns
  the incubator off (spectramax.py:388); it states no operating range, so the input is Limit.operator_required and
  every call is refused MHS.SAFETY.LIMITS_UNSET until the site overlay supplies the range of its unit.  The
  catalogue class cap.thermal.setpoint.v1 binds thermal.zone, instrument.incubator and lab.thermal_block, not the
  instrument.spectrophotometer kind of this plate reader; the incubator is one feature of the reader, so the class
  cannot bind it without misdescribing the device;
* x-cap.gormleylab.uvvis_read.v1: run a UV-Vis read from a .spr method file and report the .sda, .csv and .xml
  paths the upstream wrapper writes.  No catalogue class expresses a method-file read: cap.measure.spectrum.v1
  binds instrument.spectrophotometer but requires wavelength_min and wavelength_max inputs that the upstream
  read_UVVis() does not accept;
* x-cap.gormleylab.incubator_off.v1: set_temperature(0), the documented off state, also the SAFE-045 safe-state
  action; the @estop calls the same native method.  The clone documents no independent hardware stop, so
  estop_physical_ref is not set.

Every Fact cites a line of the clone at the pinned commit 7940d4064663d576cbe8b1200e529f3acc1ef924.  This package
is model-authored and unreviewed: only the fake backend was exercised, and the loader refuses the R2 hardware
backend until a human sets reviewed_by in driver.lock.json.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read


class Spectramax(Driver):
    device_id = "spectramax"
    device_kind = "instrument.spectrophotometer"
    mode = "hardware"
    risk = "R2"
    native = "spectramax:Spectramax"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeSpectramax"}
    vendor, model = "Molecular Devices", "SpectraMax plate reader (SoftMax Pro Automation API)"
    display_name = "SpectraMax plate reader (spectramax.Spectramax)"
    tags = ["plate reader", "spectrophotometer", "uv-vis", "softmax pro", "incubator"]
    facts = [
        Fact("Spectramax is the Python wrapper around the SoftMax Pro Automation API", source="upstream_code",
             ref="spectramax.py:1-4"),
        Fact("initialize() creates an SMPAutomationClient, connects it to a server and port, and returns False "
             "if the connection fails", source="upstream_code", ref="spectramax.py:66-98"),
        Fact("get_data() returns the current plate data as a tab-delimited string, or None on error",
             source="upstream_code", ref="spectramax.py:353-358"),
        Fact("get_instrument_status() returns the status string stored by the InstrumentStatusChanged event",
             source="upstream_code", ref="spectramax.py:405-412"),
        Fact("set_temperature() sets the incubator temperature in Celsius; 0 turns the incubator off",
             source="upstream_code", ref="spectramax.py:383-388"),
        Fact("read_UVVis() takes a .spr method file and a results base path, starts the read, saves a .sda file "
             "and exports COLUMNS .csv and .xml files", source="upstream_code", ref="spectramax.py:204-270"),
        Fact("read_UVVis() waits up to 120 s for the read command to complete", source="upstream_code",
             ref="spectramax.py:242-244"),
        Fact("The automation interface queues commands and returns their results through CommandCompleted events",
             source="vendor_doc", ref="spectramax_API.md:376-381"),
    ]
    safe_state = "incubator heating off (set_temperature 0)"

    # -- reads -------------------------------------------------------------------------------------------------
    @read("instrument_status", type="string",
          description="Last instrument status reported by SoftMax Pro (the InstrumentStatusChanged event)")
    def instrument_status(self):
        return self.native.get_instrument_status()

    @read("plate_data", type="string",
          description="Current plate data as a tab-delimited string, as returned by the SoftMax Pro GetDataCopy command")
    def plate_data(self):
        data = self.native.get_data()
        if data is None:
            raise DriverFailed("MHS.DEVICE.FAULTED", "Spectramax.get_data() returned None")
        return data

    # -- thermal set point -------------------------------------------------------------------------------------
    @action(name="x-cap.gormleylab.set_incubator_temperature.v1", risk="R2",
            description="Set the incubator temperature through SoftMax Pro; 0 turns the incubator off",
            input={"target_temperature": Field(
                "number",
                description="Target incubator temperature in Celsius; 0 turns the incubator off",
                unit="Cel",
                limit=Limit.operator_required(
                    "the clone states only that 0 turns the incubator off (spectramax.py:388) and gives no "
                    "operating range; the site supplies the bound of its unit"))},
            output={"setpoint": Field("number", unit="Cel",
                                      description="Incubator set point requested from SoftMax Pro")})
    def set_incubator_temperature(self, target_temperature):
        applied = self.native.set_temperature(target_temperature)
        if applied is False:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "Spectramax.set_temperature() returned False")
        return {"setpoint": target_temperature}

    # -- the UV-Vis read ---------------------------------------------------------------------------------------
    @action(name="x-cap.gormleylab.uvvis_read.v1",
            description="Run a UV-Vis read from a SoftMax Pro .spr method and export .sda, .csv and .xml files",
            input={
                "method": Field("string",
                                description="Path of the .spr method file on the SoftMax Pro host"),
                "results": Field("string",
                                 description="Base path of the result files (without extension) on the "
                                             "SoftMax Pro host"),
            },
            output={
                "sda_path": Field("string", description="Saved SoftMax Pro data file (.sda)"),
                "csv_path": Field("string", description="Exported COLUMNS CSV file"),
                "xml_path": Field("string", description="Exported XML file"),
            })
    def read_uvvis(self, method, results):
        completed = self.native.read_UVVis(method, results)
        if completed is False:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "Spectramax.read_UVVis() returned False")
        return {
            "sda_path": results + ".sda",
            "csv_path": results + ".csv",
            "xml_path": results + ".xml",
        }

    # -- safety ------------------------------------------------------------------------------------------------
    @action(name="x-cap.gormleylab.incubator_off.v1", safe_state=True,
            description="Turn the incubator off with set_temperature(0), the documented off state; no input",
            output={"heating_off": Field("boolean",
                                         description="True once the incubator-off command completed")})
    def incubator_off(self):
        applied = self.native.set_temperature(0.0)
        if applied is False:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "Spectramax.set_temperature(0.0) returned False")
        return {"heating_off": True}

    @estop(native="set_temperature")
    def stop(self):
        """Turn the incubator off; the runtime latches first, then calls this native method."""
        applied = self.native.set_temperature(0.0)
        if applied is False:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "Spectramax.set_temperature(0.0) returned False")

    def teardown(self):
        self.native.disconnect()
