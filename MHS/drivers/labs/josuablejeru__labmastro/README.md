# labmastro Hanmatek HM supply: the tag-bridge exemplar

A configuration-only `TagDriver` (profile `modbus`) for the holding registers that labmastro's
`HanmatekHmControl` reads and writes over Modbus RTU. This is the tag-bridge family exemplar: copy its
structure (points with source references, state reads, write-only setpoints with operator-required limits,
confirmed output commands and a confirmed stop), never its registers, facts or limits.

- The fake (`fake.py`) is a `RecordingTagTransport` register store with placeholder values. It applies writes of
  the output register to its own read-back; it models no regulation, load, protection trip or Modbus exception.
- The hardware backend (`native.py`) builds a minimalmodbus RTU transport. The TagDriver refuses it until a human
  signs `reviewed_by` with scope `hardware` in `driver.lock.json`; this package keeps `reviewed_by: null`.
- Evidence is `contract_checked` on the fake only. No device, serial port or Modbus slave was contacted.
- `output_on` energises the load at the supply's live setpoints, which the package can neither read nor bound (the
  setpoint registers are write-only upstream): the operator sets and verifies them on the supply first. The human
  reviewer should weigh this before signing.
- On a shared serial bus a stop waits for the bus at most one request timeout; a stop that meets a request holding the
  bus is refused before sending and retried by the server.
- Licence: `pyproject.toml` says MIT and the `LICENSE` file says GPL version 3; publication waits for the owner's
  decision.

See [facts.md](facts.md), [REFERENCE.md](REFERENCE.md) and the tag-bridge section of
[the authoring guide](../../../sdk/docs/driver-authoring.md).
