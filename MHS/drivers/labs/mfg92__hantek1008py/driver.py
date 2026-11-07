"""OpenMHS driver for gh.mfg92/hantek1008py: a Hantek 1008C USB oscilloscope with a waveform generator.

A direct Driver over the upstream device class ``hantek1008:Hantek1008`` (hantek1008.py:683), a subclass of
``Hantek1008Raw`` (hantek1008.py:37).  The upstream object owns the USB transport (vendor 0x0783, product 0x5725,
hantek1008.py:103-110) and builds every command as a binary frame in ``__send_cmd`` (hantek1008.py:156-175); a
command table cannot reproduce that wire form, so this package is a direct Driver rather than a family helper.

* reads: the active channel ids, the vertical scale factor of every channel, the zero offset of every channel, the
  pause thread state, and the waveform length the generator API reports;
* actions: enable or disable the eight generator outputs, set the generator speed in rpm, upload a bit-pattern
  waveform, start or stop the USB keep-alive pause thread, and a safe-state action that disables the generator;
* the native stop is ``Hantek1008.set_generator_on(False)``: the generator outputs are disabled.  ``init`` already
  sets the generator speed to 300000 and turns the generator off (hantek1008.py:284-285), so power-up is the same
  output-off state.

The upstream class exposes no getter for the generator state, so the generator actions return the value they
commanded; the package does not claim a readback that the clone does not implement.

NOT COVERED: the sample arrays of ``request_samples_roll_mode`` and ``request_samples_burst_mode``
(hantek1008.py:402-520): they are the oscilloscope capture path and the standard carries their scalar settings and
the generator commands, not those arrays.  The package also does not expose the constructor-only settings (time
div, trigger source/slope/level, vertical scale and active-channel selection): the clone has no public setters for
them.

Every Fact cites a line of the clone at the pinned commit 302e45ad9d47dafec8a57c36aaca0b76647b221d.  This package
is model-authored and unreviewed: it is checked on the fake backend only, and the hardware backend was never
opened or imported.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read

MODULE = "hantek1008.py"


class Hantek1008Scope(Driver):
    device_id = "hantek-1008"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "hantek1008:Hantek1008"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeHantek1008"}
    vendor, model = "Hantek", "1008C"
    display_name = "Hantek 1008C USB oscilloscope (hantek1008.Hantek1008)"
    tags = ["oscilloscope", "hantek", "usb", "signal-generator", "measurement"]
    facts = [
        Fact("Hantek1008Raw communicates with a Hantek1008 device over USB and supports configuring the device and "
             "measuring samples with it", source="upstream_code", ref=f"{MODULE}:37-42"),
        Fact("Hantek1008 extends Hantek1008Raw with raw-to-volt conversion and zero-offset shift compensation",
             source="upstream_code", ref=f"{MODULE}:683-687"),
        Fact("The device has 8 channels", source="upstream_code", ref=f"{MODULE}:434-435"),
        Fact("Channel ids and indices are zero based, and channel names are one based", source="upstream_code",
             ref=f"{MODULE}:43-44"),
        Fact("The vertical scale factors are 0.02, 0.125 and 1.0", source="upstream_code", ref=f"{MODULE}:47"),
        Fact("get_vscales returns one vertical scale factor per channel and get_active_channels returns the active "
             "channel ids", source="upstream_code", ref=f"{MODULE}:637-645"),
        Fact("get_zero_offset returns the zero offset of one channel at a vertical scale", source="upstream_code",
             ref=f"{MODULE}:525-536"),
        Fact("init measures the zero offsets of all eight channels at each of the three vertical scales",
             source="upstream_code", ref=f"{MODULE}:327-353"),
        Fact("get_generator_waveform_max_length reports 1440", source="upstream_code",
             ref=f"{MODULE}:539-540"),
        Fact("set_generator_waveform currently accepts at most 62 bytes; each byte is a bit pattern for the eight "
             "digital outputs", source="upstream_code", ref=f"{MODULE}:564-577"),
        Fact("set_generator_speed asserts a speed of 1 to 750000 rpm and sends a computed pulse length",
             source="upstream_code", ref=f"{MODULE}:548-562"),
        Fact("set_generator_on turns the generator on with parameter 0x01 and off with 0x00", source="upstream_code",
             ref=f"{MODULE}:542-546"),
        Fact("init sets the generator speed to 300000 and turns the generator off", source="upstream_code",
             ref=f"{MODULE}:284-285"),
        Fact("pause starts a thread that sends a ping every 10 ms, cancel_pause stops it, and is_paused reports "
             "whether it runs", source="upstream_code", ref=f"{MODULE}:587-610"),
        Fact("connect finds the USB device by vendor id 0x0783 and product id 0x5725", source="upstream_code",
             ref=f"{MODULE}:103-110"),
        Fact("close cancels a running pause, sends a ping and command 0xf4, then resets the USB device",
             source="upstream_code", ref=f"{MODULE}:612-620"),
        Fact("The README describes the project as tooling for Hantek 1008 USB oscilloscopes", source="vendor_doc",
             ref="README.md:3"),
        Fact("The README states Python >= 3.6 and requires pyusb and overrides", source="vendor_doc",
             ref="README.md:23-24"),
    ]
    safe_state = "waveform generator outputs disabled (generator off)"

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("active_channels",
          type=Field("array", items=Field("integer", unit="1", description="Zero-based channel id"),
                     min_items=1, max_items=8,
                     description="Active channel ids, zero based; channel names are one based"))
    def active_channels(self):
        return [int(channel) for channel in self.native.get_active_channels()]

    @read("vertical_scales",
          type=Field("array", length=8, items=Field("number", unit="1", description="Vertical scale factor"),
                     description="Vertical scale factor of each of the 8 channels; the allowed values are 0.02, "
                                 "0.125 and 1.0"))
    def vertical_scales(self):
        return [float(scale) for scale in self.native.get_vscales()]

    @read("zero_offsets",
          type=Field("array", length=8,
                     items=Field("number", unit="1", description="Zero offset in raw sample units"),
                     description="Zero offset of each of the 8 channels at its current vertical scale"))
    def zero_offsets(self):
        return [float(self.native.get_zero_offset(channel))
                for channel in range(self.native.channel_count())]

    @read("paused", type="boolean", description="True while the USB keep-alive pause thread is running")
    def paused(self):
        return bool(self.native.is_paused())

    @read("generator_waveform_max_length", type="integer", unit="1",
          description="Maximum waveform length reported by get_generator_waveform_max_length; "
                      "set_generator_waveform currently accepts at most 62 bytes")
    def generator_waveform_max_length(self):
        return int(self.native.get_generator_waveform_max_length())

    # -- generator commands -----------------------------------------------------------------------------------------
    @action(name="x-cap.mfg92.set_generator_on.v1",
            description="Enable or disable the eight digital waveform-generator outputs",
            input={"on": Field("boolean",
                               description="True to enable the generator outputs, False to disable them")},
            output={"on": Field("boolean", description="Generator state that was commanded")})
    def set_generator_on(self, on):
        self.native.set_generator_on(bool(on))
        return {"on": bool(on)}

    @action(name="x-cap.mfg92.set_generator_speed.v1",
            description="Set the generator speed in revolutions per minute",
            input={"speed_rpm": Field("integer", unit="/min",
                                      description="Generator speed; the upstream asserts 1 to 750000 rpm",
                                      limit=Limit(min=1, max=750000, source="upstream_code",
                                                  ref=f"{MODULE}:551"))},
            output={"speed_rpm": Field("integer", unit="/min", description="Speed that was commanded")})
    def set_generator_speed(self, speed_rpm):
        self.native.set_generator_speed(int(speed_rpm))
        return {"speed_rpm": int(speed_rpm)}

    @action(name="x-cap.mfg92.set_generator_waveform.v1",
            description="Upload a waveform as bytes; bit i of each byte is digital output i",
            input={"waveform": Field("array", unit="1",
                                     items=Field("integer", unit="1",
                                                 description="One byte: bit i switches output i on or off"),
                                     min_items=1, max_items=62,
                                     description="Waveform bytes, at most 62 (hantek1008.py:576); each byte is 0 "
                                                 "to 255",
                                     limit=Limit(min=0, max=255, source="upstream_code",
                                                 ref=f"{MODULE}:577"))},
            output={"waveform": Field("array", unit="1",
                                      items=Field("integer", unit="1", description="Waveform byte"),
                                      description="Waveform bytes that were commanded")})
    def set_generator_waveform(self, waveform):
        values = [int(byte) for byte in waveform]
        self.native.set_generator_waveform(values)
        return {"waveform": values}

    @action(name="x-cap.mfg92.set_paused.v1",
            description="Start or stop the USB keep-alive pause thread",
            input={"paused": Field("boolean",
                                   description="True to start the pause thread, False to stop it")},
            output={"paused": Field("boolean", description="Pause state after the call")})
    def set_paused(self, paused):
        if paused and not self.native.is_paused():
            self.native.pause()
        elif not paused and self.native.is_paused():
            self.native.cancel_pause()
        return {"paused": bool(self.native.is_paused())}

    # -- safety -----------------------------------------------------------------------------------------------------
    @action(name="x-cap.mfg92.generator_off.v1", safe_state=True,
            description="Disable the waveform generator outputs (the safe state); it takes no input",
            output={"on": Field("boolean", description="False once the generator outputs are disabled")})
    def generator_off(self):
        self.native.set_generator_on(False)
        return {"on": False}

    @estop(native="set_generator_on")
    def stop(self):
        """The native stop: disable the generator outputs.  The runtime latches first, then calls this method."""
        self.native.set_generator_on(False)

    def teardown(self):
        self.native.close()
