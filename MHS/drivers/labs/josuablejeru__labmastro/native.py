"""Hardware transport factory for the Hanmatek HM supply (imported only for a reviewed hardware backend).

The acceptance gate never imports this module, and the TagDriver refuses the
hardware backend until a human signs ``reviewed_by`` with scope ``hardware`` in
driver.lock.json. ``connect`` builds a minimalmodbus RTU instrument with the
upstream's line settings (labmastro/power_supply/hanmatek/hm/instrument.py:15-28)
and adapts it to the TagBridge transport interface:

* ``read_point`` reads holding/input registers (function 3/4) or a coil/discrete
  bit (function 1/2) and returns a list of words or ``[bool]``;
* ``write_point`` writes one holding register (function 6) or one coil
  (function 5) and returns ``True`` only after minimalmodbus validated the
  slave's echo.

Outcome mapping. Only a slave exception that states the request was not
executed (Modbus exception codes 1, 2 and 3: illegal function, address or value)
becomes ``TagRefused`` (no effect). minimalmodbus is expected to raise
``IllegalRequestError`` for exactly those codes; that name is NOT verified here
(no minimalmodbus source is in this workspace; the upstream pins version 2.1.1
in poetry.lock lines 403-404), and when the installed library has no such class
nothing is mapped. Every other exception, including slave device failure (4),
acknowledge (5) and busy (6), a timeout or a bad echo, propagates: the bridge
treats it as an unknown outcome and fences further effects until a confirmed
stop. A request that never left because the bus stayed busy is refused here.

Bus wait. One lock serializes the bus. A stop waits for it at most its own
``timeout_s``; if an ordinary request holds the bus for its whole timeout, the
stop's first attempt is refused (nothing sent) and the server retries the stop.

The reviewer must, before signing: confirm the installed minimalmodbus version
and its ``IllegalRequestError`` class and codes, run this against the supply
under supervision, and check how the supply handles a request whose reply is
lost.
"""

import threading

from mhs.bridge.tags import TagRefused

#: The upstream instrument's serial line settings (instrument.py:24-28): 9600 baud, 8N1, 1 s timeout.
BAUDRATE, BYTESIZE, STOPBITS = 9600, 8, 1


def connect(port, unit=1, **_options):
    """Open the operator's serial port as a Modbus RTU master for slave ``unit`` (upstream default 1)."""
    import minimalmodbus  # vendor library: imported only here, at hardware time

    instrument = minimalmodbus.Instrument(str(port), int(unit), mode=minimalmodbus.MODE_RTU)
    instrument.serial.baudrate = BAUDRATE
    instrument.serial.bytesize = BYTESIZE
    instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
    instrument.serial.stopbits = STOPBITS
    instrument.clear_buffers_before_each_transaction = True
    return MinimalModbusTransport(instrument, minimalmodbus)


class MinimalModbusTransport:
    """One serial bus: requests are serialized with a bounded wait (a busy bus refuses before sending)."""

    def __init__(self, instrument, library):
        self._instrument = instrument
        # Only "not executed" slave exceptions (codes 1-3) mean no effect; see the module docstring.
        self._not_executed = getattr(library, "IllegalRequestError", ())
        self._lock = threading.Lock()

    def _bus(self, timeout_s):
        if not self._lock.acquire(timeout=max(0.0, float(timeout_s))):
            raise TagRefused("the serial bus stayed busy; the request was not sent", code="busy")
        try:
            self._instrument.serial.timeout = float(timeout_s)
        except BaseException:
            self._lock.release()       # never keep the bus after a failed reconfiguration
            raise

    def read_point(self, request, *, timeout_s):
        self._bus(timeout_s)
        try:
            table, register, words = request["table"], request["register"], request["words"]
            if table in ("holding", "input"):
                code = 3 if table == "holding" else 4
                return list(self._instrument.read_registers(register, words, functioncode=code))
            code = 1 if table == "coil" else 2
            return [bool(self._instrument.read_bit(register, functioncode=code))]
        except self._not_executed as exc:
            raise TagRefused(str(exc), code="illegal-request") from exc
        finally:
            self._lock.release()

    def write_point(self, request, raw, *, timeout_s):
        self._bus(timeout_s)
        try:
            table, register = request["table"], request["register"]
            if table == "holding":
                self._instrument.write_register(register, int(raw[0]), number_of_decimals=0, functioncode=6,
                                                signed=False)
            elif table == "coil":
                self._instrument.write_bit(register, 1 if raw else 0, functioncode=5)
            else:
                raise TagRefused(f"{table} registers are read-only", code="read-only")
            return True
        except self._not_executed as exc:
            raise TagRefused(str(exc), code="illegal-request") from exc
        finally:
            self._lock.release()

    def close(self):
        self._instrument.serial.close()
