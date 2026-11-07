"""Fake backend of the Tektronix AFG driver: an in-memory stand-in for ``tektronix_func_gen:FuncGen``.

Gate G7 compares every public member of ``FakeFuncGen`` with the upstream class: ``ch1``, ``ch2``,
``get_settings``, ``set_settings``, ``write``, ``close``, ``get_error``, ``get_frequency_lock``,
``set_frequency_lock`` and ``get_waveform_catalogue`` are all members of ``FuncGen``.  The channel object behind
``ch1``/``ch2`` only offers the five channel getters the driver reads; the driver changes settings through
``FuncGen.set_settings`` and turns the outputs off through ``FuncGen.write``, exactly as the upstream class does.

Every starting value is test data, not a fact about an instrument: each is marked ``# placeholder``.  Nothing here
talks to a device.
"""

import re

_OUTPUT = re.compile(r"OUTPut([12]):STATe\s+(ON|OFF|1|0)", re.IGNORECASE)


class _FakeChannel:
    """The channel getters the driver reads (the upstream ``FuncGenChannel`` methods)."""

    def __init__(self, owner, channel):
        self._owner = owner
        self._channel = channel

    def get_output_state(self):
        return 1 if self._owner._output[self._channel] else 0

    def get_function(self):
        return self._owner._function[self._channel]

    def get_amplitude(self):
        return self._owner._amplitude[self._channel]

    def get_offset(self):
        return self._owner._offset[self._channel]

    def get_frequency(self):
        return self._owner._frequency[self._channel]


class FakeFuncGen:
    """A fresh in-memory function generator per endpoint; every starting value is a placeholder."""

    def __init__(self, **_options):
        self._output = {1: True, 2: False}                       # placeholder: channel 1 on, channel 2 off
        self._function = {1: "SIN", 2: "RAMP"}                   # placeholder
        self._amplitude = {1: 0.5, 2: 1.0}                       # placeholder: Vpp
        self._offset = {1: 0.0, 2: 0.0}                          # placeholder: V
        self._frequency = {1: 1000.0, 2: 1000.0}                 # placeholder: Hz
        self._frequency_lock = False                             # placeholder
        self._error = '+0,"No error"'                            # placeholder
        self._catalogue = ["USER5"]                              # placeholder
        self._closed = False                                     # placeholder
        self.written = []
        self._channels = {1: _FakeChannel(self, 1), 2: _FakeChannel(self, 2)}

    @property
    def ch1(self):
        return self._channels[1]

    @property
    def ch2(self):
        return self._channels[2]

    def _settings(self, channel):
        return {
            "output": ("ON" if self._output[channel] else "OFF", ""),
            "function": (self._function[channel], ""),
            "amplitude": (self._amplitude[channel], "Vpp"),
            "offset": (self._offset[channel], "V"),
            "frequency": (self._frequency[channel], "Hz"),
        }

    def get_settings(self):
        return [self._settings(1), self._settings(2)]

    def set_settings(self, settings):
        for channel, entry in zip((1, 2), settings):
            self._output[channel] = str(entry["output"][0]).strip().upper() in ("ON", "1")
            self._function[channel] = str(entry["function"][0])
            self._amplitude[channel] = float(entry["amplitude"][0])
            self._offset[channel] = float(entry["offset"][0])
            self._frequency[channel] = float(entry["frequency"][0])

    def get_error(self):
        return self._error

    def get_frequency_lock(self):
        return self._frequency_lock

    def set_frequency_lock(self, state, use_channel=1):
        text = str(state).strip().upper()
        if text not in ("ON", "OFF"):
            raise ValueError(f"frequency lock state must be ON or OFF, got {state!r}")
        self._frequency_lock = text == "ON"

    def get_waveform_catalogue(self):
        return list(self._catalogue)

    def write(self, command, custom_err_message=None):
        text = str(command).strip()
        self.written.append(text)
        match = _OUTPUT.fullmatch(text)
        if match is None:
            raise ValueError(f"the fake implements the output-state commands of the driver, not {text!r}")
        self._output[int(match.group(1))] = match.group(2).upper() in ("ON", "1")
        return len(text)

    def close(self):
        self._closed = True
