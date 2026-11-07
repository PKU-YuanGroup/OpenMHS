"""OpenMHS driver for gh.snhobbs/hp894xx: an HP 89400-series vector signal analyzer over a Prologix GPIB bridge.

A direct Driver (decorated methods) over the upstream class HP894xx.HP89400Device:HP89400Device
(python/HP894xx/HP89400Device.py:55).  The upstream class queries the analyzer through a Prologix
GPIB-Ethernet adapter (README.md:2) and returns the values as the text of the GPIB reply; the reads here
convert the numeric replies to floats and keep the unit strings as they are.

* reads: the centre and span of the X axis, the X and Y unit strings, the configured data-point count, the
  average count, the operating-condition register, and the error queue entry and its leading code;
* ``x-cap.snhobbs.acquire_spectrum.v1``: one trace.  ``read_data`` starts the read and parses the
  comma-separated reply into the list of Y values (python/HP894xx/HP89400Device.py:198-211); the action also
  reports the metadata with which the README reconstructs the X axis (README.md:55);
* ``x-cap.snhobbs.abort_measurement.v1``: the native ``abor`` write (python/HP894xx/HP89400Device.py:130-137);
* ``x-cap.snhobbs.enable_autorange.v1``: ``SENS:VOLT:RANGE:AUTO`` with an integer 0/1 setting
  (python/HP894xx/HP89400Device.py:189-190).

This package exposes no numeric setting, so it declares no Limit: it does not infer a bound from a sample
capture, a constructor default or an unread PDF.  The upstream interface is observational (reads, a trace
read, an abort and a boolean autorange setting); it has no motion, heater or radiation source, so the declared
risk is R0 (MHS/spec/04-safety.md:66) and no e-stop or safe-state action is required.

Every Fact cites a line of the clone at the pinned commit (6745a53c20fb02b1a178fde70b1975b6b86f3518).  This
package is model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran on an
analyzer.
"""

from mhs.driver import Driver, Fact, Field, action, read


def _text(value):
    """The GPIB reply as text: the upstream transport may hand back bytes or str."""
    if isinstance(value, bytes):
        return value.decode("ascii", "replace").strip()
    return str(value).strip()


def _number(value):
    """A numeric GPIB reply (for example ``+2.50000000000000E+006``) as a float."""
    return float(_text(value))


class HP89400(Driver):
    device_id = "hp89400"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R0"
    native = "HP894xx.HP89400Device:HP89400Device"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeHP89400"}
    vendor, model = "Hewlett-Packard", "HP 89400 series vector signal analyzer"
    display_name = "HP 89400 series vector signal analyzer (HP894xx.HP89400Device)"
    tags = ["vector signal analyzer", "spectrum", "gpib", "prologix", "measurement"]
    facts = [
        Fact("The upstream driver class is HP89400Device, a PrologixGPIBEthernetDevice", source="upstream_code",
             ref="python/HP894xx/HP89400Device.py:55"),
        Fact("The class constructor forwards its arguments to PrologixGPIBEthernetDevice", source="upstream_code",
             ref="python/HP894xx/HP89400Device.py:56-57"),
        Fact("The README describes the package as HP89400 Series Vector Signal Analyzer GPIB Control using the "
             "Prologix GPIB-ETHERNET adapter", source="vendor_doc", ref="README.md:2"),
        Fact("GetXCenter queries SENS:FREQ:CENT? and GetXSpan queries SENS:FREQ:SPAN?", source="upstream_code",
             ref="python/HP894xx/HP89400Device.py:121-125"),
        Fact("GetXUnits queries CALC:X:UNIT:FREQ? and GetYUnits queries CALC:UNIT:POW?", source="upstream_code",
             ref="python/HP894xx/HP89400Device.py:114-119"),
        Fact("GetDataLength queries CALC:DATA:HEAD:POIN? and returns an int", source="upstream_code",
             ref="python/HP894xx/HP89400Device.py:111-112"),
        Fact("GetReadDataPoints queries SENS:AVER:COUN:INT? and returns an int", source="upstream_code",
             ref="python/HP894xx/HP89400Device.py:192-193"),
        Fact("get_operating_condition queries STAT:OPER:COND? and returns an int", source="upstream_code",
             ref="python/HP894xx/HP89400Device.py:171-173"),
        Fact("get_error_code takes the leading comma-separated field of an error string as an int",
             source="upstream_code", ref="python/HP894xx/HP89400Device.py:74-76"),
        Fact("read_errors queries SYST:ERR?, and read_error_code returns get_error_code(read_errors())",
             source="upstream_code", ref="python/HP894xx/HP89400Device.py:95-99"),
        Fact("read_data starts a data read with StartDataRead and parses the comma-separated reply into floats",
             source="upstream_code", ref="python/HP894xx/HP89400Device.py:198-211"),
        Fact("StartDataRead writes CALC:DATA?", source="upstream_code",
             ref="python/HP894xx/HP89400Device.py:195-196"),
        Fact("abort writes abor until the write succeeds", source="upstream_code",
             ref="python/HP894xx/HP89400Device.py:130-137"),
        Fact("enable_autorange writes SENS:VOLT:RANGE:AUTO with an integer 0/1 setting", source="upstream_code",
             ref="python/HP894xx/HP89400Device.py:189-190"),
        Fact("The README's sample capture shows a 5 MHz span centred at 2.5 MHz with 1601 points, X unit HZ and "
             "Y unit VRMS/RTHZ", source="vendor_doc", ref="README.md:23-41"),
        Fact("The README states that no x values are saved, only y values, and that the x values can be "
             "determined from the header", source="vendor_doc", ref="README.md:55"),
    ]

    # -- state ----------------------------------------------------------------------------------------------------
    @read("center_frequency", unit="Hz", description="Centre of the X axis, read with SENS:FREQ:CENT?")
    def center_frequency(self):
        return _number(self.native.GetXCenter())

    @read("span", unit="Hz", description="Span of the X axis, read with SENS:FREQ:SPAN?")
    def span(self):
        return _number(self.native.GetXSpan())

    @read("x_units", type="string", description="Unit of the X axis as reported by the analyzer")
    def x_units(self):
        return _text(self.native.GetXUnits())

    @read("y_units", type="string", description="Unit of the Y values as reported by the analyzer")
    def y_units(self):
        return _text(self.native.GetYUnits())

    @read("data_points", type="integer", unit="1",
          description="Configured number of data points, read with CALC:DATA:HEAD:POIN?")
    def data_points(self):
        return int(self.native.GetDataLength())

    @read("average_count", type="integer", unit="1",
          description="Average count of the measurement, read with SENS:AVER:COUN:INT?")
    def average_count(self):
        return int(self.native.GetReadDataPoints())

    @read("operating_condition", type="integer", unit="1",
          description="Operating-condition register, read with STAT:OPER:COND?")
    def operating_condition(self):
        return int(self.native.get_operating_condition())

    @read("error_code", type="integer", unit="1",
          description="Leading status code of the next error-queue entry, read with SYST:ERR?")
    def error_code(self):
        return int(self.native.read_error_code())

    @read("errors", type="string", description="Next error-queue entry, read with SYST:ERR?")
    def errors(self):
        return _text(self.native.read_errors())

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.snhobbs.acquire_spectrum.v1",
            description="Read one trace: start a data read, return the Y values and the X/Y metadata the "
                        "analyzer reports",
            output={
                "values": Field("array", unit="1", items=Field("number"),
                                description="Measured Y values in the current y_units unit"),
                "points": Field("integer", unit="1", description="Number of Y values returned"),
                "x_units": Field("string", description="Unit of the X axis as reported by the analyzer"),
                "y_units": Field("string", description="Unit of the Y values as reported by the analyzer"),
                "center_frequency": Field("number", unit="Hz",
                                          description="Centre of the X axis as reported by the analyzer"),
                "span": Field("number", unit="Hz", description="Span of the X axis as reported by the analyzer"),
                "sampled_at": Field("string", description="Time the trace was read"),
            })
    def acquire_spectrum(self):
        values = [float(item) for item in self.native.read_data()]
        return {
            "values": values,
            "points": len(values),
            "x_units": _text(self.native.GetXUnits()),
            "y_units": _text(self.native.GetYUnits()),
            "center_frequency": _number(self.native.GetXCenter()),
            "span": _number(self.native.GetXSpan()),
        }

    @action(name="x-cap.snhobbs.abort_measurement.v1",
            description="Abort the measurement with the native abor write",
            output={"aborted": Field("boolean", description="True once the abort write returned")})
    def abort_measurement(self):
        self.native.abort()
        return {"aborted": True}

    @action(name="x-cap.snhobbs.enable_autorange.v1",
            description="Enable or disable the input autorange with SENS:VOLT:RANGE:AUTO",
            input={"enabled": Field("boolean", description="True enables autorange, False disables it")},
            output={"enabled": Field("boolean",
                                     description="The state requested from the analyzer; the upstream method "
                                                 "has no read-back")})
    def enable_autorange(self, enabled):
        setting = bool(enabled)
        self.native.enable_autorange(setting)
        return {"enabled": setting}
