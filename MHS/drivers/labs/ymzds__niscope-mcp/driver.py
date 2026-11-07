"""OpenMHS driver for gh.ymzds/niscope-mcp: an NI PXIe oscilloscope through the upstream DirectBackend.

A direct Driver over ``niscope_mcp.backends.direct:DirectBackend`` (direct.py:20-21), the class that opens
``niscope.Session`` objects and fetches waveforms.  The upstream server is a front end over the same class
(__main__.py:1280).  The class reports one resource per scope and names its channels by index
(direct.py:273-275).

* reads: the instrument model, and the per-channel vertical settings, horizontal sample rate and record length,
  and trigger source, level and slope that ``get_current_config`` reports (direct.py:258-283);
* writes: the settings ``configure_channel``, ``configure_horizontal`` and ``configure_trigger`` accept
  (direct.py:88-127).  The clone states common values for the vertical range, the input impedance and the minimum
  sample rate in its help text (__main__.py:1208-1214); those are the sourced limits below.  No text states the
  vertical offset, trigger level or record-length range, so those writes are ``Limit.operator_required`` and are
  refused ``MHS.SAFETY.LIMITS_UNSET`` until the site overlay supplies a bound (site-limits.example.json shows
  one example; it is not a statement about any unit);
* actions: ``x-cap.ymzds.measure_waveform.v1`` returns the scalar measurements of ``measure_waveform``
  (direct.py:166-191) and ``x-cap.ymzds.auto_setup.v1`` runs the native ``auto_setup`` (direct.py:129-130).

The waveform sample arrays are not exposed by this package: the 0.9 catalogue has no oscilloscope waveform class,
and the gate's fake returns a small placeholder array.  The scalar measurements and every setting are covered.

``get_current_config`` does not report ``bandwidth_filter`` or the hidden horizontal fields (num_records,
ref_position, enforce_realtime), so those are taken from backend options and keep the upstream dataclass values
when the operator does not set them (base.py:24-29, base.py:54-61).  The same is true for trigger coupling and
holdoff (base.py:33-41).

This package is model-authored and unreviewed.  It is R1: the loader refuses the hardware backend of an
unreviewed model-written package only at R2 and R3, so no such protection is claimed here.  The acceptance gate
uses the fake backend only; no hardware was attached or driven.
"""

from dataclasses import dataclass

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write


@dataclass
class _ChannelConfig:
    """The fields ``DirectBackend.configure_channel`` reads from the upstream ChannelConfig."""

    enabled: bool
    vertical_range: float
    vertical_offset: float
    vertical_coupling: str
    probe_attenuation: float
    input_impedance: float
    bandwidth_filter: str


@dataclass
class _HorizontalConfig:
    """The fields ``DirectBackend.configure_horizontal`` reads from the upstream HorizontalConfig."""

    min_sample_rate: float
    min_num_pts: int
    num_records: int
    ref_position: float
    enforce_realtime: bool
    acquisition_type: str


@dataclass
class _TriggerConfig:
    """The fields ``DirectBackend.configure_trigger`` reads for an edge trigger."""

    source: str
    level: float
    slope: str
    coupling: str
    holdoff: float
    type: str


def _enum_name(value) -> str:
    """The member name of an enum-like value (``VerticalCoupling.DC`` or ``DC`` -> ``DC``)."""
    return str(value).rsplit(".", 1)[-1].strip().upper()


class NiscopeMcp(Driver):
    device_id = "niscope"
    device_kind = "instrument"
    resource_id = "main"
    mode = "hardware"
    risk = "R1"
    native = "niscope_mcp.backends.direct:DirectBackend"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeNiscopeMcp"}
    vendor, model = "National Instruments", "PXIe-5160 / 5164 / 5110"
    display_name = "NI PXIe oscilloscope (niscope DirectBackend)"
    tags = ["oscilloscope", "ni-scope", "pxie", "waveform", "instrument"]
    facts = [
        Fact("The package supports the NI PXIe-5160, 5164 and 5110 and states that it requires Windows and NI "
             "hardware", source="vendor_doc", ref="README.md:5"),
        Fact("Adaptive sampling raises the sample rate towards 30 times the signal frequency and is capped at "
             "1.25 GS/s", source="vendor_doc", ref="README.md:9"),
        Fact("The hardware backend imports the niscope package", source="upstream_code",
             ref="niscope_mcp/backends/direct.py:9"),
        Fact("DirectBackend drives real NI oscilloscopes through the niscope API", source="upstream_code",
             ref="niscope_mcp/backends/direct.py:20-21"),
        Fact("scan_devices opens niscope.Session(name, reset_device=False) for each candidate PXI slot and reads "
             "the model, channel count and maximum rates", source="upstream_code",
             ref="niscope_mcp/backends/direct.py:31-55"),
        Fact("open_device opens niscope.Session(resource_name, reset_device=False) for the selected scope",
             source="upstream_code", ref="niscope_mcp/backends/direct.py:57-64"),
        Fact("configure_channel writes channel_enabled, vertical_range, vertical_offset, vertical_coupling, "
             "probe_attenuation and input_impedance", source="upstream_code",
             ref="niscope_mcp/backends/direct.py:88-97"),
        Fact("configure_trigger writes the trigger source, level and slope, and configure_horizontal writes "
             "min_sample_rate, horz_min_num_pts, horz_num_records, horz_record_ref_position and "
             "horz_enforce_realtime", source="upstream_code", ref="niscope_mcp/backends/direct.py:101-127"),
        Fact("read_waveform fetches num_samples and downsamples the time and voltage arrays to at most 2000 "
             "points", source="upstream_code", ref="niscope_mcp/backends/direct.py:137-164"),
        Fact("measure_waveform fetches num_samples and returns rounded frequency, period, amplitude, RMS, "
             "minimum, maximum, mean, rise time, fall time, duty cycle, sample count and sample rate",
             source="upstream_code", ref="niscope_mcp/backends/direct.py:166-191"),
        Fact("get_current_config reports the model, the horizontal sample rate, record length and actual sample "
             "rate, the trigger source, level and slope, and per-channel enabled, vertical range, offset, "
             "coupling, probe attenuation and input impedance", source="upstream_code",
             ref="niscope_mcp/backends/direct.py:258-283"),
        Fact("ChannelConfig carries vertical_range in Vpp, vertical_offset in V, vertical_coupling AC/DC/GND, "
             "probe_attenuation, input_impedance in ohms and bandwidth_filter", source="upstream_code",
             ref="niscope_mcp/backends/base.py:20-29"),
        Fact("TriggerConfig carries source, level, slope, coupling, holdoff and type", source="upstream_code",
             ref="niscope_mcp/backends/base.py:32-49"),
        Fact("HorizontalConfig carries min_sample_rate, min_num_pts, num_records, ref_position, "
             "enforce_realtime and acquisition_type", source="upstream_code",
             ref="niscope_mcp/backends/base.py:52-61"),
        Fact("The configure_scope help text names the channel, horizontal and trigger settings and their units",
             source="upstream_code", ref="niscope_mcp/__main__.py:381-386"),
        Fact("The help text lists vertical_range common values 0.1-50 Vpp, input impedance 50 or 1000000 ohm, "
             "and min_sample_rate common values 1e6-1.25e9 S/s", source="upstream_code",
             ref="niscope_mcp/__main__.py:1208-1214"),
        Fact("main() serves the MCP server over get_backend('direct')", source="upstream_code",
             ref="niscope_mcp/__main__.py:1280"),
    ]
    safe_state = ("all acquisition sessions are closed; the instrument stops acquiring and drives no output")

    # -- native target ------------------------------------------------------------------------------------------
    def _resource_name(self) -> str:
        """The resource selected by the operator option, or the first scope scan_devices reports."""
        resource = getattr(self, "_resource", None)
        if resource is None:
            options = dict(self.options or {})
            resource = options.get("resource_name")
            if not resource:
                devices = self.native.scan_devices()
                if not devices:
                    raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                                       "no NI PXIe oscilloscope was reported by scan_devices")
                resource = devices[0].resource_name
            self._resource = str(resource)
            self._channel = str(options.get("channel", "0"))
            self.native.open_device(self._resource)
        return self._resource

    def _channel_name(self) -> str:
        self._resource_name()
        return self._channel

    def setup(self) -> None:
        self._resource_name()

    def teardown(self) -> None:
        self.native.close_all()

    # -- current state -------------------------------------------------------------------------------------------
    def _channel_state(self) -> dict:
        config = self.native.get_current_config(self._resource_name())
        channel = (config.get("channels") or {}).get(self._channel_name())
        if channel is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"the scope does not report channel {self._channel!r}")
        return channel

    def _trigger_state(self) -> dict:
        config = self.native.get_current_config(self._resource_name())
        return dict(config.get("trigger") or {})

    def _horizontal_state(self) -> dict:
        config = self.native.get_current_config(self._resource_name())
        return dict(config.get("horizontal") or {})

    # -- writes --------------------------------------------------------------------------------------------------
    def _set_channel(self, **changes) -> None:
        channel = self._channel_state()
        channel.update(changes)
        options = dict(self.options or {})
        self.native.configure_channel(self._resource_name(), self._channel_name(), _ChannelConfig(
            enabled=bool(channel["enabled"]),
            vertical_range=float(channel["vertical_range_vpp"]),
            vertical_offset=float(channel["vertical_offset_v"]),
            vertical_coupling=_enum_name(channel["vertical_coupling"]),
            probe_attenuation=float(channel["probe_attenuation"]),
            input_impedance=float(channel["input_impedance_ohms"]),
            bandwidth_filter=str(options.get("bandwidth_filter", "FULL")),
        ))
        self.native.commit(self._resource_name())

    def _set_horizontal(self, **changes) -> None:
        horizontal = self._horizontal_state()
        horizontal.update(changes)
        options = dict(self.options or {})
        self.native.configure_horizontal(self._resource_name(), _HorizontalConfig(
            min_sample_rate=float(horizontal["sample_rate_sps"]),
            min_num_pts=int(horizontal["record_length"]),
            num_records=int(options.get("num_records", 1)),
            ref_position=float(options.get("ref_position", 50.0)),
            enforce_realtime=bool(options.get("enforce_realtime", True)),
            acquisition_type=str(options.get("acquisition_type", "NORMAL")),
        ))
        self.native.commit(self._resource_name())

    def _set_trigger(self, **changes) -> None:
        trigger = self._trigger_state()
        trigger.update(changes)
        options = dict(self.options or {})
        self.native.configure_trigger(self._resource_name(), _TriggerConfig(
            source=str(trigger["source"]),
            level=float(trigger["level_v"]),
            slope=_enum_name(trigger["slope"]),
            coupling=str(options.get("trigger_coupling", "DC")),
            holdoff=float(options.get("trigger_holdoff", 0.0)),
            type="EDGE",
        ))
        self.native.commit(self._resource_name())

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("device_model", type="string", description="Instrument model reported by the scope")
    def device_model(self):
        return str(self.native.get_current_config(self._resource_name()).get("model", ""))

    @read("channel_enabled", type="boolean", description="True while the selected channel is enabled")
    def channel_enabled(self):
        return bool(self._channel_state()["enabled"])

    @read("vertical_range", unit="V", description="Vertical range")
    def vertical_range(self):
        return float(self._channel_state()["vertical_range_vpp"])

    @read("vertical_offset", unit="V", description="Vertical offset")
    def vertical_offset(self):
        return float(self._channel_state()["vertical_offset_v"])

    @read("vertical_coupling", type="string", enum=["AC", "DC", "GND"],
          description="Vertical coupling")
    def vertical_coupling(self):
        return _enum_name(self._channel_state()["vertical_coupling"])

    @read("probe_attenuation", unit="1", description="Probe attenuation")
    def probe_attenuation(self):
        return float(self._channel_state()["probe_attenuation"])

    @read("input_impedance", unit="Ohm", description="Input impedance")
    def input_impedance(self):
        return float(self._channel_state()["input_impedance_ohms"])

    @read("sample_rate", unit="Hz", description="Requested minimum sample rate")
    def sample_rate(self):
        return float(self._horizontal_state()["sample_rate_sps"])

    @read("record_length", type="integer", unit="1", description="Requested record length in samples")
    def record_length(self):
        return int(self._horizontal_state()["record_length"])

    @read("trigger_source", type="string", description="Trigger source reported by the scope")
    def trigger_source(self):
        return str(self._trigger_state().get("source", ""))

    @read("trigger_level", unit="V", description="Trigger level")
    def trigger_level(self):
        return float(self._trigger_state()["level_v"])

    @read("trigger_slope", type="string", enum=["POSITIVE", "NEGATIVE"], description="Trigger slope")
    def trigger_slope(self):
        return _enum_name(self._trigger_state()["slope"])

    # -- writes --------------------------------------------------------------------------------------------------
    @write("channel_enabled", type="boolean", description="Enable or disable the selected channel")
    def set_channel_enabled(self, value):
        self._set_channel(enabled=bool(value))
        return bool(value)

    @write("vertical_range", unit="V", description="Vertical range",
           limit=Limit(min=0.1, max=50, source="upstream_code", ref="niscope_mcp/__main__.py:1211"))
    def set_vertical_range(self, value):
        self._set_channel(vertical_range_vpp=float(value))
        return value

    @write("vertical_offset", unit="V", description="Vertical offset",
           limit=Limit.operator_required(
               "no text of the clone states the vertical offset range of the scope; the site sets the range of "
               "its unit in site-limits.json"))
    def set_vertical_offset(self, value):
        self._set_channel(vertical_offset_v=float(value))
        return value

    @write("vertical_coupling", type="string", enum=["AC", "DC", "GND"],
           description="Vertical coupling")
    def set_vertical_coupling(self, value):
        self._set_channel(vertical_coupling=str(value))
        return value

    @write("probe_attenuation", unit="1", description="Probe attenuation",
           limit=Limit(allowed=[1, 10, 100], source="upstream_code", ref="niscope_mcp/__main__.py:382"))
    def set_probe_attenuation(self, value):
        self._set_channel(probe_attenuation=float(value))
        return value

    @write("input_impedance", unit="Ohm", description="Input impedance",
           limit=Limit(allowed=[50, 1000000], source="upstream_code", ref="niscope_mcp/__main__.py:1212"))
    def set_input_impedance(self, value):
        self._set_channel(input_impedance_ohms=float(value))
        return value

    @write("sample_rate", unit="Hz", description="Requested minimum sample rate",
           limit=Limit(min=1e6, max=1.25e9, source="upstream_code", ref="niscope_mcp/__main__.py:1213"))
    def set_sample_rate(self, value):
        self._set_horizontal(sample_rate_sps=float(value))
        return value

    @write("record_length", type="integer", unit="1", description="Requested record length in samples",
           limit=Limit.operator_required(
               "no text of the clone states a record-length bound; the site sets the range of its unit in "
               "site-limits.json"))
    def set_record_length(self, value):
        self._set_horizontal(record_length=int(value))
        return value

    @write("trigger_source", type="string", description="Trigger source reported by the scope")
    def set_trigger_source(self, value):
        self._set_trigger(source=str(value))
        return value

    @write("trigger_level", unit="V", description="Trigger level",
           limit=Limit.operator_required(
               "no text of the clone states the trigger-level range; the site sets the range of its unit in "
               "site-limits.json"))
    def set_trigger_level(self, value):
        self._set_trigger(level_v=float(value))
        return value

    @write("trigger_slope", type="string", enum=["POSITIVE", "NEGATIVE"], description="Trigger slope")
    def set_trigger_slope(self, value):
        self._set_trigger(slope=str(value))
        return value

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.ymzds.measure_waveform.v1",
            description="Acquire one channel and return its scalar waveform measurements",
            output={
                "frequency_hz": Field("number", unit="Hz", description="Measured frequency"),
                "period_sec": Field("number", unit="s", description="Measured period"),
                "amplitude_vpp": Field("number", unit="V", description="Measured peak-to-peak amplitude"),
                "rms_v": Field("number", unit="V", description="Measured RMS voltage"),
                "min_v": Field("number", unit="V", description="Minimum sample voltage"),
                "max_v": Field("number", unit="V", description="Maximum sample voltage"),
                "mean_v": Field("number", unit="V", description="Mean sample voltage"),
                "rise_time_sec": Field("number", unit="s", description="Measured 10-90% rise time"),
                "fall_time_sec": Field("number", unit="s", description="Measured 10-90% fall time"),
                "duty_cycle_pct": Field("number", unit="%", description="Measured duty cycle"),
                "num_samples": Field("integer", unit="1", description="Number of acquired samples"),
                "sample_rate_sps": Field("number", unit="Hz", description="Acquisition sample rate"),
            })
    def measure_waveform(self):
        measurement = self.native.measure_waveform(self._resource_name(), self._channel_name())
        return {
            "frequency_hz": measurement.frequency_hz,
            "period_sec": measurement.period_sec,
            "amplitude_vpp": measurement.amplitude_vpp,
            "rms_v": measurement.rms_v,
            "min_v": measurement.min_v,
            "max_v": measurement.max_v,
            "mean_v": measurement.mean_v,
            "rise_time_sec": measurement.rise_time_sec,
            "fall_time_sec": measurement.fall_time_sec,
            "duty_cycle_pct": measurement.duty_cycle_pct,
            "num_samples": measurement.num_samples,
            "sample_rate_sps": measurement.sample_rate_sps,
        }

    @action(name="x-cap.ymzds.auto_setup.v1", description="Run the native oscilloscope auto setup (Autoset)",
            output={"configured": Field("boolean", description="True once auto setup returned")})
    def auto_setup(self):
        self.native.auto_setup(self._resource_name())
        self.native.commit(self._resource_name())
        return {"configured": True}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: close every acquisition session (DirectBackend.close_all)."""
        self.native.close_all()
