"""Fake backend of the Hantek driver: an in-memory stand-in for pyhantek6022BE:Hantek.

Gate G7: every public method defined here exists on the upstream class (GetData, get_rate, set_samplerate,
set_chvdiv, SetSampleRate, SetVDiv and close), and the one attribute the driver reaches, ChVDiv, is set by the
upstream __init__ (pyhantek6022BE.py:80).  The samplerate and vertical-division tables are the upstream ones
(pyhantek6022BE.py:77-78, 83-86), so the fake accepts and refuses the same values.  The data-length table is the
upstream one too (pyhantek6022BE.py:91-94).

All other numbers below are placeholder test data, not facts: the fake returns 512 samples per channel instead of
the real buf_len = dictDatLen_N[samplerate] // 2 (131072 at the default 16 MS/s, pyhantek6022BE.py:91-97).  The
trace is a deterministic pattern so state reads are reproducible.  close() marks the fake closed but keeps the
last acquisition available, so a state read after an e-stop can still be served; a real released device would
not.  Nothing here talks to a device.
"""

# The voltage conversion below is the upstream one, not a bound: (raw - 128) / 255 * 10 * V/div
# (pyhantek6022BE.py:171-172).
_FAKE_SAMPLES = 512  # placeholder: real acquisitions are buf_len samples per channel


class FakeHantek6022be:
    def __init__(self, **_options):
        # Upstream tables (pyhantek6022BE.py:77-78, 83-86, 91-94); accepted values, not test data.
        self.dictVDiv_N = {1: 1, 2: 0.5, 5: 0.2, 10: 0.1}
        self.dictN_VDiv = dict(map(reversed, self.dictVDiv_N.items()))
        self.ChVDiv = [1, 1]  # placeholder: the upstream default (pyhantek6022BE.py:80)
        self.dictSR_N = {48: 48_000_000, 16: 16_000_000, 8: 8_000_000,
                         4: 4_000_000, 1: 1_000_000, 50: 500_000,
                         20: 200_000, 10: 100_000}
        self.dictN_SR = dict(map(reversed, self.dictSR_N.items()))
        self.samplerate = 16_000_000  # placeholder: the upstream default (pyhantek6022BE.py:88)
        self.dictDatLen_N = {48_000_000: 2097152, 16_000_000: 262144,
                             8_000_000: 262144, 4_000_000: 262144,
                             1_000_000: 262144, 500_000: 1048576,
                             200_000: 1048576, 100_000: 1048576}
        self.data_len = self.dictDatLen_N[self.samplerate]
        self.buf_len = self.data_len // 2
        self._closed = False
        self._close_calls = 0

    def GetData(self):
        ch1, ch2 = [], []
        for index in range(_FAKE_SAMPLES):
            raw1 = index % 256                       # placeholder test pattern
            raw2 = (index * 3 + 64) % 256            # placeholder test pattern
            ch1.append((raw1 - 128.) / 255. * 10. * self.ChVDiv[0])
            ch2.append((raw2 - 128.) / 255. * 10. * self.ChVDiv[1])
        return [ch1, ch2]

    def get_rate(self):
        return self.samplerate

    def set_samplerate(self, rate):
        if rate in self.dictN_SR:
            self.samplerate = rate
            self.data_len = self.dictDatLen_N[self.samplerate]
            self.buf_len = self.data_len // 2
            self.SetSampleRate()

    def set_chvdiv(self, chvdiv):
        for index in range(len(chvdiv)):
            if chvdiv[index] in self.dictN_VDiv:
                self.ChVDiv[index] = chvdiv[index]
        self.SetVDiv()

    def SetSampleRate(self):
        self._last_sample_rate_code = self.dictN_SR[self.samplerate]  # placeholder: not used by the driver

    def SetVDiv(self):
        self._last_vdiv_code = [self.dictN_VDiv[item] for item in self.ChVDiv]  # placeholder: not used

    def close(self):
        self._closed = True
        self._close_calls += 1
