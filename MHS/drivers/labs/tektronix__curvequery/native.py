"""Hardware backend: run the upstream curve feature against a Tektronix 4/5/6 Series MSO over PyVISA.

Used only with ``backend="hardware"`` and ``allow_hardware=True``, which is an operator decision.  This package is
model-authored and unreviewed (``driver.lock.json`` ``reviewed_by`` is null) and nothing in it ever ran against an
instrument.  The loader refuses the hardware backend of an unreviewed model-written package at R2 and R3 only; this
package is R0, so that guard does not apply to it and must not be claimed here.

Options of the backend:

* ``resource_name`` (required): the VISA resource name of the oscilloscope, for example
  ``TCPIP::192.168.1.10::INSTR`` (README.md:25-27).

The upstream feature class derives from ``visadore.base.FeatureBase``, which is outside the clone and is not
imported here.  Its ``feature()`` reads only ``self.resource_manager`` and ``self.resource_name``
(curvequery/_tek_series_mso_curve_feat.py:32 and the helper calls), so the factory builds the upstream object and
supplies exactly those two attributes.  A long endpoint keeps one PyVISA resource manager; each ``feature()`` call
opens and closes its own VISA resource, as the clone does.
"""


def connect(resource_name, **_options):
    """Return a ``TekSeriesCurveFeat`` bound to ``resource_name``; import the clone only on the hardware path."""
    import pyvisa
    from curvequery._tek_series_mso_curve_feat import TekSeriesCurveFeat

    feature = object.__new__(TekSeriesCurveFeat)
    feature.resource_manager = pyvisa.ResourceManager()
    feature.resource_name = resource_name
    return feature
