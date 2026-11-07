"""OpenMHS driver for gh.pymeasure/pymeasure: the Keithley DMM6500 6.5-digit multimeter.

The card is a driver pack (one card for a repository of many device classes; recon picks the device class).  The
first entry symbol ``pymeasure.instruments.keithley.keithleyDMM6500:KeithleyDMM6500`` is the class that matches the
card's candidate classes (``cap.measure.current.v1``, ``cap.measure.resistance.v1``, ``cap.measure.voltage.v1``,
``cap.device.configure.v1``) and its ``instrument.dmm`` resource, so this package drives the DMM.

This is a direct Driver (decorated methods) over the upstream class, with the hardware factory in ``native.py``:

* reads: the active measurement mode, the NPLC integration time and the number of display digits;
* one write: NPLC, limited by the 0.0005 to 15 range the upstream ``nplc`` control validates;
* the three measurement classes the catalogue binds to ``instrument.dmm``: ``cap.measure.voltage.v1``,
  ``cap.measure.current.v1`` and ``cap.measure.resistance.v1``.  Each configures the mode through the upstream
  ``measure_*`` method and then reads the ``:READ?`` measurement property, as the upstream class documents;
* the native stop is ``scan_stop()`` (it writes ``:ABOR``): the e-stop aborts the measurement arming and triggering
  sequence.  This driver sets no source output, heater or motion, so aborting the scan is its stop path.

DEVIATION FROM THE CARD'S HELPER: the card's ``helper`` is PythonObjectDriver (family python-object), but a
measurement method configures a mode and then reads a second property, and the stop is the upstream
``scan_stop()``; a family command table cannot express that.  The card's ``decision`` is direct-driver, so the
package is a direct Driver over the upstream class.

Every Fact and Limit cites a line of the clone at the pinned commit 9c6a96014e74bda79988ae0757a6b38ca390d247.
This package is model-authored and unreviewed (``driver.lock.json`` ``reviewed_by`` is null); the hardware backend
was never opened and the fake is an in-memory object, not a recording of the device.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

#: The upstream module of the native class, relative to the clone root.
MODULE = "pymeasure/instruments/keithley/keithleyDMM6500.py"


class KeithleyDMM6500(Driver):
    device_id = "keithley-dmm6500"
    device_kind = "instrument.dmm"
    mode = "hardware"
    risk = "R1"
    native = "pymeasure.instruments.keithley.keithleyDMM6500:KeithleyDMM6500"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeKeithleyDMM6500"}
    vendor, model = "Keithley", "DMM6500 6.5-digit multimeter"
    display_name = "Keithley DMM6500 multimeter"
    tags = ["dmm", "multimeter", "electrical measurement", "scpi", "keithley"]
    facts = [
        Fact("KeithleyDMM6500 is a 6.5-digit multimeter; the class uses the SCPI command set to communicate with "
             "the instrument", source="upstream_code", ref=f"{MODULE}:160-164"),
        Fact("voltage is the ':READ?' measurement in volts of the active measurement mode", source="upstream_code",
             ref=f"{MODULE}:603-606"),
        Fact("measure_voltage() switches the mode to DC voltage, or AC voltage with ac=True, and sets the voltage "
             "range", source="upstream_code", ref=f"{MODULE}:700-713"),
        Fact("current is the ':READ?' measurement in amperes of the active measurement mode",
             source="upstream_code", ref=f"{MODULE}:486-489"),
        Fact("measure_current() switches the mode to DC current, or AC current with ac=True, and sets the current "
             "range", source="upstream_code", ref=f"{MODULE}:583-596"),
        Fact("The DC current full-scale ranges are 10e-6 to 10 A (10 A only on the rear terminals)",
             source="upstream_code", ref=f"{MODULE}:494-495"),
        Fact("measure_resistance() selects 2-wire resistance with wires=2 or 4-wire resistance with wires=4 and "
             "sets the range; any other value raises ValueError", source="upstream_code",
             ref=f"{MODULE}:811-829"),
        Fact("temperature is the ':READ?' measurement in degrees Celsius of the active measurement mode",
             source="upstream_code", ref=f"{MODULE}:961-964"),
        Fact("The NPLC integration time of the active mode is validated as a truncated range with "
             "values=[0.0005, 15]", source="upstream_code", ref=f"{MODULE}:349-366"),
        Fact("The number of display digits of the active mode is validated as one of 3, 4, 5, 6",
             source="upstream_code", ref=f"{MODULE}:368-376"),
        Fact("scan_stop() aborts a scanning measurement by writing :ABOR, stopping the measurement arming and "
             "triggering sequence", source="upstream_code", ref=f"{MODULE}:1315-1321"),
    ]
    safe_state = "measurement scan aborted (:ABOR); the instrument stops arming and triggering measurements"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("mode", type="string", description="Active measurement mode of the instrument (voltage, current, ...)")
    def measurement_mode(self):
        return self.native.mode

    @read("nplc", unit="1", description="Integration time in power line cycles of the active measurement mode")
    def nplc(self):
        return self.native.nplc

    @read("digits", type="integer", unit="1", description="Number of display digits of the active measurement mode")
    def digits(self):
        return self.native.digits

    # -- writes -----------------------------------------------------------------------------------------------
    @write("nplc", unit="1", description="Integration time in power line cycles of the active measurement mode",
           limit=Limit(min=0.0005, max=15, source="upstream_code", ref=f"{MODULE}:365",
                       reason="the upstream nplc control validates the truncated range values=[0.0005, 15]"))
    def set_nplc(self, value):
        self.native.nplc = value
        return float(self.native.nplc)

    # -- measurement capabilities of instrument.dmm -----------------------------------------------------------
    @action(cap="cap.measure.voltage.v1", description="Measure a voltage with the DMM6500 and return it",
            input={"dc": Field("boolean", description="True to measure DC voltage, False for AC voltage")})
    def measure_voltage(self, dc: bool = True):
        self.native.measure_voltage(ac=not dc)
        return {"voltage": float(self.native.voltage)}

    @action(cap="cap.measure.current.v1", description="Measure a current with the DMM6500 and return it",
            input={"range_a": Field(
                "number", unit="A", description="Full-scale current range in amperes (10e-6 to 10 A)",
                limit=Limit(min=10e-6, max=10, source="upstream_code", ref=f"{MODULE}:494-495",
                            reason="the upstream current_range docstring lists 10e-6 to 10 A as the available "
                                   "ranges (10 A only on the rear terminals)"))})
    def measure_current(self, range_a: float = None):
        if range_a is None:
            self.native.measure_current()          # the upstream default range (max_current=10e-3)
        else:
            self.native.measure_current(max_current=range_a)
        return {"current": float(self.native.current)}

    @action(cap="cap.measure.resistance.v1", description="Measure a resistance with the DMM6500 and return it",
            input={"four_wire": Field("boolean",
                                      description="True for a 4-wire resistance measurement, False for 2-wire")})
    def measure_resistance(self, four_wire: bool = False):
        self.native.measure_resistance(wires=4 if four_wire else 2)
        return {"resistance": float(self.native.resistance), "four_wire": bool(four_wire)}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop(native="scan_stop")
    def stop(self):
        """The native stop: scan_stop() writes :ABOR and aborts the measurement arming and triggering sequence."""
        self.native.scan_stop()

    def teardown(self):
        self.native.close()
