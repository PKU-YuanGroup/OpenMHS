"""OpenMHS driver for gh.t-wagner/pymeasure: a Keithley 2000 multimeter over its channel API.

A direct Driver (decorated methods) over the upstream class
``instruments.keithley2000_multimeter:Keithley2000Multimeter``.  The class is a PyVisaInstrument that
exposes the three measurement channels it creates in ``__init__`` (voltage_dc, current_dc and resistance;
``instruments/keithley2000_multimeter.py:651-659``).  A channel's ``query()`` selects its sense function,
sends ``TRIG:SIGN`` and reads ``FETCH?`` (``instruments/keithley2000_multimeter.py:69-90``).  These requests
are assembled per channel and the object offers its channels through the pymeasure container, so a SCPI
command table cannot express the interface: this package is a direct Driver, not the card's ScpiDriver.

* reads: the identity, the DC voltage, the DC current and the resistance;
* the three catalogue read capabilities ``cap.measure.voltage.v1``, ``cap.measure.current.v1`` and
  ``cap.measure.resistance.v1``, one measurement action each; each action can take the class's optional
  channel selector, range and mode inputs where the clone defines them;
* one write, ``voltage_range`` (the SENS:VOLT:DC:RANG setting of the voltage channel), bounded by the
  range the upstream setter states;
* ``@reset`` runs the upstream ``reset`` after an operator accepts a reset of a latched e-stop.

The clone only defines a DC voltage function and a two-wire resistance function, so ``dc=false`` and
``four_wire=true`` are refused with ``MHS.DEVICE.PRECONDITION_UNMET`` rather than inventing an AC or
four-wire command.  The configure binding's class floor makes the package R1; the e-stop runs the upstream
``reset`` (*RST, *CLS), and no hardware e-stop is claimed.

Every Fact cites a line of the clone at the pinned commit d9c552f3a3fabd51c9fb4b76cd1e095f738e96bf.  This
package is model-authored and unreviewed (``driver.lock.json`` ``reviewed_by`` is null); the acceptance gate
runs the fake backend only, and nothing here ran on hardware.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, reset, write

MULTIMETER = "instruments/keithley2000_multimeter.py"


class Keithley2000Multimeter(Driver):
    device_id = "keithley2000"
    device_kind = "instrument.dmm"
    mode = "hardware"
    risk = "R1"
    native = "instruments.keithley2000_multimeter:Keithley2000Multimeter"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeKeithley2000"}
    vendor, model = "Keithley Instruments", "2000 multimeter"
    display_name = "Keithley 2000 multimeter"
    tags = ["keithley", "2000", "dmm", "multimeter", "voltage", "current", "resistance"]
    facts = [
        Fact("Keithley2000Multimeter is a PyVisaInstrument opened at a VISA address", source="upstream_code",
             ref=f"{MULTIMETER}:639-642"),
        Fact("The multimeter creates three channels in this order: voltage_dc, current_dc and resistance",
             source="upstream_code", ref=f"{MULTIMETER}:651-659"),
        Fact("The voltage channel selects the VOLT:DC sense function", source="upstream_code",
             ref=f"{MULTIMETER}:225-226"),
        Fact("The current channel selects the CURR:DC sense function", source="upstream_code",
             ref=f"{MULTIMETER}:254-255"),
        Fact("The resistance channel selects the RES sense function", source="upstream_code",
             ref=f"{MULTIMETER}:283-284"),
        Fact("A channel query writes TRIG:SIGN and reads the measurement with FETCH?", source="upstream_code",
             ref=f"{MULTIMETER}:84-88"),
        Fact("A channel query returns a list and appends the first FETCH? value for each sample",
             source="upstream_code", ref=f"{MULTIMETER}:82-90"),
        Fact("identification queries *IDN?", source="upstream_code", ref=f"{MULTIMETER}:677-679"),
        Fact("reset writes *RST and *CLS and then loads the defaults", source="upstream_code",
             ref=f"{MULTIMETER}:667-671"),
        Fact("A channel range property reads the range with a RANG? query of its sense function",
             source="upstream_code", ref=f"{MULTIMETER}:229-232"),
        Fact("The voltage range setter accepts 0 V to 1010 V", source="upstream_code",
             ref=f"{MULTIMETER}:236-245"),
        Fact("The current range setter accepts 0 A to 3.1 A", source="upstream_code",
             ref=f"{MULTIMETER}:265-274"),
        Fact("The resistance range setter accepts 0 Ohm to 120e6 Ohm", source="upstream_code",
             ref=f"{MULTIMETER}:294-303"),
    ]
    safe_state = "multimeter reset to its defaults (*RST, *CLS)"

    def _channel(self, expected, channel):
        """The upstream channel named ``expected``; a different selector, or a missing channel, is refused."""
        if channel is not None and str(channel) != expected:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"this action reads the {expected} channel; got channel {channel!r}")
        for item in self.native.channels():
            if getattr(item, "name", None) == expected:
                return item
        raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                           f"the backend does not expose the {expected} channel")

    # -- state reads ----------------------------------------------------------------------------------------------
    @read("identification", type="string", description="Identity string returned by the *IDN? query")
    def identification(self):
        return str(self.native.identification)

    @read("voltage_dc", unit="V", description="DC voltage measured on the voltage_dc channel")
    def voltage_dc(self):
        return float(self._channel("voltage_dc", None).query()[0])

    @read("current_dc", unit="A", description="DC current measured on the current_dc channel")
    def current_dc(self):
        return float(self._channel("current_dc", None).query()[0])

    @read("resistance", unit="Ohm", description="Resistance measured on the resistance channel")
    def resistance(self):
        return float(self._channel("resistance", None).query()[0])

    @read("voltage_range", unit="V", description="Measurement range of the voltage_dc channel")
    def voltage_range(self):
        return float(self._channel("voltage_dc", None).range)

    @write("voltage_range", unit="V",
           description="Measurement range of the voltage_dc channel (SENS:VOLT:DC:RANG)",
           limit=Limit(min=0, max=1010, source="upstream_code", ref=f"{MULTIMETER}:236-245"))
    def set_voltage_range(self, value):
        selected = self._channel("voltage_dc", None)
        selected.range = float(value)
        return float(selected.range)

    # -- catalogue measurement actions ----------------------------------------------------------------------------
    @action(cap="cap.measure.voltage.v1",
            description="Trigger a DC voltage measurement on the voltage_dc channel and return the first sample",
            input={
                "channel": Field(
                    "string", description="Channel to read: the clone creates only the voltage_dc voltage channel",
                    limit=Limit(allowed=("voltage_dc",), source="upstream_code", ref=f"{MULTIMETER}:653")),
                "range_v": Field(
                    "number", unit="V",
                    description="Measurement range to set before the sample (SENS:VOLT:DC:RANG); omit it to keep "
                                "the range the instrument has",
                    limit=Limit(min=0, max=1010, source="upstream_code", ref=f"{MULTIMETER}:236-245")),
                "dc": Field(
                    "boolean", description="DC measurement; the clone defines only the VOLT:DC function, so false "
                                           "is refused rather than measured"),
            })
    def measure_voltage(self, channel=None, range_v=None, dc=None):
        if dc is False:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the clone defines only the VOLT:DC function; no AC voltage function is available")
        selected = self._channel("voltage_dc", channel)
        if range_v is not None:
            selected.range = float(range_v)
        output = {"voltage": float(selected.query()[0])}
        if range_v is not None:
            output["range_v"] = float(selected.range)
        return output

    @action(cap="cap.measure.current.v1",
            description="Trigger a DC current measurement on the current_dc channel and return the first sample",
            input={
                "channel": Field(
                    "string", description="Channel to read: the clone creates only the current_dc current channel",
                    limit=Limit(allowed=("current_dc",), source="upstream_code", ref=f"{MULTIMETER}:656")),
                "range_a": Field(
                    "number", unit="A",
                    description="Measurement range to set before the sample (SENS:CURR:DC:RANG); omit it to keep "
                                "the range the instrument has",
                    limit=Limit(min=0, max=3.1, source="upstream_code", ref=f"{MULTIMETER}:265-274")),
            })
    def measure_current(self, channel=None, range_a=None):
        selected = self._channel("current_dc", channel)
        if range_a is not None:
            selected.range = float(range_a)
        output = {"current": float(selected.query()[0])}
        if range_a is not None:
            output["range_a"] = float(selected.range)
        return output

    @action(cap="cap.measure.resistance.v1",
            description="Trigger a two-wire resistance measurement on the resistance channel and return the first "
                        "sample",
            input={
                "channel": Field(
                    "string", description="Channel to read: the clone creates only the resistance channel",
                    limit=Limit(allowed=("resistance",), source="upstream_code", ref=f"{MULTIMETER}:659")),
                "four_wire": Field(
                    "boolean", description="Four-wire measurement; the clone defines only the two-wire RES function, "
                                           "so true is refused rather than measured"),
            })
    def measure_resistance(self, channel=None, four_wire=None):
        if four_wire is True:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the clone defines only the RES function; no four-wire resistance function is "
                               "available")
        selected = self._channel("resistance", channel)
        output = {"resistance": float(selected.query()[0])}
        if four_wire is not None:
            output["four_wire"] = False
        return output

    # -- safety and operator recovery -----------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the upstream reset (*RST and *CLS)."""
        self.native.reset()

    @reset
    def recover(self):
        """Run the upstream reset (*RST and *CLS) after an operator accepts a reset of a latched e-stop."""
        self.native.reset()
