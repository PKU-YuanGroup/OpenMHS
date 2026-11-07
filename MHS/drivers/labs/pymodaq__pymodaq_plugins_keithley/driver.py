"""OpenMHS driver for gh.pymodaq/pymodaq_plugins_keithley: the Keithley 2100 digital multimeter.

This is a direct Driver over the clone's ``Keithley2100VISADriver`` and not the card's ScpiDriver.  The upstream
``set_mode`` builds the SCPI line from parts: a fixed ``:CONF:`` prefix plus the function selected by the mode
name (keithley2100_VISADriver.py:97-119).  A command table cannot reproduce those lines, so the driver calls the
upstream class through ``self.native`` and the hardware backend opens it in ``native.py``.  The fake backend
implements the same public methods with test data only.

* reads: the measurement, the identity, the installed option card, the last instrument error and the mode this
  driver last applied;
* write: the measurement mode, restricted to the six names the upstream code documents;
* action: the native reset (``*CLS`` then ``*RST``), exposed as an extension because no stable catalogue class
  describes resetting an instrument;
* e-stop: the native reset, the only recovery the upstream class offers.

Every Fact and Limit cites a line of the clone at the pinned commit
(7698a50e9f596e6655b33de2b88dedd4b79786f4).  This package is model-authored and unreviewed; it is checked on the
fake backend only and no hardware run has been made.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

NATIVE = "src/pymodaq_plugins_keithley/hardware/keithley2100/keithley2100_VISADriver.py"

#: The measurement modes named by the set_mode docstring (keithley2100_VISADriver.py:87).  The aliases the code
#: also accepts (Ohm2, Ohm4, V, I) are not offered: one canonical name per function is enough, and the allowed set
#: below is exactly the documented set.
MODES = ["VDC", "VAC", "IDC", "IAC", "R2W", "R4W"]

#: The driver's sentinel for "no mode has been applied by this driver yet".  It is not a device mode.
UNSET = "unknown"


class Keithley2100(Driver):
    device_id = "keithley2100"
    device_kind = "instrument.dmm"
    mode = "hardware"
    risk = "R1"
    native = ("pymodaq_plugins_keithley.hardware.keithley2100.keithley2100_VISADriver:"
              "Keithley2100VISADriver")
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeKeithley2100"}
    vendor, model = "Keithley Instruments", "2100"
    display_name = "Keithley 2100 digital multimeter"
    tags = ["keithley", "2100", "multimeter", "dmm", "visa", "scpi"]
    facts = [
        Fact("The plugin lists the Keithley 2100 as a 0D viewer multimeter", source="vendor_doc",
             ref="README.rst:43-47"),
        Fact("set_mode documents VDC, VAC, IDC, IAC, R2W and R4W as the supported measurement modes",
             source="upstream_code", ref=f"{NATIVE}:87"),
        Fact("set_mode picks the function from the mode name: Ohm2/R2W -> RES, Ohm4/R4W -> FRES, VDC/V -> VOLT:DC, "
             "VAC -> VOLT:AC, IDC/I -> CURR:DC and IAC -> CURR:AC",
             source="upstream_code", ref=f"{NATIVE}:99-110"),
        Fact("A configuration is sent as ':CONF:' followed by the function name, with an optional range and "
             "resolution appended", source="upstream_code", ref=f"{NATIVE}:97-119"),
        Fact("read() sends READ? and converts the answer to float", source="upstream_code", ref=f"{NATIVE}:79-80"),
        Fact("The identity, installed option card and last error are queried with *IDN?, *OPT? and SYST:ERR?",
             source="upstream_code", ref=f"{NATIVE}:47-54"),
        Fact("reset() sends *CLS and then *RST", source="upstream_code", ref=f"{NATIVE}:75-77"),
        Fact("The VISA resource is opened with a newline write termination", source="upstream_code",
             ref=f"{NATIVE}:29-31"),
        Fact("close() opens all routes with ROUT:OPEN:ALL before it closes the VISA resource", source="upstream_code",
             ref=f"{NATIVE}:43-45"),
    ]
    safe_state = ("the instrument is reset with *CLS and *RST and the driver no longer assumes the mode it "
                  "applied")

    @read("reading", description="Measurement in the unit of the active function (volts, amperes or ohms); "
            "the upstream class does not say which unit is active")
    def reading(self):
        return self.native.read()

    @read("identification", type="string", description="Identity returned by *IDN?")
    def identification(self):
        return self.native.get_idn()

    @read("card", type="string", description="Installed option card returned by *OPT?")
    def card(self):
        return self.native.get_card()

    @read("error", type="string", description="Last instrument error returned by SYST:ERR?")
    def error(self):
        return self.native.get_error()

    @read("mode", type="string",
          description="Measurement mode last applied through this driver; 'unknown' until the first mode write")
    def read_mode(self):
        return self._mode

    @write("mode", type="string", description="Measurement mode (set_mode)",
           limit=Limit(allowed=MODES, source="upstream_code", ref=f"{NATIVE}:87",
                       reason="the set_mode docstring names these six modes; the function map applies them"))
    def write_mode(self, value):
        self.native.set_mode(value)
        self._mode = value

    @action(name="x-cap.pymodaq.keithley2100_reset.v1",
            description="Reset the instrument with the native reset (*CLS, *RST)",
            output={"reset": Field("boolean", description="True once the native reset has been sent")})
    def reset_instrument(self):
        self.native.reset()
        self._mode = UNSET
        return {"reset": True}

    @estop
    def stop(self):
        """The native reset: the upstream class offers no other stop path."""
        self.native.reset()
        self._mode = UNSET

    def setup(self):
        self._mode = UNSET

    def teardown(self):
        self.native.close()
