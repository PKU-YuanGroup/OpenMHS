OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Tag, register and PV helper (`TagDriver`)

This change adds `TagDriver`, the helper of the `tag-bridge` family: a configuration-only driver for devices that a
server exposes as named points. One helper carries three profiles, `modbus` (holding and input registers, coils,
discrete inputs), `epics-ca` (Channel Access PV suffixes; the deployment prefix stays with the native transport) and
`alpaca` (ASCOM Alpaca properties and methods). Each package declares a finite point table in which every address
cites the clone line that shows it; reads become resource state or observation actions, writes become
`cap.device.configure.v1` or fixed and input-bound command steps, and the stop is a fixed write or method call
confirmed by a fresh read. OPC UA, Tango, ADS and S7 are deliberately not profiles of this version: the only
waiting cards that import OPC UA or Tango use them as service layers over serial or SDK devices, and an untested
profile would be unreviewed surface. The compiler refuses them by name.

The ten waiting cards were read with their pinned clones. Five are tag-shaped. The Hanmatek HM supply of
`gh.josuablejeru/labmastro` (Modbus RTU) becomes the family exemplar. `gh.danielballan/caproto-rpi` (the `hat` IOC,
whose `state = 0` drives every pin low), `gh.nsls-ii-sst/caproto_cryostat` (as an R0 temperature observer; its three
writes are fire-and-forget ZeroMQ sends with no stop for a magnet cycle) and the dome rotation scope of
`gh.holtzmanjon/apoalpyca` (AbortSlew switches the rotation power relay off; shutter relays run on fixed timers with
no abort route and stay out; a slew thread that has not yet energised the relay can undo an abort, which the package
must narrow and disclose) can be dispatched with the helper. `gh.festo-se/festo-pgva` stays blocked: no source line
offers a stop for a running timed valve pulse or a vent of the chambers, the manual trigger always raises, pump
disable is skipped by the upstream for firmware 2.1.3, and an output-pressure setpoint of 0 mbar is a regulation
setpoint that neither closes the valve nor ends a pulse and can only be confirmed by an analog sensor; this confirms
the earlier source preflight. The other five cards are misrouted (serial instruments with an OPC UA mailbox demo, a deployment-defined
pack of soft IOCs, a detector with its own TCP client and an optional Tango plugin, a serial data glove, and UR arm
research code with a vendored Robotiq gripper helper); correction proposals are recorded for the maintainers, not
applied.

`TagBridge` reads and writes through an injected transport with `read_point`, `write_point` and, for Alpaca,
`invoke_point`; the SDK imports no vendor library. Ordinary writes and commands hold one transaction lock, take the
e-stop epoch before waiting and are refused once a stop fired; a command pre-empted after an earlier step was written
ends unknown. A transport exception, a missing acknowledgement, an Alpaca error that does not state "not performed"
or an acknowledged write whose confirmation does not hold is an unknown outcome: the point leaves the state and
ordinary effects are refused `MHS.DEVICE.PRECONDITION_UNMET` until a confirmed stop succeeds; a write-only setpoint
whose write was lost then keeps commands refused until it is written again. Only a device refusal that states no
effect (a Modbus exception response mapped by the transport, the Alpaca numbers 0x400, 0x401, 0x407, 0x408, 0x409,
0x40B and 0x40C verified against the AlpycaDevice template) fails without uncertainty. Values a register cannot
represent exactly, by their shortest decimal representation, are refused, never rounded across an operator limit. The
stop never takes the transaction lock and is achieved only when every step was acknowledged, every confirmation holds
on a fresh read, no ordinary request was in flight from its start to its last read and the endpoint is open;
otherwise the server keeps its latch and retries. Reset writes nothing and needs a confirmed stop of the current
epoch. A driver with any write or effectful command must declare that stop; R2 and R3 hardware also needs an
input-free safe-state action with fixed steps and confirmation. A device without a real stop route may only observe.

Every TagDriver hardware backend needs a schema-valid lock with a human `reviewed_by` of scope `hardware` before any
factory or connection runs, at every risk class and for every author, as for ROS: address maps are deployment
specific and an industrial server can front anything. The driver checks it before the factory, again before the
bridge is built, and `mhs.adapter.load_driver` refuses with `review_required`. Declarations are copied and
fingerprinted at construction; a later change of the class, options or backends refuses every operation except the
stop.

Gate G7 checks that every point's source reference shows its address in its role at the pinned commit: in Python
source (parsed, never imported) the register is the address argument of a Modbus read or write call, whose table and
direction must match the point, or a register constant; the PV suffix an assignment target or string literal; the
Alpaca member a class, function or string literal; function codes, scale factors and comments do not count, and
undecidable cases are warnings for the reviewer. It also checks that `native` is an entry symbol found in the clone, and that every request the fake received during G6 and G8 equals a declared point
with a permitted access, a finite timeout and a codec-valid value. The new SDK modules join the gate's import and
integrity snapshot, so package code that changes them fails G3. `RecordingTagTransport` is the deterministic fake
base; SDK fixtures cover all three profiles.

Private validation on 2026-11-04 (Claude, claude-opus-5-5, a model; no human review), revised on 2026-11-05 after a
different-model review (Claude Sonnet, findings F1 to F15): the exemplar `MHS/drivers/labs/josuablejeru__labmastro`
passes G1 to G9 with no finding (digest `sha256:b26ea08fdc555f40c7118c8f7b7f808a21005b307d618a80f92ce1909c64f2e6`) and
`collect.py --strict` with no warning; its ten package tests pass. The three synthetic fixtures pass G1 to G8, and 48
new SDK tests cover the compiler and its bounds, exact codecs (huge integers and values off the register grid
included), unknown outcomes (lost, unacknowledged and unconfirmed writes, cancellation between steps), write-only
points after a stop, stop confirmation with an in-flight write and during close, reset across e-stop epochs, the
verified Alpaca refusal numbers, hardware admission and the G7 role-based source and wire checks. A mutation re-run
kills every mutant of the reviewed rules except three that remove one of two redundant checks. The complete SDK suite
runs 3,164 tests with six skips. Of the 302 registry tests, one validator check waits for the registry rebuild to sync
the new package's status; with the package set aside all 302 pass. The registry family entry now names `TagDriver` and
the exemplar; the generated family page carries the authoring rules, and the cards lose `helper:tag-bridge` only when
the registry is rebuilt. No device, Modbus slave, IOC, Alpaca server or vendor library was used, `reviewed_by` stays
null everywhere, and the evidence is `contract_checked`. A confirmation read proves what a device reports, not
physical quiescence; the EPICS and Alpaca profiles have no package yet.
