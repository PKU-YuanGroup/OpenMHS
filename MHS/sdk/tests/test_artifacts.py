"""Ownership, lifecycle and counterexamples for local immutable artifacts."""
import hashlib
import os
from pathlib import Path
import tempfile
import threading
import unittest

from mhs.artifacts import ArtifactScope, LocalArtifactStore
from mhs.errors import MHSError


class ArtifactStoreTests(unittest.TestCase):
    def make(self, **options):
        store = LocalArtifactStore(**options)
        self.addCleanup(store.close)
        store.bind("mhs://localhost/lab")
        return store

    def stage(self, store, data=b"image", session="session-a", command="command-a"):
        scope = ArtifactScope(session, "device", "camera", "cap.sensing.image.v1", command)
        publisher = store.publisher(scope, lambda: None)
        descriptor = publisher.publish(data, "image/png")
        return publisher, descriptor

    def publish(self, store, **options):
        publisher, descriptor = self.stage(store, **options)
        self.assertEqual(publisher.prepare({"image_ref": descriptor["uri"]}), [descriptor])
        publisher.commit()
        return descriptor

    def test_endpoint_uri_uses_authority_and_owner_is_not_content_digest(self):
        store = self.make()
        first = self.publish(store)
        second = self.publish(store, session="session-b")
        self.assertTrue(first["uri"].startswith("mhs+artifact://localhost/"))
        self.assertNotEqual(first["uri"], second["uri"])
        self.assertEqual(first["digest"], second["digest"])
        self.assertEqual(store._total_bytes, 5)
        self.assertEqual(store.read(first["uri"], "session-a", lambda scope: None)["data"], b"image")
        for uri in (first["uri"].replace("localhost", "foreign"), first["uri"] + "?x=1",
                    first["uri"] + "/../../secret", "file:///private/secret", "https://localhost/secret"):
            with self.subTest(uri=uri), self.assertRaises(MHSError):
                store.read(uri, "session-a", lambda scope: None)
        with self.assertRaises(MHSError):
            store.read(first["uri"], "session-b", lambda scope: None)

    def test_staged_and_aborted_artifacts_are_never_readable(self):
        store = self.make()
        publisher, descriptor = self.stage(store)
        with self.assertRaises(MHSError):
            store.read(descriptor["uri"], "session-a", lambda scope: None)
        publisher.abort()
        self.assertEqual((store._total_bytes, len(store._grants)), (0, 0))
        with self.assertRaises(MHSError):
            publisher.prepare({"image_ref": descriptor["uri"]})
        publisher, descriptor = self.stage(store)
        with self.assertRaises(MHSError):
            publisher.prepare({"image_ref": "foreign"})
        self.assertEqual(len(store._grants), 0)

    def test_pending_grants_count_against_quota_and_expiry_never_retargets(self):
        now = [0.0]
        store = self.make(max_artifact_bytes=5, max_total_bytes=5, max_artifacts=1,
                          ttl_s=1, clock=lambda: now[0])
        pub, descriptor = self.stage(store)
        with self.assertRaises(MHSError):
            self.stage(store, session="session-b")
        pub.prepare({"image_ref": descriptor["uri"]})
        pub.commit()
        now[0] = 1.0
        with self.assertRaises(MHSError):
            store.read(descriptor["uri"], "session-a", lambda scope: None)
        newer = self.publish(store, data=b"newer")
        self.assertNotEqual(newer["uri"], descriptor["uri"])
        with self.assertRaises(MHSError):
            store.read(descriptor["uri"], "session-a", lambda scope: None)

    def test_full_unexpired_store_refuses_without_evicting_valid_grant(self):
        store = self.make(max_artifact_bytes=5, max_total_bytes=5)
        descriptor = self.publish(store)
        with self.assertRaises(MHSError):
            self.publish(store, data=b"other")
        self.assertEqual(store.read(descriptor["uri"], "session-a", lambda scope: None)["data"], b"image")

    def test_tamper_symlink_and_foreign_file_never_escape_root(self):
        with tempfile.TemporaryDirectory() as parent:
            sentinel = Path(parent) / "user-data"
            sentinel.write_bytes(b"preserve")
            store = self.make(directory=parent)
            descriptor = self.publish(store)
            path = store._root / descriptor["digest"].split(":")[1]
            path.write_bytes(b"other")
            with self.assertRaises(MHSError):
                store.read(descriptor["uri"], "session-a", lambda scope: None)
            path.unlink()
            path.symlink_to(sentinel)
            with self.assertRaises((OSError, MHSError)):
                store.read(descriptor["uri"], "session-a", lambda scope: None)
            store.close()
            self.assertEqual(sentinel.read_bytes(), b"preserve")
            self.assertFalse(store._root.exists())

    def test_explicit_guard_and_scope_callback_are_enforced(self):
        store = self.make()
        def refuse(*args):
            raise PermissionError("not authorized")
        publisher = store.publisher(ArtifactScope("a", "d", "r", "cap", "c"), refuse)
        with self.assertRaises(PermissionError):
            publisher.publish(b"image", "image/png")
        descriptor = self.publish(store)
        with self.assertRaises(PermissionError):
            store.read(descriptor["uri"], "session-a", refuse)

    def test_concurrent_capacity_is_atomic(self):
        store = self.make(max_artifacts=1)
        start = threading.Barrier(3)
        outcomes = []
        def publish(number):
            start.wait()
            try:
                outcomes.append(self.stage(store, command=str(number)))
            except MHSError:
                outcomes.append(None)
        threads = [threading.Thread(target=publish, args=(n,)) for n in range(2)]
        for thread in threads:
            thread.start()
        start.wait()
        for thread in threads:
            thread.join(2)
            self.assertFalse(thread.is_alive())
        self.assertEqual(sum(item is not None for item in outcomes), 1)

    def test_invalid_bounds_and_untrusted_endpoint_names(self):
        for options in ({"max_artifacts": True}, {"ttl_s": 0}, {"max_artifact_bytes": 17 * 1024 * 1024}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                LocalArtifactStore(**options)
        for endpoint in ("localhost", "https://localhost", "mhs://user:pass@localhost", "mhs://localhost?q=1"):
            with self.subTest(endpoint=endpoint):
                store = LocalArtifactStore()
                try:
                    with self.assertRaises(ValueError):
                        store.bind(endpoint)
                finally:
                    store.close()


    def test_lazy_publisher_still_refuses_actual_bytes_on_unbound_or_closed_store(self):
        store = LocalArtifactStore()
        self.addCleanup(store.close)
        scope = ArtifactScope("s", "d", "r", "cap", "c")
        empty = store.publisher(scope, lambda: None)
        self.assertEqual(empty.prepare({}), [])
        empty.abort()
        with self.assertRaises(MHSError):
            store.publisher(scope, lambda: None).publish(b"image", "image/png")
        self.assertEqual(store._grants, {})
        store.bind("mhs://localhost")
        store.close()
        unused = store.publisher(scope, lambda: None)
        self.assertEqual(unused.prepare({}), [])
        unused.abort()
        with self.assertRaises(MHSError):
            store.publisher(scope, lambda: None).publish(b"image", "image/png")
        self.assertEqual(store._grants, {})
