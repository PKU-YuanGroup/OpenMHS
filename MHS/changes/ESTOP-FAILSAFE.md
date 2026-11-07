# ESTOP-FAILSAFE — an emergency stop is recognised by what it asks for, and a stop that names no device stops them all

Two behaviours of the e-stop that the specification realignment (WP-09) recorded as known limitations, decided by the maintainer in the
fail-safe direction: a request whose `method` is `mhs.safety.estop` now latches although its JSON-RPC envelope is defective, and an e-stop
that names no device on an endpoint that serves several devices stops every device instead of being refused. An e-stop without the bearer
token stays refused. Written test first: `MHS/sdk/tests/safety/test_estop_failsafe.py` (29 tests; of the first 26, 19 failed before the change and the rest pinned behaviour that stays).

## What changed

- **A defective envelope no longer keeps an e-stop from latching** (WP-09 follow-up F2, `CORE-076`). A JSON object whose `method` is exactly
  `mhs.safety.estop`, or `mhs.command` naming `cap.motion.estop.v1` in object `params`, is served although `jsonrpc` is not `"2.0"`, the `id`
  is not a string or an integer, or `params` is not an object (`server._dispatch_message`, `_envelope_defect`, `_serve_defective_estop`). The
  answer is still the error of the defect (`MHS.PROTOCOL.INVALID_REQUEST` or `INVALID_PARAMS`; `id` null when the id is unusable; nothing for
  a notification) and `error.data.details` carry `estop_served`, the `defect` and the receipt, or, when nothing could be engaged,
  `estop_error`. The defect is appended to the reason of the stop, so the evidence says the request was irregular. Parameters that cannot be
  used are dropped, a `device_id` that names no device included, so the stop covers every device. Anything that is not such a JSON object
  (not JSON, a number, an array holding none) is refused as before, and so is every other method with the same defects.
- **An e-stop that names no device stops all of them** (F6, `CORE-076`). The devices of a stop are the one it names, else the single device
  of its session, else the only device of the endpoint, else all of them (`_estop_devices`). They are engaged concurrently, so a stop path
  that hangs on one device never delays the latch of another (`_engage_estops`). The answer is one receipt, the first that is not
  `completed` or else the first, with `x-vendor.estop` = `{scope: "all_devices", devices: [{device_id, status, receipt_id,
  safe_state_achieved, error?}]}`; it is `completed` only when every device's stop succeeded (SAFE-002), and a device whose engagement
  raised is reported `failed` `SAFE_STATE_UNREACHED`. The catalogue form (`mhs.command` on `cap.motion.estop.v1`) stops every device that
  binds the class. An unknown `device_id` is still `MHS.DEVICE.UNKNOWN` and stops nothing; a session on one device keeps its stop to that
  device; a single-device endpoint is unchanged (no marker).
- **Unchanged on purpose** (F5): with `auth_tokens` an e-stop without the bearer token is a 401 before the body is decoded, malformed or
  not (pinned by a test). The CLI (`mhs estop`, one call per device) and the MCP tool `mhs__estop` (`device_id` required) are unchanged.
- **Spec**: `core.md` CORE-076 and CORE-074, `02-wire-protocol.md` section 11.2. The test of the pinned multi-device refusal
  (`test_estop_latch.test_estop_of_a_device_outside_the_session`) now asserts the stop-all.

## Not done

- The MCP projection still asks the model for a `device_id`; letting a model call `mhs__estop` without one would change a tool schema and the
  host's device-bound approval exception, which is a separate decision.
- A body that is not parseable JSON, or whose method cannot be read, cannot be recognised as an e-stop and is refused as before (a text
  scan for the method name would also match it inside a string).
- WP-09 follow-up F1 (an `achieved_by` action is callable while latched) is untouched.
