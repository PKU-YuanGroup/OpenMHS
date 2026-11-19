"""OpenMHS driver for gh.cnpem/sophys-common: the CompactERAS Soft IOC electrometer.

A direct Driver (decorated methods) over the upstream ophyd device class
``sophys.common.devices.compacteras:CompactERAS``.  The class defines four ``Channel`` components
(``CH1`` to ``CH4``), and each Channel declares a read-only ``voltage`` ``EpicsSignalRO`` on the
``Voltage`` suffix and a read-only ``current`` ``EpicsSignalRO`` on the ``Current`` suffix
(src/sophys/common/devices/compacteras.py:16-21, 66-69).  The driver serves those measurements:

* read state: the Soft IOC version, the supported-device list, and the voltage and current of each
  of the four channels;
* ``cap.measure.voltage.v1`` and ``cap.measure.current.v1``: one channel selected by the optional
  ``channel`` input (``CH1`` to ``CH4``); the class defaults to channel 1 when it is omitted;
* no write, no configuration and no acquisition command: the clone exposes writable Channel and
  Scale components, but no text file states their ranges or safe values, so this package binds only
  the read-only measurement path;
* no native stop: the CompactERAS class has no stop, abort or acquisition method.  This is an R0
  read-only integration (MHS/spec/04-safety.md: data only, no physical effect); the endpoint's
  software e-stop latch changes nothing on the device, and the driver does not claim otherwise.

DEVIATION FROM THE CARD: the card names helper ``PythonObjectDriver``.  A PythonObjectDriver command
table binds one fixed native path per capability, while one measurement has to select one of four
Channel components from an input.  A decorated direct Driver expresses that selection, the optional
channel default and the measurement result; the card's direct-driver decision is unchanged.

Every Fact cites a line of the clone at the pinned commit
8bcf1e54511791b0f20ce1dc4d15a8cd6cc47eff.  This package is model-authored and unreviewed: it has
been checked on the fake backend only, the hardware backend was never imported or opened, and no
hardware run is claimed.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, action, read

#: The channel components of CompactERAS (src/sophys/common/devices/compacteras.py:66-69).
CHANNELS = ("CH1", "CH2", "CH3", "CH4")


class CompactEras(Driver):
    device_id = "compacteras"
    device_kind = "instrument.dmm"
    mode = "hardware"
    risk = "R0"
    native = "sophys.common.devices.compacteras:CompactERAS"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeCompactERAS"}
    vendor, model = "LNLS/SIRIUS", "CompactERAS Soft IOC"
    display_name = "CompactERAS four-channel electrometer (read only)"
    tags = ["ophyd", "epics", "electrometer", "current", "voltage", "compacteras", "read-only"]
    safe_state = (
        "unchanged: the package only reads the four CompactERAS channels and never writes a "
        "setpoint, a Channel/Scale setting or an acquisition command; an e-stop engages the "
        "endpoint's software latch and stops nothing physical"
    )
    facts = [
        Fact("CompactERAS is an ophyd Device documented as a CompactERAS Soft IOC; the class "
             "docstring names the channels through the CH{0..4} attributes and the class declares "
             "the CH1 to CH4 Channel components",
             source="upstream_code", ref="src/sophys/common/devices/compacteras.py:49-69"),
        Fact("Channel.voltage is an EpicsSignalRO Component on the Voltage suffix and "
             "Channel.current is an EpicsSignalRO Component on the Current suffix",
             source="upstream_code", ref="src/sophys/common/devices/compacteras.py:16-21"),
        Fact("CompactERAS.CH1 to CH4 are Channel Components with the CH1: to CH4: suffixes",
             source="upstream_code", ref="src/sophys/common/devices/compacteras.py:66-69"),
        Fact("version reads the Version PV and supported_devices reads the DevicesUsed PV, both as "
             "string signals",
             source="upstream_code", ref="src/sophys/common/devices/compacteras.py:56-61"),
        Fact("sampling_rate reads the SamplingRate PV and acquisition_bandwidth reads the "
             "AcquisitionBandwidth PV",
             source="upstream_code", ref="src/sophys/common/devices/compacteras.py:58-59"),
        Fact("verifyVersion reads version.get() and returns False when the read raises "
             "ConnectionTimeoutError",
             source="upstream_code", ref="src/sophys/common/devices/compacteras.py:102-115"),
        Fact("getSupportedDevices splits the supported_devices reply on single spaces",
             source="upstream_code", ref="src/sophys/common/devices/compacteras.py:144-146"),
    ]

    # -- read-only state ---------------------------------------------------------------------------------------
    @read("version", type="string", description="Soft IOC version string read from the Version PV")
    def version(self):
        return str(self.native.version.get())

    @read("supported_devices", type="string",
          description="Space-separated list of devices reported by the DevicesUsed PV")
    def supported_devices(self):
        return str(self.native.supported_devices.get())

    @read("voltage_ch1", unit="V", description="Voltage of channel CH1")
    def voltage_ch1(self):
        return float(self.native.CH1.voltage.get())

    @read("voltage_ch2", unit="V", description="Voltage of channel CH2")
    def voltage_ch2(self):
        return float(self.native.CH2.voltage.get())

    @read("voltage_ch3", unit="V", description="Voltage of channel CH3")
    def voltage_ch3(self):
        return float(self.native.CH3.voltage.get())

    @read("voltage_ch4", unit="V", description="Voltage of channel CH4")
    def voltage_ch4(self):
        return float(self.native.CH4.voltage.get())

    @read("current_ch1", unit="A", description="Current of channel CH1")
    def current_ch1(self):
        return float(self.native.CH1.current.get())

    @read("current_ch2", unit="A", description="Current of channel CH2")
    def current_ch2(self):
        return float(self.native.CH2.current.get())

    @read("current_ch3", unit="A", description="Current of channel CH3")
    def current_ch3(self):
        return float(self.native.CH3.current.get())

    @read("current_ch4", unit="A", description="Current of channel CH4")
    def current_ch4(self):
        return float(self.native.CH4.current.get())

    # -- the measurement capabilities --------------------------------------------------------------------------
    @action(cap="cap.measure.voltage.v1",
            description="Measure the voltage of one CompactERAS channel",
            input={"channel": Field("string", description="Channel name, one of CH1 to CH4")})
    def measure_voltage(self, channel="CH1"):
        return {"voltage": self._measure(channel, "voltage")}

    @action(cap="cap.measure.current.v1",
            description="Measure the current of one CompactERAS channel",
            input={"channel": Field("string", description="Channel name, one of CH1 to CH4")})
    def measure_current(self, channel="CH1"):
        return {"current": self._measure(channel, "current")}

    def _measure(self, channel, field):
        """Read ``channel.field`` from the native Device; the channel names are the class components."""
        if channel not in CHANNELS:
            raise DriverFailed(
                "MHS.DEVICE.PRECONDITION_UNMET",
                f"channel {channel!r} is not one of {list(CHANNELS)}",
            )
        signal = getattr(getattr(self.native, channel), field)
        return float(signal.get())
