"""Fake backend of the Thorlabs MCM3000 driver: an in-memory stand-in for thorlabs_MCM3000:Controller.

Gate G7: every public method defined here exists on the upstream class in the clone: ``get_position_um``,
``move_um`` and ``close`` (thorlabs_MCM3000.py:179-201).  The driver reaches ``channels`` and the private ``_send``
frame writer, both of which the upstream class defines (thorlabs_MCM3000.py:45-54, 62-75); the fake's ``_send``
answers the framed commands of the clone (the 0A 04 position query, the 53 04 move and the 65 04 vendor stop) so
the recorded wire bytes are the clone's.

The conversion factors, starting positions and travel are test data, each marked ``# placeholder``; they are not
facts about a stage.  The fake moves instantly and does not model motion over time, the encoder quantisation,
reversed axes, the 5 s serial timeout or the controller's one-count tolerance.  Nothing here talks to a device.
"""

#: The framed commands of the upstream class (thorlabs_MCM3000.py:97-102, 135-138) and of the vendor protocol
#: (MCM3000_Direct_Serial_Communication.pdf:2).
_QUERY_HEADER = b"\x0a\x04"
_MOVE_HEADER = b"\x53\x04\x06\x00\x00\x00"
_SET_ZERO_HEADER = b"\x09\x04\x06\x00\x00\x00"
_STOP_HEADER = b"\x65\x04"


class FakeMcm3000:
    def __init__(self, **_options):
        self.name = "MCM3000"
        self.channels = (0, 1, 2)
        self.position_um = [0.0, 0.0, 0.0]                 # placeholder start positions
        self._um_per_count = [0.5, 0.5, 0.5]               # placeholder conversion factors
        self._counts = [0, 0, 0]                            # placeholder encoder counts
        self.received = []                                  # test data: the bytes the fake answered
        self.closed = False

    # -- the upstream public surface the driver uses --------------------------------------------------------------
    def get_position_um(self, channel):
        self._get_encoder_counts(channel)
        return self.position_um[channel]

    def move_um(self, channel, move_um, relative=True, block=True):
        if relative:
            self._get_encoder_counts(channel)
            move_um += self.position_um[channel]
        counts = int(round(move_um / self._um_per_count[channel]))
        self._move_to_encoder_count(channel, counts, block)
        return self.position_um[channel]

    def close(self):
        self.closed = True

    # -- the framed protocol of the clone -------------------------------------------------------------------------
    def _send(self, cmd, channel, response_bytes=None):
        assert channel in self.channels
        self.received.append(bytes(cmd))
        if cmd[:2] == _QUERY_HEADER:
            count = int(self._counts[channel]).to_bytes(4, "little", signed=True)
            return b"\x0a\x04\x00\x00\x06\x00" + bytes([channel]) + b"\x00" + count
        if cmd[:6] == _MOVE_HEADER:
            target = int.from_bytes(cmd[6:8], "little")
            assert target == channel
            self._counts[channel] = int.from_bytes(cmd[8:12], "little", signed=True)
            self.position_um[channel] = self._counts[channel] * self._um_per_count[channel]
            return None
        if cmd[:6] == _SET_ZERO_HEADER:
            self._counts[channel] = int.from_bytes(cmd[8:12], "little", signed=True)
            self.position_um[channel] = self._counts[channel] * self._um_per_count[channel]
            return None
        if cmd[:2] == _STOP_HEADER:
            # Abrupt stop: the fake keeps the last position and has no motion over time to cancel.
            return None
        raise AssertionError(f"unsupported fake command {bytes(cmd)!r}")

    def _get_encoder_counts(self, channel):
        channel_byte = channel.to_bytes(1, "little")
        response = self._send(_QUERY_HEADER + channel_byte + b"\x00\x00\x00", channel, response_bytes=12)
        assert response[6:7] == channel_byte
        self._counts[channel] = int.from_bytes(response[-4:], "little", signed=True)
        self.position_um[channel] = self._counts[channel] * self._um_per_count[channel]
        return self._counts[channel]

    def _move_to_encoder_count(self, channel, encoder_counts, block=True):
        channel_bytes = channel.to_bytes(2, "little")
        encoder_bytes = int(encoder_counts).to_bytes(4, "little", signed=True)
        self._send(_MOVE_HEADER + channel_bytes + encoder_bytes, channel)
        return None
