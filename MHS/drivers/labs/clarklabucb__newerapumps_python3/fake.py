"""Fake serial chain of the New Era NE-500 driver: a pyserial-like handle that answers the protocol of new_era3.py.

The upstream ``PumpControl`` class stores the open pyserial handle in ``self.ser`` (pump_control3.py:23); this fake
stands in for that handle.  The driver calls ``FakeNewEraPump.ser()`` and then only the pyserial methods ``write``,
``readline`` and ``close`` on the returned link, so the public surface of the fake is the upstream attribute name
``ser`` and nothing else.  The link parses the upstream commands from the parts the driver builds: ``<n>DIRINF`` /
``<n>DIRWDR``, ``<n>RAT<value>UH|MH``, ``<n>RAT``, ``<n>DIA<mm>``, ``<n>DIA``, ``<n>RUN``, ``<n>STP`` and the
broadcast ``*STP``.  A query replies in the layout ``get_rate`` and ``get_diameter`` read (new_era3.py:68-97,
118-124): ``<n>RA<T|W><value><UH|MH>`` for a rate and ``<n>DIA<value>`` for a diameter.  An unknown command, or a
command for another address of the chain, gets no reply, and a reply is never a ``?`` unless the command is unknown.

Nothing here talks to an instrument.  The numbers below are test data (start rate, start diameter, start address),
marked ``# placeholder``; they are not facts or limits of the device.
"""


class _FakeLink:
    """One pyserial-like handle of the fake chain, addressed like one pump."""

    def __init__(self, address):
        self.address = address                 # placeholder
        self.flow_rate = 0.0                   # placeholder: absolute set point in uL/hour
        self.direction = "INF"                 # placeholder
        self.diameter = 4.699                  # placeholder: mm
        self.running = False                   # placeholder
        self.written = []
        self._pending = []

    # -- pyserial surface -----------------------------------------------------------------------------------------
    def write(self, data):
        if isinstance(data, str):
            text = data
        else:
            text = bytes(data).decode("ascii", "replace")
        text = text.strip("\r\n")
        self.written.append(text)
        self._answer(text)

    def readline(self):
        if not self._pending:
            return b""                         # no reply, as an unaddressed pump of the chain would give
        return self._pending.pop(0)

    def close(self):
        pass

    # -- protocol -------------------------------------------------------------------------------------------------
    def _answer(self, text):
        if not text:
            return
        if text.startswith("*"):
            command = text[1:]
            if command == "STP":
                self.running = False
                self._pending.append((text + "\r").encode("ascii"))
            elif command == "RUN":
                self.running = True
                self._pending.append((text + "\r").encode("ascii"))
            else:
                self._pending.append(b"?\r")
            return
        if not text[0].isdigit():
            self._pending.append(b"?\r")
            return
        address = int(text[0])
        if address != self.address:
            return
        body = text[1:]
        if body.startswith("DIR"):
            direction = body[3:]
            if direction not in ("INF", "WDR"):
                self._pending.append(b"?\r")
                return
            self.direction = direction
            self._pending.append((text + "\r").encode("ascii"))
            return
        if body.startswith("RAT"):
            argument = body[3:]
            if not argument:
                self._pending.append(self._rate_reply(address))
                return
            if argument.endswith("UH"):
                self.flow_rate = float(argument[:-2])
            elif argument.endswith("MH"):
                self.flow_rate = float(argument[:-2]) * 1000.0
            else:
                self._pending.append(b"?\r")
                return
            self._pending.append((text + "\r").encode("ascii"))
            return
        if body.startswith("DIA"):
            argument = body[3:]
            if not argument:
                self._pending.append(f"{address}DIA{self.diameter:g}\r".encode("ascii"))
                return
            self.diameter = float(argument)
            self._pending.append((text + "\r").encode("ascii"))
            return
        if body == "RUN":
            self.running = True
            self._pending.append((text + "\r").encode("ascii"))
            return
        if body == "STP":
            self.running = False
            self._pending.append((text + "\r").encode("ascii"))
            return
        self._pending.append(b"?\r")

    def _rate_reply(self, address):
        letter = "W" if self.direction == "WDR" else "T"
        if self.flow_rate >= 5000:
            value, unit = self.flow_rate / 1000.0, "MH"
        else:
            value, unit = self.flow_rate, "UH"
        return f"{address}RA{letter}{value:g}{unit}\r".encode("ascii")


class FakeNewEraPump:
    """The fake backend object: the upstream PumpControl's ``ser`` attribute as a method returning the link."""

    def __init__(self, **options):
        address = int(options.get("address", 0))   # placeholder: pump 0 of the chain
        self._link = _FakeLink(address)

    def ser(self):
        return self._link
