"""Fake backend of the CLSLab:Light driver: an in-memory stand-in for host_nonwireless:Talker.

Gate G7: every public method defined here exists on the upstream class
(``extra/nonwireless/lib/host_nonwireless.py:6-27``): ``send``, ``receive`` and ``close``.  The fake answers the two
text commands the host helper sends (``src/self_driving_lab_demo/utils/observe.py:373-382``) and keeps the LED color
and the queued sensor reply in memory.  Every number below is test data, not a fact about the device; nothing here
talks to hardware or imports the upstream package.
"""


class FakeTalker:
    def __init__(self, **_options):
        self._color = [0, 0, 0]      # placeholder: the firmware's startup sequence ends with the LED off
        self._pending = []
        self._closed = False

    def send(self, text):
        if self._closed:
            raise RuntimeError("the fake serial link is closed")
        if text.startswith("set_color("):
            parts = [part.strip() for part in text[text.index("(") + 1:text.rindex(")")].split(",")]
            if len(parts) != 3:
                raise ValueError(f"set_color needs three arguments, got {text!r}")
            self._color = [int(part) for part in parts]      # placeholder: the fake stores the bytes as given
            return None
        if text.startswith("read_sensor("):
            parts = [part.strip() for part in text[text.index("(") + 1:text.rindex(")")].split(",")]
            if len(parts) != 3:
                raise ValueError(f"read_sensor needs three arguments, got {text!r}")
            astep, atime, gain = int(parts[0]), int(parts[1]), float(parts[2])
            self._pending.append(repr(self._spectrum(astep, atime, gain)))
            return None
        raise ValueError(f"the fake does not know the command {text!r}")

    def receive(self):
        if not self._pending:
            raise ValueError("the fake has no reply queued")
        return self._pending.pop(0)

    def close(self):
        self._closed = True

    def _spectrum(self, astep, atime, gain):
        # placeholder: synthetic channel counts, not a recording of the AS7341
        scale = (astep + 1) * (atime + 1) * gain / 1000.0
        red, green, blue = self._color
        level = 1.0 + red + green + blue
        weights = (0.20, 0.35, 0.55, 0.75, 1.00, 1.15, 1.30, 1.45)      # placeholder
        return [int(scale * level * weight) for weight in weights]
