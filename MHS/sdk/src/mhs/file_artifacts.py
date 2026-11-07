"""Publish files that a native wrote, from one declared directory, through the endpoint's artifact store.

A driver whose upstream writes its primary output to files (an area detector's file writer, an instrument that
exports a report) declares one :class:`NativeFileDirectory` per output directory and publishes named regular files of
that directory through the command's :class:`~mhs.artifacts.ArtifactPublisher`.  The result is an ordinary local
artifact (``docs/image-artifacts.md``): the receipt's ``artifacts[]`` descriptor carries the sha256 digest and media
type of the published bytes, and ``x-vendor["openmhs.native_files"]`` lists every file with its own name, size,
sha256 and media type.  One file is published as its own bytes; a list of files as one deterministic ZIP bundle
(``application/zip``) whose ``manifest.json`` repeats that list.

Fail-closed rules (``docs/file-artifacts.md``):

* The directory is declared by its real absolute path: no symbolic link in any component, never the file-system
  root, never writable by every user.  Its identity (device, inode) is fixed at declaration; every publication opens
  the path again one component at a time without following a link and refuses when the identity differs.
* A name is one path component of a closed ASCII set (``[A-Za-z0-9][A-Za-z0-9._-]{0,127}``): no separator, no
  ``..``, no hidden name, so nothing outside the directory or below it can be named.
* A file must be a regular file with one link before it is opened; it is opened relative to the directory with
  ``O_NOFOLLOW``, must still be the same inode, non-empty and at most ``max_file_bytes``; it is read in a bounded loop
  and refused when it changed while it was read or when its name no longer refers to it.
* The media type comes from the declared suffix table (the longest matching suffix); any other file is refused.
* At most ``max_files`` files per artifact, within the store's own per-artifact bound and descriptor metadata bound;
  :meth:`NativeFileDirectory.matching` examines at most ``max_entries`` directory entries and refuses more matches
  than ``max_files`` instead of truncating.
* Cleanup policy ``keep`` (the only policy): the native's file is never modified, renamed or removed.  The published
  copy is the artifact store's (private, content-addressed, removed when the grant expires or the endpoint closes).

The helper reads only the names the driver passes.  A driver derives them from the native's own state (an
acquisition id the device reports, a file name its API returns), never from command input: a binding that passed a
caller's string through would make the declared directory a file server.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import stat
import zipfile
from typing import Any, Mapping, Sequence

from .artifacts import _MEDIA, MAX_ARTIFACT_BYTES, MAX_ARTIFACT_METADATA_BYTES, ArtifactPublisher, publisher_from_context
from .errors import MHSError
from .signals import Cancelled

__all__ = ["BUNDLE_MEDIA_TYPE", "CLEANUP_POLICIES", "FORMAT", "MAX_ENTRIES", "MAX_FILES", "VENDOR_KEY",
           "NativeFileDirectory"]

#: Format of the bundle manifest and of the descriptor extension.
FORMAT = "openmhs.native-files.v1"
#: Key of the descriptor ``x-vendor`` extension that lists the published files.
VENDOR_KEY = "openmhs.native_files"
#: Media type of a bundle of several files.
BUNDLE_MEDIA_TYPE = "application/zip"
#: Largest number of files in one artifact (with 128-character names it keeps the extension under 4096 bytes).
MAX_FILES = 8
#: Largest number of directory entries :meth:`NativeFileDirectory.matching` may examine.
MAX_ENTRIES = 65536
#: Largest number of declared suffixes.
MAX_SUFFIXES = 16
#: The supported cleanup policies of the native's files.
CLEANUP_POLICIES = ("keep",)

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_SUFFIX = re.compile(r"\.[A-Za-z0-9][A-Za-z0-9._-]{0,15}\Z")
_MAX_PATH = 4096
_CHUNK = 1 << 20
# ``os.open`` is not looked up in ``os.supports_dir_fd``: a process guard (the acceptance gate's device guard) may
# wrap it, and every POSIX build of CPython supports ``dir_fd`` for it.
_POSIX = (os.name == "posix" and hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY")
          and os.stat in os.supports_dir_fd and os.scandir in os.supports_fd)
_DIRECTORY_FLAGS = (os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_CLOEXEC", 0))
_FILE_FLAGS = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
               | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOCTTY", 0))
_MANIFEST = "manifest.json"
_MEMBER_PREFIX = "files/"
#: The JSON text of a sha256 that has not been computed yet (the metadata bound is checked before any read).
_PENDING_SHA256 = "0" * 64


def _refuse(message: str, reason: str) -> MHSError:
    """A refused publication: no artifact grant is created and the command's receipt is failed."""
    return MHSError("MHS.CAPABILITY.OUTPUT_INVALID", message, {"retryable": False, "details": {"reason": reason}})


def _count(value: Any, label: str, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{label} must be an integer in 1..{maximum}")
    return value


def _same_file(first: os.stat_result, second: os.stat_result) -> bool:
    return (first.st_dev, first.st_ino) == (second.st_dev, second.st_ino)


def _unchanged(first: os.stat_result, second: os.stat_result) -> bool:
    return (_same_file(first, second) and first.st_size == second.st_size and first.st_nlink == second.st_nlink
            and first.st_mtime_ns == second.st_mtime_ns and first.st_ctime_ns == second.st_ctime_ns)


def _check_cancelled(context: Any) -> None:
    event = getattr(context, "cancel_event", None)
    is_set = getattr(event, "is_set", None)
    if callable(is_set) and is_set():
        raise Cancelled("file artifact publication was cancelled")


def _encoded(document: Any) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


class NativeFileDirectory:
    """One declared directory whose regular files a driver may publish as artifacts (module docstring).

    ``directory`` is the real absolute path (``str`` or path-like); ``media_types`` maps file-name suffixes
    (``".h5"``) to the media type published for them; ``max_file_bytes`` bounds one file (at most 16 MiB, the
    store's absolute bound; the endpoint's store may allow less); ``cleanup`` must be ``"keep"``; ``max_files``
    bounds the files of one artifact (1..8); ``max_entries`` bounds the directory entries one
    :meth:`matching` call examines (1..65536).  Invalid declarations raise :class:`ValueError`, so a driver that
    declares the directory in ``setup()`` fails to open instead of serving a weaker contract.
    """

    def __init__(self, directory: str | os.PathLike[str], *, media_types: Mapping[str, str], max_file_bytes: int,
                 cleanup: str, max_files: int = 1, max_entries: int = 4096) -> None:
        if not _POSIX:
            raise ValueError("native file artifacts need POSIX descriptor-relative opens (O_NOFOLLOW, dir_fd)")
        path = os.fspath(directory)
        if type(path) is not str or not path or len(path) > _MAX_PATH or "\x00" in path:
            raise ValueError("the declared directory must be a non-empty text path of at most 4096 characters")
        if not path.startswith("/"):
            raise ValueError("the declared directory must be an absolute path")
        stripped = path.rstrip("/")
        parts = stripped.split("/")[1:]
        if not stripped or any(part in ("", ".", "..") for part in parts):
            raise ValueError("the declared directory must be a normalised absolute path below the file-system root "
                             "(no '.', '..' or empty component)")
        if os.path.realpath(stripped) != stripped:
            raise ValueError("the declared directory must be its real path: a symbolic link in it is never followed "
                             "(resolve the path before declaring it)")
        if not isinstance(media_types, Mapping) or not 1 <= len(media_types) <= MAX_SUFFIXES:
            raise ValueError(f"media_types must map 1..{MAX_SUFFIXES} file-name suffixes to media types")
        table: dict[str, str] = {}
        for suffix, media_type in media_types.items():
            if type(suffix) is not str or not _SUFFIX.fullmatch(suffix):
                raise ValueError(f"suffix {suffix!r} must be '.' followed by 1..16 letters, digits, '.', '_' or '-'")
            if type(media_type) is not str or len(media_type) > 127 or not _MEDIA.fullmatch(media_type):
                raise ValueError(f"media type {media_type!r} of {suffix!r} is not a lower-case type/subtype")
            table[suffix] = media_type
        self.max_file_bytes = _count(max_file_bytes, "max_file_bytes", MAX_ARTIFACT_BYTES)
        self.max_files = _count(max_files, "max_files", MAX_FILES)
        self.max_entries = _count(max_entries, "max_entries", MAX_ENTRIES)
        if type(cleanup) is not str or cleanup not in CLEANUP_POLICIES:
            raise ValueError(f"cleanup must be one of {list(CLEANUP_POLICIES)}: the SDK never removes or changes a "
                             "file the native wrote")
        self.cleanup = cleanup
        self.media_types = dict(sorted(table.items()))
        self.path = stripped
        self._parts = tuple(parts)
        try:
            fd = self._walk()
        except OSError as exc:
            raise ValueError(f"the declared directory cannot be opened without following a link "
                             f"({type(exc).__name__})") from exc
        try:
            info = os.fstat(fd)
        finally:
            os.close(fd)
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("the declared path is not a directory")
        if info.st_mode & stat.S_IWOTH:
            raise ValueError("the declared directory is writable by every user: its files cannot be attributed to "
                             "the native")
        self._identity = (info.st_dev, info.st_ino)

    def describe(self) -> dict[str, Any]:
        """The declaration (for notes, facts and tests); it holds no secret and no open descriptor."""
        return {"directory": self.path, "media_types": dict(self.media_types), "max_file_bytes": self.max_file_bytes,
                "max_files": self.max_files, "max_entries": self.max_entries, "cleanup": self.cleanup}

    # -- directory --------------------------------------------------------------------------------------------------
    def _walk(self) -> int:
        """Open the declared path from the root, one component at a time, never following a link."""
        fd = os.open("/", _DIRECTORY_FLAGS)
        try:
            for part in self._parts:
                child = os.open(part, _DIRECTORY_FLAGS, dir_fd=fd)
                os.close(fd)
                fd = child
        except BaseException:
            os.close(fd)
            raise
        return fd

    def _root(self) -> int:
        try:
            fd = self._walk()
        except OSError as exc:
            raise _refuse(f"the declared directory cannot be opened without following a link "
                          f"({type(exc).__name__})", "file_directory") from exc
        try:
            info = os.fstat(fd)
            if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != self._identity:
                raise _refuse("the declared directory was replaced after it was declared", "file_directory")
            if info.st_mode & stat.S_IWOTH:
                raise _refuse("the declared directory became writable by every user", "file_directory")
        except BaseException:
            os.close(fd)
            raise
        return fd

    def media_type(self, name: str) -> str | None:
        """The declared media type of ``name`` (longest matching suffix), or ``None``."""
        best = None
        for suffix, media_type in self.media_types.items():
            if name.endswith(suffix) and len(name) > len(suffix) and (best is None or len(suffix) > len(best[0])):
                best = (suffix, media_type)
        return best[1] if best is not None else None

    def matching(self, pattern: str | re.Pattern[str]) -> list[str]:
        """The sorted names of the regular files directly in the directory whose whole name matches ``pattern``.

        Only names of the closed set are candidates; links, directories and special files never match.  More than
        ``max_entries`` entries in the directory, or more than ``max_files`` matches, refuse (``file_count``)
        instead of returning a truncated list.  An empty list is a valid answer.
        """
        if isinstance(pattern, str):
            regex = re.compile(pattern)
        elif isinstance(pattern, re.Pattern) and isinstance(pattern.pattern, str):
            regex = pattern
        else:
            raise TypeError("pattern must be a regular expression over text")
        fd = self._root()
        try:
            names: list[str] = []
            seen = 0
            with os.scandir(fd) as entries:
                for entry in entries:
                    seen += 1
                    if seen > self.max_entries:
                        raise _refuse(f"the declared directory holds more than {self.max_entries} entries",
                                      "file_count")
                    name = entry.name
                    if not _NAME.fullmatch(name) or not regex.fullmatch(name):
                        continue
                    try:
                        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    except FileNotFoundError:
                        continue
                    if stat.S_ISREG(info.st_mode):
                        names.append(name)
                        if len(names) > self.max_files:
                            raise _refuse(f"more than {self.max_files} files match: the artifact would be "
                                          "incomplete", "file_count")
            return sorted(names)
        finally:
            os.close(fd)

    # -- publication ------------------------------------------------------------------------------------------------
    def _open(self, directory_fd: int, name: str) -> tuple[int, os.stat_result]:
        try:
            entry = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError as exc:
            raise _refuse(f"{name} does not exist in the declared directory", "file_missing") from exc
        except OSError as exc:
            raise _refuse(f"{name} cannot be examined ({type(exc).__name__})", "file_unreadable") from exc
        if stat.S_ISLNK(entry.st_mode):
            raise _refuse(f"{name} is a symbolic link, which is never followed", "file_link")
        if not stat.S_ISREG(entry.st_mode):
            raise _refuse(f"{name} is not a regular file", "file_type")
        try:
            fd = os.open(name, _FILE_FLAGS, dir_fd=directory_fd)
        except OSError as exc:
            raise _refuse(f"{name} cannot be opened without following a link ({type(exc).__name__})",
                          "file_changed") from exc
        try:
            info = os.fstat(fd)
            if not _same_file(info, entry) or not stat.S_ISREG(info.st_mode):
                raise _refuse(f"{name} was replaced while it was opened", "file_changed")
            if info.st_nlink != 1:
                raise _refuse(f"{name} has {info.st_nlink} links; a hard-linked file is refused", "file_link")
            if not 0 < info.st_size <= self.max_file_bytes:
                raise _refuse(f"{name} has {info.st_size} bytes; a file must hold 1..{self.max_file_bytes}",
                              "file_size")
        except BaseException:
            os.close(fd)
            raise
        return fd, info

    @staticmethod
    def _read(directory_fd: int, fd: int, name: str, before: os.stat_result) -> bytes:
        chunks: list[bytes] = []
        total = 0
        expected = before.st_size
        while True:
            chunk = os.read(fd, min(_CHUNK, expected + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > expected:
                raise _refuse(f"{name} grew while it was read", "file_changed")
        if total != expected:
            raise _refuse(f"{name} shrank while it was read", "file_changed")
        if not _unchanged(before, os.fstat(fd)):
            raise _refuse(f"{name} changed while it was read", "file_changed")
        try:
            entry = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except OSError as exc:
            raise _refuse(f"{name} was renamed or removed while it was read", "file_changed") from exc
        if not _same_file(entry, before):
            raise _refuse(f"{name} was replaced while it was read", "file_changed")
        return b"".join(chunks)

    def publish(self, context: Any, names: str | Sequence[str]) -> dict[str, Any]:
        """Publish one file (``names`` a string) or a bundle of files (a list or tuple) of the declared directory.

        ``context`` is the driver's ``self.ctx`` (or the command's :class:`~mhs.artifacts.ArtifactPublisher`).
        Returns ``{"artifact_ref", "media_type", "size_bytes", "sha256", "files": [{"name", "size_bytes", "sha256",
        "media_type"}]}``; the driver returns ``artifact_ref`` in its output (the endpoint refuses an output that does
        not name the published artifact).  Every refusal raises before a grant exists: ``MHS.DEVICE.NOT_READY``
        without an artifact store, :class:`~mhs.signals.Cancelled` once the command is cancelled, otherwise
        ``MHS.CAPABILITY.OUTPUT_INVALID`` with ``details.reason``.
        """
        publisher = context if isinstance(context, ArtifactPublisher) else publisher_from_context(context)
        if publisher is None:
            raise MHSError("MHS.DEVICE.NOT_READY", "file artifacts need the endpoint's artifact store",
                           {"retryable": False})
        bundle = not isinstance(names, str)
        if bundle and not isinstance(names, (list, tuple)):
            raise _refuse("names must be one file name or a list of file names", "file_name")
        listed = list(names) if bundle else [names]
        if not 1 <= len(listed) <= self.max_files:
            raise _refuse(f"an artifact holds 1..{self.max_files} files, not {len(listed)}", "file_count")
        media: dict[str, str] = {}
        for name in listed:
            if type(name) is not str or not _NAME.fullmatch(name):
                raise _refuse(f"{name!r} is not one file name of [A-Za-z0-9][A-Za-z0-9._-]{{0,127}}", "file_name")
            if name in media:
                raise _refuse(f"{name} is listed twice", "file_count")
            media_type = self.media_type(name)
            if media_type is None:
                raise _refuse(f"{name} has no declared suffix ({sorted(self.media_types)})", "file_type")
            media[name] = media_type
        if bundle:
            listed.sort()
        _check_cancelled(context)
        directory_fd = self._root()
        contents: dict[str, bytes] = {}
        try:
            opened: list[tuple[str, int, os.stat_result]] = []
            try:
                for name in listed:
                    fd, info = self._open(directory_fd, name)
                    opened.append((name, fd, info))
                sizes = {name: info.st_size for name, _fd, info in opened}
                if bundle:
                    # ZIP_STORED with ASCII names: 30 + 46 header bytes and the name twice per member, 22 at the end.
                    members = 22 + 76 + 2 * len(_MANIFEST) + sum(
                        76 + 2 * len(_MEMBER_PREFIX + name) + size for name, size in sizes.items())
                    if members > publisher.max_bytes:
                        raise _refuse(f"the {len(listed)} files need more than the store's {publisher.max_bytes}-byte "
                                      "artifact bound", "file_size")
                elif sizes[listed[0]] > publisher.max_bytes:
                    raise _refuse(f"{listed[0]} exceeds the store's {publisher.max_bytes}-byte artifact bound",
                                  "file_size")
                pending = self._vendor([{"name": name, "size_bytes": sizes[name], "sha256": _PENDING_SHA256,
                                         "media_type": media[name]} for name in listed])
                if len(_encoded(pending)) > MAX_ARTIFACT_METADATA_BYTES:
                    raise _refuse("the file list exceeds the descriptor metadata bound", "file_count")
                for name, fd, info in opened:
                    _check_cancelled(context)
                    contents[name] = self._read(directory_fd, fd, name, info)
            finally:
                for _name, fd, _info in opened:
                    os.close(fd)
        finally:
            os.close(directory_fd)
        files = [{"name": name, "size_bytes": len(contents[name]),
                  "sha256": hashlib.sha256(contents[name]).hexdigest(), "media_type": media[name]} for name in listed]
        if bundle:
            data = self._bundle(files, contents, publisher.max_bytes)
            media_type = BUNDLE_MEDIA_TYPE
        else:
            data = contents[listed[0]]
            media_type = media[listed[0]]
        _check_cancelled(context)
        descriptor = publisher.publish(data, media_type, output_field="artifact_ref", x_vendor=self._vendor(files))
        return {"artifact_ref": descriptor["uri"], "media_type": media_type, "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(), "files": [dict(item) for item in files]}

    def _vendor(self, files: list[dict[str, Any]]) -> dict[str, Any]:
        return {VENDOR_KEY: {"format": FORMAT, "cleanup": self.cleanup, "files": [dict(item) for item in files]}}

    @staticmethod
    def _bundle(files: list[dict[str, Any]], contents: Mapping[str, bytes], limit: int) -> bytes:
        manifest = _encoded({"format": FORMAT, "files": [{**item, "member": _MEMBER_PREFIX + item["name"]}
                                                         for item in files]})
        members = [(_MANIFEST, manifest)] + [(_MEMBER_PREFIX + item["name"], contents[item["name"]]) for item in files]
        expected = 22 + sum(76 + 2 * len(member) + len(value) for member, value in members)
        if expected > limit:
            raise _refuse(f"the bundle needs {expected} bytes, more than the store's {limit}-byte artifact bound",
                          "file_size")
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
            for member, value in members:
                info = zipfile.ZipInfo(member, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100600 << 16
                archive.writestr(info, value)
        result = output.getvalue()
        if len(result) != expected:
            raise _refuse("the bundle layout differs from its bounded size", "file_size")
        return result
