"""Fake backend of the ScanImage TCP/IP client package: an in-memory stand-in for the upstream client.

Gate G7: every public method defined here is a method of ``py_json_client:ScanimageTcpipClient`` at the pinned
commit 9de4309aef951b390ed4b5a1240797a54d1001d8: ``close``, ``si_get``, ``si_set``, ``si_eval`` and ``si_feval``
(py_json_client.py:35-119).  The reply shapes follow the client's own dummy server: get and set work on a values
dictionary, eval and feval return a placeholder output per requested output (dummy_json_server.py:55-79), and
close is the teardown.  This fake is the *client object* itself and keeps everything in memory: no socket, no
server and no network.  The upstream dummy server is a TCP server that waits for a connection
(dummy_json_server.py:97-105); the acceptance gate runs without network, so the package uses this recording fake
instead (RESULT.json notes).

Numbers here are test data, not facts about the device: every one is marked ``# placeholder``.
"""

# placeholder: the initial value of hSI.hRoiManager.scanZoomFactor in this model
_START_SCAN_ZOOM = 1.0
# placeholder: the prefix of the output values an eval/feval returns (the dummy server returns "dummyvalueN")
_DUMMY_OUTPUT = "dummyvalue"


class FakeScanimageTcpipClient:
    """A recording stand-in for the upstream client: a property table, a call log and a close flag."""

    def __init__(self, **_options):
        self.closed = False
        self.calls = []                                     # (method name, arguments) of every call received
        self.values = {"hSI.hRoiManager.scanZoomFactor": _START_SCAN_ZOOM}

    def close(self):
        self.calls.append(("close",))
        self.closed = True

    def si_get(self, serv_var):
        self.calls.append(("si_get", serv_var))
        return self.values.get(serv_var)

    def si_set(self, serv_var, value):
        self.calls.append(("si_set", serv_var, value))
        self.values[serv_var] = value
        return None

    def si_eval(self, eval_str, num_outputs):
        self.calls.append(("si_eval", eval_str, num_outputs))
        if num_outputs == 0:
            return None
        return [f"{_DUMMY_OUTPUT}{index}" for index in range(1, num_outputs + 1)]

    def si_feval(self, feval_str, num_outputs, inputs=[]):
        self.calls.append(("si_feval", feval_str, num_outputs, list(inputs)))
        if num_outputs == 0:
            return None
        return [f"{_DUMMY_OUTPUT}{index}" for index in range(1, num_outputs + 1)]
