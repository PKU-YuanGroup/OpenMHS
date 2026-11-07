"""Fake serial backend of the GP350 driver: an in-memory stand-in for ``collectors.serial_client:SerialClient``.

Gate G7 checks every public method defined here against the upstream ``SerialClient`` class
(collectors/serial_client.py:8-88): only ``send_command`` and ``close`` are public, and both exist there.  The fake
answers the GP350 commands the clone documents (``DS IG``, ``IGB``, ``DGS``, ``IG1 ON|OFF``, ``IG2 ON|OFF``,
``DG ON|OFF``) with plain test data.  Each number and reply below is marked ``# placeholder``: none of them is a
Fact, a Limit or a reference, and nothing here talks to an instrument.

Fidelity gaps, on purpose:

* the pressure reply is always the same valid reading, also when no filament is on; the real controller answers
  ``9.90E+09`` then (docs/operations/gp350-wiring.md:173-176), and the driver rejects that reply;
* ``DG ON`` always succeeds, also at a pressure at which the real controller answers ``OK`` while ``DGS`` still
  reports degas off (README.md:139);
* setting a switch to the value it already has answers ``INVALID``, like the upstream simulator
  (simulators/simulator.py:365-379); the driver verifies the readback instead of trusting the reply.
"""


class FakeSerialClient:
    """A line client that holds the switch state of one simulated GP350 controller."""

    def __init__(self, **_options):
        self._filament_1 = True                  # placeholder: a running ion gauge has one filament on
        self._filament_2 = False                 # placeholder
        self._degas = False                      # placeholder
        self._pressure_reply = "1.20E-07"        # placeholder: docs/operations/gp350-wiring.md:42
        self._closed = False
        self._commands = []

    # -- public surface of SerialClient ---------------------------------------------------------------
    def send_command(self, command: str) -> str:
        if self._closed:
            raise RuntimeError("serial port is closed")
        text = command.strip()
        self._commands.append(text)

        if text == "DS IG":
            return self._pressure_reply
        if text == "IGB":
            return f"{int(self._filament_2)}{int(self._filament_1)}"
        if text == "DGS":
            return "1" if self._degas else "0"
        if text in ("IG1 ON", "IG1 OFF"):
            return self._set_switch("1", text.endswith("ON"))
        if text in ("IG2 ON", "IG2 OFF"):
            return self._set_switch("2", text.endswith("ON"))
        if text in ("DG ON", "DG OFF"):
            return self._set_switch("D", text.endswith("ON"))
        return "SYNTAX ERROR"                   # placeholder: the clone's syntax-error reply

    def close(self) -> None:
        self._closed = True

    # -- private state helpers (not part of the upstream surface) --------------------------------------
    def _set_switch(self, switch: str, on: bool) -> str:
        if switch == "D":
            current = self._degas
            self._degas = on
        elif switch == "1":
            current = self._filament_1
            self._filament_1 = on
        else:
            current = self._filament_2
            self._filament_2 = on
        return "INVALID" if current == on else "OK"   # placeholder: the upstream simulator's same-state reply
