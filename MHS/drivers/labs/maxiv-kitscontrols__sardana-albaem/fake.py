"""Fake backend of the ALBA EM2 driver: an in-memory stand-in for sardana_albaem.ctrl.em2:Em2.

Gate G7: every public method and property defined here exists on the upstream ``Em2`` class: the SCPI ``command``
method (sardana_albaem/ctrl/em2.py:181-185), the acquisition, trigger and timestamp properties
(em2.py:187-287), and the three acquisition methods (em2.py:289-297).  The driver reaches the per-channel settings
through ``command`` with the same CHANxx:* strings the upstream ``Channel`` class uses (em2.py:51-82), so this fake
answers those strings and nothing else.

The starting values are test data of this stand-in, not device facts; each one is marked ``# placeholder`` and none
is copied into a Fact, a Limit or the reference.  The values never move by themselves, so reading the state twice
gives the same state.  Nothing here talks to an electrometer.
"""


class FakeEm2:
    def __init__(self, **_options):
        self._idn = "FAKE,ALBAEM2,0,0.0.0"             # placeholder test data
        self._state = "ON"                             # placeholder test data
        self._acquisition_mode = "CURRENT"             # placeholder test data
        self._acquisition_time_s = 0.01                # placeholder test data
        self._nb_points = 100                          # placeholder test data
        self._nb_points_ready = 0                      # placeholder test data
        self._trigger_mode = "SOFTWARE"                # placeholder test data
        self._trigger_input = "TRIGGER_IN"             # placeholder test data
        self._trigger_polarity = "POSITIVE"            # placeholder test data
        self._trigger_precision = False                # placeholder test data
        self._trigger_delay_s = 0.0                    # placeholder test data
        self._timestamp_data = False                   # placeholder test data
        self._current = [1.0e-9, 2.0e-9, 3.0e-9, 4.0e-9]   # placeholder test data
        self._range = ["1uA", "1uA", "1uA", "1uA"]         # placeholder test data
        self._inversion = [False, False, False, False]     # placeholder test data

    # -- identification and acquisition state ----------------------------------------------------------------
    @property
    def idn(self):
        return self._idn

    @property
    def acquisition_state(self):
        return self._state

    @property
    def acquisition_mode(self):
        return self._acquisition_mode

    @acquisition_mode.setter
    def acquisition_mode(self, value):
        self._acquisition_mode = str(value)

    @property
    def acquisition_time(self):
        return self._acquisition_time_s

    @acquisition_time.setter
    def acquisition_time(self, value):
        self._acquisition_time_s = float(value)

    @property
    def nb_points(self):
        return self._nb_points

    @nb_points.setter
    def nb_points(self, value):
        self._nb_points = int(value)

    @property
    def nb_points_ready(self):
        return self._nb_points_ready

    # -- trigger and timestamp settings ------------------------------------------------------------------------
    @property
    def trigger_input(self):
        return self._trigger_input

    @trigger_input.setter
    def trigger_input(self, value):
        self._trigger_input = str(value)

    @property
    def trigger_mode(self):
        return self._trigger_mode

    @trigger_mode.setter
    def trigger_mode(self, value):
        self._trigger_mode = str(value)

    @property
    def trigger_polarity(self):
        return self._trigger_polarity

    @trigger_polarity.setter
    def trigger_polarity(self, value):
        self._trigger_polarity = str(value)

    @property
    def trigger_precision(self):
        return self._trigger_precision

    @trigger_precision.setter
    def trigger_precision(self, value):
        self._trigger_precision = bool(value)

    @property
    def trigger_delay(self):
        return self._trigger_delay_s

    @trigger_delay.setter
    def trigger_delay(self, value):
        self._trigger_delay_s = float(value)

    @property
    def timestamp_data(self):
        return self._timestamp_data

    @timestamp_data.setter
    def timestamp_data(self, value):
        self._timestamp_data = bool(value)

    # -- the SCPI command path used for the channels -----------------------------------------------------------
    def command(self, cmd):
        text = str(cmd).strip()
        head, _, rest = text.partition(":")
        if not head.startswith("CHAN") or len(head) != 6:
            raise ValueError(f"fake Em2 does not implement {text!r}")
        index = int(head[4:]) - 1
        if index < 0 or index > 3:
            raise ValueError(f"fake Em2 has no channel in {text!r}")
        if rest == "INSC?":
            return repr(self._current[index])
        if rest == "CABO:RANGE?":
            return self._range[index]
        if rest == "CABO:INVE?":
            return "On" if self._inversion[index] else "Off"
        if rest.startswith("CABO:RANGE "):
            self._range[index] = rest[len("CABO:RANGE "):]
            return ""
        if rest.startswith("CABO:INVE "):
            self._inversion[index] = rest[len("CABO:INVE "):] == "On"
            return ""
        raise ValueError(f"fake Em2 does not implement {text!r}")

    # -- acquisition actions -----------------------------------------------------------------------------------
    def start_acquisition(self, soft_trigger=True):
        self._state = "RUNNING"          # placeholder test data
        self._nb_points_ready = 0        # placeholder test data

    def stop_acquisition(self):
        self._state = "ON"               # placeholder test data

    def software_trigger(self):
        self._nb_points_ready += 1       # placeholder test data
        return ""
