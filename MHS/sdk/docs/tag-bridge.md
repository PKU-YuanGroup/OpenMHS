# Tag, register and PV devices: `TagDriver`

`TagDriver` (registry family `tag-bridge`) is a configuration-only helper for devices that a server exposes as named
points: Modbus registers and coils, EPICS Channel Access PVs, ASCOM Alpaca properties and methods. A package declares
a finite point table with the source line of every address; the SDK's `TagBridge` reads and writes those points
through a transport object, confirms stops by reading points back, and refuses everything the table does not
declare. Exemplar: [`MHS/drivers/labs/josuablejeru__labmastro`](../../drivers/labs/josuablejeru__labmastro/driver.py)
(Modbus RTU bench supply). SDK fixtures for all three profiles are under `MHS/sdk/tests/fixtures/tag_*`.

Not supported in this version: OPC UA, Tango, ADS and S7 profiles (the compiler refuses them), multi-word Modbus
writes, arrays, interlock or native reset bindings, long-running or cancellable commands, subscriptions, discovery and
any address the package does not declare. A device that needs one of them is a `HELPER_MISSING` or a direct `Driver`.

## When to use it

Use it when the upstream code addresses the device by register number, PV name or Alpaca member, and the device or
server (not the upstream Python class) is what an agent controls. The upstream class stays the provenance
(`native = "package.module:Class"`, parsed, never imported). Do not use it when the tag protocol is incidental: a
repository whose device speaks a serial or SDK protocol and only re-exports it through an OPC UA or Tango service is
a serial, SCPI or direct driver.

## Declaration

```python
from mhs.driver import Action, Fact, Field, Limit, TagDriver

class Supply(TagDriver):
    device_id, device_kind, mode, risk = "my-supply", "instrument.smu", "hardware", "R2"
    native = "vendor_pkg.control:SupplyControl"
    backends = {"fake": ".fake:FakeSupply", "hardware": ".native:connect"}
    safe_state = "Output register written 0 and read back 0; setpoints keep their values."
    tag_config = {"profile": "modbus", "timeout_ms": 1000, "points": {
        "output": {"table": "holding", "register": 0x0001, "type": "bool", "access": "read-write",
                   "source_ref": "vendor_pkg/control.py:66-82"},
        "voltage_set": {"table": "holding", "register": 0x0030, "type": "uint16", "decimals": 2,
                        "access": "write", "source_ref": "vendor_pkg/control.py:33"}}}
    parameters = {"output_enabled": Field("boolean", description="Output state read back"),
                  "voltage_setpoint": Field("number", unit="V", writable=True,
                                            limit=Limit.operator_required("no range in the clone"),
                                            description="Voltage setpoint; last acknowledged write")}
    reads = {"output_enabled": {"point": "output"}}
    writes = {"voltage_setpoint": {"point": "voltage_set"}}
    commands = {"x-cap.owner.output_off.v1": {"steps": [{"write": "output", "value": False}],
                                              "confirm": [{"point": "output", "equals": False}],
                                              "result": {"output_enabled": {"point": "output"}}}}
    actions = {"x-cap.owner.output_off.v1": Action(name="output_off", safe_state=True, description="...",
                                                   output={"output_enabled": Field("boolean", description="...")})}
    safety_bindings = {"estop": {"steps": [{"write": "output", "value": False}],
                                 "confirm": [{"point": "output", "equals": False}]}}
```

`tag_config` keys: `profile` (`modbus`, `epics-ca`, `alpaca`), `points` (1 to 64), `timeout_ms` (per request, 1 to
10000, default 1000), `confirm_ms` (how long a confirmation may be re-read, 0 to 1500, default 0: one read),
`poll_ms` (10 to 500). The `alpaca` profile also needs `device_type` (lower case), `device_number` and
`device_type_ref` (the line that routes that device type, for example `init_routes(app, 'dome', dome)`).

Every point has `access` (`read`, `write`, `read-write`), `type`, `source_ref` and an optional `description`:

| Profile | Address keys | Types |
|---|---|---|
| `modbus` | `table` (`holding`, `input`, `coil`, `discrete`), `register` (0..65535), `words` (implied by the type), `word_order` (`big` = high word first, or `little`; two-word types only), `decimals` (0..6, integer types only) | `uint16`, `int16`, `bool` (register 0/1, strict), `uint32`, `int32`, `float32`; coils and discrete inputs are `bool` |
| `epics-ca` | `pv`: the PV suffix the source shows; the deployment prefix is the operator's and belongs to `native.py` | `integer` (32-bit), `number`, `string` (ASCII, at most 40 bytes) |
| `alpaca` | `member` (lower case); a writable property adds `field`, its PUT form field (`Slaved`); a method is `{"member": ..., "method": True, "params": {"Azimuth": "number"}}` | `integer`, `number`, `boolean`, `string` |

Input tables and discrete inputs are read-only. Multi-word values are read-only (no pinned source shows a function 16
write). A write-only point is shown in the state as the last value this endpoint wrote and the device acknowledged,
never as a measurement; use it only when no source line shows that the address is readable.

### Reads, writes and commands

* `reads` maps a parameter to a readable point; `writes` maps a writable parameter to a writable point, with an
  optional `verify` point read back after the write (same type and resolution).
* `commands` maps a capability id to:
  * an effectful command: `steps` (1 to 8 of `{"write": point, "value": v}`, `{"write": point, "input": field}`,
    or for Alpaca `{"invoke": method, "args": {"Form": {"value": v} | {"input": field}}}`), optional `confirm`
    (`{"point": p, "equals": v}` or `{"point": p, "in": [...]}`, exactly comparable types only), optional
    `result` (`{"field": {"point": p} | {"input": name} | {"value": v}}`); it needs an explicit `Action`;
  * an observation: `{"read": {"field": point}}` (`values.field` for `cap.sensing.read.v1`), no inputs, and for an
    `x-cap` id `Action(verb="read")`. Any input is refused; a catalogue read class whose optional inputs appear in
    its examples needs `fixtures/conformance.json` with `"valid": {}` for that class.
* Values are engineering values. The codec is exact: a float counts by its shortest decimal representation (the
  value a JSON request carries), so 3.3 on a 0.01 V register is the word 330, while `3.305`, `3.30000001` and
  `0.1 + 0.2` (0.30000000000000004) are refused (`MHS.CAPABILITY.INPUT_INVALID`), as are `0.1` as float32 and
  integers beyond the register range (however large). Nothing is rounded, so no value crosses an operator limit
  on its way to the device.
* Every numeric input or writable parameter needs a sourced `Limit` or `Limit.operator_required(...)`; a register's
  codec range is not a device limit.

### The stop

A driver with any write or effectful command must declare `safety_bindings["estop"]`: fixed steps and at least one
confirmation predicate. R2 and R3 hardware also needs an input-free `Action(safe_state=True)` command with fixed steps
and confirmation (SAFE-045) unless a human cites a physical stop (`estop_physical_ref`). A tag device without a real
stop route may only observe: then declare reads (and `verb="read"` observations) only, at R0.

Cite why the stop is a stop: the upstream method that writes it, and what it does not stop (setpoints left as they
are, a relay on another register, stored pressure, a motion that coasts). An acknowledgement alone never proves a
stop. Keep `timeout_ms` and `confirm_ms` of a stop within the device's e-stop budget (`estop_latency_ms`, default
1000 ms): a stop that has not confirmed by then is reported unreached and retried, never assumed.

## Runtime semantics (`TagBridge`)

* Ordinary writes and commands hold one transaction lock, capture the e-stop epoch before waiting, and are refused
  with `MHS.SAFETY.ESTOP_ENGAGED` once a stop fired. A multi-step command pre-empted after an earlier step was written
  ends `unknown`.
* After dispatch, a transport exception, a missing acknowledgement, an Alpaca error that does not state "not
  performed", or an acknowledged write whose confirmation does not hold within `confirm_ms` (or cannot be read) is
  `MHS.OUTCOME.UNKNOWN` (a confirmation that does not hold carries the observed values in `details`; a slow readback
  cannot be told from a refused effect).
  The point is marked uncertain (its cached value leaves the state) and the device owes a confirmation, so ordinary
  writes and commands are refused `MHS.DEVICE.PRECONDITION_UNMET` until a confirmed stop (the e-stop or the safe-state
  action) succeeds. Reads are never blocked.
* A confirmed stop clears that fence and resolves readable points (every read observes them), the Alpaca methods it
  ends and the points it writes itself. A write-only point it does not write keeps an unknown value no read can
  establish: it stays in `uncertain_points`, `outcome_uncertain` stays true, the state omits it, and commands are
  refused until it is written again and acknowledged, by a parameter write or by a command whose first steps write
  it; parameter writes stay allowed so the operator can re-establish it. A supply is therefore never switched on at
  an unknown setpoint.
* `TagRefused` from the transport (a Modbus exception response that states the request was not executed, a refused
  put) and the Alpaca errors that state "not performed" mean no effect: `failed` with `MHS.DEVICE.FAULTED`, no
  uncertainty. The Alpaca numbers are those of the ASCOM AlpycaDevice template (`device/exceptions.py` in
  `gh.holtzmanjon/apoalpyca`): NotImplemented `0x400`, InvalidValue `0x401`, NotConnected `0x407`, Parked `0x408`,
  Slaved `0x409`, InvalidOperation `0x40B`, ActionNotImplemented `0x40C`. OperationCancelled `0x40E` (an in-progress
  operation), ValueNotSet `0x402` (meant for reads), driver errors `0x500..0xFFF` and undefined numbers such as
  `0x4FF` are unknown outcomes.
* The stop never takes the transaction lock. It is achieved only when every stop step was acknowledged, every
  confirmation holds on a fresh read, no ordinary request was in flight from its start to its last read, and the
  endpoint is open; otherwise the server reports `MHS.SAFETY.SAFE_STATE_UNREACHED`, keeps the latch and retries.
* `reset` writes nothing: it needs a confirmed stop of the current e-stop epoch, no owed confirmation and nothing in
  flight, and re-reads the confirmation points before it releases the bridge latch. A write-only point left uncertain
  does not block reset (writes must stay possible to re-establish it); commands stay refused until it is rewritten.

## Fake and native backends

* The fake is the package's own `RecordingTagTransport` subclass (`mhs.bridge.tag_fake`): seed the declared
  addresses with placeholder values (`# placeholder`), model the device's visible behaviour in `on_write` and, for
  Alpaca, `on_invoke` (return the Alpaca error number). Unseeded addresses are refused like a device without them.
  The `refuse`, `fail` and `silent` sets drive negative tests.
* The hardware backend is `native.py`: import the vendor client there (pymodbus, minimalmodbus, a Channel Access
  client, an HTTP client for Alpaca) and return an object with `read_point(request, *, timeout_s)`,
  `write_point(request, raw, *, timeout_s)` and, for Alpaca, `invoke_point(request, args, *, timeout_s)`.
  `write_point` returns `True` only after the device acknowledged (Modbus echo, Channel Access put completion); Alpaca
  transports return the parsed response object. Raise `mhs.bridge.tags.TagRefused` only when the device states it did
  not perform the request. Honour `timeout_s`; serialize a shared bus with a bounded wait. Deployment data (port,
  host, unit id, PV prefix, Alpaca host and port) are backend options, never Facts.
* Every `TagDriver` hardware backend needs a schema-valid `driver.lock.json` with a human `reviewed_by` of scope
  `hardware` before any factory or connection runs, at every risk class and for every author; `mhs.adapter.load_driver`
  refuses it with `review_required`. Models keep `reviewed_by: null`.
* A shared bus is serialized by the transport: a stop waits for the bus at most its own `timeout_s`, so a stop that
  meets a request holding the bus for its whole timeout fails its first attempt and the server retries it (CORE-077).
  Keep `timeout_ms` short on a shared bus.
* `python3 -m mhs.driver export` labels a tag driver's adapter manifest `other`: the adapter schema's family list has
  no `tag-bridge` value.

## Gate checks

G7 (`mhs.driver.tag_check`) checks that every point's `source_ref` shows its address in its role at the pinned commit.
In Python source (parsed with `ast`, so comments, strings and unrelated numbers do not count) a Modbus register must be
the address argument of a Modbus read or write call on a cited line (the first positional argument, or an address
keyword such as `address` or `registeraddress`, of a Modbus-shaped call: `read_holding_registers`, `write_register`,
`read_coils`, `read_bit`, `write_float` and the like) or the value of a register constant or map entry; function
codes, counts, scale factors such as `* 100`, comments and calls such as `set_input_current(1000)` are not
addresses. The gate takes the first positional argument as the address: for a library that passes the slave id
first (umodbus), cite a line with the address keyword or the register constant. Where
the call shows its table and direction (its name, or an explicit `functioncode`), they must agree with the point: a
`read-write` point cites lines that both read and write it. An EPICS PV suffix must be an assignment target or a
string literal, an Alpaca member a class, function or string literal, and the Alpaca device type a string literal at
`device_type_ref`. A register shown only as a constant, a call that does not show its table, and a cited file that is
not parseable Python (checked as text) give the warning `TAG_ADDRESS_UNDECIDED`: read that line. G7 also checks that
`native` is an entry symbol found in the clone, and that every request the fake received during G6 and G8 equals a
declared point with a permitted access, a finite `timeout_s` and a codec-valid value (`TAG_ADDRESS_NOT_UPSTREAM`,
`TAG_TABLE_NOT_UPSTREAM`, `TAG_ACCESS_NOT_UPSTREAM`, `TAG_WIRE_UNDECLARED`, `TAG_WIRE_ACCESS`, `TAG_WIRE_VALUE`,
`TAG_WIRE_TIMEOUT`). This proves where the addresses occur in the pinned source and that nothing undeclared reached
the transport. It does not prove a deployment's address map, a register's meaning or scale, or a physical stop: a
reviewer still reads every cited line.
