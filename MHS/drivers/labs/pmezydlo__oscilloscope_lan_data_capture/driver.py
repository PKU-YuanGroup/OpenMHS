"""OpenMHS driver for gh.pmezydlo/oscilloscope_lan_data_capture: a Rigol DS1000Z oscilloscope over text SCPI.

A direct Driver over the upstream class ``oscilloscope_functions:oscilloscope``.  The card proposes the SerialDriver
(family ``serial``, decision ``family-config``), but the clone assembles every channel command at run time
(``":" + check_chan + ":DISP?"`` and ``":" + channel + ":SCAL?"``), so a fixed command table cannot reproduce the
lines the device receives (G7); this package calls the upstream methods and the exact queries the clone builds.
DEVIATION FROM THE CARD is recorded in RESULT.json.

* reads: the four identity fields the clone parses from ``*IDN?`` (manufacturer, device name, serial number and
  firmware version), the active-channel list captured by ``get_active_channel()`` at connect, and the timebase scale
  and offset read with ``:TIM:SCAL?`` and ``:TIM:OFFS?``;
* ``x-cap.pmezydlo.settings.v1`` (read): one snapshot of the identity, the active channels, the timebase and the
  vertical scale and offset of every active channel, read with the ``:<CHANn>:SCAL?`` and ``:<CHANn>:OFFS?`` queries
  of the clone.  No catalogue class carries an oscilloscope's timebase and vertical settings, so the action is an
  extension with an inline schema;
* no write, no numeric input and no Limit: the clone sets no numeric instrument setting, so this package invents no
  bound and has no operator-required path.

NOT COVERED: the waveform array and the PNG plot.  ``plot`` reads ``:WAV:DATA?`` into a byte string and builds the
voltage and time arrays (oscilloscope_functions.py:37-48), but the method also references ``tUnit`` at line 62 while
only the commented-out code names it (lines 50-57), so the method cannot complete; this package reads the scalar
settings the same queries expose and does not transfer samples.

The clone is Python 2 code: its LAN transport is a copy of the Python 2.7 telnetlib (telnetlib_receive_all.py:1-2),
its serial write passes text to ``serial.write``, and the package's ``device`` constructor imports the telnet copy
(measure_interfaces.py:2, 80-101).  This package therefore registers no hardware backend and is checked on the fake
backend only; no hardware was attached and no hardware run is claimed.

Every Fact cites a line of the clone at the pinned commit (f68c0b8d5acb7592ad21fd39b453d5a4d892a91e).  This package
is model-authored and unreviewed (driver.lock.json reviewed_by is null).
"""

from mhs.driver import Driver, Fact, Field, action, read

OSCILLOSCOPE = "oscilloscope_functions.py"
INTERFACES = "measure_interfaces.py"
EXAMPLE = "oscilloscope.py"


class RigolDs1000z(Driver):
    device_id = "rigol-ds1000z"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R0"
    native = "oscilloscope_functions:oscilloscope"
    backends = {"fake": ".fake:FakeOscilloscope"}
    vendor, model = "Rigol", "DS1000Z series oscilloscope"
    display_name = "Rigol DS1000Z series oscilloscope (oscilloscope_functions.oscilloscope)"
    tags = ["oscilloscope", "rigol", "ds1000z", "scpi", "lan", "serial", "usb", "waveform"]
    facts = [
        Fact("The project captures data from a Rigol DS1000Z series oscilloscope over LAN", source="vendor_doc",
             ref="README.md:2"),
        Fact("The oscilloscope class extends the device transport class", source="upstream_code",
             ref=f"{OSCILLOSCOPE}:6"),
        Fact("The device constructor sends *IDN? on connect", source="upstream_code", ref=f"{INTERFACES}:144"),
        Fact("The *IDN? reply is split into manufacturer, device name, serial number and firmware version",
             source="upstream_code", ref=f"{INTERFACES}:152-155"),
        Fact("The active-channel list starts empty and get_active_channel fills it", source="upstream_code",
             ref=f"{OSCILLOSCOPE}:11-19"),
        Fact("get_active_channel builds channel names CHAN1 through CHANn from the configured channel count",
             source="upstream_code", ref=f"{OSCILLOSCOPE}:14"),
        Fact("A channel is kept as active when its display query answers '1\\n'", source="upstream_code",
             ref=f"{OSCILLOSCOPE}:17-19"),
        Fact("The clone's example constructs the oscilloscope with four channels over USB", source="upstream_code",
             ref=f"{EXAMPLE}:14"),
        Fact("plot reads the timebase scale with :TIM:SCAL? and the timebase offset with :TIM:OFFS?",
             source="upstream_code", ref=f"{OSCILLOSCOPE}:26-27"),
        Fact("plot reads each active channel's vertical scale with :<CHANn>:SCAL? and offset with :<CHANn>:OFFS?",
             source="upstream_code", ref=f"{OSCILLOSCOPE}:32-33"),
        Fact("The captured time axis runs from time_offset - 6 * time_scale to time_offset + 6 * time_scale",
             source="upstream_code", ref=f"{OSCILLOSCOPE}:48"),
        Fact("plot sets the waveform point mode with :WAV:POIN:MODE RAW, reads :WAV:DATA? with the channel name "
             "and writes :KEY:FORCE", source="upstream_code", ref=f"{OSCILLOSCOPE}:37-39"),
        Fact("The waveform reply drops its first 10 characters before the samples are converted",
             source="upstream_code", ref=f"{OSCILLOSCOPE}:38"),
        Fact("plot references tUnit, but tUnit is only named in commented-out code, so the method cannot complete",
             source="upstream_code", ref=f"{OSCILLOSCOPE}:62"),
        Fact("The serial transport writes a command and reads one line back", source="upstream_code",
             ref=f"{INTERFACES}:22-25"),
        Fact("The LAN transport sends *OPC? until it reads 1\\n, then sends the command with a newline and reads "
             "until a newline", source="upstream_code", ref=f"{INTERFACES}:90-98"),
        Fact("The LAN transport is a copy of the Python 2.7 telnetlib with a patch that keeps null characters",
             source="upstream_code", ref="telnetlib_receive_all.py:1-2"),
        Fact("The USB transport read ignores its command argument and sends *OPC? without returning a value",
             source="upstream_code", ref=f"{INTERFACES}:58-67"),
    ]

    def setup(self):
        """Ask the clone which channels are displayed; get_active_channel accumulates into active_chan."""
        self.native.get_active_channel()

    def teardown(self):
        self.native.close()

    @read("manufacturer", type="string", description="Manufacturer parsed from the *IDN? reply")
    def manufacturer(self):
        return self.native.manufacturer

    @read("instrument_model", type="string", description="Device name parsed from the *IDN? reply")
    def instrument_model(self):
        return self.native.dev_name

    @read("serial_number", type="string", description="Serial number parsed from the *IDN? reply")
    def serial_number(self):
        return self.native.serial_number

    @read("firmware_version", type="string", description="Firmware version parsed from the *IDN? reply")
    def firmware_version(self):
        return self.native.firmware_version

    @read("active_channels", type="array", items=Field("string", description="Name of an active channel"),
          description="Channels whose display query answered '1' when get_active_channel() ran at connect")
    def active_channels(self):
        return list(self.native.active_chan)

    @read("timebase_scale_s_per_div", unit="s", description="Timebase scale in seconds per division (:TIM:SCAL?)")
    def timebase_scale_s_per_div(self):
        return float(self.native.read(":TIM:SCAL?"))

    @read("timebase_offset_s", unit="s", description="Timebase offset in seconds (:TIM:OFFS?)")
    def timebase_offset_s(self):
        return float(self.native.read(":TIM:OFFS?"))

    @action(name="x-cap.pmezydlo.settings.v1", verb="read",
            description="Read the identity, the active channels and the timebase and vertical settings",
            output={
                "manufacturer": Field("string", description="Manufacturer parsed from the *IDN? reply"),
                "instrument_model": Field("string", description="Device name parsed from the *IDN? reply"),
                "serial_number": Field("string", description="Serial number parsed from the *IDN? reply"),
                "firmware_version": Field("string", description="Firmware version parsed from the *IDN? reply"),
                "active_channels": Field("array", items=Field("string", description="Name of an active channel"),
                                         description="Channels whose display query answered '1' at connect"),
                "timebase_scale_s_per_div": Field("number", unit="s",
                                                   description="Timebase scale in seconds per division (:TIM:SCAL?)"),
                "timebase_offset_s": Field("number", unit="s",
                                           description="Timebase offset in seconds (:TIM:OFFS?)"),
                "channel_scales_v_per_div": Field(
                    "array", unit="V", items=Field("number", unit="V"),
                    description="Vertical scale of each active channel in volts per division (:<CHANn>:SCAL?)"),
                "channel_offsets_v": Field(
                    "array", unit="V", items=Field("number", unit="V"),
                    description="Vertical offset of each active channel in volts (:<CHANn>:OFFS?)"),
            })
    def settings(self):
        channels = list(self.native.active_chan)
        return {
            "manufacturer": self.native.manufacturer,
            "instrument_model": self.native.dev_name,
            "serial_number": self.native.serial_number,
            "firmware_version": self.native.firmware_version,
            "active_channels": channels,
            "timebase_scale_s_per_div": float(self.native.read(":TIM:SCAL?")),
            "timebase_offset_s": float(self.native.read(":TIM:OFFS?")),
            "channel_scales_v_per_div": [float(self.native.read(":" + channel + ":SCAL?")) for channel in channels],
            "channel_offsets_v": [float(self.native.read(":" + channel + ":OFFS?")) for channel in channels],
        }
