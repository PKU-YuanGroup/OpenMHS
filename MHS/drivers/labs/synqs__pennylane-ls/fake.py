"""Fake backend of the SYNQS single-qudit driver: an in-memory stand-in for
``pennylane_ls.single_qudit_device:SingleQuditDevice``.

Gate G7: every public method defined here exists on the upstream class or on its ``DjangoDevice`` base
(``single_qudit_device.py:23``, ``django_device.py:12``).  The fake follows the upstream control flow:
``pre_apply`` resets and builds ``experiment_0``, ``apply`` encodes one native operation, ``sample`` posts the job
once and then fetches it, ``check_job_status`` answers the job state and ``wait_till_done`` is the upstream poll loop
without the network.  It never imports the clone and never talks to a device.

The fake is analytic, not a recording and not an upstream simulator: it does not evaluate the qudit physics, the
server queue, the labscript-qc timing or the HTTP transport.  Its samples and job id are placeholders.
"""

import math


class FakeSingleQuditDevice:
    def __init__(self, **options):
        self.url_prefix = str(options.get("url", "http://fake.invalid/api/singlequdit/"))  # placeholder
        self.username = options.get("username")
        self.password = options.get("password")
        self.blocking = bool(options.get("blocking", True))  # placeholder
        self.shots = int(options.get("shots", 1))            # placeholder
        self.job_id = None
        self.job_payload = {}
        self.qdim = 2                                        # placeholder
        self._samples = []                                   # private test data

    # -- DjangoDevice surface ------------------------------------------------------------------------------------
    def pre_apply(self):
        self.reset()
        self.job_payload = {
            "experiment_0": {
                "instructions": [],
                "num_wires": 1,
                "shots": self.shots,
                "wire_order": "interleaved",
            },
        }

    def check_job_status(self):
        if self.job_id is None:
            return "NONE"
        return "DONE"

    def wait_till_done(self):
        while self.check_job_status() != "DONE":
            return

    # -- SingleQuditDevice surface -------------------------------------------------------------------------------
    def apply(self, operation, wires, par):
        if operation == "Load":
            self.qdim = par[0] + 1
            instruction = ("load", [0], list(par))
        elif operation == "RLX":
            instruction = ("rlx", [0], [par[0] % (2 * math.pi)])
        elif operation == "RLZ":
            instruction = ("rlz", [0], [par[0] % (2 * math.pi)])
        elif operation == "RLZ2":
            instruction = ("rlz2", [0], list(par))
        else:
            raise KeyError(operation)
        self.job_payload["experiment_0"]["instructions"].append(instruction)

    def sample(self, observable, wires, par):
        if observable not in ("ZObs", "LZ", "LZ2"):
            raise KeyError(observable)
        if self.job_id is None:
            self.job_payload["experiment_0"]["instructions"].append(("measure", [0], []))
            self.job_id = "fake-job-1"  # placeholder
            self._samples = self._measured(observable)
            if self.blocking:
                self.wait_till_done()
            else:
                return self.job_id
        if self.blocking:
            self.wait_till_done()
        elif self.check_job_status() != "DONE":
            return self.job_id
        return self._samples

    def reset(self):
        self.qdim = 2        # placeholder
        self.job_id = None
        self.job_payload = None
        self._samples = []

    def _measured(self, observable):
        dimension = max(1, int(self.qdim))
        raw = [(index + 1) % dimension for index in range(int(self.shots))]  # placeholder values
        if observable == "ZObs":
            return [float(value) for value in raw]
        if observable == "LZ":
            return [float(value) - self.qdim / 2 for value in raw]
        return [(float(value) - self.qdim / 2) ** 2 for value in raw]
