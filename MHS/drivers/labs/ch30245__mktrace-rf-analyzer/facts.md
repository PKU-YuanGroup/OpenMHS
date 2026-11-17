# Facts and tags for gh.ch30245/mktrace-rf-analyzer

Every fact cites the pinned clone at commit `44169387a49c06994455e6c502ddae4edab8cabc`: `vendor_doc` for a text
file of the clone and `upstream_code` for `pna.py`. The driver copies the same facts into `facts = [Fact(...)]`; the
generated reference is built from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| `NaClient` stores host and port and defaults the port to 5025 | upstream_code | `pna.py:236-241` |
| A session is a raw TCP socket with a 10 s connect timeout and a default 180 s I/O timeout | upstream_code | `pna.py:178-182` |
| Every SCPI command is ASCII terminated by a newline | upstream_code | `pna.py:203-204` |
| `identify` opens a short-lived session, queries `*IDN?` and closes it | upstream_code | `pna.py:254-264` |
| The supported identity gate accepts Keysight PNA/N522/N523/N524/N526/N529 and Rohde & Schwarz ZVA/ZVB/ZVT | upstream_code | `pna.py:167-175` |
| `capture` accepts only 1, 2 or 4 ports before opening a session | upstream_code | `pna.py:274-279` |
| `capture` reads `*IDN?` and dispatches to the Keysight or the Rohde & Schwarz sequence | upstream_code | `pna.py:280-299` |
| The Keysight capture selects a measurement, sweeps once, saves a Touchstone file and transfers it with `MMEM:TRAN?` | upstream_code | `pna.py:696-716` |
| The Rohde & Schwarz capture turns continuous sweep off, sweeps once and saves/transfers a Touchstone file | upstream_code | `pna.py:831-844` |
| `configure_measurements` adds missing Keysight S-parameter measurements without replacing existing ones | upstream_code | `pna.py:304-333` |
| `configure_measurements` refuses non-Keysight analyzers without changing state | upstream_code | `pna.py:320-324` |
| `abort_active_session` closes the active I/O session and sends no SCPI abort command | upstream_code | `pna.py:247-252` |
| A received Touchstone payload is validated before the target file is atomically replaced | upstream_code | `pna.py:343-363` |
| The default capture file name is a timestamped MKTrace name with the `.s1p`, `.s2p` or `.s4p` suffix | upstream_code | `pna.py:125-128` |
| MKCal calibration is simulator-only | vendor_doc | `README.md:5-7` |
| The automated tests do not contact real hardware | vendor_doc | `README.md:67-69` |

## Limits

The only numeric inputs are the port count of the two actions: the upstream rejects every value other than 1, 2 and 4
(`pna.py:123-124`, `pna.py:149-150`). No text of the clone states a frequency, power or IF bandwidth bound; the
driver does not expose those settings, so it does not invent one. The driver chooses a 180 s action budget, equal
to the upstream default per-I/O timeout (`pna.py:179`); this is not an upstream deadline for the whole sequence.

## Model review: blocked stop

`abort_active_session` only closes transport I/O (`pna.py:247-252`, `pna.py:186-201`). It sends no sweep abort
or RF-output disable and does not read back a stopped analyzer. The e-stop now attempts the transport close and
raises `MHS.SAFETY.SAFE_STATE_UNREACHED`, keeping the endpoint latch engaged. An analyzer may still be sweeping,
and closing the session can prevent the restoration queries and writes from succeeding (`pna.py:724-782`,
`pna.py:849-867`). A source-backed, acknowledged stop is required before this hardware route can be accepted.
The clone has no top-level licence file; the card's required publication review remains an owner decision.

The fake now refuses a Keysight capture unless the requested S-parameters exist, as `pna.py:444-456` requires;
the artifact case configures them first. Its generated one-point data remains placeholder test data.

## Tags

`network analyzer`, `vna`, `s-parameter`, `touchstone`, `scpi`, `keysight pna`, `rohde schwarz zva`
