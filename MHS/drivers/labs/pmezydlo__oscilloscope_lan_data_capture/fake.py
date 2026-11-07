"""Fake backend of the Rigol DS1000Z package: an in-memory stand-in for oscilloscope_functions:oscilloscope.

The upstream class has no simulator and no recording, so this is an in-memory stand-in.  Gate G7 checks every
public method defined here against the upstream class surface: ``read``, ``write``, ``get_active_channel`` and
``close`` are methods of the clone (the first three through ``measure_interfaces.device``), and the identity and
channel attributes are assigned by the clone's constructors.  The state attributes are private instance data;
the public surface is the upstream method surface.

Every value below is test data, not a fact about an instrument and not a recorded session; each is marked
``# placeholder``.  Nothing here talks to a device.  The transport replies are the exact SCPI queries the clone
sends: ``:TIM:SCAL?`` and ``:TIM:OFFS?`` (oscilloscope_functions.py:26-27), ``:<CHANn>:SCAL?`` and
``:<CHANn>:OFFS?`` (oscilloscope_functions.py:32-33), and ``:<CHANn>:DISP?`` (oscilloscope_functions.py:17).
"""


class FakeOscilloscope:
    """A fresh in-memory DS1000Z per endpoint; all starting values are placeholders."""

    def __init__(self, **_options):
        # The clone's device.__init__ reads *IDN? and splits the reply into these four fields (measure_interfaces.py:144-155).
        self.manufacturer = "RIGOL TECHNOLOGIES"      # placeholder
        self.dev_name = "DS1054Z"                     # placeholder
        self.serial_number = "FAKE000000"             # placeholder
        self.firmware_version = "00.04.04.SP4"        # placeholder
        # oscilloscope.__init__ keeps the configured channel count and an empty active-channel list
        # (oscilloscope_functions.py:10-11).  The clone's example constructor uses four channels (oscilloscope.py:14).
        self.channel = 4                              # placeholder
        self.active_chan = []
        self.queries = []                             # test-only log, not part of the upstream surface
        self.written = []                             # test-only log, not part of the upstream surface

    def read(self, command):
        """The reply to one text query; a query outside the clone's set raises like an unanswered instrument."""
        self.queries.append(command)
        if command == "*IDN?":                        # measure_interfaces.py:144
            return self.manufacturer + "," + self.dev_name + "," + self.serial_number + "," + self.firmware_version + "\n"
        if command == ":TIM:SCAL?":                   # oscilloscope_functions.py:26
            return "0.001\n"                          # placeholder
        if command == ":TIM:OFFS?":                   # oscilloscope_functions.py:27
            return "0.0\n"                            # placeholder
        for index in (1, 2, 3, 4):
            if command == ":" + "CHAN%d" % index + ":DISP?":
                return ("1\n" if index in (1, 3) else "0\n")  # placeholder
            if command == ":" + "CHAN%d" % index + ":SCAL?":
                return "0.5\n"                        # placeholder
            if command == ":" + "CHAN%d" % index + ":OFFS?":
                return "0.0\n"                        # placeholder
        raise TimeoutError("the instrument does not answer " + str(command))

    def write(self, command):
        """Record a text command; the clone writes :WAV:POIN:MODE RAW and :KEY:FORCE (oscilloscope_functions.py:37-39)."""
        self.written.append(command)

    def get_active_channel(self):
        """The clone's loop over the configured channels, keeping those whose display query answers '1\\n'."""
        chan = ["CHAN%d" % index for index in range(1, self.channel + 1)]
        for check_chan in chan:
            if self.read(":" + check_chan + ":DISP?") == "1\n":
                self.active_chan += [check_chan]

    def close(self):
        pass
