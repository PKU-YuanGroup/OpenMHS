"""Fake backend of the Newport 1918-C driver: an in-memory stand-in for newport_1918c:Newport_1918c.

Gate G7: every public method defined here exists on the upstream class (newport_1918c.py:21): ``ask`` (99-127),
``write`` (129-148), ``set_wavelength`` (150-162), ``read_instant_power`` (210-219) and ``close_device`` (68-79).
The instance attributes ``serial_number`` and ``model_number`` are assigned by the upstream constructor
(newport_1918c.py:35).  The signatures mirror the upstream ones: ask(query_string), write(command_string),
set_wavelength(wavelength) and read_instant_power(wavelength=700).

Every value below is test data of this stand-in, not a device fact, and each one is marked ``# placeholder``.  The
class does not derive from Newport_1918c and never imports the clone or a DLL (G3 FAKE_IS_NATIVE).
"""


class FakeNewport1918c:
    def __init__(self, **_options):
        self.serial_number = "FAKE1918"      # placeholder: test data of this stand-in
        self.model_number = "1918-C"         # placeholder: test data of this stand-in
        self._wavelength = 700               # placeholder: the upstream read_instant_power default, test data
        self._power = 1.234e-06              # placeholder: test data, not a measurement of any device
        self._closed = False
        self._queries = {
            "PM:Lambda?": lambda: str(self._wavelength),
            "PM:Power?": lambda: f"{self._power:.6e}",
            "PM:MIN:Lambda?": lambda: "400",     # placeholder: test data of this stand-in
            "PM:MAX:Lambda?": lambda: "1100",    # placeholder: test data of this stand-in
        }

    def ask(self, query_string):
        """Answer a query as the instrument's ASCII reply (upstream ask, newport_1918c.py:99-127)."""
        try:
            answer = self._queries[query_string]
        except KeyError:
            raise ValueError(f"this stand-in has no reply for query {query_string!r}") from None
        return answer()

    def write(self, command_string):
        """Apply a command string (upstream write, newport_1918c.py:129-148)."""
        if command_string.startswith("PM:Lambda "):
            self._wavelength = int(float(command_string.split(" ", 1)[1]))

    def set_wavelength(self, wavelength):
        """Store the wavelength in whole nanometres (upstream set_wavelength, newport_1918c.py:150-162)."""
        self._wavelength = int(wavelength)

    def read_instant_power(self, wavelength=700):
        """Set the wavelength and return the two replies (upstream line 210-219)."""
        self.set_wavelength(wavelength)
        return [self.ask("PM:Lambda?"), self.ask("PM:Power?")]

    def close_device(self):
        """Close the stand-in (upstream close_device, newport_1918c.py:68-79)."""
        self._closed = True
