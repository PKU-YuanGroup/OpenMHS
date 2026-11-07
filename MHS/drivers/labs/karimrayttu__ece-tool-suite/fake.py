"""Fake backend of the ECE Tool Suite scope driver: an in-memory KeysightScope stand-in.

Gate G7: every public method defined here is a method of ``KeysightScope`` in the clone
(backend/ece_suite/instruments/keysight.py). The driver also reaches ``t``, the transport attribute
set by the upstream ``__init__`` (keysight.py:37-40); the private transport below only supplies the
``close`` method the driver's teardown calls. The clone does not simulate this class, so this file
is an in-memory stand-in, not a recording of a session.

Every number and string below is test data, not a fact from the clone or a record of an instrument:
each is marked ``# placeholder``. ``capture`` returns a five-point stand-in; the real class returns
the acquired record decoded from :WAVeform:DATA? (keysight.py:151-161). The driver serves only the
scalar summary of that record. Nothing here talks to a device.
"""


class _FakeIdn:
    """The five members of the upstream ``IdnInfo`` result (scpi.py:13-22); only ``raw`` is used."""

    def __init__(self, raw):
        parts = [item.strip() for item in raw.split(",")]
        while len(parts) < 4:
            parts.append("")
        self.vendor = parts[0]
        self.model = parts[1]
        self.serial = parts[2]
        self.firmware = parts[3]
        self.raw = raw


class _FakeTransport:
    """The transport object a real KeysightScope owns (``self.t``); the driver only closes it."""

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _FakeWaveform:
    """A small stand-in for the upstream ``Waveform`` value (provenance.py): t, v and meta."""

    def __init__(self, t, v, meta):
        self.t = t
        self.v = v
        self.meta = meta


class FakeKeysightScope:
    """A fresh in-memory oscilloscope per endpoint; all starting values are placeholders."""

    def __init__(self, **_options):
        self.t = _FakeTransport()
        self._idn = _FakeIdn("SIM,ECE-SUITE-SCOPE,SN-0000,0.0.0")  # placeholder
        self._light = {                                            # placeholder values
            "vpp": 2.4,
            "vrms": 0.85,
            "vmax": 1.2,
            "vmin": -1.2,
            "freq": 1000.0,
            "period": 0.001,
        }
        self._all = {                                              # placeholder values
            "vpp": 2.4,
            "vamp": 2.4,
            "vmax": 1.2,
            "vmin": -1.2,
            "vtop": 1.2,
            "vbase": -1.2,
            "vavg": 0.0,
            "vrms": 0.85,
            "freq": 1000.0,
            "period": 0.001,
            "duty": 50.0,
            "pwidth": 0.0005,
            "nwidth": 0.0005,
            "rise": 0.000001,
            "fall": 0.000001,
            "over": 0.0,
        }
        self._units = {                                            # the units of keysight.py:175-184
            "vpp": "V", "vamp": "V", "vmax": "V", "vmin": "V",
            "vtop": "V", "vbase": "V", "vavg": "V", "vrms": "V",
            "freq": "Hz", "period": "s", "duty": "%", "pwidth": "s",
            "nwidth": "s", "rise": "s", "fall": "s", "over": "%",
        }
        self._capture_t = [0.0, 0.00025, 0.0005, 0.00075, 0.001]    # placeholder seconds
        self._capture_v = [0.0, 1.2, 0.0, -1.2, 0.0]                # placeholder volts
        self._running = False                                      # placeholder state
        self._single = False                                       # placeholder state

    def identify(self):
        return self._idn

    def measure(self, ch=1):
        return dict(self._light)

    def measure_all(self, ch=1):
        return {key: {"value": value, "unit": self._units[key]} for key, value in self._all.items()}

    def measure_vpp(self, ch=1):
        return self._light["vpp"]

    def capture(self, ch=1):
        return _FakeWaveform(list(self._capture_t), list(self._capture_v),
                             {"points": len(self._capture_t), "vpp": 2.4})  # placeholder

    def run(self):
        self._running = True
        self._single = False

    def stop(self):
        self._running = False
        self._single = False

    def single(self):
        self._running = False
        self._single = True

    def reset(self):
        self._running = False
        self._single = False
