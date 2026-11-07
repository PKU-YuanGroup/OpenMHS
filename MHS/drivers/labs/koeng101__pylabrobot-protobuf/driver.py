"""OpenMHS driver for gh.koeng101/pylabrobot-protobuf: a Hamilton STAR through the remote ConnectRPC service.

The card's helper is ``PyLabRobotDriver``, but this upstream is not a ``LiquidHandler`` front end and no
upstream object holds one: ``RemoteSTARBackend`` is a ConnectRPC client that replaces a PyLabRobot
``STARBackend`` (src/client/py/pylabrobot_protobuf_client/star/__init__.py:21-31), and the Python server
wraps a real backend (src/service/py/pylabrobot_protobuf_service/star/__init__.py:21-40).  A
``PlrProfile`` needs a concrete ``LiquidHandler`` with a deck and tip tracking, neither of which the
card's entry class has, so this package is a direct ``Driver`` over the upstream client.  That is a
deliberate deviation from the card's helper.

What is exposed:

* reads: the remote client's channel Y and Z position maps and the iSWAP version string;
* a bounded single-channel low-level aspirate and dispense, the channel X/Y/Z move, and the
  all-channel Z-safety move;
* a no-input ``halt`` action and an ``@estop`` that both send the upstream Halt RPC.

The pinned clone is a protocol layer.  It forwards raw low-level firmware fields but states no numeric
range or unit for them, so every numeric action input is ``Limit.operator_required``: the operator must
give the installed STAR's envelope in ``site-limits.json`` before any such call is admitted.

The upstream client's methods are ``async def`` but call the synchronous ``STARServiceClientSync``
(for example ``halt``, src/client/py/pylabrobot_protobuf_client/star/_misc.py:124-125), so each RPC
blocks the driver's one event loop until the service answers.  ``setup`` awaits the service's Setup RPC
(which runs ``STARBackend.setup``, the instrument's initialisation) and ``teardown`` awaits its Stop
RPC, which the service forwards to ``STARBackend.stop``.

BLOCKED (model review, 2026-11-05): no stop is proven.  The Halt RPC is the only stop route of the card's
entry class, and the service forwards it to ``STARBackend.halt`` of PyLabRobot, which is not in the clone
(src/service/py/pylabrobot_protobuf_service/star/__init__.py:17-18), so what it does to a running
sequence cannot be read here.  And because every client call blocks the event loop, the e-stop's Halt
cannot even be sent while an aspirate, dispense or move RPC is in flight: it waits behind that call.
The e-stop therefore sends Halt (best effort) and reports ``MHS.SAFETY.SAFE_STATE_UNREACHED`` with the
latch held, and ``halt`` is not a safe-state action.  The hardware backend needs a human
``reviewed_by`` at R2 and was not run.
"""

from mhs.driver import Cancelled, Driver, DriverFailed, Fact, Field, Limit, action, estop, read


_OPERATOR_POSITION = (
    "the pinned clone forwards this raw low-level field without stating a range; the operator sets the "
    "installed STAR's envelope in site-limits.json"
)
_OPERATOR_CHANNEL = (
    "the pinned clone reports num_channels at runtime and states no channel index range; the operator "
    "sets the installed head's channel range in site-limits.json"
)


class StarRemote(Driver):
    device_id = "star-remote"
    device_kind = "lab.liquid_handler"
    mode = "hardware"
    risk = "R2"
    native = "client.py.pylabrobot_protobuf_client.star:RemoteSTARBackend"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeRemoteSTARBackend"}
    vendor, model = "koeng101", "pylabrobot-protobuf remote Hamilton STAR"
    display_name = "Hamilton STAR over pylabrobot-protobuf (RemoteSTARBackend)"
    tags = ["liquid-handler", "hamilton", "star", "protobuf", "connectrpc", "pylabrobot"]
    safe_state = (
        "none proven: the runtime latches and refuses new calls; the e-stop sends the upstream Halt RPC "
        "(forwarded to PyLabRobot's STARBackend.halt, which is not in the clone; it cannot be sent while "
        "another RPC blocks the event loop) and reports SAFE_STATE_UNREACHED with the latch held"
    )
    facts = [
        Fact("The project serves a STARService of about 150 RPCs for Hamilton STAR liquid handler control "
             "and a ResourceService for deck resources", source="vendor_doc", ref="README.md:7-8"),
        Fact("RemoteSTARBackend is a ConnectRPC client that acts as a drop-in replacement for STARBackend",
             source="upstream_code",
             ref="src/client/py/pylabrobot_protobuf_client/star/__init__.py:21-31"),
        Fact("RemoteSTARBackend.connect builds a STARServiceClientSync at the given base URL",
             source="upstream_code",
             ref="src/client/py/pylabrobot_protobuf_client/star/__init__.py:37-41"),
        Fact("STARServiceImpl wraps a real STARBackend and create_star_app serves it", source="upstream_code",
             ref="src/service/py/pylabrobot_protobuf_service/star/__init__.py:21-40"),
        Fact("The service's Stop RPC awaits STARBackend.stop", source="upstream_code",
             ref="src/service/py/pylabrobot_protobuf_service/star/_lifecycle.py:25-27"),
        Fact("The client's halt is an async def that calls the synchronous client's halt with a HaltRequest and "
             "no timeout_ms", source="upstream_code",
             ref="src/client/py/pylabrobot_protobuf_client/star/_misc.py:124-125"),
        Fact("STARServiceClientSync.halt is a plain def that returns execute_unary for the Halt method",
             source="upstream_code",
             ref="src/client/py/pylabrobot_protobuf_client/star/_generated/star_service_connect.py:6690-6697"),
        Fact("The service imports STARBackend from pylabrobot.liquid_handling.backends.hamilton.STAR_backend",
             source="upstream_code", ref="src/service/py/pylabrobot_protobuf_service/star/__init__.py:17-18"),
        Fact("The service's Setup RPC awaits STARBackend.setup", source="upstream_code",
             ref="src/service/py/pylabrobot_protobuf_service/star/_lifecycle.py:21-23"),
        Fact("The service's Halt RPC awaits STARBackend.halt", source="upstream_code",
             ref="src/service/py/pylabrobot_protobuf_service/star/_misc.py:177-179"),
        Fact("The client reads num_channels from the service and exposes it as a property", source="upstream_code",
             ref="src/client/py/pylabrobot_protobuf_client/star/_lifecycle.py:26-29"),
        Fact("The client has a move-all-pipetting-channels-to-Z-safety command", source="upstream_code",
             ref="src/client/py/pylabrobot_protobuf_client/star/_channel.py:55-56"),
        Fact("The client reads all channel Y positions as a map", source="upstream_code",
             ref="src/client/py/pylabrobot_protobuf_client/star/_channel.py:117-119"),
        Fact("The client reads all channel Z positions as a map", source="upstream_code",
             ref="src/client/py/pylabrobot_protobuf_client/star/_channel.py:135-137"),
        Fact("The client reads the iSWAP version string", source="upstream_code",
             ref="src/client/py/pylabrobot_protobuf_client/star/_iswap.py:373-375"),
        Fact("The client's low-level aspirate_pip takes per-channel lists, among them tip_pattern, x_positions, "
             "y_positions, aspiration_volumes and aspiration_speed, each defaulting to a one-element list, and "
             "calls the synchronous client", source="upstream_code",
             ref="src/client/py/pylabrobot_protobuf_client/star/_pipetting.py:591-636"),
        Fact("The client's low-level dispense_pip takes per-channel lists, among them tip_pattern, x_positions, "
             "y_positions, dispense_volumes and dispense_speed, and calls the synchronous client",
             source="upstream_code",
             ref="src/client/py/pylabrobot_protobuf_client/star/_pipetting.py:683-722"),
        Fact("The STAR service protocol declares the Halt RPC", source="upstream_code",
             ref="proto/star/v1/star_service.proto:1702"),
        Fact("The client package is installed from PyPI and connects to a STAR server at a base URL",
             source="vendor_doc", ref="README.md:32-43"),
    ]

    async def setup(self):
        await self.native.setup()

    async def teardown(self):
        await self.native.stop()

    @read("channel_y_positions", type="object",
          description="Channel Y positions reported by the remote STAR service, keyed by channel index")
    async def channel_y_positions(self):
        return await self.native.get_channels_y_positions()

    @read("channel_z_positions", type="object",
          description="Channel Z positions reported by the remote STAR service, keyed by channel index")
    async def channel_z_positions(self):
        return await self.native.get_channels_z_positions()

    @read("iswap_version", type="string", description="iSWAP firmware version reported by the remote STAR")
    async def iswap_version(self):
        return await self.native.get_iswap_version()

    @action(
        name="x-cap.koeng101.aspirate_pip.v1",
        description="Aspirate with one low-level STAR pipetting channel",
        input={
            "channel": Field("integer", description="Pipetting channel index",
                             limit=Limit.operator_required(_OPERATOR_CHANNEL)),
            "x_position": Field("integer", description="Raw low-level x-position list entry",
                                limit=Limit.operator_required(_OPERATOR_POSITION)),
            "y_position": Field("integer", description="Raw low-level y-position list entry",
                                limit=Limit.operator_required(_OPERATOR_POSITION)),
            "volume": Field("integer", description="Raw low-level aspiration-volume list entry",
                            limit=Limit.operator_required(_OPERATOR_POSITION)),
            "speed": Field("integer", description="Raw low-level aspiration-speed list entry",
                           limit=Limit.operator_required(_OPERATOR_POSITION)),
        },
        output={
            "aspirated_volume": Field("integer", description="Raw low-level aspirated-volume value sent"),
            "channel": Field("integer", description="Pipetting channel index"),
        },
    )
    async def aspirate_pip(self, channel, x_position, y_position, volume, speed):
        _count, pattern, xs, ys, volumes, speeds = self._one_channel(
            channel, x_position, y_position, volume, speed)
        await self.native.aspirate_pip(
            tip_pattern=pattern,
            x_positions=xs,
            y_positions=ys,
            aspiration_volumes=volumes,
            aspiration_speed=speeds,
        )
        self._raise_if_cancelled()
        return {"aspirated_volume": volume, "channel": channel}

    @action(
        name="x-cap.koeng101.dispense_pip.v1",
        description="Dispense with one low-level STAR pipetting channel",
        input={
            "channel": Field("integer", description="Pipetting channel index",
                             limit=Limit.operator_required(_OPERATOR_CHANNEL)),
            "x_position": Field("integer", description="Raw low-level x-position list entry",
                                limit=Limit.operator_required(_OPERATOR_POSITION)),
            "y_position": Field("integer", description="Raw low-level y-position list entry",
                                limit=Limit.operator_required(_OPERATOR_POSITION)),
            "volume": Field("integer", description="Raw low-level dispense-volume list entry",
                            limit=Limit.operator_required(_OPERATOR_POSITION)),
            "speed": Field("integer", description="Raw low-level dispense-speed list entry",
                           limit=Limit.operator_required(_OPERATOR_POSITION)),
        },
        output={
            "dispensed_volume": Field("integer", description="Raw low-level dispensed-volume value sent"),
            "channel": Field("integer", description="Pipetting channel index"),
        },
    )
    async def dispense_pip(self, channel, x_position, y_position, volume, speed):
        _count, pattern, xs, ys, volumes, speeds = self._one_channel(
            channel, x_position, y_position, volume, speed)
        await self.native.dispense_pip(
            tip_pattern=pattern,
            x_positions=xs,
            y_positions=ys,
            dispense_volumes=volumes,
            dispense_speed=speeds,
        )
        self._raise_if_cancelled()
        return {"dispensed_volume": volume, "channel": channel}

    @action(
        name="x-cap.koeng101.move_channel.v1",
        description="Move one pipetting channel along one axis",
        input={
            "channel": Field("integer", description="Pipetting channel index",
                             limit=Limit.operator_required(_OPERATOR_CHANNEL)),
            "axis": Field("string", enum=["x", "y", "z"], description="Axis to move"),
            "position": Field("integer", description="Raw channel position argument",
                              limit=Limit.operator_required(_OPERATOR_POSITION)),
        },
        output={
            "axis": Field("string", enum=["x", "y", "z"], description="Axis moved"),
            "position": Field("integer", description="Raw channel position argument sent"),
        },
    )
    async def move_channel(self, channel, axis, position):
        self._check_channel(channel)
        if axis == "x":
            await self.native.move_channel_x(channel, position)
        elif axis == "y":
            await self.native.move_channel_y(channel, position)
        else:
            await self.native.move_channel_z(channel, position)
        self._raise_if_cancelled()
        return {"axis": axis, "position": position}

    @action(
        name="x-cap.koeng101.move_all_channels_in_z_safety.v1",
        description="Move every pipetting channel to the STAR Z-safety position",
        output={"moved": Field("boolean", description="True when the Z-safety command was sent")},
    )
    async def move_all_channels_in_z_safety(self):
        await self.native.move_all_channels_in_z_safety()
        self._raise_if_cancelled()
        return {"moved": True}

    @action(
        name="x-cap.koeng101.halt.v1",
        description="Send the upstream Halt RPC (forwarded to STARBackend.halt); not a proven stop",
        output={"halted": Field("boolean", description="True when the Halt RPC returned")},
    )
    async def halt(self):
        await self.native.halt()
        return {"halted": True}

    @estop(native="halt")
    async def emergency_halt(self):
        """Send Halt, then refuse to certify a safe state (model review, 2026-11-05).

        STARBackend.halt is outside the clone, and the synchronous client cannot send Halt while another RPC
        blocks the event loop; nothing confirms that a running sequence stopped.
        """
        await self.native.halt()
        raise DriverFailed(
            "MHS.SAFETY.SAFE_STATE_UNREACHED",
            "the Halt RPC returned, but its effect (PyLabRobot STARBackend.halt) is not in the clone and nothing "
            "confirms that a running sequence stopped")

    # -- helpers ---------------------------------------------------------
    def _check_channel(self, channel):
        count = int(self.native.num_channels)
        if not 0 <= channel < count:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               f"channel {channel} is outside the reported 0..{count - 1} range")

    def _one_channel(self, channel, x_position, y_position, volume, speed):
        """Parallel one-channel lists: unused channels are False, with zero position/volume and the requested speed."""
        self._check_channel(channel)
        count = int(self.native.num_channels)
        pattern = [index == channel for index in range(count)]
        xs = [x_position if index == channel else 0 for index in range(count)]
        ys = [y_position if index == channel else 0 for index in range(count)]
        volumes = [volume if index == channel else 0 for index in range(count)]
        speeds = [speed for _ in range(count)]
        return count, pattern, xs, ys, volumes, speeds

    def _raise_if_cancelled(self):
        if self.cancelled():
            raise Cancelled("the low-level STAR command was cancelled")
