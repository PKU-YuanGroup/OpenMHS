"""Fake backend of the oscilloscope driver: an in-memory stand-in for ``osc.scope:Scope``.

Gate G7: every public method defined here is a method of ``Scope`` in the clone (osc/scope.py): identify, errors,
status, autoscale, run, stop, single, configure_channel, configure_timebase, configure_trigger, capture, measure
and close.  The state attributes are private instance data, so the fake surface is the upstream method surface.
``address`` is the upstream property (scope.py:154-156).

The clone ships its own ``SimulatedScope`` (osc/simulator.py:49), but it is upstream code and this package may not
import or run it.  This file is therefore an analytic in-memory stand-in, not a replay of captured traffic.  Every
number and string below is test data, not a fact from the clone or a record of an instrument: each is marked
``# placeholder``.  The waveform is eight samples, much shorter than a real capture (the clone asks for 2000 points
and decimates to at most 500), so the gate receipt stays small.  Nothing here talks to a device.
"""

#: Eight placeholder sample times for the fake record.
_TIMES = [-4e-4, -3e-4, -2e-4, -1e-4, 0.0, 1e-4, 2e-4, 3e-4]          # placeholder
#: Eight placeholder voltage samples of a sine-shaped fake signal.
_VOLTS = [0.0, 0.707, 1.0, 0.707, 0.0, -0.707, -1.0, -0.707]          # placeholder


class FakeScope:
    """A fresh in-memory oscilloscope per endpoint; all starting values are placeholders."""

    def __init__(self, address="SIM::DSOX1204A::0::INSTR", **_options):
        self._address = address                                        # placeholder
        self._timebase = {"scale": 5e-4, "mode": "MAIN", "position": 0.0,
                          "sample_rate": 2e6}                          # placeholder
        self._channels = [
            {"channel": channel, "scale": 0.5, "offset": 0.0, "coupling": "DC",
             "display": channel == 1, "probe": 1.0}                    # placeholder
            for channel in (1, 2, 3, 4)
        ]
        self._trigger = {"sweep": "AUTO", "source": "CHAN1", "level": 0.0,
                         "slope": "POS"}                               # placeholder
        self._acquire = {"type": "NORM", "points": 8.0}                 # placeholder
        self._closed = False

    # ------------------------------------------------------------ basic communication
    @property
    def address(self):
        return self._address

    # ------------------------------------------------------------ identity / state
    def identify(self):
        return {
            "manufacturer": "KEYSIGHT TECHNOLOGIES",                   # placeholder
            "model": "DSOX1204A",                                      # placeholder
            "serial": "SIMULATED",                                     # placeholder
            "firmware": "SIM-0.1",                                     # placeholder
            "raw": "KEYSIGHT TECHNOLOGIES,DSOX1204A,SIMULATED,SIM-0.1",  # placeholder
        }

    def errors(self):
        return []

    def status(self):
        return {
            "address": self._address,
            "timebase": dict(self._timebase),
            "channels": [dict(item) for item in self._channels],
            "trigger": dict(self._trigger),
            "acquire": dict(self._acquire),
        }

    # ------------------------------------------------------------ configuration
    def autoscale(self):
        self._channels[0]["scale"] = 0.5                               # placeholder
        self._channels[0]["offset"] = 0.0                              # placeholder
        self._timebase["scale"] = 5e-4                                 # placeholder
        self._timebase["position"] = 0.0                               # placeholder

    def run(self):
        pass

    def stop(self):
        pass

    def single(self):
        pass

    def configure_channel(self, channel, scale=None, offset=None, coupling=None, display=None, probe=None):
        for item in self._channels:
            if item["channel"] != int(channel):
                continue
            if scale is not None:
                item["scale"] = float(scale)
            if offset is not None:
                item["offset"] = float(offset)
            if coupling is not None:
                item["coupling"] = str(coupling).upper()
            if display is not None:
                item["display"] = bool(display)
            if probe is not None:
                item["probe"] = float(probe)
            return
        raise RuntimeError(f"no channel {channel}")                    # placeholder

    def configure_timebase(self, scale=None, position=None, mode=None):
        if scale is not None:
            self._timebase["scale"] = float(scale)
        if position is not None:
            self._timebase["position"] = float(position)
        if mode is not None:
            self._timebase["mode"] = str(mode).upper()

    def configure_trigger(self, source=None, level=None, slope=None, sweep=None):
        if source is not None:
            self._trigger["source"] = str(source).upper()
        if level is not None:
            self._trigger["level"] = float(level)
        if slope is not None:
            self._trigger["slope"] = str(slope).upper()
        if sweep is not None:
            self._trigger["sweep"] = str(sweep).upper()

    # ------------------------------------------------------------ acquisition
    def capture(self, channel=1, points=None, max_return=None):
        volts = [float(value) for value in _VOLTS]
        times = [float(value) for value in _TIMES]
        mean = sum(volts) / len(volts)
        stats = {"min": min(volts), "max": max(volts), "mean": mean,
                 "vpp": max(volts) - min(volts),
                 "rms": (sum(value * value for value in volts) / len(volts)) ** 0.5}
        return {
            "channel": int(channel),
            "points": len(volts),
            "returned_points": len(volts),
            "decimation": 1,
            "x_increment": 1e-4,                                        # placeholder
            "x_origin": -4e-4,                                          # placeholder
            "y_increment": 0.015625,                                    # placeholder
            "y_origin": 0.0,                                            # placeholder
            "y_reference": 128,                                         # placeholder
            "time_span": 8e-4,                                          # placeholder
            "sample_rate": 10000.0,                                     # placeholder
            "times": times,
            "volts": volts,
            "stats": stats,
            "warnings": [],
        }

    def measure(self, channel=1, names=None):
        table = {
            "vpp": 2.0, "vmax": 1.0, "vmin": -1.0, "vavg": 0.0, "vrms": 0.707,
            "amplitude": 2.0, "top": 1.0, "base": -1.0, "frequency": 1000.0,
            "period": 1e-3, "dutycycle": 50.0, "rise_time": 1e-8, "fall_time": 1e-8,
        }                                                               # placeholder
        names = names or ["vpp", "vmax", "vmin", "vavg", "frequency"]
        return {str(name).strip().lower(): table.get(str(name).strip().lower()) for name in names}

    # ------------------------------------------------------------ lifecycle
    def close(self):
        self._closed = True
