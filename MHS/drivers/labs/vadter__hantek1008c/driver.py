"""OpenMHS driver for gh.vadter/hantek1008c: a Hantek 1008C eight-channel USB instrument.

A direct Driver (decorated methods) over the upstream class ``pyhantek1008C:Hantek1008`` at the pinned clone
(commit 178773a7a7161e8ddf68a9230e944bb4c5205884).  The upstream class talks to the device over USB with a
command/echo protocol; the decorated Driver expresses its scalar settings and its waveform-generator controls.

* reads: the active channel ids, the 500-point time axis, the per-channel vertical scale factor, the generator's
  maximum waveform length, the last commanded generator on/speed values and the keep-alive pause flag;
* writes: the generator on/off state and the generator speed (1 to 750000 rpm, the upstream assertion);
* actions: send a generator waveform (at most 62 bytes, each at most 0b1111_1111), start and stop the upstream
  keep-alive pause thread, and switch the generator off (the safe-state action);
* the e-stop switches the generator off and stops the keep-alive pause thread.

The generator on/speed reads report the last value this driver commanded (the upstream class has no getter for
them); after construction the upstream init leaves the generator off at 300000 rpm (pyhantek1008C.py:332-333).

NOT COVERED: the sample arrays of request_samples_burst_mode and request_samples_roll_mode.  The clone returns
per-channel sample lists (or a 500-point time axis plus the samples); no catalogue class carries a trace array, so
this package serves the settings and status scalars and does not transfer samples.  The per-channel
``get_vscale(channel_id)`` and ``get_zero_offset(channel_id)`` getters are not bound because a @read takes no input.

Every Fact and Limit cites a line of the clone at the pinned commit.  This package is model-authored and
unreviewed; it is checked on the fake backend only (README.md of the package).
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write


class Hantek1008c(Driver):
    device_id = "hantek1008c"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "pyhantek1008C:Hantek1008"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeHantek1008"}
    vendor, model = "Hantek", "1008C"
    display_name = "Hantek 1008C eight-channel USB instrument (pyhantek1008C.Hantek1008)"
    tags = ["oscilloscope", "usb", "eight-channel", "waveform-generator", "measurement"]
    facts = [
        Fact("The udev rule matches USB vendor id 0783 and product id 5725", source="upstream_code",
             ref="60-hantek-1008C.rules:1"),
        Fact("The clone implements a variant of only the 8-channel operation mode", source="vendor_doc",
             ref="README.md:5"),
        Fact("The README states that the sample rate is set from 300 ksamples/s to 5 ksamples/s and that the "
             "channels are placed near the middle of the 2048/4096 range", source="vendor_doc",
             ref="README.md:6"),
        Fact("valid channel ids are 0 to 7 for the eight channels", source="upstream_code",
             ref="pyhantek1008C.py:517-522"),
        Fact("get_time returns a 500-point time axis built as np.linspace(0., 499, 500) / samplerate, in seconds "
             "for a samplerate in samples per second", source="upstream_code", ref="pyhantek1008C.py:261"),
        Fact("get_vscales returns the per-channel vertical scale factor; the allowed factors are 0.02, 0.125 and "
             "1.0 (the setter comment calls them Volt/Div)", source="upstream_code", ref="pyhantek1008C.py:277"),
        Fact("The upstream init1 sets the generator speed to 300000 rpm and switches the generator off",
             source="upstream_code", ref="pyhantek1008C.py:332-333"),
        Fact("set_generator_on sends command 0xb7 then 0xbb with 0x01 for on and 0x00 for off; the class has no "
             "getter for the generator state", source="upstream_code", ref="pyhantek1008C.py:632-636"),
        Fact("set_generator_speed asserts 1 <= speed_in_rpm <= 750_000 and sends the computed pulse length with "
             "command 0xb9", source="upstream_code", ref="pyhantek1008C.py:638-652"),
        Fact("get_generator_waveform_max_length returns 1440", source="upstream_code",
             ref="pyhantek1008C.py:628-630"),
        Fact("set_generator_waveform rejects a waveform longer than 62 bytes with 'Currently not supported'",
             source="upstream_code", ref="pyhantek1008C.py:666"),
        Fact("set_generator_waveform accepts every waveform value at most 0b1111_1111", source="upstream_code",
             ref="pyhantek1008C.py:667"),
        Fact("pause starts a keep-alive thread that pings the device every 0.01 s; cancel_pause joins it and "
             "is_paused reports whether it is set", source="upstream_code", ref="pyhantek1008C.py:677-700"),
    ]
    safe_state = "waveform generator outputs off and the keep-alive pause thread stopped"

    def setup(self):
        # The upstream constructor's init1 leaves the generator off at 300000 rpm (pyhantek1008C.py:332-333).
        self._generator_on = False
        self._generator_speed = 300_000

    def teardown(self):
        self.native.close()

    # -- reads ------------------------------------------------------------------------------------------------
    @read("active_channels", type="array", items="integer",
          description="Zero-based ids of the channels the instrument has active (0 to 7)")
    def active_channels(self):
        return [int(channel) for channel in self.native.get_active_channels()]

    @read("time", type="array", items="number", length=500, unit="s",
          description="Time axis of the 500-point acquisition, in seconds")
    def time(self):
        return [float(value) for value in self.native.get_time()]

    @read("vscales", type="array", items="number", length=8,
          description="Vertical scale factor of every channel, one factor per channel")
    def vscales(self):
        return [float(value) for value in self.native.get_vscales()]

    @read("generator_waveform_max_length", type="integer", unit="1",
          description="Maximum waveform length the upstream class reports, in bytes")
    def generator_waveform_max_length(self):
        return int(self.native.get_generator_waveform_max_length())

    @read("generator_on", type="boolean",
          description="Last generator output state commanded through this driver (the upstream has no getter)")
    def generator_on(self):
        return bool(self._generator_on)

    @read("generator_speed", type="integer", unit="/min",
          description="Last generator speed commanded through this driver (the upstream has no getter)")
    def generator_speed(self):
        return int(self._generator_speed)

    @read("paused", type="boolean",
          description="True while the upstream keep-alive pause thread is running")
    def paused(self):
        return bool(self.native.is_paused())

    # -- writes -------------------------------------------------------------------------------------------------
    @write("generator_on", type="boolean",
           description="Switch the generator outputs on or off (command 0xbb)")
    def set_generator_on(self, value):
        self.native.set_generator_on(bool(value))
        self._generator_on = bool(value)

    @write("generator_speed", type="integer", unit="/min",
           description="Generator speed in revolutions per minute",
           limit=Limit(min=1, max=750_000, source="upstream_code", ref="pyhantek1008C.py:641"))
    def set_generator_speed(self, value):
        self.native.set_generator_speed(int(value))
        self._generator_speed = int(value)

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.vadter.set_generator_waveform.v1",
            description="Send a generator waveform: one byte per part of the wave, each bit an output",
            input={
                "waveform": Field("array", unit="1",
                                  items=Field("integer", unit="1",
                                              limit=Limit(max=255, source="upstream_code",
                                                          ref="pyhantek1008C.py:667")),
                                  max_items=62,
                                  description="Waveform bytes (at most 62, each at most 0b1111_1111)"),
            },
            output={
                "length": Field("integer", unit="1", description="Number of waveform bytes sent"),
                "checksum": Field("integer", unit="1",
                                  description="Sum of the waveform byte values sent"),
            })
    def set_generator_waveform(self, waveform):
        values = [int(value) for value in waveform]
        self.native.set_generator_waveform(values)
        return {"length": len(values), "checksum": sum(values)}

    @action(name="x-cap.vadter.pause.v1",
            description="Start the upstream keep-alive pause thread that pings the instrument every 0.01 s",
            output={"paused": Field("boolean", description="True once the pause thread is running")})
    def pause(self):
        if not self.native.is_paused():
            self.native.pause()
        return {"paused": bool(self.native.is_paused())}

    @action(name="x-cap.vadter.resume.v1",
            description="Stop the upstream keep-alive pause thread",
            output={"paused": Field("boolean", description="False once the pause thread has stopped")})
    def resume(self):
        if self.native.is_paused():
            self.native.cancel_pause()
        return {"paused": bool(self.native.is_paused())}

    @action(name="x-cap.vadter.generator_off.v1", safe_state=True,
            description="Switch the generator off and stop the keep-alive pause thread (the safe state)",
            output={"generator_on": Field("boolean", description="False once the generator is off")})
    def generator_off(self):
        self._switch_generator_off()
        return {"generator_on": bool(self._generator_on)}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="set_generator_on")
    def stop(self):
        """The native stop: the runtime latches first, then switches the generator off."""
        self._switch_generator_off()

    def _switch_generator_off(self):
        if self.native.is_paused():
            self.native.cancel_pause()
        self.native.set_generator_on(False)
        self._generator_on = False
