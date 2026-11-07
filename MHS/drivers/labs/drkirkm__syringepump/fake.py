"""Recording fake backend of the Harvard Apparatus OEM syringe-pump driver.

The clone has no simulator and no recorded exchange, and the protocol is write-only (the upstream never reads a
reply), so this is a recording stand-in for the upstream ``Pumps`` GUI handlers rather than a transcript.  Each
button method builds the same bytes as its upstream counterpart from the corresponding Qt line edit and appends
them to ``written``.  The class defines only public methods that exist on the upstream class
(``pumpcontroller.py:228-389``), so gate G7 can read the surface against the clone.

Every starting value and recorded line below is test data, not a fact about a pump; the state is held in the
private helpers and in instance data.  Nothing here opens a serial port or talks to a device.
"""


class _FakeLineEdit:
    """The small part of a Qt line edit the upstream handlers use: ``text`` and ``setText``."""

    def __init__(self):
        self._text = ""                                                     # placeholder

    def text(self):
        return self._text

    def setText(self, text):
        self._text = str(text)


class FakePumps:
    """Stand-in for ``pumpcontroller:Pumps``: the button handlers record the bytes they would write."""

    def __init__(self, **_options):
        self.lineEdit1 = _FakeLineEdit()                                    # placeholder
        self.lineEdit2 = _FakeLineEdit()                                    # placeholder
        self.lineEdit3 = _FakeLineEdit()                                    # placeholder
        self.lineEdit4 = _FakeLineEdit()                                    # placeholder
        self.lineEdit5 = _FakeLineEdit()                                    # placeholder
        self.lineEdit6 = _FakeLineEdit()                                    # placeholder
        #: Every line the would-be port received, in order.
        self.written = []

    # -- one private recorder (not part of the upstream surface) ---------------------------------------------------
    def _write(self, *lines):
        self.written.extend(bytes(line) for line in lines)

    # -- address 00 (unprefixed commands) -------------------------------------------------------------------------
    def diambuttonClicked(self):
        self._write(b"MMD " + self.lineEdit2.text().encode("ascii") + b"\r")

    def sfrbuttonClicked(self):
        self._write(b"MLH " + self.lineEdit1.text().encode("ascii") + b"\r")

    def runbuttonClicked(self):
        self._write(b"RUN\r")

    def stopbuttonClicked(self):
        self._write(b"STP\r")

    # -- address 01 (01-prefixed commands) ------------------------------------------------------------------------
    def diam2buttonClicked(self):
        self._write(b"01MMD " + self.lineEdit3.text().encode("ascii") + b"\r")

    def mlh2buttonClicked(self):
        self._write(b"01MLH " + self.lineEdit4.text().encode("ascii") + b"\r")

    def run2buttonClicked(self):
        self._write(b"01RUN\r")

    def stop2buttonClicked(self):
        self._write(b"01STP\r")

    # -- address 02 (02-prefixed commands) ------------------------------------------------------------------------
    def diam3buttonClicked(self):
        self._write(b"02MMD " + self.lineEdit6.text().encode("ascii") + b"\r")

    def mlh3buttonClicked(self):
        self._write(b"02MLH " + self.lineEdit5.text().encode("ascii") + b"\r")

    def run3buttonClicked(self):
        self._write(b"02RUN\r")

    def stop3buttonClicked(self):
        self._write(b"02STP\r")

    # -- stop all three addresses ---------------------------------------------------------------------------------
    def stopallbuttonClicked(self):
        self._write(b"STP\r", b"01STP\r", b"02STP\r")
