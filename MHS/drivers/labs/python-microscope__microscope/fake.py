"""Fake backend of the Cobolt laser driver: an in-memory stand-in for microscope.lights.cobolt:CoboltLaser.

Gate G7: every public method and property defined here exists on microscope.lights.cobolt:CoboltLaser (directly or
through its bases, microscope/abc.py and microscope/_utils.py).  The interface follows the upstream class: enable()
is the Device method that sets the enabled flag from _do_enable, disable() is the Cobolt override that only asks for
emission off, get_is_on() reads the emission query, the power property is the LightSource property normalised to the
[0, 1] interval, and get_set_power() returns the set point it stored.  The starting values are test data of this
fake, not facts of any head.  Nothing here talks to a device.
"""


class FakeCoboltLaser:
    """An in-memory laser: emission, the power set point and the measured power, all kept as plain attributes."""

    def __init__(self, **_options):
        self._max_power_mw = 100.0      # placeholder: the head's answer to gmlp?, test data only
        self._set_point = 0.0           # placeholder: power fraction set point
        self._power = 0.0               # placeholder: power fraction the last write asked for
        self._emission = False          # placeholder: the l? answer
        self._enabled = False           # placeholder: the Device.enabled flag
        self._fault = 0                 # placeholder: the f? answer
        self._hours = 0                 # placeholder: the hrs? answer

    # -- the reads the driver makes ----------------------------------------------------------------------------
    def get_is_on(self):
        return self._emission

    def get_is_enabled(self):
        return self._enabled

    def get_status(self):
        # the five status lines of microscope/lights/cobolt.py:86-98, as replies: l?, p?, pa?, f?, hrs?
        return [
            "Emission on? " + ("1" if self._emission else "0"),
            "Target power: %.4f" % (self._set_point * self._max_power_mw / 1000.0),
            "Measured power: %.4f" % (self._get_power_mw() / 1000.0),
            "Fault? %d" % self._fault,
            "Head operating hours: %d" % self._hours,
        ]

    # -- the actuations ------------------------------------------------------------------------------------------
    def enable(self):
        # the Device.enable method: the enabled flag takes the _do_enable result, which turns emission on
        self._enabled = True
        self._emission = True

    def disable(self):
        # the Cobolt disable override: send l0 and return its reply; it leaves the enabled flag alone
        self._emission = False
        return "OK"                     # placeholder: the l0 reply, test data only

    # -- power ---------------------------------------------------------------------------------------------------
    def _get_power_mw(self):
        if not self._emission:
            return 0.0
        return self._power * self._max_power_mw

    @property
    def power(self):
        # the LightSource.power getter: _get_power_mw() / the head's maximum power
        return self._get_power_mw() / self._max_power_mw

    @power.setter
    def power(self, value):
        # the LightSource.power setter: clip to [0, 1], then set the power and the set point
        clipped = max(min(value, 1.0), 0.0)
        self._power = clipped
        self._set_point = clipped

    def get_set_power(self):
        return self._set_point
