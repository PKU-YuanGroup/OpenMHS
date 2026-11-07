"""Fake transport of the OpenCat driver: a small transcript-like stand-in for the serial firmware.

The upstream class is ``serialMaster.SerialCommunication.Communication``, a pyserial wrapper.  This fake exposes the
same public methods (``Send_data``, ``Read_Line``, ``Read_Size``, ``Close_Engine``) and answers the ASCII tokens the
driver sends the way the firmware does: the reply lines first, then the echoed token (``src/reaction.h:511-512``).
No hardware is involved, and every value below is test data, not a device fact.

The replies are the *format* of the firmware, not a recording: the model, firmware string, pitch, roll and joint
angles are placeholders.  The firmware also answers a ``d`` with ``g`` and then ``d``; the driver sends ``d`` without
waiting for it, so the fake keeps the reply and the next read tolerates the extra lines.
"""


class FakeCommunication:
    def __init__(self, **_options):
        self._buffer = b""
        self.sent = []
        self.resting = False
        self.model = "Bittle"          # placeholder
        self.firmware = "N_260806"     # placeholder
        self.pitch = 0.0               # placeholder
        self.roll = 0.0                # placeholder
        self.joints = [0] * 16         # placeholder

    def Send_data(self, data):
        payload = bytes(data)
        self.sent.append(payload)
        command = payload.decode("ascii", "replace").strip()
        if command == "?":
            self._buffer += f"{self.model}\n{self.firmware}\n?\n".encode("ascii")
        elif command == "v":
            self._buffer += f"{self.pitch:.5f}\t{self.roll:.5f}\nv\n".encode("ascii")  # placeholder values
        elif command == "j":
            header = "\t".join(str(index) for index in range(16)) + "\n"  # placeholder table header
            angles = "".join(f"{angle},\t" for angle in self.joints) + "\n"  # placeholder angles
            self._buffer += (header + angles + "j\n").encode("ascii")
        elif command == "d":
            self.resting = True
            self._buffer += b"g\nd\n"

    def Read_Line(self):
        if b"\n" not in self._buffer:
            return b""
        line, _, self._buffer = self._buffer.partition(b"\n")
        return line + b"\n"

    def Read_Size(self, size):
        chunk, self._buffer = self._buffer[:size], self._buffer[size:]
        return chunk

    def Close_Engine(self):
        pass
