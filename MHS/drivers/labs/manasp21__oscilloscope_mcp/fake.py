"""Fake backend of the oscilloscope_mcp driver: an in-memory stand-in for EthernetOscilloscope.

Gate G7: every public method defined here exists on
``oscilloscope_mcp.hardware.ethernet_backend:EthernetOscilloscope`` (ethernet_backend.py:18-55).  Like the upstream
class, every method is a coroutine function and the state is the structure ``get_status`` returns
(simulation.py:269-277): the initialized and acquisition-active flags, a channel dictionary, a timebase dictionary
and a trigger dictionary.  The starting values are test data, not device facts: each is marked ``# placeholder`` and
none of them is used as a Fact, a Limit or a reference.  The acquisition returns a shorter array than the real
simulator's record length to keep the receipt small; the real size is recorded in RESULT.json notes and in the
package driver's fidelity gaps, and the driver does not transfer samples.  Nothing here talks to a device.
"""

import math
import time
from typing import Any, Dict


class FakeEthernetOscilloscope:
    def __init__(self, **_options):
        self._initialized = False
        self._acquisition_active = False
        self._channels: Dict[int, Dict[str, Any]] = {}
        self._timebase: Dict[str, Any] = {}
        self._trigger: Dict[str, Any] = {}

    async def initialize(self, config: Dict[str, Any]) -> None:
        self._initialized = True
        sample_rate = float(config.get("sample_rate", 100_000_000.0))  # placeholder
        record_length = int(config.get("buffer_size", 1000))  # placeholder
        self._channels = {
            channel: {
                "voltage_range": 1.0,  # placeholder
                "coupling": "DC",  # placeholder
                "impedance": "1M",  # placeholder
                "enabled": True,  # placeholder
            }
            for channel in range(4)  # placeholder
        }
        self._timebase = {
            "sample_rate": sample_rate,
            "record_length": record_length,
            "time_per_div": record_length / (10.0 * sample_rate) if sample_rate else 0.0,  # placeholder
        }
        self._trigger = {
            "source": "channel0",  # placeholder
            "type": "edge",  # placeholder
            "level": 0.0,  # placeholder
            "edge": "rising",  # placeholder
            "holdoff": 0.0,  # placeholder
        }
        self._acquisition_active = False

    async def configure_channels(self, channels, voltage_range, coupling, impedance):
        if not self._initialized:
            raise RuntimeError("Oscilloscope not initialized")
        for channel in channels:
            if channel not in self._channels:
                raise ValueError(f"Invalid channel: {channel}")
        for channel in channels:
            self._channels[channel] = {
                "voltage_range": float(voltage_range),
                "coupling": str(coupling),
                "impedance": str(impedance),
                "enabled": True,
            }
        return {
            "timestamp": time.time(),  # placeholder
            "channels_configured": list(channels),
            "voltage_range": float(voltage_range),
            "coupling": str(coupling),
            "impedance": str(impedance),
        }

    async def set_timebase(self, sample_rate, record_length):
        if not self._initialized:
            raise RuntimeError("Oscilloscope not initialized")
        sample_rate = float(sample_rate)
        record_length = int(record_length)
        self._timebase = {
            "sample_rate": sample_rate,
            "record_length": record_length,
            "time_per_div": record_length / (10.0 * sample_rate) if sample_rate else 0.0,  # placeholder
        }
        return {
            "timestamp": time.time(),  # placeholder
            "actual_sample_rate": sample_rate,
            "actual_record_length": record_length,
            "memory_depth": record_length,
        }

    async def setup_trigger(self, source, trigger_type, level, edge, holdoff):
        if not self._initialized:
            raise RuntimeError("Oscilloscope not initialized")
        self._trigger = {
            "source": str(source),
            "type": str(trigger_type),
            "level": float(level),
            "edge": str(edge),
            "holdoff": float(holdoff),
        }
        return {
            "timestamp": time.time(),  # placeholder
            "trigger_id": "trigger_fake",  # placeholder
            "source": self._trigger["source"],
            "type": self._trigger["type"],
            "level": self._trigger["level"],
            "edge": self._trigger["edge"],
            "holdoff": self._trigger["holdoff"],
        }

    async def acquire_waveform(self, channels, timeout):
        if not self._initialized:
            raise RuntimeError("Oscilloscope not initialized")
        self._acquisition_active = True
        try:
            sample_rate = float(self._timebase["sample_rate"])
            count = 8  # placeholder: the real record_length comes from the timebase
            time_axis = [index / sample_rate for index in range(count)] if sample_rate else [0.0] * count
            waveform: Dict[str, Any] = {"time": time_axis, "channels": {}}
            for channel in channels:
                configuration = self._channels.get(channel)
                if configuration is None or not configuration["enabled"]:
                    continue
                amplitude = configuration["voltage_range"] * 0.5  # placeholder
                volts = [amplitude * math.sin(2.0 * math.pi * index / count) for index in range(count)]
                waveform["channels"][channel] = {
                    "voltage": volts,
                    "voltage_range": configuration["voltage_range"],
                    "coupling": configuration["coupling"],
                    "impedance": configuration["impedance"],
                }
            return {
                "timestamp": time.time(),  # placeholder
                "channels": list(channels),
                "waveform_data": waveform,
                "metadata": {
                    "sample_rate": sample_rate,
                    "record_length": count,
                    "trigger_config": dict(self._trigger),
                },
            }
        finally:
            self._acquisition_active = False

    async def stop_acquisition(self) -> None:
        self._acquisition_active = False

    async def get_status(self):
        return {
            "initialized": self._initialized,
            "acquisition_active": self._acquisition_active,
            "channels": {channel: dict(configuration)
                         for channel, configuration in self._channels.items()},
            "timebase": dict(self._timebase),
            "trigger_config": dict(self._trigger),
        }

    async def cleanup(self) -> None:
        await self.stop_acquisition()
        self._initialized = False
