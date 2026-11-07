"""Capacity preflight is an observation; final publication still owns the quota."""
import unittest

from mhs.artifacts import ArtifactScope, LocalArtifactStore
from mhs.errors import MHSError


class ArtifactPreflightTests(unittest.TestCase):
    def make(self, **options):
        store = LocalArtifactStore(**options)
        store.bind("mhs://localhost/preflight")
        self.addCleanup(store.close)
        return store

    def publisher(self, store, command, guard=lambda: None):
        publisher = store.publisher(ArtifactScope("session", "device", "main", "cap", command), guard)
        self.addCleanup(publisher.abort)
        return publisher

    def test_observation_does_not_reserve_or_evict_generic_artifacts(self):
        store = self.make(max_artifacts=1)
        first = self.publisher(store, "first")
        second = self.publisher(store, "second")
        first.preflight(100)
        second.preflight(100)
        self.assertEqual((store._grants, store._total_bytes), ({}, 0))
        descriptor = second.publish(b'{"completed":true}', "application/json", output_field="artifact_ref")
        second.prepare({"artifact_ref": descriptor["uri"]})
        second.commit()
        with self.assertRaises(MHSError):
            first.preflight(1)
        with self.assertRaises(MHSError):
            first.publish(b"pixels", "image/png")
        self.assertEqual(store.read(descriptor["uri"], "session", lambda scope: None)["data"], b'{"completed":true}')
        self.assertEqual(len(store._grants), 1)

    def test_known_byte_capacity_guard_and_closed_store_refuse_without_staging(self):
        store = self.make(max_artifact_bytes=10, max_total_bytes=10)
        publisher = self.publisher(store, "size")
        for value in (0, True, 11):
            with self.assertRaises(MHSError):
                publisher.preflight(value)
        def refuse():
            raise PermissionError("controlled admission refusal")
        guarded = self.publisher(store, "guarded", refuse)
        with self.assertRaises(PermissionError):
            guarded.preflight(1)
        self.assertEqual((store._grants, store._total_bytes), ({}, 0))
        store.close()
        with self.assertRaises(MHSError):
            publisher.preflight(1)

    def test_default_image_field_after_preflight_and_expired_capacity(self):
        clock = [0.0]
        store = self.make(max_artifacts=1, ttl_s=1, clock=lambda: clock[0])
        publisher = self.publisher(store, "image")
        publisher.preflight(16)
        descriptor = publisher.publish(b"primary pixels", "image/png")
        publisher.prepare({"image_ref": descriptor["uri"]})
        publisher.commit()
        newer = self.publisher(store, "newer")
        with self.assertRaises(MHSError):
            newer.preflight(1)
        clock[0] = 2
        newer.preflight(1)
        self.assertEqual(store._grants, {})
        with self.assertRaises(MHSError):
            store.read(descriptor["uri"], "session", lambda scope: None)


if __name__ == "__main__":
    unittest.main()
