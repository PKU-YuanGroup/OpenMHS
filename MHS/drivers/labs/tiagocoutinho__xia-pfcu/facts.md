# Facts and tags for gh.tiagocoutinho/xia-pfcu

Every fact cites its source at commit `ed95e031f718c343842bc340f4ae91eb2cb6894a`: `vendor_doc` (a text file of the
clone, here README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| PFCU is a PFCU-4 Filter Set & Relay Control Unit | upstream_code | xia_pfcu/pfcu.py:18-20 |
| The status parser reads four filter channels from the status report | upstream_code | xia_pfcu/protocol.py:112-123 |
| set_filters accepts IN, I or 1 and OUT, O or 0 (case insensitive) per filter and '=' leaves a filter unchanged | upstream_code | xia_pfcu/pfcu.py:69-95 |
| filters_status decodes each channel as FilterStatus Out=0, In=1, OpenCircuit=2, ShortCircuit=3 | upstream_code | xia_pfcu/protocol.py:11-15 |
| The status report carries the identity line, four channel states, the RS232 control flags, the shutter mode and status, and the exposure decimation | upstream_code | xia_pfcu/protocol.py:108-138 |
| The exposure conversion starts at decimation 1 and states that 65_535 is the maximum decimation | upstream_code | xia_pfcu/protocol.py:91-100 |
| start_exposure converts seconds to an exposure count and a decimation, sends the decimation command and then the exposure command | upstream_code | xia_pfcu/protocol.py:87-105 |
| close_shutter immediately closes the PF2S2 shutter and terminates an exposure in progress; close and open only work when shutter mode is enabled | upstream_code | xia_pfcu/pfcu.py:43-55 |
| enable_shutter enables the shutter commands and disable_shutter is the default condition at power-up | upstream_code | xia_pfcu/pfcu.py:30-41 |
| Requests are framed as !PFCU<module> <command>\r and replies start with % | upstream_code | xia_pfcu/protocol.py:49-64 |
| The tango server opens the connection with eol=b';\\r\\n' and wraps PFCU with the configured module | upstream_code | xia_pfcu/tango/server/pfcu.py:21-29 |
| The README exposes the serial line at 9600 baud | vendor_doc | README.md:67 |

Limits:

- `decimation`: 1 to 65535, from `xia_pfcu/protocol.py:91-100`, where the conversion starts at
  `decimation = 1` and the comment calls `65_535` the maximum decimation. The gate reads the Python literal
  `65_535` as the two numbers 65 and 535, so it reports `G4.REF_VALUE` for the upper bound; the cited text really
  states the bound. The lower bound is the starting value of the same algorithm.
- `filter_a`..`filter_d`: only `in` and `out`, from `xia_pfcu/pfcu.py:73-74`, where `set_filters` documents
  `"IN"`, `"I"`, `"1"` and `1` as inserted and `"OUT"`, `"O"`, `"0"` and 0 as removed. The driver publishes the
  canonical lower-case names and accepts only those; the upstream accepts the other spellings too.
- `x-cap.tiagocoutinho.start_exposure.v1` `duration_s`: `Limit.operator_required`, because no text file of the clone
  states an exposure-duration range. `site-limits.example.json` shows the overlay that fills it; until the site
  supplies a range, every start_exposure call is refused `MHS.SAFETY.LIMITS_UNSET`.

Safety: the e-stop and the safe-state action `x-cap.tiagocoutinho.close_shutter.v1` both call the native
`close_shutter` (`xia_pfcu/pfcu.py:50-55`), which closes the focal-plane shutter and terminates an exposure in
progress. No line of the clone documents an independent hardware e-stop, so `estop_physical_ref` is not set; the
safe-state action satisfies SAFE-045 for this R2 hardware driver. The shutter commands only work when shutter mode is
enabled (`xia_pfcu/pfcu.py:43-47`); the driver exposes that mode as the writable `shutter_enabled` state. The runtime
reads every state field from the PFCU through `status`/`info` and `filters_status` (xia_pfcu/pfcu.py:57-67,
xia_pfcu/protocol.py:108-138).

Not exposed: `insert_filter`, `remove_filter` (the four `set_filters` fields cover the same channels),
`clear_short_error` (a latched short is cleared by turning the channel off or by the Z command; the driver does not
retry it), the per-channel shorted/open flags and TTL/front-panel details, and `write_readline` (the raw framed
command). The hardware factory was never run: the package is checked on the fake backend only.

Tags: filter-set, shutter, optical-path, xia, pfcu
