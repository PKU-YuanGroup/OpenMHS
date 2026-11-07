"""OpenMHS driver for gh.manasp21/oscilloscope_mcp: the Ethernet oscilloscope backend of the clone.

A direct Driver (decorated methods) over ``oscilloscope_mcp.hardware.ethernet_backend:EthernetOscilloscope``.
The upstream class is a stub: its constructor logs that Ethernet hardware is not implemented and every method
delegates to a ``SimulatedOscilloscope`` (ethernet_backend.py:18-55).  The clone therefore exposes the simulated
instrument's settings and acquisition through this class, and every method here is ``async def`` because the
upstream methods are coroutines.

* reads: the initialized and acquisition-active flags, the number of configured channels, the timebase, the
  first configured channel's voltage range, coupling and impedance, and the trigger settings;
* writes: sample rate, record length, voltage range, coupling and impedance; each setter reads the current
  status and changes one setting through the upstream ``set_timebase`` or ``configure_channels``;
* actions: configure one channel, set up the trigger, acquire a channel and report the scalar measurements of
  the captured trace, and stop the acquisition (the safe state);
* the native stop is ``stop_acquisition``; it is both the e-stop and the safe-state action.

NOT COVERED: the waveform array.  The clone returns a ``record_length``-long time axis and one voltage array
per channel (simulation.py:212-260); no catalogue class carries a trace array, so this package serves the
settings, the status and a scalar summary of one acquired channel (sample count, sample rate, time window,
minimum, maximum and RMS voltage) and does not transfer the samples.  See RESULT.json notes.

Every Fact and Limit cites a line of the clone at the pinned commit (49b9c4a7b06b0a98688f5f9cd689ec21c25d3eeb).
This package is model-authored and unreviewed, and the upstream Ethernet backend is only a simulation stub, so
the hardware backend has never been tried on an instrument.
"""

import math

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

ETHERNET = "src/oscilloscope_mcp/hardware/ethernet_backend.py"
BASE = "src/oscilloscope_mcp/hardware/base.py"
SIMULATION = "src/oscilloscope_mcp/hardware/simulation.py"


def _channel_limit() -> Limit:
    return Limit(allowed=[0, 1, 2, 3], source="upstream_code", ref=f"{SIMULATION}:90")


def _voltage_range_limit() -> Limit:
    return Limit(min=0.001, max=100.0, source="upstream_code", ref=f"{BASE}:183-184")


def _coupling_limit() -> Limit:
    return Limit(allowed=["DC", "AC", "GND"], source="upstream_code", ref=f"{BASE}:185")


def _impedance_limit() -> Limit:
    return Limit(allowed=["50", "1M"], source="upstream_code", ref=f"{BASE}:186")


class OscilloscopeMcp(Driver):
    device_id = "oscilloscope"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "oscilloscope_mcp.hardware.ethernet_backend:EthernetOscilloscope"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeEthernetOscilloscope"}
    vendor = "manasp21"
    model = "Ethernet oscilloscope backend (simulation stub)"
    display_name = "Oscilloscope MCP Ethernet backend (oscilloscope_mcp.EthernetOscilloscope)"
    tags = ["oscilloscope", "instrument", "acquisition", "simulation", "asyncio"]
    facts = [
        Fact("EthernetOscilloscope is a stub: its constructor logs that Ethernet is not implemented and every "
             "method delegates to a SimulatedOscilloscope", source="upstream_code", ref=f"{ETHERNET}:18-55"),
        Fact("The simulated oscilloscope initializes four channels with a default timebase and trigger",
             source="upstream_code", ref=f"{SIMULATION}:39-70"),
        Fact("configure_channels raises ValueError for a channel outside range(4)", source="upstream_code",
             ref=f"{SIMULATION}:88-91"),
        Fact("set_timebase clamps the sample rate to max_sample_rate and the record length to max_memory_depth",
             source="upstream_code", ref=f"{SIMULATION}:121-129"),
        Fact("The capability record states max_sample_rate 1e9, max_bandwidth 500e6, max_channels 4 and "
             "max_memory_depth 1e9", source="upstream_code", ref=f"{BASE}:178-182"),
        Fact("The capability record states a voltage range of 0.001 to 100.0 and lists DC, AC and GND coupling "
             "and 50 and 1M impedance", source="upstream_code", ref=f"{BASE}:183-186"),
        Fact("The supported trigger types are edge, pulse, pattern and protocol", source="upstream_code",
             ref=f"{BASE}:187"),
        Fact("get_status reports initialized, acquisition_active, channels, timebase and trigger_config",
             source="upstream_code", ref=f"{SIMULATION}:269-277"),
        Fact("setup_trigger stores the source, type, level, edge and holdoff in trigger_config",
             source="upstream_code", ref=f"{SIMULATION}:152-158"),
        Fact("acquire_waveform builds waveform_data with a shared time axis and per-channel voltage arrays",
             source="upstream_code", ref=f"{SIMULATION}:212-260"),
        Fact("stop_acquisition sets acquisition_active to False", source="upstream_code",
             ref=f"{SIMULATION}:264-267"),
        Fact("cleanup stops the acquisition before marking the oscilloscope uninitialized", source="upstream_code",
             ref=f"{SIMULATION}:279-283"),
        Fact("The README describes multi-channel acquisition with 4 channels and configurable sample rates",
             source="vendor_doc", ref="README.md:8"),
    ]
    safe_state = "acquisition stopped (the native stop_acquisition path)"

    async def setup(self):
        config = dict(self.options.get("config") or {})
        await self.native.initialize(config)

    async def teardown(self):
        await self.native.cleanup()

    # -- reads ------------------------------------------------------------------------------------------------
    @read("initialized", type="boolean", description="True when the backend reports that it is initialized")
    async def initialized(self):
        return bool((await self.native.get_status())["initialized"])

    @read("acquisition_active", type="boolean",
          description="True while the backend reports an acquisition in progress")
    async def acquisition_active(self):
        return bool((await self.native.get_status())["acquisition_active"])

    @read("channel_count", type="integer", unit="1",
          description="Number of channels the backend reports in its channel configuration")
    async def channel_count(self):
        return len((await self.native.get_status())["channels"])

    @read("sample_rate_hz", unit="Hz", description="Configured sample rate of the current timebase")
    async def sample_rate_hz(self):
        return float((await self.native.get_status())["timebase"]["sample_rate"])

    @read("record_length", type="integer", unit="1",
          description="Configured record length in samples of the current timebase")
    async def record_length(self):
        return int((await self.native.get_status())["timebase"]["record_length"])

    @read("voltage_range_v", unit="V",
          description="Voltage range of the first configured channel")
    async def voltage_range_v(self):
        channel = self._first_channel(await self.native.get_status())
        return float(channel["voltage_range"])

    @read("coupling", type="string", description="Coupling of the first configured channel")
    async def coupling(self):
        channel = self._first_channel(await self.native.get_status())
        return str(channel["coupling"])

    @read("impedance", type="string", description="Input impedance of the first configured channel")
    async def impedance(self):
        channel = self._first_channel(await self.native.get_status())
        return str(channel["impedance"])

    @read("trigger_source", type="string", description="Trigger source as stored by setup_trigger")
    async def trigger_source(self):
        return str((await self.native.get_status())["trigger_config"]["source"])

    @read("trigger_type", type="string", description="Trigger type as stored by setup_trigger")
    async def trigger_type(self):
        return str((await self.native.get_status())["trigger_config"]["type"])

    @read("trigger_level_v", unit="V", description="Trigger level as stored by setup_trigger")
    async def trigger_level_v(self):
        return float((await self.native.get_status())["trigger_config"]["level"])

    @read("trigger_edge", type="string", description="Trigger edge as stored by setup_trigger")
    async def trigger_edge(self):
        return str((await self.native.get_status())["trigger_config"]["edge"])

    @read("trigger_holdoff_s", unit="s", description="Trigger holdoff as stored by setup_trigger")
    async def trigger_holdoff_s(self):
        return float((await self.native.get_status())["trigger_config"]["holdoff"])

    # -- writes -----------------------------------------------------------------------------------------------
    @write("sample_rate_hz", unit="Hz",
           description="Sample rate of the timebase, keeping the current record length",
           limit=Limit(max=1e9, source="upstream_code", ref=f"{BASE}:179"))
    async def set_sample_rate_hz(self, value):
        status = await self.native.get_status()
        record_length = int(status["timebase"]["record_length"])
        await self.native.set_timebase(value, record_length)
        return float((await self.native.get_status())["timebase"]["sample_rate"])

    @write("record_length", type="integer", unit="1",
           description="Record length in samples of the timebase, keeping the current sample rate",
           limit=Limit(max=1e9, source="upstream_code", ref=f"{BASE}:182"))
    async def set_record_length(self, value):
        status = await self.native.get_status()
        sample_rate = float(status["timebase"]["sample_rate"])
        await self.native.set_timebase(sample_rate, value)
        return int((await self.native.get_status())["timebase"]["record_length"])

    @write("voltage_range_v", unit="V",
           description="Voltage range applied to every configured channel",
           limit=_voltage_range_limit())
    async def set_voltage_range_v(self, value):
        channels, _old_range, coupling, impedance = self._channel_configuration(await self.native.get_status())
        await self.native.configure_channels(channels, value, coupling, impedance)
        return float(self._first_channel(await self.native.get_status())["voltage_range"])

    @write("coupling", type="string", enum=["DC", "AC", "GND"],
           description="Coupling applied to every configured channel",
           limit=_coupling_limit())
    async def set_coupling(self, value):
        channels, voltage_range, _old_coupling, impedance = self._channel_configuration(
            await self.native.get_status())
        await self.native.configure_channels(channels, voltage_range, value, impedance)
        return str(self._first_channel(await self.native.get_status())["coupling"])

    @write("impedance", type="string", enum=["50", "1M"],
           description="Input impedance applied to every configured channel",
           limit=_impedance_limit())
    async def set_impedance(self, value):
        channels, voltage_range, coupling, _old_impedance = self._channel_configuration(
            await self.native.get_status())
        await self.native.configure_channels(channels, voltage_range, coupling, value)
        return str(self._first_channel(await self.native.get_status())["impedance"])

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.manasp21.configure_channel.v1",
            description="Configure one channel's voltage range, coupling and impedance",
            input={
                "channel": Field("integer", unit="1", description="Channel number the backend accepts",
                                 limit=_channel_limit()),
                "voltage_range": Field("number", unit="V", description="Voltage range of the channel",
                                       limit=_voltage_range_limit()),
                "coupling": Field("string", description="Coupling of the channel",
                                  limit=_coupling_limit(), enum=["DC", "AC", "GND"]),
                "impedance": Field("string", description="Input impedance of the channel",
                                   limit=_impedance_limit(), enum=["50", "1M"]),
            },
            output={
                "channel": Field("integer", unit="1", description="Configured channel number"),
                "voltage_range": Field("number", unit="V", description="Voltage range reported after the write"),
                "coupling": Field("string", description="Coupling reported after the write"),
                "impedance": Field("string", description="Impedance reported after the write"),
            })
    async def configure_channel(self, channel, voltage_range, coupling, impedance):
        await self.native.configure_channels([channel], voltage_range, coupling, impedance)
        status = await self.native.get_status()
        configured = status["channels"][channel]
        return {
            "channel": channel,
            "voltage_range": float(configured["voltage_range"]),
            "coupling": str(configured["coupling"]),
            "impedance": str(configured["impedance"]),
        }

    @action(name="x-cap.manasp21.setup_trigger.v1",
            description="Configure the trigger source, type, level, edge and holdoff",
            input={
                "source": Field("string", description="Trigger source name, for example channel0"),
                "trigger_type": Field("string", description="Trigger type",
                                      limit=Limit(allowed=["edge", "pulse", "pattern", "protocol"],
                                                  source="upstream_code", ref=f"{BASE}:187"),
                                      enum=["edge", "pulse", "pattern", "protocol"]),
                "level": Field("number", unit="V", description="Trigger level",
                               limit=Limit.operator_required(
                                   "no text of the clone states a trigger level bound; the site supplies the "
                                   "vertical trigger range of its instrument")),
                "edge": Field("string", description="Trigger edge, for example rising"),
                "holdoff": Field("number", unit="s", description="Trigger holdoff",
                                 limit=Limit.operator_required(
                                     "no text of the clone states a trigger holdoff bound; the site supplies the "
                                     "holdoff range of its instrument")),
            },
            output={
                "source": Field("string", description="Trigger source stored by the backend"),
                "trigger_type": Field("string", description="Trigger type stored by the backend"),
                "level": Field("number", unit="V", description="Trigger level stored by the backend"),
                "edge": Field("string", description="Trigger edge stored by the backend"),
                "holdoff": Field("number", unit="s", description="Trigger holdoff stored by the backend"),
            })
    async def setup_trigger(self, source, trigger_type, level, edge, holdoff):
        result = await self.native.setup_trigger(source, trigger_type, level, edge, holdoff)
        return {
            "source": str(result["source"]),
            "trigger_type": str(result["type"]),
            "level": float(result["level"]),
            "edge": str(result["edge"]),
            "holdoff": float(result["holdoff"]),
        }

    @action(name="x-cap.manasp21.acquire_waveform.v1",
            description="Acquire one channel and report the scalar measurements of the captured trace",
            input={
                "channel": Field("integer", unit="1", description="Channel number to acquire",
                                 limit=_channel_limit()),
                "timeout": Field("number", unit="s", description="Time the backend may spend acquiring",
                                 limit=Limit.operator_required(
                                     "the clone's acquire_waveform timeout is an argument, not a device bound; the "
                                     "site supplies the wait bound of its deployment")),
            },
            output={
                "channel": Field("integer", unit="1", description="Acquired channel number"),
                "sample_count": Field("integer", unit="1", description="Number of samples in the trace"),
                "sample_rate_hz": Field("number", unit="Hz", description="Sample rate reported with the trace"),
                "time_start_s": Field("number", unit="s", description="Time of the first sample"),
                "time_end_s": Field("number", unit="s", description="Time of the last sample"),
                "minimum_voltage_v": Field("number", unit="V", description="Minimum sample voltage"),
                "maximum_voltage_v": Field("number", unit="V", description="Maximum sample voltage"),
                "rms_voltage_v": Field("number", unit="V", description="Root mean square sample voltage"),
            })
    async def acquire_waveform(self, channel, timeout):
        result = await self.native.acquire_waveform([channel], timeout)
        waveform = result["waveform_data"]
        series = waveform["channels"].get(channel)
        if series is None:
            series = waveform["channels"].get(str(channel))
        if not series or not series.get("voltage"):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"channel {channel} returned no samples; configure and enable it first")
        voltages = [float(item) for item in series["voltage"]]
        times = [float(item) for item in waveform["time"]]
        if not times:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "the acquisition returned no time axis")
        rms = math.sqrt(sum(item * item for item in voltages) / len(voltages))
        return {
            "channel": channel,
            "sample_count": len(voltages),
            "sample_rate_hz": float(result["metadata"]["sample_rate"]),
            "time_start_s": times[0],
            "time_end_s": times[-1],
            "minimum_voltage_v": min(voltages),
            "maximum_voltage_v": max(voltages),
            "rms_voltage_v": rms,
        }

    @action(name="x-cap.manasp21.stop_acquisition.v1", safe_state=True,
            description="Stop the acquisition (the native safe state); it takes no input",
            output={
                "acquisition_active": Field("boolean",
                                            description="False once the backend reports no acquisition"),
            })
    async def stop_acquisition(self):
        await self.native.stop_acquisition()
        return {"acquisition_active": bool((await self.native.get_status())["acquisition_active"])}

    # -- safety -------------------------------------------------------------------------------------------------------
    @estop(native="stop_acquisition")
    async def stop(self):
        """The native stop: the runtime latches first, then calls stop_acquisition."""
        await self.native.stop_acquisition()

    # -- helpers ------------------------------------------------------------------------------------------------------
    @staticmethod
    def _first_channel(status):
        channels = status["channels"]
        if not channels:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the backend reports no channel configuration")
        return channels[sorted(channels)[0]]

    @staticmethod
    def _channel_configuration(status):
        channels = sorted(status["channels"])
        if not channels:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the backend reports no channel configuration")
        first = status["channels"][channels[0]]
        return channels, float(first["voltage_range"]), str(first["coupling"]), str(first["impedance"])
