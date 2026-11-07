"""Fake backend of the curvequery driver: an in-memory stand-in for ``TekSeriesCurveFeat``.

Gate G7: the only public method defined here is ``feature``, which is the one public method of
``curvequery._tek_series_mso_curve_feat:TekSeriesCurveFeat`` in the clone.  The returned collection copies the
shape of the clone's ``api_types``: ``WaveformCollection.sources`` is the key list of ``data``, and each
``Waveform`` is a namedtuple of ``data``, ``x_scale`` and ``y_scale`` (api_types.py:4-7, 31-44).

The clone has no object-level simulator: its tests address a real instrument through Visadore and PyVISA
(test/conftest.py:2, 46-53), so this file is an in-memory stand-in, not a recording or a transcript.  Every number
below is test data, not a device fact: each is marked ``# placeholder`` and none is copied into a Fact, a Limit or
a reference.  The arrays are deliberately short stand-ins; the real record length is the instrument's
``horizontal:recordlength?`` reply (curve_feat.py:149, 171-173).  Nothing here talks to an instrument.
"""

from collections import namedtuple

_XScale = namedtuple("XScale", "slope offset unit")
_YScale = namedtuple("YScale", "top bottom")
_Waveform = namedtuple("Waveform", "data x_scale y_scale")

#: Test horizontal scale shared by the fake sources.
_X_SCALE = _XScale(slope=1e-06, offset=-5e-06, unit="s")  # placeholder
#: Test vertical window of the analog source.
_Y_SCALE = _YScale(top=1.5, bottom=-1.5)  # placeholder
#: Test analog samples.
_ANALOG_SAMPLES = [0.0, 0.5, 1.0, 0.5, 0.0, -0.5]  # placeholder
#: Test digital bit samples for the decomposed source.
_DIGITAL_SAMPLES = [0, 1, 1, 0, 1, 0]  # placeholder
#: Test 8-bit word samples for the undecomposed source.
_WORD_SAMPLES = [0, 3, 7, 3, 1, 0]  # placeholder


class _Collection:
    """Copy of the clone's WaveformCollection surface used by the driver (api_types.py:31-44)."""

    def __init__(self):
        self.idn = None
        self.data = {}

    @property
    def sources(self):
        return list(self.data.keys())

    def __getitem__(self, item):
        return self.data[item]

    def __len__(self):
        return len(self.data.keys())


class FakeCurveFeature:
    """A fresh in-memory curve feature per endpoint; all values are placeholders, not a recording."""

    def __init__(self, **_options):
        pass

    def feature(self, *, use_pbar=True, decompose_dch=True, verbose=False):
        """Return the same collection shape the clone's feature() builds (curve_feat.py:20-46)."""
        collection = _Collection()
        collection.data["CH1"] = _Waveform(list(_ANALOG_SAMPLES), _X_SCALE, _Y_SCALE)
        if decompose_dch:
            collection.data["CH2_D0"] = _Waveform(list(_DIGITAL_SAMPLES), _X_SCALE, None)
        else:
            collection.data["CH2"] = _Waveform(list(_WORD_SAMPLES), _X_SCALE, None)
        return collection
