"""Fake backend of the APT piezo driver: an in-memory stand-in for interface.module:Module.

Gate G7: every public method defined here exists on ``interface.module:Module`` in
the clone: ``move(position)``, ``zero()`` and ``set_closed_loop(enable)``
(``interface/module.py:29``, ``52``, ``59``). The fake also carries ``max_travel``,
the instance attribute ``Module.__init__`` sets (``interface/module.py:23``). It
starts at zero with closed loop enabled like ``Module.__init__``
(``interface/module.py:25-27``) and clamps travel to ``max_travel`` like ``move``
(``interface/module.py:37-38``). It records only the values the driver sends and
never talks to a device. All numbers here are test data, not device facts.
"""


class FakePiezoModule:
    def __init__(self, max_travel=30.0, **_options):
        self.max_travel = max_travel   # placeholder: a fake configuration value
        self._position = 0.0           # placeholder: the zero position
        self._closed_loop = True       # placeholder: the Module constructor's initial mode

    def move(self, position):
        # the upstream clamps the requested travel to [0, max_travel] (interface/module.py:37-38)
        self._position = max(min(float(self.max_travel), float(position)), 0.0)  # placeholder: zero position

    def zero(self):
        self._position = 0.0

    def set_closed_loop(self, enable):
        self._closed_loop = bool(enable)
