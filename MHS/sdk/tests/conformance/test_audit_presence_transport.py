"""Transport failures are not proof that a mandatory method is implemented.

CON-018: a presence probe may count a method as present only when dispatch is
shown. A dropped connection, the SDK transport error, or any other exception
that is not the probe's recognized method-specific rejection leaves presence
unverified (fail closed).
"""

from __future__ import annotations

import unittest

from mhs.client import TransportError
from mhs.conformance.presence import check_method_presence, probe_method
from mhs.errors import MHSError


class _Context:
    """Enough of a suite context for ``mhs.operations.cancel`` to be built."""

    def __init__(self, client):
        self.client = client
        self.primary_device = {
            "device_id": "mhs://fake/device",
            "capabilities": [{"capability_id": "cap.world.step.v1"}],
        }
        self.primary_capability = {"capability_id": "cap.world.step.v1"}
        self.primary_resource = "state"
        self._session = "mhs_s_fake"

    def ensure_session(self):
        return self._session


def _client(error: BaseException):
    class Client:
        def request(self, method, params):
            raise error

    return Client()


class TransportFailureIsNotPresenceTests(unittest.TestCase):
    """In-memory probes of ``mhs.operations.cancel`` (semantic)."""

    def test_connection_error_is_unverified(self):
        ctx = _Context(_client(ConnectionError("connection reset")))
        outcome = probe_method(ctx, "mhs.operations.cancel")
        self.assertEqual(outcome.status, "unverified")
        self.assertIsNone(outcome.code)
        missing, unverified, results = check_method_presence(ctx, ["mhs.operations.cancel"])
        self.assertEqual(missing, [])
        self.assertEqual(unverified, ["mhs.operations.cancel"])
        self.assertEqual(results[0].status, "unverified")

    def test_transport_closed_is_unverified(self):
        ctx = _Context(_client(TransportError(
            "MHS.TRANSPORT.CLOSED", "transport is closed", {"may_have_effect": False},
        )))
        outcome = probe_method(ctx, "mhs.operations.cancel")
        self.assertEqual(outcome.status, "unverified")
        self.assertEqual(outcome.code, "MHS.TRANSPORT.CLOSED")
        missing, unverified, _results = check_method_presence(ctx, ["mhs.operations.cancel"])
        self.assertEqual(missing, [])
        self.assertEqual(unverified, ["mhs.operations.cancel"])

    def test_unstructured_exception_is_unverified(self):
        ctx = _Context(_client(RuntimeError("no response")))
        outcome = probe_method(ctx, "mhs.operations.cancel")
        self.assertEqual(outcome.status, "unverified")
        self.assertIsNone(outcome.code)
        _missing, unverified, _results = check_method_presence(ctx, ["mhs.operations.cancel"])
        self.assertEqual(unverified, ["mhs.operations.cancel"])

    def test_unrecognized_structured_code_is_unverified(self):
        # A code outside the probe's recognized semantic rejections does not
        # prove the cancel handler ran (a gateway can emit it for every method).
        ctx = _Context(_client(MHSError("MHS.INTERNAL.ERROR", "endpoint crashed")))
        outcome = probe_method(ctx, "mhs.operations.cancel")
        self.assertEqual(outcome.status, "unverified")
        self.assertEqual(outcome.code, "MHS.INTERNAL.ERROR")
        _missing, unverified, _results = check_method_presence(ctx, ["mhs.operations.cancel"])
        self.assertEqual(unverified, ["mhs.operations.cancel"])

    def test_recognized_semantic_rejection_is_present(self):
        ctx = _Context(_client(MHSError("MHS.OPERATION.UNKNOWN", "unknown operation")))
        outcome = probe_method(ctx, "mhs.operations.cancel")
        self.assertEqual(outcome.status, "present")
        self.assertEqual(outcome.code, "MHS.OPERATION.UNKNOWN")
        missing, unverified, _results = check_method_presence(ctx, ["mhs.operations.cancel"])
        self.assertEqual(missing, [])
        self.assertEqual(unverified, [])

    def test_legacy_recognized_code_is_present(self):
        class Legacy(Exception):
            code = "MHS.OPERATION.NOT_FOUND"

        ctx = _Context(_client(Legacy("unknown operation")))
        outcome = probe_method(ctx, "mhs.operations.cancel")
        self.assertEqual(outcome.status, "present")
        self.assertEqual(outcome.code, "MHS.OPERATION.UNKNOWN")

    def test_successful_dispatch_is_present(self):
        class Client:
            def request(self, method, params):
                return {"operation_id": params["operation_id"], "status": "running"}

        outcome = probe_method(_Context(Client()), "mhs.operations.cancel")
        self.assertEqual(outcome.status, "present")

    def test_result_probe_transport_failure_stays_unverified(self):
        # Result probes already refused every rejection. This must stay so.
        ctx = _Context(_client(TransportError("MHS.TRANSPORT.CLOSED", "transport is closed")))
        outcome = probe_method(ctx, "mhs.hello")
        self.assertEqual(outcome.status, "unverified")
        self.assertEqual(outcome.detail, "valid request was rejected")


if __name__ == "__main__":
    unittest.main()
