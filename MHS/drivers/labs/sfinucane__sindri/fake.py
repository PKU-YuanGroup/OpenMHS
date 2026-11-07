"""Fake backend of the BERTScope driver: an in-memory stand-in for sindri.tektronix.bertscope:BERTScope_TCP.

Gate G7: every public member defined here is a member of ``BERTScope_TCP`` in the clone
(sindri/tektronix/bertscope.py:464-472, with the Mainframe and Detector features at lines 163-425).  Like the
upstream lantz class, ``idn``, ``is_running`` and ``run_duration`` are Feat-style properties, while the measurements,
``run``, ``stop``, ``reset`` and ``detector_reset_results`` are callable Actions.

The upstream getters return pint Quantities for the temperature, the bit counts and the times; this package does not
depend on pint, so the fake returns the plain magnitudes (the driver accepts both).  The clone has no simulator for
this class, so this file is an in-memory stand-in, not a recording of a session.  Every starting value and the
identity string below is test data, not a fact from the clone or a record of an instrument: each starting value is
marked ``# placeholder``.  The reset methods set the counters to zero, which is the factory-default behavior of the
stand-in.  Nothing here talks to a device.
"""


class FakeBERTScope_TCP:
    """A fresh in-memory BERTScope per endpoint; all starting values are placeholders."""

    def __init__(self, **_options):
        self._idn = "TEKTRONIX,BERTScope,FAKE0000,1.0"   # placeholder
        self._temperature = 31.5                         # placeholder
        self._running = False                            # placeholder
        self._run_duration = 0.0                         # placeholder
        self._bit_count = 1_000_000.0                    # placeholder
        self._error_count = 1_000.0                      # placeholder
        self._bit_error_rate = 0.001                     # placeholder
        self._elapsed_time = 10.0                        # placeholder
        self._resyncs = 3                                # placeholder
        self._error_free_bits = 999_000.0                # placeholder
        self._error_free_time = 9.5                      # placeholder

    # -- lantz Feats ----------------------------------------------------------------------------------------------
    @property
    def idn(self):
        return self._idn

    @property
    def is_running(self):
        return 1 if self._running else 0

    @property
    def run_duration(self):
        return self._run_duration

    @run_duration.setter
    def run_duration(self, value):
        self._run_duration = float(value)

    # -- Actions --------------------------------------------------------------------------------------------------
    def get_internal_temperature(self):
        return self._temperature

    def get_detector_bit_count(self):
        return self._bit_count

    def get_detector_error_count(self):
        return self._error_count

    def get_detector_bit_error_rate(self):
        return self._bit_error_rate

    def get_detector_elapsed_time(self):
        return self._elapsed_time

    def get_detector_resyncs(self):
        return self._resyncs

    def get_detector_error_free_bits_count(self):
        return self._error_free_bits

    def get_detector_error_free_time(self):
        return self._error_free_time

    def run(self):
        self._running = True

    def stop(self):
        self._running = False

    def reset(self):
        # *RST: the factory default power-up state; the detector counters are zeroed too.
        self._running = False
        self._run_duration = 0.0
        self._bit_count = 0.0
        self._error_count = 0.0
        self._bit_error_rate = 0.0
        self._elapsed_time = 0.0
        self._resyncs = 0
        self._error_free_bits = 0.0
        self._error_free_time = 0.0

    def detector_reset_results(self):
        self._bit_count = 0.0
        self._error_count = 0.0
        self._bit_error_rate = 0.0
        self._elapsed_time = 0.0
        self._resyncs = 0
        self._error_free_bits = 0.0
        self._error_free_time = 0.0
