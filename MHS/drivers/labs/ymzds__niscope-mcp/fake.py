"""Fake backend of the niscope-mcp driver: an in-memory stand-in for DirectBackend.

Gate G7: every public method defined here is a method of
``niscope_mcp.backends.direct:DirectBackend`` (direct.py:31-283); the private helpers and attributes are not part
of the checked surface.  The state mirrors the dictionary ``DirectBackend.get_current_config`` returns
(direct.py:258-283), so a write through ``configure_channel``, ``configure_horizontal`` or ``configure_trigger``
is visible in the next read.  Nothing here imports the upstream package or talks to a device.

Every numeric literal that models device state or a canned measurement reply is test data, not a fact or a limit;
each such line is marked ``# placeholder``.  No value was copied into driver.py, facts.md, a Limit or a reference.
"""

import copy
from dataclasses import dataclass, field


@dataclass
class _DeviceInfo:
    resource_name: str
    model: str
    channels: int
    max_sample_rate: float
    max_input_frequency: float
    faulty: bool = False
    fault_reason: str = ""


@dataclass
class _Waveform:
    channel: str
    time: list
    voltage: list
    raw_samples: int
    sample_interval: float
    trigger_offset: float
    stats: dict


@dataclass
class _Measurement:
    channel: str
    frequency_hz: float = 0.0
    period_sec: float = 0.0
    amplitude_vpp: float = 0.0
    rms_v: float = 0.0
    min_v: float = 0.0
    max_v: float = 0.0
    mean_v: float = 0.0
    rise_time_sec: float = 0.0
    fall_time_sec: float = 0.0
    duty_cycle_pct: float = 0.0
    num_samples: int = 0
    sample_rate_sps: float = 0.0


@dataclass
class _AutoMeasure(_Measurement):
    time: list = field(default_factory=list)
    voltage: list = field(default_factory=list)
    raw_samples: int = 0
    stats: dict = field(default_factory=dict)
    signal_type: str = "dc"
    adapt_history: list = field(default_factory=list)

    @property
    def vpp(self) -> float:
        return self.amplitude_vpp or self.stats.get("peak_to_peak", 0.0)


class FakeNiscopeMcp:
    def __init__(self, **_options):
        self._sessions: dict[str, bool] = {}
        self._bad_devices: set[str] = set()
        self._state = {
            "resource_name": "PXI1Slot3",  # placeholder
            "model": "PXIe-5160",  # placeholder
            "channels": {
                "0": {
                    "enabled": True,  # placeholder
                    "vertical_range_vpp": 5.0,  # placeholder
                    "vertical_offset_v": 0.0,  # placeholder
                    "vertical_coupling": "DC",  # placeholder
                    "probe_attenuation": 1.0,  # placeholder
                    "input_impedance_ohms": 1000000.0,  # placeholder
                }
            },
            "horizontal": {
                "sample_rate_sps": 1000000.0,  # placeholder
                "record_length": 10000,  # placeholder
                "actual_sample_rate_sps": 1000000.0,  # placeholder
            },
            "trigger": {
                "source": "0",  # placeholder
                "level_v": 1.0,  # placeholder
                "slope": "POSITIVE",  # placeholder
            },
        }

    # -- lifecycle -----------------------------------------------------------------------------------------------
    def scan_devices(self):
        return [_DeviceInfo(
            resource_name="PXI1Slot3",  # placeholder
            model="PXIe-5160",  # placeholder
            channels=1,  # placeholder
            max_sample_rate=1.25e9,  # placeholder
            max_input_frequency=500e6,  # placeholder
        )]

    def open_device(self, resource_name):
        if resource_name in self._bad_devices:
            raise RuntimeError(f"Device {resource_name} previously marked faulty.")
        self._sessions[resource_name] = True

    def close_device(self, resource_name):
        self._sessions.pop(resource_name, None)

    def close_all(self):
        self._sessions.clear()

    def mark_bad(self, resource_name, reason):
        self._bad_devices.add(resource_name)
        self.close_device(resource_name)

    # -- configuration -------------------------------------------------------------------------------------------
    def configure_channel(self, resource_name, channel, config):
        state = self._state["channels"].setdefault(str(channel), {})
        state["enabled"] = bool(config.enabled)
        state["vertical_range_vpp"] = float(config.vertical_range)
        state["vertical_offset_v"] = float(config.vertical_offset)
        state["vertical_coupling"] = str(config.vertical_coupling)
        state["probe_attenuation"] = float(config.probe_attenuation)
        state["input_impedance_ohms"] = float(config.input_impedance)

    def configure_trigger(self, resource_name, config):
        self._state["trigger"]["source"] = str(config.source)
        self._state["trigger"]["level_v"] = float(config.level)
        self._state["trigger"]["slope"] = str(config.slope)

    def configure_horizontal(self, resource_name, config):
        self._state["horizontal"]["sample_rate_sps"] = float(config.min_sample_rate)
        self._state["horizontal"]["record_length"] = int(config.min_num_pts)

    def auto_setup(self, resource_name):
        self._sessions.setdefault(resource_name, True)

    def commit(self, resource_name):
        return None

    # -- acquisition ---------------------------------------------------------------------------------------------
    def read_waveform(self, resource_name, channel, num_samples=10000, timeout=5.0):
        n = 8  # placeholder: the device fetches num_samples, the fake returns a small array
        dt = 1e-9  # placeholder
        voltage = [0.0, 0.5, 1.0, 1.5, 2.0, 1.5, 1.0, 0.5]  # placeholder
        return _Waveform(
            channel=str(channel),
            time=[float(i * dt) for i in range(n)],
            voltage=voltage,
            raw_samples=n,
            sample_interval=dt,
            trigger_offset=0.0,  # placeholder
            stats={"min": 0.0, "max": 2.0, "mean": 1.0, "std": 0.7, "peak_to_peak": 2.0},  # placeholder
        )

    def measure_waveform(self, resource_name, channel, num_samples=100000, timeout=5.0):
        return _Measurement(
            channel=str(channel),
            frequency_hz=1000000.0,  # placeholder
            period_sec=1e-6,  # placeholder
            amplitude_vpp=2.0,  # placeholder
            rms_v=0.707,  # placeholder
            min_v=0.0,  # placeholder
            max_v=2.0,  # placeholder
            mean_v=1.0,  # placeholder
            rise_time_sec=1e-8,  # placeholder
            fall_time_sec=1e-8,  # placeholder
            duty_cycle_pct=50.0,  # placeholder
            num_samples=8,  # placeholder
            sample_rate_sps=1e9,  # placeholder
        )

    def auto_measure(self, resource_name, channel, timeout=10.0, preserve_trigger=False):
        measurement = self.measure_waveform(resource_name, channel)
        return _AutoMeasure(
            channel=measurement.channel,
            frequency_hz=measurement.frequency_hz,
            period_sec=measurement.period_sec,
            amplitude_vpp=measurement.amplitude_vpp,
            rms_v=measurement.rms_v,
            min_v=measurement.min_v,
            max_v=measurement.max_v,
            mean_v=measurement.mean_v,
            rise_time_sec=measurement.rise_time_sec,
            fall_time_sec=measurement.fall_time_sec,
            duty_cycle_pct=measurement.duty_cycle_pct,
            num_samples=measurement.num_samples,
            sample_rate_sps=measurement.sample_rate_sps,
            time=[0.0, 1e-9],  # placeholder
            voltage=[0.0, 2.0],  # placeholder
            raw_samples=measurement.num_samples,
            stats={"min": 0.0, "max": 2.0, "mean": 1.0, "std": 0.7, "peak_to_peak": 2.0},  # placeholder
            signal_type="periodic",  # placeholder
            adapt_history=["fake acquisition"],  # placeholder
        )

    def get_current_config(self, resource_name):
        return copy.deepcopy(self._state)
