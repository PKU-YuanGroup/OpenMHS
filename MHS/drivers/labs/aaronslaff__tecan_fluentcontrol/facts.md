# Facts and tags for gh.aaronslaff/tecan_fluentcontrol

Every fact cites the clone at commit `5bbff1713f97e75eab6f8b204f293b79a4104a33`.  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The scripts control FluentControl instruments programmatically for deck layouts and liquid transfer operations | vendor_doc | FLUENT_CONTROL_README.md:3 |
| The client takes a base URL and authenticates with a bearer API key or HTTP basic credentials | upstream_code | fluent_control_automation.py:86-113 |
| get_instrument_status reads GET /api/v1/status and get_deck_layout reads GET /api/v1/deck/layout | upstream_code | fluent_control_automation.py:159-167 |
| post_transfer_session posts the transfers to /api/v1/transfers/session with a generated session_id and status pending | upstream_code | fluent_control_automation.py:190-210 |
| start_transfer_session posts to /api/v1/transfers/session/{session_id}/start | upstream_code | fluent_control_automation.py:212-215 |
| get_transfer_status reads GET /api/v1/transfers/session/{session_id}/status | upstream_code | fluent_control_automation.py:217-220 |
| cancel_transfer_session posts to /api/v1/transfers/session/{session_id}/cancel and takes the session id | upstream_code | fluent_control_automation.py:222-225 |
| A transfer finishes with status completed, failed or cancelled | upstream_code | fluent_control_automation.py:344 |
| Source and destination are position IDs, liquid class and tip type are names, and the volume is in microliters | vendor_doc | FLUENT_CONTROL_README.md:245-249 |
| Aspiration and dispense speeds are in microliters per second, the air gap and mix volume in microliters, and the retract distance in millimetres | vendor_doc | FLUENT_CONTROL_README.md:250-257 |

## Limits

The only numeric action input is `volume_ul` of `x-cap.aaronslaff.post_transfer_session.v1`.  No text file of the
clone states a transfer volume range, and the capacity of the tips depends on the tips installed on a unit, so the
field carries `Limit.operator_required`: every transfer is refused `MHS.SAFETY.LIMITS_UNSET` until an operator
overlay supplies the range.  `site-limits.example.json` is an example overlay, not a statement about any unit.

The transfer fields `aspiration_speed`, `dispense_speed`, `air_gap`, `touch_off`, `mix_cycles`, `mix_volume`,
`blow_out` and `retract_distance` are optional in the upstream `TransferParameters` and are not exposed: no text file
gives their ranges, so a bounded action cannot include them without inventing bounds.

## What is exposed and what is not

The driver exposes the status and deck reads, the transfer-session lifecycle, and the session status.  The deck is
read-only: the clone does not document the GET deck document, so a writable state field cannot reproduce the
`LabwarePosition` list without inventing that schema.  The upstream `post_deck_layout` method is therefore not exposed.

## Safety

The upstream client has no global stop request; its only stop path is `cancel_transfer_session(session_id)`
(fluent_control_automation.py:222-225).  The e-stop cancels the session the driver last created or started; with no
tracked session it queries the instrument status.  The `x-cap.aaronslaff.cancel_active_transfer.v1` action is the
safe-state action and follows the same path.  No text file of the clone documents an independent hardware e-stop, so
`estop_physical_ref` is not set.  This is a limitation of the API, not a claim of an independent stop.

This package is model-authored and unreviewed.  The hardware backend was never run; the fake is an in-memory object,
not a recording of a device.  The package is checked on the fake backend only.

Tags: liquid-handler, pipetting, tecan, http
