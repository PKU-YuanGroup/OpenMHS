"""OpenMHS driver for gh.aakafosfor/hameg_hm1507: the HAMEG HM1507 oscilloscope over its serial remote control.

A direct Driver (decorated methods) over the upstream class ``HAMEG_HM1507:HAMEG_HM1507``.  The upstream interface is
write-only: ``autoset``, ``timeBase`` and ``channel`` build byte commands from a command prefix, a base or channel
number, ``=`` and one character whose bits are the setting (HAMEG_HM1507.py:87-114).  A SerialDriver command table
cannot express those assembled bytes without changing their syntax, so the package uses the direct shape
(driver-authoring.md, "Choosing the shape").

* writes: one time base (A or B, single sweep and time/div) and one channel (1 or 2, invert, DC/AC and volts/div),
  each as one object whose setter sends exactly one upstream call;
* action: ``autoset`` (the upstream ``AUTOSET`` command);
* the native stop: ``disconnect`` sends ``rm0`` and closes the port (HAMEG_HM1507.py:70-75).

The class has no read or query method (HAMEG_HM1507.py:77-85, where ``readline`` is commented out), so the resource
state reports the values this driver last sent; a front-panel change is not visible.  Every Fact and Limit cites a
line of the clone at the pinned commit 0a03fdc25414d400331769c9e125dd80e0cf5964.  This package is model-authored
and unreviewed; the acceptance gate runs the fake backend only and no hardware was used.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, write

TIME_DIVS = [
    "50ns",
    "100ns",
    "200ns",
    "500ns",
    "1us",
    "2us",
    "5us",
    "10us",
    "20us",
    "50us",
    "100us",
    "200us",
    "500us",
    "1ms",
    "2ms",
    "5ms",
    "10ms",
    "20ms",
    "50ms",
    "100ms",
    "200ms",
    "500ms",
    "1s",
    "2s",
    "5s",
    "10s",
    "20s",
    "50s",
    "100s",
]

V_DIVS = [
    "1mV",
    "2mV",
    "5mV",
    "10mV",
    "20mV",
    "50mV",
    "100mV",
    "200mV",
    "500mV",
    "1V",
    "2V",
    "5V",
    "10V",
    "20V",
]


class HamegHm1507(Driver):
    device_id = "hameg-hm1507"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "HAMEG_HM1507:HAMEG_HM1507"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeHamegHm1507"}
    vendor = "HAMEG"
    model = "HM1507"
    display_name = "HAMEG HM1507 oscilloscope (serial remote control)"
    tags = ["oscilloscope", "hameg", "hm1507", "serial", "instrument"]
    facts = [
        Fact("The remote interface is a serial port opened at 19200 baud with RTS/CTS, two stop bits, no parity "
             "and a one-second timeout", source="upstream_code", ref="HAMEG_HM1507.py:62-67"),
        Fact("connect() sends a single space after opening the port", source="upstream_code",
             ref="HAMEG_HM1507.py:68"),
        Fact("A command is written one character at a time and then a carriage return", source="upstream_code",
             ref="HAMEG_HM1507.py:77-82"),
        Fact("The class has no read or query method; the only readline call is commented out", source="upstream_code",
             ref="HAMEG_HM1507.py:77-85"),
        Fact("autoset() sends AUTOSET", source="upstream_code", ref="HAMEG_HM1507.py:87-88"),
        Fact("Only time bases A and B exist", source="upstream_code", ref="HAMEG_HM1507.py:90-92"),
        Fact("A time base setting adds 32 for single sweep plus the index of the time/div value and sends "
             "TB<base>=<chr(settings)>", source="upstream_code", ref="HAMEG_HM1507.py:93-100"),
        Fact("The time/div list has 29 entries from 50ns to 100s", source="upstream_code",
             ref="HAMEG_HM1507.py:6-36"),
        Fact("Only channels 1 and 2 exist", source="upstream_code", ref="HAMEG_HM1507.py:102-104"),
        Fact("A channel setting starts at 16, adds 32 for invert, 64 for AC coupling and the index of the "
             "volts/div value, then sends CH<channel>=<chr(settings)>", source="upstream_code",
             ref="HAMEG_HM1507.py:105-114"),
        Fact("The volts/div list has 14 entries from 1mV to 20V", source="upstream_code",
             ref="HAMEG_HM1507.py:37-52"),
        Fact("disconnect() sends rm0 and closes the port", source="upstream_code", ref="HAMEG_HM1507.py:70-75"),
        Fact("The upstream GUI keeps separate settings for channels 1 and 2 and for time bases A and B",
             source="upstream_code", ref="gui.py:15-36"),
    ]
    safe_state = "serial remote control released with rm0 and the port closed; the scope keeps its last settings"

    @write("timebase", type="object",
           description="One time base: A or B, single sweep and time/div",
           properties={
               "base": Field("string", enum=["A", "B"],
                             description="Time base A or B",
                             limit=Limit(allowed=["A", "B"], source="upstream_code",
                                         ref="HAMEG_HM1507.py:91")),
               "single": Field("boolean", description="Single sweep (the upstream adds 32)"),
               "time_div": Field("string", enum=TIME_DIVS,
                                 description="Time per division",
                                 limit=Limit(allowed=TIME_DIVS, source="upstream_code",
                                             ref="HAMEG_HM1507.py:6-36")),
           })
    def set_timebase(self, value):
        self.native.timeBase(str(value["base"]), bool(value["single"]), str(value["time_div"]))

    @write("channel", type="object",
           description="One channel: 1 or 2, invert, DC/AC and volts/div",
           properties={
               "channel": Field("integer", unit="1",
                                description="Channel 1 or 2",
                                limit=Limit(allowed=[1, 2], source="upstream_code",
                                            ref="HAMEG_HM1507.py:103")),
               "invert": Field("boolean", description="Invert the channel (the upstream adds 32)"),
               "mode_dc": Field("boolean", description="DC coupling; False selects AC (the upstream adds 64)"),
               "volts_div": Field("string", enum=V_DIVS,
                                  description="Volts per division",
                                  limit=Limit(allowed=V_DIVS, source="upstream_code",
                                              ref="HAMEG_HM1507.py:37-52")),
           })
    def set_channel(self, value):
        self.native.channel(int(value["channel"]), bool(value["invert"]), bool(value["mode_dc"]),
                            str(value["volts_div"]))

    @action(name="x-cap.aakafosfor.autoset.v1", risk="R1",
            description="Run the scope's automatic setup (the upstream AUTOSET command)",
            output={"applied": Field("boolean", description="True after AUTOSET was sent")})
    def autoset(self):
        self.native.autoset()
        return {"applied": True}

    @estop(native="disconnect")
    def stop(self):
        """The native stop: release remote control with rm0 and close the port."""
        self.native.disconnect()
