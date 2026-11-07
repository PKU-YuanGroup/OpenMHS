# Facts and tags for gh.koeng101/pylabrobot-protobuf

Every fact cites the pinned clone at `c9b0a575d1be8efe95615af98928bf98fbddd243`. The same facts are in
`driver.py`; the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The project serves a STARService of about 150 RPCs for Hamilton STAR liquid handler control and a ResourceService for deck resources | vendor_doc | README.md:7-8 |
| RemoteSTARBackend is a ConnectRPC client that acts as a drop-in replacement for STARBackend | upstream_code | src/client/py/pylabrobot_protobuf_client/star/__init__.py:21-31 |
| RemoteSTARBackend.connect builds a STARServiceClientSync at the given base URL | upstream_code | src/client/py/pylabrobot_protobuf_client/star/__init__.py:37-41 |
| STARServiceImpl wraps a real STARBackend and create_star_app serves it | upstream_code | src/service/py/pylabrobot_protobuf_service/star/__init__.py:21-40 |
| The service's Stop RPC awaits STARBackend.stop | upstream_code | src/service/py/pylabrobot_protobuf_service/star/_lifecycle.py:25-27 |
| The client's halt is an async def that calls the synchronous client's halt with a HaltRequest and no timeout_ms | upstream_code | src/client/py/pylabrobot_protobuf_client/star/_misc.py:124-125 |
| STARServiceClientSync.halt is a plain def that returns execute_unary for the Halt method | upstream_code | src/client/py/pylabrobot_protobuf_client/star/_generated/star_service_connect.py:6690-6697 |
| The service imports STARBackend from pylabrobot.liquid_handling.backends.hamilton.STAR_backend | upstream_code | src/service/py/pylabrobot_protobuf_service/star/__init__.py:17-18 |
| The service's Setup RPC awaits STARBackend.setup | upstream_code | src/service/py/pylabrobot_protobuf_service/star/_lifecycle.py:21-23 |
| The service's Halt RPC awaits STARBackend.halt | upstream_code | src/service/py/pylabrobot_protobuf_service/star/_misc.py:177-179 |
| The client reads num_channels from the service and exposes it as a property | upstream_code | src/client/py/pylabrobot_protobuf_client/star/_lifecycle.py:26-29 |
| The client has a move-all-pipetting-channels-to-Z-safety command | upstream_code | src/client/py/pylabrobot_protobuf_client/star/_channel.py:55-56 |
| The client reads all channel Y positions as a map | upstream_code | src/client/py/pylabrobot_protobuf_client/star/_channel.py:117-119 |
| The client reads all channel Z positions as a map | upstream_code | src/client/py/pylabrobot_protobuf_client/star/_channel.py:135-137 |
| The client reads the iSWAP version string | upstream_code | src/client/py/pylabrobot_protobuf_client/star/_iswap.py:373-375 |
| The client's low-level aspirate_pip takes per-channel lists, among them tip_pattern, x_positions, y_positions, aspiration_volumes and aspiration_speed, each defaulting to a one-element list, and calls the synchronous client | upstream_code | src/client/py/pylabrobot_protobuf_client/star/_pipetting.py:591-636 |
| The client's low-level dispense_pip takes per-channel lists, among them tip_pattern, x_positions, y_positions, dispense_volumes and dispense_speed, and calls the synchronous client | upstream_code | src/client/py/pylabrobot_protobuf_client/star/_pipetting.py:683-722 |
| The STAR service protocol declares the Halt RPC | upstream_code | proto/star/v1/star_service.proto:1702 |
| The client package is installed from PyPI and connects to a STAR server at a base URL | vendor_doc | README.md:32-43 |

## Shape

The card's helper `PyLabRobotDriver` does not fit this upstream. `RemoteSTARBackend` is a remote
`STARBackend` client, not a PyLabRobot `LiquidHandler`, and no upstream object holds a handler with a deck
or tip tracking. The package is therefore a direct `Driver` over the client (DEVIATION FROM THE CARD).
The driver imports no upstream module; `native.py` imports the client package only on the hardware path.

## Reads

The three read parameters call `get_channels_y_positions`, `get_channels_z_positions` and
`get_iswap_version` on the client. The first two return a map keyed by channel index; the third returns a
version string.

## Limits

The pinned clone is a protocol layer. It forwards raw low-level firmware fields but states no numeric
range or unit for them; the README only says the service exposes about 150 STAR RPCs. Every numeric
action input (`channel`, `x_position`, `y_position`, `volume`, `speed`, `position`) is therefore
`Limit.operator_required`. No bound is copied from a constructor or catalogue default. The operator
supplies the installed instrument's envelope in `site-limits.json`; `site-limits.example.json` contains
placeholders for the gate and is not a statement about any instrument.

## Safety

BLOCKED (model review, 2026-11-05): no stop is proven, so the `@estop` sends Halt and then reports
`MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held, and `x-cap.koeng101.halt.v1` is an ordinary action, not a
safe-state action. At R2 the gate then fails G3 `SAFE-045` (no hardware e-stop and no safe-state action), the
expected blocked state.

- The only stop route is the upstream Halt RPC. `RemoteSTARBackend.halt` is an `async def` that calls the
  synchronous client's `halt` without a `timeout_ms` (src/client/py/pylabrobot_protobuf_client/star/_misc.py:124-125,
  `_generated/star_service_connect.py:6690-6697`); the service awaits `STARBackend.halt`
  (src/service/py/pylabrobot_protobuf_service/star/_misc.py:177-179).
- `STARBackend` is PyLabRobot's (src/service/py/pylabrobot_protobuf_service/star/__init__.py:17-18), not part of
  the clone, so what Halt does to a running sequence cannot be read here. No quiescence is claimed.
- Every client method blocks the driver's single event loop for its whole RPC, so the e-stop's Halt cannot be sent
  while an aspirate, dispense or move RPC is in flight: it waits behind that call, and the runtime reports the stop
  unreached after its budget (`test_halt_cannot_be_sent_while_a_blocking_rpc_holds_the_event_loop`, with the fake's
  `block_s` switch modelling the synchronous client).
- The service's Stop RPC (src/service/py/pylabrobot_protobuf_service/star/_lifecycle.py:25-27) is
  wired to driver `teardown`, never to the e-stop.
- `setup` awaits the service's Setup RPC, which awaits `STARBackend.setup`
  (src/service/py/pylabrobot_protobuf_service/star/_lifecycle.py:21-23): on hardware that initializes the
  instrument (an R2 motion) when the backend is first used.
- Hardware R2: the loader refuses the hardware backend of this model-authored, unreviewed package until
  a human signs `reviewed_by`; no hardware run is claimed.
- Unblocking needs a stop whose effect is source-proven (PyLabRobot's `STARBackend.halt` at a pinned commit, or a
  human-cited physical stop) and a client that can send it while another RPC runs (the generated asynchronous
  `STARServiceClient`, or the synchronous client off the event loop); the card's `PyLabRobotDriver` route also needs
  an operator-defined deck, which the clone does not have.

## Fakes

The fake is an in-process stand-in for `RemoteSTARBackend` with the same public asynchronous method
names. Every number and string in it is a placeholder, not a fact: it models no motion, fluid, service,
transport or safety interlock, and it answers at once unless its `block_s` test switch makes `aspirate_pip` block
the event loop the way the upstream synchronous client does. It is not a recording and does not replay captured traffic.

Tags: liquid-handler, hamilton, star, protobuf, connectrpc, pylabrobot
