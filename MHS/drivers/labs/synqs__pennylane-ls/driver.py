"""OpenMHS driver for gh.synqs/pennylane-ls: the SYNQS single-qudit cold-atom device.

A direct Driver over the card's entry class ``pennylane_ls.single_qudit_device:SingleQuditDevice`` (line 23), the
PennyLane Device that turns a circuit into a JSON job payload and posts it to a Django control server.  The card names
PythonObjectDriver, but that family binds one native method per command; the native primary control is the pair
``apply`` (one instruction per gate) plus ``sample`` (post, poll and fetch), so this package is a direct Driver.  See
RESULT.json for the deviation.

* reads: the qudit dimension, the shots of the current payload, the job id, the job status and the control-server URL;
* one action: ``x-cap.synqs.run_experiment.v1`` loads a sequence of the native single-qudit operations, posts the job,
  polls ``get_job_status/`` with a cancellation check and returns the measured samples;
* the clone has no stop, cancel or abort route: the only HTTP endpoints it calls are ``post_job/``,
  ``get_job_status/`` and ``get_job_result/``.  ``reset()`` (single_qudit_device.py:163-166) only clears local Python
  state, and ``wait_till_done`` (django_device.py:62-70) is an unbounded two-second poll.  A posted job therefore runs
  to completion on the control server and this package cannot declare a safe state or an independent stop.  This is
  why the package is blocked (RESULT.json), not because the fake is difficult.

The control server is the labscript-qc server for real hardware (README.md:12,37) and the qsimsim hardware simulator
by default (single_qudit_device.py:44).  The README describes optical-tweezer cold-atom experiments (README.md:10), so
the package declares R2; the clone states no laser class, so R3 is not claimed.  The fake is an in-memory stand-in,
not a recording and not an upstream simulator.  The package is model-authored and unreviewed (reviewed_by null); no
hardware backend was built or run.
"""

import math
import time
from collections.abc import Mapping

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, read

_PARAMETERS_REASON = (
    "no text file of the clone states one range for the operation parameter: it is an angle for RLX, RLZ and RLZ2 "
    "and a qudit-dimension offset for Load (single_qudit_ops.py:58-113). The operation encoders wrap the angles "
    "modulo 2*pi and pass the Load offset to qdim = par[0] + 1; the clone states no safe bound for the server "
    "experiment, so the site supplies the range of its deployment"
)
_SHOTS_REASON = (
    "the constructor default shots=1 is a default, not a device bound (single_qudit_device.py:40-48); no text file "
    "of the clone states a shot-count range or a server-side limit, so the site supplies the range of its deployment"
)


class SynqsSingleQudit(Driver):
    device_id = "pennylane-ls"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R2"
    native = "pennylane_ls.single_qudit_device:SingleQuditDevice"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeSingleQuditDevice"}
    vendor, model = "SYNQS", "pennylane-ls single-qudit cold-atom device"
    display_name = "SYNQS single-qudit cold-atom device (pennylane_ls.SingleQuditDevice)"
    tags = ["cold atoms", "quantum", "pennylane", "single qudit", "job submission", "optical tweezers"]
    facts = [
        Fact("SingleQuditDevice is the PennyLane Device subclass for the single-qudit remote backend",
             source="upstream_code", ref="pennylane_ls/single_qudit_device.py:23"),
        Fact("DjangoDevice is the base class for devices that call an external server",
             source="upstream_code", ref="pennylane_ls/django_device.py:12"),
        Fact("SingleQuditDevice constructs with one wire and the given number of shots",
             source="upstream_code", ref="pennylane_ls/single_qudit_device.py:52-60"),
        Fact("The default control-server URL is http://qsimsim.synqs.org/api/singlequdit/",
             source="upstream_code", ref="pennylane_ls/single_qudit_device.py:44"),
        Fact("pre_apply resets the device and builds experiment_0 with an instructions array, num_wires, shots and "
             "wire_order interleaved", source="upstream_code", ref="pennylane_ls/django_device.py:72-84"),
        Fact("apply maps RLX, RLZ, RLZ2 and Load through _operation_map and appends the encoded instruction to the "
             "job payload", source="upstream_code", ref="pennylane_ls/single_qudit_device.py:63-78"),
        Fact("The operation encoders write [0] as the wire, wrap the RLX and RLZ angles modulo 2*pi, and set qdim to "
             "par[0] + 1 for Load", source="upstream_code", ref="pennylane_ls/single_qudit_ops.py:58-113"),
        Fact("sample appends a measure instruction, posts the payload to url_prefix + post_job/ and stores the "
             "returned job_id", source="upstream_code", ref="pennylane_ls/single_qudit_device.py:118-136"),
        Fact("check_job_status GETs url_prefix + get_job_status/ with the job id, username and password and raises "
             "SyntaxError when the status is ERROR", source="upstream_code", ref="pennylane_ls/django_device.py:42-60"),
        Fact("wait_till_done sleeps two seconds between get_job_status/ polls and stops only on DONE",
             source="upstream_code", ref="pennylane_ls/django_device.py:62-70"),
        Fact("sample fetches url_prefix + get_job_result/ and reads results[0].data.memory as integer shots",
             source="upstream_code", ref="pennylane_ls/single_qudit_device.py:142-159"),
        Fact("reset only clears the local qdim, job_id and job_payload", source="upstream_code",
             ref="pennylane_ls/single_qudit_device.py:163-166"),
        Fact("The README describes experiments controlled by the Labscript Suite through a JSON interface",
             source="vendor_doc", ref="README.md:12"),
        Fact("The README describes interacting fermions in two optical tweezers", source="vendor_doc",
             ref="README.md:10"),
        Fact("The README points real hardware to the labscript-qc repository", source="vendor_doc", ref="README.md:37"),
    ]
    safe_state = (
        "no safe state is available: the clone exposes no stop, cancel or abort route for a submitted job, so a "
        "posted experiment runs to completion on the control server and reset() only clears local Python state"
    )

    # -- reads --------------------------------------------------------------------------------------------------
    @read("qdim", type="integer", unit="1", description="Qudit dimension of the loaded circuit")
    def qdim(self):
        return int(self.native.qdim)

    @read("shots", type="integer", unit="1",
          description="Shots in the current job payload, or the configured shots before the first payload")
    def shots(self):
        payload = self.native.job_payload
        if isinstance(payload, Mapping):
            experiment = payload.get("experiment_0")
            if isinstance(experiment, Mapping) and experiment.get("shots") is not None:
                return int(experiment["shots"])
        return int(self.native.shots)

    @read("job_id", type="string", description="Job id returned by the control server, empty before the first job")
    def job_id(self):
        return "" if self.native.job_id is None else str(self.native.job_id)

    @read("job_status", type="string",
          description="Last control-server status for the current job, NONE when no job was posted")
    def job_status(self):
        if self.native.job_id is None:
            return "NONE"
        return str(self.native.check_job_status())

    @read("endpoint", type="string", description="Control-server URL prefix the native object posts to")
    def endpoint(self):
        return str(self.native.url_prefix)

    # -- the primary control --------------------------------------------------------------------------------------
    @action(name="x-cap.synqs.run_experiment.v1", long_running=True, max_duration_ms=86400000, cancellable=True,
            description="Load the native single-qudit operations into the job payload, post the job, poll the "
                        "control server with a cancellation check and return the measured samples",
            input={
                "operations": Field("array", min_items=1,
                                    description="Gate sequence in the native instruction order: one object per "
                                                "native apply() call",
                                    items=Field("object", description="One native operation",
                                                properties={
                                                    "operation": Field("string",
                                                                       description="Native operation name",
                                                                       enum=["Load", "RLX", "RLZ", "RLZ2"]),
                                                    "parameters": Field(
                                                        "array", unit="1",
                                                        description="Native operation parameters; one value for "
                                                                    "each of these operations",
                                                        items=Field("number", unit="1"),
                                                        limit=Limit.operator_required(_PARAMETERS_REASON)),
                                                })),
                "shots": Field("integer", unit="1", description="Shots requested for this job",
                               limit=Limit.operator_required(_SHOTS_REASON)),
                "observable": Field("string", description="Native single-qudit observable used for the result",
                                    enum=["ZObs", "LZ", "LZ2"]),
            },
            output={
                "samples": Field("array", description="Measured single-qudit samples after the native observable "
                                                      "conversion", items=Field("number", unit="1")),
                "job_id": Field("string", description="Job id returned by the control server"),
                "qdim": Field("integer", unit="1", description="Qudit dimension after the loaded operations"),
            })
    def run_experiment(self, operations, shots, observable="ZObs"):
        self.check_cancelled()
        sequence = self._sequence(operations)
        previous_shots = int(self.native.shots)
        previous_blocking = bool(self.native.blocking)
        self.native.shots = int(shots)
        try:
            self.native.pre_apply()
            for operation, parameters in sequence:
                self.check_cancelled()
                self.native.apply(operation, [0], parameters)
            self.native.blocking = False
            job_id = self.native.sample(observable, [0], [])
            while True:
                self.check_cancelled()
                try:
                    status = self.native.check_job_status()
                except SyntaxError as exc:
                    raise DriverFailed("MHS.DEVICE.FAULTED", str(exc)) from exc
                if status == "DONE":
                    break
                time.sleep(0.05)
            samples = self.native.sample(observable, [0], [])
        finally:
            self.native.blocking = previous_blocking
            self.native.shots = previous_shots
        self.check_cancelled()
        return {"samples": [float(value) for value in samples], "job_id": str(job_id),
                "qdim": int(self.native.qdim)}

    @staticmethod
    def _sequence(operations):
        if not isinstance(operations, (list, tuple)) or not operations:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "operations must be a non-empty array")
        sequence = []
        for item in operations:
            if not isinstance(item, Mapping):
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "each operation must be an object")
            operation = str(item.get("operation"))
            if operation not in ("Load", "RLX", "RLZ", "RLZ2"):
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                                   f"operation {operation!r} is not in the native single-qudit operation map")
            parameters = item.get("parameters")
            if not isinstance(parameters, (list, tuple)) or len(parameters) != 1:
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                                   f"{operation} takes exactly one parameter for the single-qudit device")
            try:
                value = float(parameters[0])
            except (TypeError, ValueError) as exc:
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                                   f"{operation} parameter is not a number") from exc
            if not math.isfinite(value):
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", f"{operation} parameter is not finite")
            if operation == "Load" and (not value.is_integer() or value < 0):
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                                   "Load parameter is the native qdim - 1 and must be a non-negative integer")
            sequence.append((operation, [value]))
        return sequence
