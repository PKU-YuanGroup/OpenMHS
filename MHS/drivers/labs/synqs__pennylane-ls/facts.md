# Facts and tags for gh.synqs/pennylane-ls

Every fact cites its source at commit `4bd2a7a20c70cf2756edda4343922b0e5a680090`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| SingleQuditDevice is the PennyLane Device subclass for the single-qudit remote backend | upstream_code | pennylane_ls/single_qudit_device.py:23 |
| DjangoDevice is the base class for devices that call an external server | upstream_code | pennylane_ls/django_device.py:12 |
| SingleQuditDevice constructs with one wire and the given number of shots | upstream_code | pennylane_ls/single_qudit_device.py:52-60 |
| The default control-server URL is http://qsimsim.synqs.org/api/singlequdit/ | upstream_code | pennylane_ls/single_qudit_device.py:44 |
| pre_apply resets the device and builds experiment_0 with an instructions array, num_wires, shots and wire_order interleaved | upstream_code | pennylane_ls/django_device.py:72-84 |
| apply maps RLX, RLZ, RLZ2 and Load through _operation_map and appends the encoded instruction to the job payload | upstream_code | pennylane_ls/single_qudit_device.py:63-78 |
| The operation encoders write [0] as the wire, wrap the RLX and RLZ angles modulo 2*pi, and set qdim to par[0] + 1 for Load | upstream_code | pennylane_ls/single_qudit_ops.py:58-113 |
| sample appends a measure instruction, posts the payload to url_prefix + post_job/ and stores the returned job_id | upstream_code | pennylane_ls/single_qudit_device.py:118-136 |
| check_job_status GETs url_prefix + get_job_status/ with the job id, username and password and raises SyntaxError when the status is ERROR | upstream_code | pennylane_ls/django_device.py:42-60 |
| wait_till_done sleeps two seconds between get_job_status/ polls and stops only on DONE | upstream_code | pennylane_ls/django_device.py:62-70 |
| sample fetches url_prefix + get_job_result/ and reads results[0].data.memory as integer shots | upstream_code | pennylane_ls/single_qudit_device.py:142-159 |
| reset only clears the local qdim, job_id and job_payload | upstream_code | pennylane_ls/single_qudit_device.py:163-166 |
| The README describes experiments controlled by the Labscript Suite through a JSON interface | vendor_doc | README.md:12 |
| The README describes interacting fermions in two optical tweezers | vendor_doc | README.md:10 |
| The README points real hardware to the labscript-qc repository | vendor_doc | README.md:37 |

Limits: both the operation parameter and the shot count are `Limit.operator_required`. The operation parameter is an
angle for RLX/RLZ/RLZ2 and a qudit-dimension offset for Load, so one range does not describe it; the constructor
default `shots=1` is a library default, not a device bound. `site-limits.example.json` supplies example values for the
gate's conformance run only; every call is refused `MHS.SAFETY.LIMITS_UNSET` without an operator overlay.

Safety: this package is blocked. The only HTTP routes the clone calls are `post_job/`, `get_job_status/` and
`get_job_result/` (single_qudit_device.py:121,144; django_device.py:47). There is no stop, cancel or abort route.
`reset()` (single_qudit_device.py:163-166) clears local Python state only; `wait_till_done` (django_device.py:62-70)
polls forever for DONE. The README points real hardware to the labscript-qc repository (README.md:37), which
develops the control server, so a posted job is a physical cold-atom experiment. The package declares R2
because the README describes optical-tweezer cold-atom experiments (README.md:10,12); the clone states no laser
class, so it does not claim R3. No independent hardware
e-stop is documented in the clone and no native stop exists, so neither `estop_physical_ref` nor a safe-state action
is available. The driver therefore has no `@estop` and the gate reports G3 NO_ESTOP / SAFE-045; this is the blocker,
not a test gap.

Fake: an in-memory source-shaped stand-in, not a recording and not an upstream simulator. It models the native
`pre_apply`/`apply`/`sample`/`check_job_status` flow and stores placeholder samples; it does not model the qudit
physics, the Django queue, the HTTP transport, labscript-qc or any timing. Its start values, URL, job id and samples
are placeholders and are not facts about the device.

Not covered: `MultiQuditDevice` and `FermionDevice` are other entry symbols of the clone and are not served by this
package. The real control-server response schema, credentials, queue policy and labscript-qc hardware are not
validated. The hardware backend was never built or run and the package is model-authored and unreviewed
(`reviewed_by` null).

Tags: cold atoms, quantum, pennylane, single qudit, job submission, optical tweezers
