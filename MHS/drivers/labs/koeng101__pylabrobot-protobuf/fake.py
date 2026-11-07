"""Fake backend of the remote STAR driver: an in-process stand-in for RemoteSTARBackend.

The upstream class is an asynchronous ConnectRPC client (src/client/py/pylabrobot_protobuf_client/star/__init__.py:21-31)
whose mixins call a STAR service; this fake keeps the same public method names and async shape but answers from
plain attributes.  Gate G7 checks every public name below against the pinned upstream class.

Every number and string here is test data, not a fact about a STAR: the channel count, positions, version and
tracked volume are placeholders.  The fake has no motion, fluidics, service, transport or safety model, and it is
not a recording.

The upstream client's ``async def`` methods call a synchronous RPC client, so a running RPC blocks the event loop.
By default this fake answers at once; the test switch ``block_s`` (a placeholder duration) makes ``aspirate_pip``
block the loop with ``time.sleep`` the way the upstream client does, so a test can show that the e-stop's Halt
waits behind it (model review, 2026-11-05).
"""

import time


class FakeRemoteSTARBackend:
    """Stand-in for RemoteSTARBackend with only the methods this package calls."""

    def __init__(self, **_options):
        self._num_channels = 8                  # placeholder: installed channel count, not a device fact
        self._y = {index: 0.0 for index in range(self._num_channels)}   # placeholder: starting Y positions
        self._z = {index: 0.0 for index in range(self._num_channels)}   # placeholder: starting Z positions
        self._version = "placeholder-iswap-0.0"  # placeholder: iSWAP version string
        self._tracked_volume = 0                # placeholder: fake tracked volume, not a real reading
        self._halts = 0
        self._stops = 0
        self._moves = []
        self.block_s = 0.0                      # placeholder test switch: loop-blocking time of aspirate_pip

    @property
    def num_channels(self):
        return self._num_channels

    async def setup(self):
        return None

    async def stop(self):
        self._stops += 1

    async def halt(self):
        self._halts += 1

    async def aspirate_pip(self, **kwargs):
        if self.block_s:
            time.sleep(self.block_s)            # the upstream's synchronous RPC inside an async def
        self._tracked_volume += sum(kwargs.get("aspiration_volumes") or [])   # placeholder bookkeeping
        return None

    async def dispense_pip(self, **kwargs):
        self._tracked_volume -= sum(kwargs.get("dispense_volumes") or [])     # placeholder bookkeeping
        return None

    async def move_channel_x(self, channel, x):
        self._moves.append(("x", channel, x))    # placeholder record, no physical motion
        return None

    async def move_channel_y(self, channel, y):
        self._y[channel] = float(y)              # placeholder position update
        return None

    async def move_channel_z(self, channel, z):
        self._z[channel] = float(z)              # placeholder position update
        return None

    async def move_all_channels_in_z_safety(self):
        self._moves.append(("z-safety", -1, 0))  # placeholder record, no physical motion
        return None

    async def get_channels_y_positions(self):
        return dict(self._y)

    async def get_channels_z_positions(self):
        return dict(self._z)

    async def get_iswap_version(self):
        return self._version
