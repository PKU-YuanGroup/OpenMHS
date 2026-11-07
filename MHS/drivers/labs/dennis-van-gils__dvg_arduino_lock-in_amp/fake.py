"""Fake backend of the Alia driver: an in-memory stand-in for Alia_protocol_serial:Alia.

Gate G7: every public method here exists on ``Alia`` (query_ref, query_ADC_autocalibration, set_ref, turn_on and
turn_off; Alia_protocol_serial.py:394-457, 534-570, 661-845), and ``config``/``lockin_paused`` are set by the upstream
__init__ (Alia_protocol_serial.py:161-162).  The methods mirror the upstream signatures, including
``turn_off() -> (success, was_off, answer_bytes)`` and ``set_ref(waveform=None, freq=None, V_offset=None, ...)``.

The starting values are test data, not facts about any device; every one is marked ``# placeholder``.  The fake mimics
the firmware's positive clamps, its N_LUT frequency quantization and its clipping flags (main.cpp:332-340, 374-398),
so a write has an observable effect.  Nothing here talks to a device.
"""

import math
from enum import Enum


class _Waveform(Enum):
    """The upstream Waveform names and values (Alia_protocol_serial.py:42-48); only the name is used here."""

    Unknown = -1
    Sine = 0
    Square = 1
    Triangle = 2


class _FakeConfig:
    """The attributes ``Alia.config`` publishes that this driver reads (Alia_protocol_serial.py:56-137)."""

    def __init__(self):
        self.ref_waveform = _Waveform.Square          # placeholder
        self.ref_freq = 250.0                         # placeholder
        self.ref_V_offset = 1.5                       # placeholder
        self.ref_V_ampl = 0.8                         # placeholder
        self.ref_V_ampl_RMS = 0.8                     # placeholder (Square keeps RMS equal to the peak)
        self.ref_is_clipping_HI = False
        self.ref_is_clipping_LO = False
        self.ADC_autocal_is_valid = True              # placeholder
        self.ADC_autocal_gaincorr = 0                 # placeholder
        self.ADC_autocal_offsetcorr = 0               # placeholder
        self.Fs = 25000.0                             # placeholder
        self.BLOCK_SIZE = 100                         # placeholder
        self.A_REF = 3.3                              # placeholder


class FakeAlia:
    def __init__(self, **_options):
        self.config = _FakeConfig()
        self.lockin_paused = True

    # -- reads ----------------------------------------------------------------------------------------------------
    def query_ref(self):
        return True

    def query_ADC_autocalibration(self):
        return True

    # -- writes ---------------------------------------------------------------------------------------------------
    def set_ref(self, waveform=None, freq=None, V_offset=None, V_ampl=None, V_ampl_RMS=None):
        config = self.config
        if waveform is not None:
            config.ref_waveform = waveform
            config.ref_V_ampl = config.ref_V_ampl_RMS * self._rms_factor()
        if freq is not None:
            value = float(freq)
            if value > 0:
                n_lut = round(config.Fs / value)
                n_lut = max(20, min(1000, n_lut))            # placeholder: firmware LUT bounds
                config.ref_freq = config.Fs / n_lut
            else:
                config.ref_freq = 0.0
        if V_offset is not None:
            config.ref_V_offset = max(float(V_offset), 0.0)
        if V_ampl is not None:
            config.ref_V_ampl = max(float(V_ampl), 0.0)
            config.ref_V_ampl_RMS = config.ref_V_ampl / self._rms_factor()
        if V_ampl_RMS is not None:
            config.ref_V_ampl_RMS = max(float(V_ampl_RMS), 0.0)
            config.ref_V_ampl = config.ref_V_ampl_RMS * self._rms_factor()
        config.ref_is_clipping_LO = config.ref_V_offset - config.ref_V_ampl < 0.0
        config.ref_is_clipping_HI = config.ref_V_offset + config.ref_V_ampl > config.A_REF
        return True

    # -- acquisition ----------------------------------------------------------------------------------------------
    def turn_on(self, reset_timer=False):
        self.lockin_paused = False
        return True

    def turn_off(self, raises_on_timeout=False):
        was_off = self.lockin_paused
        self.lockin_paused = True
        answer = b"already_off\n" if was_off else b"off\n"
        return True, was_off, answer

    # -- helpers --------------------------------------------------------------------------------------------------
    def _rms_factor(self):
        name = getattr(self.config.ref_waveform, "name", "Sine")
        if name == "Square":
            return 1.0
        if name == "Triangle":
            return math.sqrt(3.0)
        return math.sqrt(2.0)
