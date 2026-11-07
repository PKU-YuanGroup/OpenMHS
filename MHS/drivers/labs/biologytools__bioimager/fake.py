"""Fake backend of the Cobolt laser driver: an in-memory stand-in for CoboltLaser.

Gate G7: every public member defined here exists on
``PythonMicroscope.microscope.lights.cobolt:CoboltLaser`` and its bases in the clone (``get_is_on``,
``get_status``, ``enable``, ``disable``, ``get_set_power`` and the ``power`` property).  The methods keep the
upstream semantics that the driver relies on: ``get_is_on`` reports emission, ``disable`` turns emission off,
``enable`` turns it on, and the ``power`` property stores a fraction and its set point.  Nothing here imports the
clone or talks to a device.

All numbers below are test data, not limits or facts about any head: they are marked ``# placeholder``.
"""


class FakeCoboltLaser:
    def __init__(self, **_options):
        self._emission = False          # placeholder: fake starts with emission off
        self._power = 0.0               # placeholder: fake measured power fraction
        self._set_power = 0.0           # placeholder: fake power set point fraction

    def get_is_on(self):
        return self._emission

    def get_status(self):
        # The five lines answer the five queries of the upstream get_status (cobolt.py:87-99).
        return [
            "Emission on? " + ("1" if self._emission else "0"),          # placeholder reply
            "Target power: " + f"{self._set_power:.1f}",                  # placeholder reply
            "Measured power: " + f"{self._power if self._emission else 0.0:.1f}",  # placeholder reply
            "Fault? 0",                                                  # placeholder reply
            "Head operating hours: 0",                                   # placeholder reply
        ]

    def enable(self):
        self._emission = True
        return True

    def disable(self):
        self._emission = False

    def get_set_power(self):
        return self._set_power

    @property
    def power(self):
        return self._power if self._emission else 0.0

    @power.setter
    def power(self, value):
        # The upstream LightSource property clips to [0, 1] before calling _do_set_power (abc.py:1237-1244).
        self._power = max(min(float(value), 1.0), 0.0)
        self._set_power = self._power
