"""Files a native wrote are published from one declared directory, fail-closed (mhs.file_artifacts)."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import stat
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from mhs import file_artifacts as fa
from mhs.artifacts import ArtifactScope, LocalArtifactStore
from mhs.bridge.base import BridgeContext
from mhs.errors import MHSError
from mhs.file_artifacts import NativeFileDirectory
from mhs.signals import Cancelled

H5 = "application/x-hdf5"


def real_temp(test) -> Path:
    holder = tempfile.TemporaryDirectory(prefix="mhs-file-artifacts-")
    test.addCleanup(holder.cleanup)
    return Path(os.path.realpath(holder.name))


def write(directory: Path, name: str, data: bytes) -> Path:
    path = directory / name
    path.write_bytes(data)
    return path


class FileArtifactCase(unittest.TestCase):
    def setUp(self):
        self.base = real_temp(self)
        self.data = self.base / "data"
        self.data.mkdir(mode=0o750)
        os.chmod(self.data, 0o750)
        self.store = LocalArtifactStore()
        self.addCleanup(self.store.close)
        self.store.bind("mhs://localhost/files")
        self.commands = 0

    def root(self, **options):
        options.setdefault("media_types", {".h5": H5, ".csv": "text/csv"})
        options.setdefault("max_file_bytes", 4096)
        options.setdefault("cleanup", "keep")
        options.setdefault("max_files", 4)
        return NativeFileDirectory(self.data, **options)

    def publisher(self, store=None):
        self.commands += 1
        store = store or self.store
        return store.publisher(ArtifactScope("session", "device", "main", "x-cap.test.files.v1",
                                             f"command-{self.commands}"), lambda: None)

    def assertRefused(self, reason, call, *args):
        with self.assertRaises(MHSError) as caught:
            call(*args)
        self.assertEqual(caught.exception.code, "MHS.CAPABILITY.OUTPUT_INVALID", caught.exception)
        self.assertEqual(caught.exception.data["details"]["reason"], reason, caught.exception)
        return caught.exception

    def assertNothingStored(self, store=None):
        store = store or self.store
        self.assertEqual(store._grants, {})
        self.assertEqual(store._blobs, {})
        self.assertEqual(list(store._root.iterdir()), [])


class DeclarationTests(FileArtifactCase):
    def test_a_valid_declaration_describes_itself_and_holds_no_descriptor(self):
        root = self.root(media_types={".h5": H5}, max_files=8, max_entries=65536)
        self.assertEqual(root.describe(), {"directory": str(self.data), "media_types": {".h5": H5},
                                           "max_file_bytes": 4096, "max_files": 8, "max_entries": 65536,
                                           "cleanup": "keep"})
        self.assertEqual(NativeFileDirectory(str(self.data) + "/", media_types={".h5": H5}, max_file_bytes=1,
                                             cleanup="keep").path, str(self.data))

    def test_paths_that_are_not_the_real_absolute_directory_are_refused(self):
        link = self.base / "link"
        link.symlink_to(self.data, target_is_directory=True)
        write(self.data, "file.h5", b"x")
        inner = self.data / "inner"
        inner.mkdir()
        for path in ("relative/data", "/", "//", str(self.data) + "/../data", str(self.data) + "/./inner",
                     str(self.base) + "//data", str(self.data) + "\x00", "", str(link), str(link) + "/inner",
                     str(self.data / "missing"), str(self.data / "file.h5")):
            with self.subTest(path=path), self.assertRaises(ValueError):
                NativeFileDirectory(path, media_types={".h5": H5}, max_file_bytes=1, cleanup="keep")
        with self.assertRaises(ValueError):
            NativeFileDirectory(os.fsencode(self.data), media_types={".h5": H5}, max_file_bytes=1, cleanup="keep")
        # A link is named as such before any descriptor walk (the walk with O_NOFOLLOW would refuse it too).
        with self.assertRaises(ValueError) as caught:
            NativeFileDirectory(link, media_types={".h5": H5}, max_file_bytes=1, cleanup="keep")
        self.assertIn("real path", str(caught.exception))

    def test_a_directory_every_user_may_write_is_refused(self):
        os.chmod(self.data, 0o777)
        with self.assertRaises(ValueError):
            self.root()
        os.chmod(self.data, stat.S_ISVTX | 0o777)
        with self.assertRaises(ValueError):
            self.root()

    def test_bounds_media_types_and_cleanup_are_closed(self):
        bad = [dict(max_file_bytes=0), dict(max_file_bytes=16 * 1024 * 1024 + 1), dict(max_file_bytes=True),
               dict(max_file_bytes=1.0), dict(max_files=0), dict(max_files=9), dict(max_entries=0),
               dict(max_entries=65537), dict(cleanup="delete"), dict(cleanup="remove_after_commit"),
               dict(cleanup=None), dict(cleanup="Keep"), dict(media_types={}),
               dict(media_types={"h5": H5}), dict(media_types={".": H5}), dict(media_types={"./h5": H5}),
               dict(media_types={".h5": "Application/X-HDF5"}), dict(media_types={".h5": "hdf5"}),
               dict(media_types={".h5": H5 + "; charset=x"}), dict(media_types=[(".h5", H5)]),
               dict(media_types={f".s{i}": H5 for i in range(17)})]
        for options in bad:
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.root(**options)


class SingleFileTests(FileArtifactCase):
    def test_one_file_is_published_byte_for_byte_with_hash_media_type_and_file_list(self):
        payload = b"\x89HDF\r\n\x1a\n" + bytes(range(256))
        path = write(self.data, "run_1_meta.h5", payload)
        before = os.stat(path)
        pub = self.publisher()
        result = self.root().publish(pub, "run_1_meta.h5")
        digest = hashlib.sha256(payload).hexdigest()
        self.assertEqual(result["media_type"], H5)
        self.assertEqual(result["sha256"], digest)
        self.assertEqual(result["files"], [{"name": "run_1_meta.h5", "size_bytes": len(payload), "sha256": digest,
                                            "media_type": H5}])
        prepared = pub.prepare({"artifact_ref": result["artifact_ref"]})
        self.assertEqual(prepared[0]["digest"], "sha256:" + digest)
        self.assertEqual(prepared[0]["media_type"], H5)
        self.assertEqual(prepared[0]["x-vendor"], {"openmhs.native_files": {
            "format": "openmhs.native-files.v1", "cleanup": "keep", "files": result["files"]}})
        pub.commit()
        read = self.store.read(result["artifact_ref"], "session", lambda scope: None)
        self.assertEqual(read["data"], payload)
        # cleanup "keep": the native's file is untouched and nothing else appeared in its directory
        after = os.stat(path)
        self.assertEqual((after.st_ino, after.st_size, after.st_mtime_ns, after.st_nlink),
                         (before.st_ino, before.st_size, before.st_mtime_ns, before.st_nlink))
        self.assertEqual(path.read_bytes(), payload)
        self.assertEqual(sorted(os.listdir(self.data)), ["run_1_meta.h5"])

    def test_the_longest_declared_suffix_names_the_media_type(self):
        write(self.data, "report.tar.gz", b"tgz")
        write(self.data, "plain.gz", b"gz")
        root = self.root(media_types={".gz": "application/gzip", ".tar.gz": "application/x-gtar"})
        self.assertEqual(root.publish(self.publisher(), "report.tar.gz")["media_type"], "application/x-gtar")
        self.assertEqual(root.publish(self.publisher(), "plain.gz")["media_type"], "application/gzip")
        self.assertIsNone(root.media_type(".gz"))

    def test_names_outside_the_closed_set_are_refused_before_anything_is_opened(self):
        write(self.data, "ok.h5", b"x")
        (self.base / "outside.h5").write_bytes(b"secret")
        root = self.root()
        names = ["../outside.h5", "/etc/hosts", "inner/ok.h5", ".hidden.h5", "-dash.h5", "", "ok.h5\x00",
                 "a" * 126 + ".h5", "sp ace.h5", "ok.h5/", "é.h5", 7, None, b"ok.h5"]
        with patch.object(fa.os, "open", side_effect=AssertionError("opened")):
            for name in names:
                with self.subTest(name=name):
                    self.assertRefused("file_name", root.publish, self.publisher(), name)
                    self.assertRefused("file_name", root.publish, self.publisher(), [name])
        self.assertRefused("file_name", root.publish, self.publisher(), {"ok.h5"})
        self.assertNothingStored()

    def test_undeclared_suffixes_links_special_files_and_missing_files_are_refused(self):
        write(self.data, "notes.txt", b"x")
        outside = self.base / "secret.h5"
        outside.write_bytes(b"secret")
        (self.data / "escape.h5").symlink_to(outside)
        write(self.data, "target.h5", b"target")
        (self.data / "inner.h5").symlink_to(self.data / "target.h5")
        os.link(self.data / "target.h5", self.data / "hard.h5")
        (self.data / "folder.h5").mkdir()
        os.mkfifo(self.data / "pipe.h5")
        root = self.root()
        cases = [("notes.txt", "file_type"), ("escape.h5", "file_link"), ("inner.h5", "file_link"),
                 ("hard.h5", "file_link"), ("target.h5", "file_link"), ("folder.h5", "file_type"),
                 ("pipe.h5", "file_type"), ("absent.h5", "file_missing")]
        for name, reason in cases:
            with self.subTest(name=name):
                self.assertRefused(reason, root.publish, self.publisher(), name)
        self.assertNothingStored()

    def test_empty_and_oversized_files_are_refused_by_size_before_reading(self):
        write(self.data, "empty.h5", b"")
        write(self.data, "big.h5", b"x" * 4097)
        write(self.data, "store.h5", b"x" * 64)
        root = self.root()
        reads = []
        original = fa.os.read
        with patch.object(fa.os, "read", side_effect=lambda *args: reads.append(args) or original(*args)):
            self.assertRefused("file_size", root.publish, self.publisher(), "empty.h5")
            self.assertRefused("file_size", root.publish, self.publisher(), "big.h5")
            small = LocalArtifactStore(max_artifact_bytes=32, max_total_bytes=64)
            self.addCleanup(small.close)
            small.bind("mhs://localhost/small")
            self.assertRefused("file_size", root.publish, self.publisher(small), "store.h5")
            self.assertRefused("file_size", root.publish, self.publisher(small), ["store.h5"])
            self.assertNothingStored(small)
        self.assertEqual(reads, [])
        self.assertNothingStored()

    def test_without_an_artifact_store_publication_is_not_ready(self):
        write(self.data, "ok.h5", b"x")
        for context in (None, BridgeContext(), object()):
            with self.subTest(context=context), self.assertRaises(MHSError) as caught:
                self.root().publish(context, "ok.h5")
            self.assertEqual(caught.exception.code, "MHS.DEVICE.NOT_READY")

    def test_the_command_publisher_is_taken_from_the_driver_context(self):
        write(self.data, "ok.h5", b"ctx")
        pub = self.publisher()
        context = BridgeContext(extra={"_mhs_artifact_publisher": pub})
        result = self.root().publish(context, "ok.h5")
        self.assertEqual(pub._ids[0], result["artifact_ref"].rsplit("/", 1)[1])

    def test_a_cancelled_command_publishes_nothing(self):
        write(self.data, "a.h5", b"a")
        write(self.data, "b.h5", b"b")
        event = threading.Event()
        event.set()
        context = BridgeContext(cancel_event=event, extra={"_mhs_artifact_publisher": self.publisher()})
        with self.assertRaises(Cancelled):
            self.root().publish(context, "a.h5")
        # cancelled between two files of a bundle
        event = threading.Event()
        context = BridgeContext(cancel_event=event, extra={"_mhs_artifact_publisher": self.publisher()})
        original = NativeFileDirectory._read

        def read_then_cancel(directory_fd, fd, name, before):
            data = original(directory_fd, fd, name, before)
            event.set()
            return data

        with patch.object(NativeFileDirectory, "_read", staticmethod(read_then_cancel)):
            with self.assertRaises(Cancelled):
                self.root().publish(context, ["a.h5", "b.h5"])
        self.assertNothingStored()

    def test_store_capacity_refusal_leaves_no_grant(self):
        write(self.data, "a.h5", b"a" * 16)
        full = LocalArtifactStore(max_artifacts=1)
        self.addCleanup(full.close)
        full.bind("mhs://localhost/full")
        first = self.publisher(full)
        first.prepare({"artifact_ref": self.root().publish(first, "a.h5")["artifact_ref"]})
        first.commit()
        with self.assertRaises(MHSError) as caught:
            self.root().publish(self.publisher(full), "a.h5")
        self.assertEqual(caught.exception.data["details"]["reason"], "artifact_capacity")
        self.assertEqual(len(full._grants), 1)


class ChangeWhileReadingTests(FileArtifactCase):
    def opened(self, name, data=b"0123456789"):
        write(self.data, name, data)
        root = self.root()
        directory_fd = root._root()
        self.addCleanup(os.close, directory_fd)
        fd, info = root._open(directory_fd, name)
        self.addCleanup(os.close, fd)
        return directory_fd, fd, info

    def test_growth_shrinking_rewrites_renames_and_replacements_are_refused(self):
        directory_fd, fd, info = self.opened("grow.h5")
        with open(self.data / "grow.h5", "ab") as stream:
            stream.write(b"more")
        self.assertRefused("file_changed", NativeFileDirectory._read, directory_fd, fd, "grow.h5", info)

        directory_fd, fd, info = self.opened("shrink.h5")
        os.truncate(self.data / "shrink.h5", 3)
        self.assertRefused("file_changed", NativeFileDirectory._read, directory_fd, fd, "shrink.h5", info)

        directory_fd, fd, info = self.opened("touch.h5")
        os.utime(self.data / "touch.h5", ns=(info.st_atime_ns, info.st_mtime_ns + 5_000_000_000))
        self.assertRefused("file_changed", NativeFileDirectory._read, directory_fd, fd, "touch.h5", info)

        directory_fd, fd, info = self.opened("moved.h5")
        os.rename(self.data / "moved.h5", self.data / "elsewhere.h5")
        self.assertRefused("file_changed", NativeFileDirectory._read, directory_fd, fd, "moved.h5", info)

        directory_fd, fd, info = self.opened("swap.h5")
        write(self.data, "swap.tmp", b"0123456789")
        os.replace(self.data / "swap.tmp", self.data / "swap.h5")
        self.assertRefused("file_changed", NativeFileDirectory._read, directory_fd, fd, "swap.h5", info)

        directory_fd, fd, info = self.opened("same.h5")
        self.assertEqual(NativeFileDirectory._read(directory_fd, fd, "same.h5", info), b"0123456789")

    def test_a_name_that_names_another_inode_after_the_read_is_refused(self):
        # integrator v4 (2026-11-05; Claude Sonnet safety lens M1 of p4-artifacts): the final check alone. The open
        # descriptor still equals its stat (size, links, times), but the name now names another inode, as after the
        # file was moved away on a file system that keeps its change time on a rename and a new file took the name.
        # (On this platform a rename changes the ctime, so the earlier check refuses the real rename first.)
        directory_fd, fd, info = self.opened("read.h5")
        write(self.data, "taken.h5", b"0123456789")
        refused = self.assertRefused("file_changed", NativeFileDirectory._read, directory_fd, fd, "taken.h5", info)
        self.assertIn("was replaced while it was read", str(refused))

    def test_a_file_swapped_for_a_link_between_the_check_and_the_open_is_refused(self):
        write(self.data, "race.h5", b"x")
        (self.base / "secret.h5").write_bytes(b"secret")
        root = self.root()
        original = fa.os.open

        def swap(path, flags, *args, **kwargs):
            if path == "race.h5":
                os.unlink(self.data / "race.h5")
                os.symlink(self.base / "secret.h5", self.data / "race.h5")
            return original(path, flags, *args, **kwargs)

        with patch.object(fa.os, "open", side_effect=swap):
            self.assertRefused("file_changed", root.publish, self.publisher(), "race.h5")
        self.assertNothingStored()

    def test_a_replaced_relinked_or_opened_up_directory_refuses_publication(self):
        write(self.data, "a.h5", b"a")
        root = self.root()
        os.rename(self.data, self.base / "moved")
        (self.data).mkdir()
        write(self.data, "a.h5", b"a")
        self.assertRefused("file_directory", root.publish, self.publisher(), "a.h5")
        self.assertRefused("file_directory", root.matching, r".*")
        os.unlink(self.data / "a.h5")
        os.rmdir(self.data)
        (self.data).symlink_to(self.base / "moved", target_is_directory=True)
        self.assertRefused("file_directory", root.publish, self.publisher(), "a.h5")
        os.unlink(self.data)
        os.rename(self.base / "moved", self.data)
        self.assertEqual(root.publish(self.publisher(), "a.h5")["files"][0]["name"], "a.h5")
        os.chmod(self.data, 0o757)
        self.assertRefused("file_directory", root.publish, self.publisher(), "a.h5")
        os.chmod(self.data, 0o750)
        parent = self.base / "parent"
        parent.mkdir()
        nested = parent / "data"
        nested.mkdir()
        write(nested, "n.h5", b"n")
        deep = NativeFileDirectory(nested, media_types={".h5": H5}, max_file_bytes=16, cleanup="keep")
        os.rename(parent, self.base / "parent-real")
        (self.base / "parent").symlink_to(self.base / "parent-real", target_is_directory=True)
        self.assertRefused("file_directory", deep.publish, self.publisher(), "n.h5")


class BundleTests(FileArtifactCase):
    def test_a_bundle_is_a_deterministic_stored_zip_with_a_manifest(self):
        files = {"run_2_000001.h5": b"frames-one", "run_2_000002.h5": b"frames-two", "run_2_meta.h5": b"meta"}
        for name, data in files.items():
            write(self.data, name, data)
        root = self.root()
        first = root.publish(self.publisher(), ["run_2_meta.h5", "run_2_000002.h5", "run_2_000001.h5"])
        second_pub = self.publisher()
        second = root.publish(second_pub, ("run_2_000001.h5", "run_2_000002.h5", "run_2_meta.h5"))
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertEqual(first["media_type"], "application/zip")
        self.assertEqual([item["name"] for item in second["files"]], sorted(files))
        second_pub.prepare({"artifact_ref": second["artifact_ref"]})
        second_pub.commit()
        data = self.store.read(second["artifact_ref"], "session", lambda scope: None)["data"]
        self.assertEqual(hashlib.sha256(data).hexdigest(), second["sha256"])
        archive = zipfile.ZipFile(io.BytesIO(data))
        self.assertEqual(archive.namelist(), ["manifest.json"] + [f"files/{name}" for name in sorted(files)])
        for info in archive.infolist():
            self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
            self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
        manifest = json.loads(archive.read("manifest.json"))
        self.assertEqual(manifest["format"], "openmhs.native-files.v1")
        for item in manifest["files"]:
            content = archive.read(item["member"])
            self.assertEqual(content, files[item["name"]])
            self.assertEqual(item["sha256"], hashlib.sha256(content).hexdigest())
            self.assertEqual(item["size_bytes"], len(content))
            self.assertEqual(item["media_type"], H5)
        self.assertEqual([{key: value for key, value in item.items() if key != "member"}
                          for item in manifest["files"]], second["files"])

    def test_bundle_counts_duplicates_and_bounds_are_refused_before_reading(self):
        for index in range(5):
            write(self.data, f"f{index}.h5", b"x" * 10)
        root = self.root(max_files=4)
        original = fa.os.read
        reads = []
        with patch.object(fa.os, "read", side_effect=lambda *args: reads.append(args) or original(*args)):
            self.assertRefused("file_count", root.publish, self.publisher(), [])
            self.assertRefused("file_count", root.publish, self.publisher(), [f"f{i}.h5" for i in range(5)])
            self.assertRefused("file_count", root.publish, self.publisher(), ["f0.h5", "f0.h5"])
            tight = LocalArtifactStore(max_artifact_bytes=300, max_total_bytes=300)
            self.addCleanup(tight.close)
            tight.bind("mhs://localhost/tight")
            self.assertRefused("file_size", root.publish, self.publisher(tight), ["f0.h5", "f1.h5", "f2.h5"])
            with patch.object(fa, "MAX_ARTIFACT_METADATA_BYTES", 100):
                self.assertRefused("file_count", root.publish, self.publisher(), ["f0.h5", "f1.h5"])
        self.assertEqual(reads, [])
        self.assertNothingStored()

    def test_the_largest_bundle_metadata_fits_the_descriptor_bound(self):
        names = [f"{index}" + "n" * 124 + ".h5" for index in range(8)]
        for name in names:
            write(self.data, name, b"x")
        long_type = "application/" + "x" * 115
        root = self.root(media_types={".h5": long_type}, max_files=8)
        result = root.publish(self.publisher(), names)
        self.assertEqual(len(result["files"]), 8)
        self.assertLessEqual(len(json.dumps({"openmhs.native_files": {"format": fa.FORMAT, "cleanup": "keep",
                                                                       "files": result["files"]}})), 4096)


class MatchingTests(FileArtifactCase):
    def test_matching_lists_only_regular_files_of_the_closed_set_sorted(self):
        for name in ("run_3_meta.h5", "run_3_000001.h5", "run_30_000001.h5", "run_3.nxs", ".run_3_x.h5"):
            write(self.data, name, b"x")
        (self.data / "run_3_link.h5").symlink_to(self.data / "run_3_meta.h5")
        (self.data / "run_3_dir.h5").mkdir()
        os.mkfifo(self.data / "run_3_fifo.h5")
        root = self.root()
        self.assertEqual(root.matching(r"run_3_[A-Za-z0-9._-]+\.h5"), ["run_3_000001.h5", "run_3_meta.h5"])
        self.assertEqual(root.matching(r"nothing"), [])
        with self.assertRaises(TypeError):
            root.matching(b"run")

    def test_more_matches_or_entries_than_declared_refuse_instead_of_truncating(self):
        for index in range(5):
            write(self.data, f"m{index}.h5", b"x")
        self.assertRefused("file_count", self.root(max_files=4).matching, r"m\d\.h5")
        self.assertEqual(len(self.root(max_files=5).matching(r"m\d\.h5")), 5)
        self.assertRefused("file_count", self.root(max_entries=4).matching, r"nothing")
        self.assertEqual(self.root(max_entries=5).matching(r"nothing"), [])


class EndpointTests(FileArtifactCase):
    """A decorated driver publishes through the real endpoint: receipt descriptor, MCP-free local read."""

    def make_driver(self):
        from mhs.driver import Driver, Field, action, estop

        directory = self.data

        class Native:
            def __init__(self):
                self.runs = 0

            def acquire(self):
                self.runs += 1
                name = f"run_{self.runs}.csv"
                (directory / name).write_bytes(b"wavelength,intensity\n500,%d\n" % self.runs)
                return name

            def stop(self):
                pass

        class Instrument(Driver):
            device_id, device_kind, mode, risk = "file-instrument", "instrument", "hardware", "R1"
            native = "instrument:Instrument"
            backends = {"fake": Native}
            safe_state = "acquisition stopped"

            def setup(self):
                self.files = NativeFileDirectory(directory, media_types={".csv": "text/csv"}, max_file_bytes=1024,
                                                 cleanup="keep")

            @action(name="x-cap.openmhs-tutorial.acquire-file.v1", description="Acquire one run and publish its file",
                    output={"artifact_ref": Field("string", description="The run's file"),
                            "name": Field("string", description="File name the native reported")})
            def acquire(self):
                name = self.native.acquire()
                return {"artifact_ref": self.files.publish(self.ctx, name)["artifact_ref"], "name": name}

            @estop
            def stop(self):
                self.native.stop()

        return Instrument

    def test_receipt_descriptor_and_original_session_read(self):
        from mhs.client import InProcessTransport, MHSClient
        from mhs.driver.build import build_server

        driver = self.make_driver()(backend="fake")
        store = LocalArtifactStore()
        server = build_server(driver, artifact_store=store)
        self.addCleanup(server.close)
        client = MHSClient(InProcessTransport(server))
        client.hello()
        device_id = next(iter(server.devices))
        capability = "x-cap.openmhs-tutorial.acquire-file.v1"
        client.open_session([device_id], capabilities=[capability])
        receipt = client.invoke(capability, {}, device_id=device_id)
        self.assertEqual(receipt["status"], "completed", receipt)
        expected = b"wavelength,intensity\n500,1\n"
        artifact = receipt["artifacts"][0]
        self.assertEqual(artifact["uri"], receipt["output"]["artifact_ref"])
        self.assertEqual(artifact["digest"], "sha256:" + hashlib.sha256(expected).hexdigest())
        self.assertEqual(artifact["media_type"], "text/csv")
        self.assertEqual(artifact["x-vendor"]["openmhs.native_files"]["files"][0]["name"], "run_1.csv")
        read = client.read_artifact(artifact["uri"], session_id=client.session_id)
        self.assertEqual(read["data"], expected)
        # the native's file stays where it was written
        self.assertEqual((self.data / "run_1.csv").read_bytes(), expected)

    def test_without_a_store_the_command_fails_and_publishes_nothing(self):
        from mhs.client import InProcessTransport, MHSClient
        from mhs.driver.build import build_server

        driver = self.make_driver()(backend="fake")
        server = build_server(driver)
        self.addCleanup(server.close)
        client = MHSClient(InProcessTransport(server))
        client.hello()
        device_id = next(iter(server.devices))
        capability = "x-cap.openmhs-tutorial.acquire-file.v1"
        client.open_session([device_id], capabilities=[capability])
        receipt = client.invoke(capability, {}, device_id=device_id)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.NOT_READY")
        self.assertNotIn("artifacts", receipt)


GATE_DRIVER = '''from mhs.driver import Driver, Field, action, estop, read, reset
from mhs.file_artifacts import NativeFileDirectory


class Instrument(Driver):
    device_id, device_kind, mode, risk = "gate-files", "instrument", "hardware", "R1"
    native = "instrument:Instrument"
    backends = {"fake": ".fake:FakeInstrument", "hardware": ".native:connect"}
    safe_state = "Acquisition stopped"

    def setup(self):
        self.files = NativeFileDirectory(self.native.output_directory, media_types={".csv": "text/csv"},
                                         max_file_bytes=4096, cleanup="keep")

    @read("runs", type="integer", description="Runs the instrument wrote")
    def runs(self):
        return self.native.runs

    @action(name="x-cap.openmhs-tutorial.acquire-file.v1", description="Acquire one run and publish its report file",
            output={"artifact_ref": Field("string", description="The run's report file"),
                    "name": Field("string", description="File name the instrument reported")})
    def acquire(self):
        name = self.native.acquire()
        published = self.files.publish(self.ctx, name)
        return {"artifact_ref": published["artifact_ref"], "name": name}

    @estop
    def stop(self):
        self.native.stop()

    @reset
    def reset_instrument(self):
        self.native.reset()
'''
GATE_NATIVE = '''# Synthetic source contract: each run writes one report file into the instrument's output directory.
import os
import shutil
import tempfile
import weakref


class Instrument:
    def __init__(self):
        self.output_directory = os.path.realpath(tempfile.mkdtemp(prefix="mhs-file-gate-"))
        weakref.finalize(self, shutil.rmtree, self.output_directory, True)
        self.runs = 0
        self.stopped = False

    def acquire(self):
        if self.stopped:
            raise RuntimeError("instrument stopped")
        self.runs += 1
        name = "run_%d.csv" % self.runs
        with open(os.path.join(self.output_directory, name), "wb") as stream:
            stream.write(b"wavelength,intensity\\n500,1\\n")
        return name

    def stop(self):
        self.stopped = True

    def reset(self):
        self.stopped = False
'''


class GateTests(unittest.TestCase):
    def package(self):
        from tests.driver import gate_support as gs

        directory = gs.copy_tutorial(self)
        (directory / "driver.py").write_text(GATE_DRIVER)
        (directory / "vendor" / "instrument.py").write_text(GATE_NATIVE)
        (directory / "fake.py").write_text(GATE_NATIVE.replace("class Instrument:", "class FakeInstrument:"))
        (directory / "native.py").write_text(
            'def connect(**options):\n    raise AssertionError("Hardware factory must never run in the gate")\n')
        (directory / "site-limits.example.json").unlink()
        gs.edit_json(directory, "task.json", safety={"expected_mode": "hardware", "risk_floor": "R1"},
                     entry_symbols=[{"symbol": "instrument:Instrument", "file": "instrument.py", "line": 8,
                                     "confidence": "ast"}])
        gs.edit_json(directory, "driver.lock.json",
                     backends={"hardware": ".native:connect", "fake": ".fake:FakeInstrument"})
        gs.regenerate(directory)
        return gs, directory

    def test_the_gate_owns_a_default_store_for_a_declared_artifact_output_and_passes(self):
        from mhs.driver.check import _Context

        gs, directory = self.package()
        stores = []
        original = _Context._artifact_store

        def observe(driver):
            store = original(driver)
            stores.append(store)
            return store

        with patch.object(_Context, "_artifact_store", staticmethod(observe)):
            report = gs.check(directory)
        self.assertTrue(report["passed"], [(g["id"], g["findings"]) for g in report["gates"] if g["findings"]])
        self.assertEqual(gs.statuses(report)["G6"], "pass")
        self.assertTrue(stores)
        self.assertTrue(all(store is not None for store in stores))
        self.assertTrue(all(store._closed for store in stores))

    def test_declared_outputs_select_the_store_and_other_drivers_get_none(self):
        from mhs.driver.check import _Context, _declares_artifact_output
        from mhs.driver import Driver, Field, action, estop

        class Plain(Driver):
            device_id, device_kind, mode, risk = "plain", "instrument", "hardware", "R0"
            native = "x:Y"
            backends = {"fake": object}
            safe_state = "idle"

            @action(name="x-cap.openmhs-tutorial.ping.v1", description="Ping",
                    output={"ok": Field("boolean", description="ok")})
            def ping(self):
                return {"ok": True}

            @estop
            def stop(self):
                pass

        plain = Plain(backend="fake")
        self.assertFalse(any(_declares_artifact_output(binding) for binding in plain._model.bindings))
        self.assertIsNone(_Context._artifact_store(plain))
        instrument = EndpointTests.make_driver(self._endpoint_case())(backend="fake")
        self.assertTrue(any(_declares_artifact_output(binding) for binding in instrument._model.bindings))
        store = _Context._artifact_store(instrument)
        self.assertIsInstance(store, LocalArtifactStore)
        store.close()

    def _endpoint_case(self):
        case = EndpointTests("test_receipt_descriptor_and_original_session_read")
        case.data = real_temp(self)
        return case

    def test_mcp_resource_read_returns_the_file_bytes(self):
        from mhs.client import InProcessTransport, MHSClient
        from mhs.driver.check import _Context
        from mhs.mcp import MCPPolicy, MCPProjection

        _gs, directory = self.package()
        ctx = _Context(directory, "fake", None, None, False)
        self.addCleanup(ctx.close)
        endpoint = ctx.endpoint()
        self.addCleanup(endpoint.close)
        client = MHSClient(InProcessTransport(endpoint.server))
        client.hello()
        projection = MCPProjection(client, policy=MCPPolicy(enabled=True, allow_hardware=False))
        self.addCleanup(projection.close)

        def rpc(method, params=None):
            return projection.handle_message({"jsonrpc": "2.0", "id": method, "method": method,
                                              "params": params or {}})

        rpc("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                           "clientInfo": {"name": "file-artifact-test", "version": "1"}})
        tools = rpc("tools/list")["result"]["tools"]
        tool = next(item["name"] for item in tools if item["name"].startswith("mhs__gate_files"))
        result = rpc("tools/call", {"name": tool, "arguments": {}})["result"]
        receipt = result["structuredContent"]["receipt"]
        self.assertEqual(receipt["status"], "completed", receipt)
        artifact = receipt["artifacts"][0]
        content = rpc("resources/read", {"uri": artifact["uri"]})["result"]["contents"][0]
        data = base64.b64decode(content["blob"], validate=True)
        self.assertEqual(data, b"wavelength,intensity\n500,1\n")
        self.assertEqual(content["mimeType"], "text/csv")
        self.assertEqual(artifact["digest"], "sha256:" + hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    unittest.main()
