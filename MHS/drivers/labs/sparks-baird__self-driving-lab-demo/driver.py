"""OpenMHS driver for gh.sparks-baird/self-driving-lab-demo: the nonwireless CLSLab:Light Pico demo.

A direct Driver over the upstream ``extra.nonwireless.lib.host_nonwireless:Talker`` serial class.  The card names the
``PythonObjectDriver`` helper (family ``python-object``); the real interface is not a Python method call but the two
text commands the Pico parses, ``set_color(R, G, B)`` and ``read_sensor(astep, atime, gain)``, sent through the
serial transport.  The family grammar binds one native method per command and ``Talker.send`` returns no reply, so it
cannot express the send-then-receive measurement; this package is a direct Driver (DEVIATION FROM THE CARD, recorded
in RESULT.json notes).

* read: ``color``, the last RGB value the driver sent (the firmware has no color read-back; its startup sequence
  ends with ``set_color(0, 0, 0)``);
* write: ``color``, one NeoPixel on pin 28, three bytes 0 to 255;
* action: an ``x-cap`` measurement with the AS7341 ASTEP, ATIME and gain settings, returning the eight fixed channel
  centres and the eight intensity values; ``cap.measure.spectrum.v1`` requires a wavelength range and does not take
  the sensor's integration settings, so an extension carries the real interface;
* e-stop: ``set_color(0, 0, 0)`` through the same ``send`` path.

Every Fact cites a line of the clone at the pinned commit (051e91e34b63e5ce357df3db7e7425186c5c635c).  This package
is model-authored and unreviewed; it is checked on the fake backend only and no hardware was attached or run.
"""

import ast

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The upstream host helper that establishes the wire syntax: src/self_driving_lab_demo/utils/observe.py:362-386.
HOST_HELPER = "src/self_driving_lab_demo/utils/observe.py"
#: The AS7341 channel table: src/self_driving_lab_demo/utils/channel_info.py:3-11 and 26-35.
CHANNELS = "src/self_driving_lab_demo/utils/channel_info.py"
#: The nonwireless Pico firmware: src/extra/nonwireless/main.py:10-51.
FIRMWARE = "src/extra/nonwireless/main.py"

#: The nominal centres of the eight AS7341 channels, in nm (channel_info.py:3-11).
WAVELENGTHS = [410.0, 440.0, 470.0, 510.0, 550.0, 583.0, 620.0, 670.0]


class ClslabLight(Driver):
    device_id = "clslab-light"
    device_kind = "instrument.spectrometer"
    mode = "hardware"
    #: R1, above the card's floor: the generic configure class carries an R1 floor and the device emits light
    #: through an addressable LED.  No laser, pump, heater or motion stage is part of this nonwireless demo.
    risk = "R1"
    native = "extra.nonwireless.lib.host_nonwireless:Talker"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeTalker"}
    vendor = "sparks-baird"
    model = "CLSLab:Light nonwireless Pico demo"
    display_name = "CLSLab:Light NeoPixel + AS7341 (nonwireless serial)"
    tags = ["spectrometer", "as7341", "neopixel", "led", "serial", "self-driving-lab", "color-matching"]
    facts = [
        Fact("The nonwireless host helper opens the serial port at 115200 baud and writes set_color(R, G, B) and "
             "read_sensor(astep, atime, gain) lines, reading one reply line and one extra line",
             source="upstream_code", ref=f"{HOST_HELPER}:362-386"),
        Fact("Talker appends CR FF to the command text, reads the echoed line, strips a '>>> ' prompt and raises "
             "ValueError when the echo differs", source="upstream_code",
             ref="src/extra/nonwireless/lib/host_nonwireless.py:12-20"),
        Fact("Talker.receive reads to a CR terminator and strips the line", source="upstream_code",
             ref="src/extra/nonwireless/lib/host_nonwireless.py:22-24"),
        Fact("The nonwireless Pico's set_color writes one NeoPixel on pin 28; read_sensor sets ASTEP, ATIME and gain "
             "and returns every channel", source="upstream_code", ref=f"{FIRMWARE}:10-24"),
        Fact("The nonwireless firmware's startup sequence ends with set_color(0, 0, 0), so the LED is off after boot",
             source="upstream_code", ref=f"{FIRMWARE}:27-32"),
        Fact("The eight AS7341 channels are ch410, ch440, ch470, ch510, ch550, ch583, ch620 and ch670",
             source="upstream_code", ref=f"{CHANNELS}:26-35"),
        Fact("The nominal channel centres are 410, 440, 470, 510, 550, 583, 620 and 670 nm",
             source="upstream_code", ref=f"{CHANNELS}:3-11"),
        Fact("Sensor.all_channels runs an F1F4CN and an F5F8CN measurement and returns the eight values f1 to f8",
             source="upstream_code", ref="src/extra/nonwireless/lib/as7341_sensor.py:100-109"),
        Fact("The total integration time is (ASTEP + 1) * (ATIME + 1) * 2.78 / 1000 ms",
             source="upstream_code", ref="src/extra/nonwireless/lib/as7341.py:491-500"),
        Fact("The host asserts atime 0 to 255, astep 0 to 65534 and gain 0.5 to 512",
             source="upstream_code", ref=f"{HOST_HELPER}:76-78"),
        Fact("The AS7341 gain code runs from 0 to 10 and maps to the factors 0.5, 1, 2, ..., 512",
             source="upstream_code", ref="src/extra/nonwireless/lib/as7341.py:502-505"),
        Fact("The MQTT firmware for the same Pico asserts that R, G and B are each between 0 and 255",
             source="upstream_code", ref="src/public_mqtt_sdl_demo/main.py:163-165"),
        Fact("The nonwireless firmware parser reads one line, splits it on parentheses and dispatches set_color and "
             "read_sensor", source="upstream_code", ref=f"{FIRMWARE}:38-51"),
        Fact("The nonwireless firmware's read_sensor branch unpacks two arguments and then calls a three-argument "
             "read_sensor", source="upstream_code", ref=f"{FIRMWARE}:48-50"),
    ]
    safe_state = "NeoPixel off: set_color(0, 0, 0) is sent through the serial link"

    def setup(self):
        # The firmware's startup sequence ends with set_color(0, 0, 0) (main.py:27-32).
        self._color = [0, 0, 0]

    # -- reads ------------------------------------------------------------------------------------------------
    @read("color", type="array", items="integer", length=3, unit="1",
          description="Last RGB color the driver sent to the one NeoPixel, as three bytes 0 to 255; the firmware "
                      "offers no color read-back and its startup sequence leaves the LED off")
    def color(self):
        return list(self._color)

    # -- writes -----------------------------------------------------------------------------------------------
    @write("color", type="array", items="integer", length=3, unit="1",
           description="RGB color of the one NeoPixel, in the order red, green, blue, each byte 0 to 255",
           limit=Limit(min=0, max=255, source="upstream_code", ref="src/public_mqtt_sdl_demo/main.py:163-165",
                       reason="the MQTT firmware for the same Pico asserts each of R, G and B is between 0 and 255; "
                              "the nonwireless firmware writes the tuple to the NeoPixel without its own assertion"))
    def set_color(self, value):
        red, green, blue = (int(item) for item in value)
        self.native.send(f"set_color({red}, {green}, {blue})")
        self._color = [red, green, blue]
        return list(self._color)

    # -- measurement ------------------------------------------------------------------------------------------
    @action(name="x-cap.sparks-baird.measure_spectrum.v1",
            description="Measure the eight fixed AS7341 bands through the current NeoPixel color, with the ATIME, "
                        "ASTEP and gain settings the command carries; the reply is one list of eight intensities",
            input={
                "atime": Field("integer", unit="1",
                               description="ATIME integration step count, 0 to 255: the total integration time is "
                                           "(ASTEP + 1) * (ATIME + 1) * 2.78 / 1000 ms",
                               limit=Limit(min=0, max=255, source="upstream_code", ref=f"{HOST_HELPER}:76")),
                "astep": Field("integer", unit="1",
                               description="ASTEP integration step count, 0 to 65534",
                               limit=Limit(min=0, max=65534, source="upstream_code", ref=f"{HOST_HELPER}:77")),
                "gain": Field("number", unit="1",
                              description="AS7341 ADC gain factor, 0.5 to 512 (the sensor's code is 0 to 10)",
                              limit=Limit(min=0.5, max=512, source="upstream_code", ref=f"{HOST_HELPER}:78")),
            },
            output={
                "wavelengths": Field("array", items="number", unit="nm", length=8,
                                     description="Nominal centres of the eight AS7341 bands, in nm"),
                "intensities": Field("array", items="number", unit="1", length=8,
                                     description="Eight channel readings returned by the sensor, in arbitrary units"),
                "integration_ms": Field("number", unit="ms",
                                        description="Total integration time computed from ASTEP and ATIME"),
            })
    def measure_spectrum(self, atime, astep, gain):
        atime = int(atime)
        astep = int(astep)
        gain = float(gain)
        self.native.send(f"read_sensor({astep}, {atime}, {gain:g})")
        reply = self.native.receive()
        try:
            values = ast.literal_eval(reply)
        except (SyntaxError, ValueError) as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the sensor reply is not a list: {reply!r}") from exc
        if not isinstance(values, list) or len(values) != len(WAVELENGTHS):
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the sensor returned {values!r}, not the eight channel values")
        integration_ms = (astep + 1) * (atime + 1) * 2.78 / 1000.0
        return {"wavelengths": list(WAVELENGTHS), "intensities": [float(item) for item in values],
                "integration_ms": integration_ms}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The safe state: the runtime latches first, then the driver sends set_color(0, 0, 0)."""
        self.native.send("set_color(0, 0, 0)")
        self._color = [0, 0, 0]

    def teardown(self):
        self.native.close()
