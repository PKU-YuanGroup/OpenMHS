"""OpenMHS driver for gh.vadter/hantek6022be: a Hantek 6022BE two-channel USB oscilloscope.

A direct Driver (decorated methods) over the upstream device class pyhantek6022BE:Hantek.  The upstream class is
synchronous, owns the USB device in its constructor (pyhantek6022BE.py:10-108), acquires on GetData and configures
the instrument with set_samplerate / set_chvdiv.

* reads: the sample rate per channel, the vertical division of each channel, and one acquisition summary (sample
  count, window duration, minimum, maximum and RMS voltage of each channel) computed from the upstream GetData;
* writes: the sample rate and the vertical division of each channel, limited to the values the upstream accepts;
* the upstream close() resets the USB device and releases it; it is the e-stop and the teardown.

NOT COVERED: the waveform array.  GetData returns one voltage array per channel of buf_len = data_len // 2
samples (131072 at the default 16 MS/s; pyhantek6022BE.py:91-97, 162-174).  No catalogue class carries an
oscilloscope trace, so this package does not transfer the samples: it reports the scalar measurements of the
acquisition and the settings.  The fake returns a smaller trace and RESULT.json names the real size.

Every Fact cites a line of the clone at the pinned commit (548ff23984044ed1b8265358cfd20312e37cce8b).  This
package is model-authored and unreviewed: it is checked on the fake backend only, and the hardware backend was
never started.
"""

import math

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, estop, read, write

# The samplerate table of the upstream constructor: these are the keys of dictN_SR, the only rates
# set_samplerate accepts (pyhantek6022BE.py:83-86, 176-178).
SAMPLE_RATES = [100_000, 200_000, 500_000, 1_000_000, 4_000_000, 8_000_000, 16_000_000, 48_000_000]
# The vertical divisions of the upstream constructor: the keys of dictN_VDiv (pyhantek6022BE.py:77-78, 208).
VDIV_VALUES = [1.0, 0.5, 0.2, 0.1]

SAMPLE_RATE_LIMIT = Limit(allowed=SAMPLE_RATES, source="upstream_code", ref="pyhantek6022BE.py:83-85")
VDIV_LIMIT = Limit(allowed=VDIV_VALUES, source="upstream_code", ref="pyhantek6022BE.py:77-78")


def _summary(samples):
    values = [float(item) for item in samples]
    if not values:
        raise DriverFailed("MHS.DEVICE.FAULTED", "GetData returned no samples for a channel")
    return {
        "minimum_v": min(values),
        "maximum_v": max(values),
        "rms_v": math.sqrt(sum(item * item for item in values) / len(values)),
    }


class Hantek6022be(Driver):
    device_id = "hantek6022be"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "pyhantek6022BE:Hantek"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeHantek6022be"}
    vendor, model = "Hantek", "6022BE"
    display_name = "Hantek 6022BE USB oscilloscope (pyhantek6022BE.Hantek)"
    resource_title = "Hantek 6022BE two-channel oscilloscope"
    tags = ["oscilloscope", "usb", "instrument", "acquisition", "voltage"]
    facts = [
        Fact("Hantek is the USB oscilloscope class: it loads firmware through USB vendor 0x04b4 product 0x6022 and "
             "then talks to vendor 0x04b5 product 0x6022", source="upstream_code", ref="pyhantek6022BE.py:8-39"),
        Fact("The samplerate table maps 48, 16, 8, 4 and 1 MS/s and 500, 200 and 100 kS/s",
             source="upstream_code", ref="pyhantek6022BE.py:83-85"),
        Fact("set_samplerate accepts a rate only when it is a key of dictN_SR; otherwise it prints the available "
             "rates and leaves the device unchanged", source="upstream_code", ref="pyhantek6022BE.py:176-202"),
        Fact("The vertical-division table is {1: 1, 2: 0.5, 5: 0.2, 10: 0.1}; dictN_VDiv reverses it",
             source="upstream_code", ref="pyhantek6022BE.py:77-78"),
        Fact("set_chvdiv accepts a channel value only when it is a key of dictN_VDiv",
             source="upstream_code", ref="pyhantek6022BE.py:204-222"),
        Fact("The default samplerate is 16 MS/s per channel and both channels start at 1 V/div",
             source="upstream_code", ref="pyhantek6022BE.py:80-88"),
        Fact("GetData reads dictDatLen_N[samplerate] bytes and returns two voltage arrays scaled by "
             "(raw - 128) / 255 * 10 * ChVDiv", source="upstream_code", ref="pyhantek6022BE.py:162-174"),
        Fact("buf_len is data_len // 2 samples per channel and dictDatLen_N maps each samplerate to its data length",
             source="upstream_code", ref="pyhantek6022BE.py:91-97"),
        Fact("get_rate returns the samplerate and get_time returns linspace(0, buf_len - 1, buf_len) / samplerate",
             source="upstream_code", ref="pyhantek6022BE.py:227-233"),
        Fact("get_rates returns 50 kHz, 250 kHz, 500 kHz, 2 MHz, 4 MHz, 8 MHz and 24 MHz",
             source="upstream_code", ref="pyhantek6022BE.py:235-240"),
        Fact("close() resets the USB device and disposes its resources", source="upstream_code",
             ref="pyhantek6022BE.py:494-506"),
    ]
    safe_state = "acquisition stopped and the USB device released by the native close() (the scope has no output)"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("sample_rate", type="integer", unit="Hz",
          description="Sample rate per channel in samples per second")
    def sample_rate(self):
        return int(self.native.get_rate())

    @read("ch1_vdiv", unit="V", description="Channel 1 vertical division in volts per division")
    def ch1_vdiv(self):
        return float(self.native.ChVDiv[0])

    @read("ch2_vdiv", unit="V", description="Channel 2 vertical division in volts per division")
    def ch2_vdiv(self):
        return float(self.native.ChVDiv[1])

    @read("acquisition", type="object", description="Scalar measurements of the most recent acquisition of both channels",
          properties={
              "sample_count": Field("integer", unit="1", description="Samples the acquisition returned per channel"),
              "duration_s": Field("number", unit="s", description="Acquired window duration"),
              "channel1_min_v": Field("number", unit="V", description="Minimum voltage of channel 1"),
              "channel1_max_v": Field("number", unit="V", description="Maximum voltage of channel 1"),
              "channel1_rms_v": Field("number", unit="V", description="RMS voltage of channel 1"),
              "channel2_min_v": Field("number", unit="V", description="Minimum voltage of channel 2"),
              "channel2_max_v": Field("number", unit="V", description="Maximum voltage of channel 2"),
              "channel2_rms_v": Field("number", unit="V", description="RMS voltage of channel 2"),
          })
    def acquisition(self):
        data = self.native.GetData()
        ch1 = [float(item) for item in data[0]]
        ch2 = [float(item) for item in data[1]]
        if not ch1 or not ch2:
            raise DriverFailed("MHS.DEVICE.FAULTED", "GetData returned no samples")
        rate = float(self.native.get_rate())
        if rate <= 0:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the device reports sample rate {rate!r}")
        first, second = _summary(ch1), _summary(ch2)
        return {
            "sample_count": len(ch1),
            "duration_s": len(ch1) / rate,
            "channel1_min_v": first["minimum_v"],
            "channel1_max_v": first["maximum_v"],
            "channel1_rms_v": first["rms_v"],
            "channel2_min_v": second["minimum_v"],
            "channel2_max_v": second["maximum_v"],
            "channel2_rms_v": second["rms_v"],
        }

    # -- writes -----------------------------------------------------------------------------------------------
    @write("sample_rate", type="integer", unit="Hz",
           description="Sample rate per channel in samples per second; one of the rates of the samplerate table",
           limit=SAMPLE_RATE_LIMIT)
    def set_sample_rate(self, value):
        self.native.set_samplerate(value)
        return int(self.native.get_rate())

    @write("ch1_vdiv", unit="V", description="Channel 1 vertical division in volts per division",
           limit=VDIV_LIMIT)
    def set_ch1_vdiv(self, value):
        self.native.set_chvdiv([value, float(self.native.ChVDiv[1])])
        return float(self.native.ChVDiv[0])

    @write("ch2_vdiv", unit="V", description="Channel 2 vertical division in volts per division",
           limit=VDIV_LIMIT)
    def set_ch2_vdiv(self, value):
        self.native.set_chvdiv([float(self.native.ChVDiv[0]), value])
        return float(self.native.ChVDiv[1])

    # -- safety -------------------------------------------------------------------------------------------------
    @estop(native="close")
    def stop(self):
        """The native stop: the runtime latches first, then close() resets and releases the USB device."""
        self.native.close()

    def teardown(self):
        self.native.close()
