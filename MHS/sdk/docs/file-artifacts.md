# Files a native wrote, published as artifacts

Some upstream APIs never hand their primary output to the caller: an area detector's file writer puts frames into
HDF5 files, an instrument exports a report next to its data. `mhs.file_artifacts` lets a direct `Driver` publish such
files through the endpoint's [local artifact store](image-artifacts.md), with the same grants, receipts, expiry and
MCP resource reads as an image or a point cloud. It is opt-in and fail-closed: a file is published only from one
directory the driver declared, only by a name the driver passes, only as a bounded regular file that did not change
while it was read.

```python
import re

from mhs.driver import Driver, DriverFailed, Field, action, estop
from mhs.file_artifacts import NativeFileDirectory


class Detector(Driver):
    ...  # identity, backends, facts, safe_state as usual

    def setup(self):
        # The directory the native writes to, as the deployment configured it (here a field of the native).
        self.files = NativeFileDirectory(self.native.output_directory,
                                         media_types={".h5": "application/x-hdf5"},
                                         max_file_bytes=16 * 1024 * 1024, max_files=8, cleanup="keep")

    @action(name="x-cap.example.collection-files.v1",
            description="Publish the files of the last collection as one bounded artifact",
            output={"artifact_ref": Field("string", description="ZIP of the collection's files"),
                    "files": Field("integer", description="Number of files in the artifact")})
    def collection_files(self):
        # The name prefix comes from the native's own state, never from command input.
        names = self.files.matching(re.escape(self.native.acquisition_id()) + r"_[A-Za-z0-9._-]+\.h5")
        if not names:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "no file of this acquisition")
        published = self.files.publish(self.ctx, names)
        return {"artifact_ref": published["artifact_ref"], "files": len(published["files"])}
```

The names and the acquisition id above are illustrative; a package cites the upstream lines that say where its native
writes and how it names the files, and says in its facts and notes what the clone does not state.

## Declaring the directory

`NativeFileDirectory(directory, *, media_types, max_file_bytes, cleanup, max_files=1, max_entries=4096)` raises
`ValueError` for any declaration it cannot honour, so a driver that declares the directory in `setup()` fails to
open instead of serving a weaker contract.

| Argument | Rule |
| --- | --- |
| `directory` | the real absolute path (`str` or path-like): no `.`, `..` or empty component, no symbolic link anywhere in it (resolve it yourself first, for example `os.path.realpath`), not the file-system root, an existing directory that is not writable by every user |
| `media_types` | 1..16 file-name suffixes (`.h5`, `.tar.gz`; 2..17 characters) mapped to lower-case `type/subtype` media types; a file is published with the type of its longest matching suffix, and a file with no declared suffix is refused |
| `max_file_bytes` | 1..16 MiB per file (the store's absolute bound); the endpoint's store may allow less per artifact (2 MiB by default) |
| `max_files` | 1..8 files in one artifact (with 128-character names this keeps the descriptor extension under its 4096-byte bound) |
| `max_entries` | 1..65,536 directory entries that one `matching()` call may examine |
| `cleanup` | `"keep"`, the only policy: the SDK never modifies, renames or removes a file the native wrote |

The declaration fixes the directory's identity (device and inode). Every publication opens the path again from the
root, one component at a time with `O_NOFOLLOW`, and refuses (`file_directory`) when a component became a link, the
directory was replaced (renamed away and recreated), or it became writable by every user. The declaration holds no
open descriptor.

## Publishing

`files.publish(self.ctx, name)` publishes one file as its own bytes and media type. `files.publish(self.ctx, [names])`
publishes 1..`max_files` files as one bundle. Both return

```json
{"artifact_ref": "mhs+artifact://lab/01J...", "media_type": "application/x-hdf5", "size_bytes": 1234,
 "sha256": "...", "files": [{"name": "run_1_meta.h5", "size_bytes": 1234, "sha256": "...",
                             "media_type": "application/x-hdf5"}]}
```

The action returns `artifact_ref` in its output (the endpoint refuses an output that does not name the published
artifact, as for every artifact). The receipt's `artifacts[]` descriptor carries the digest (`sha256:` of the
published bytes), media type, size and expiry, and

```json
{"x-vendor": {"openmhs.native_files": {"format": "openmhs.native-files.v1", "cleanup": "keep",
  "files": [{"name": "run_1_meta.h5", "size_bytes": 1234, "sha256": "...", "media_type": "application/x-hdf5"}]}}}
```

so every file's own hash and media type are in the receipt even when the artifact is a bundle.

`files.matching(pattern)` lists the regular files directly in the directory whose whole name matches the regular
expression, sorted. Links, directories, special files and names outside the closed set never match. It refuses
(`file_count`) when the directory holds more than `max_entries` entries or more than `max_files` files match, rather
than returning a truncated list; an empty list is a valid answer.

### Bundle format

A bundle is `application/zip` with stored (uncompressed) members, fixed dates (1980-01-01) and modes (0600), in a
fixed order: `manifest.json`, then `files/<name>` for each file sorted by name. `manifest.json` is
`{"format": "openmhs.native-files.v1", "files": [{"name", "member", "size_bytes", "sha256", "media_type"}]}` (sorted
keys, compact JSON), so the same files give the same bytes and the same digest. The whole bundle must fit the
store's per-artifact bound; the size is computed from the files' sizes before any byte is read.

## What is refused

Every refusal happens before a grant exists: the command's receipt is `failed` with
`MHS.CAPABILITY.OUTPUT_INVALID` and `details.reason`, and nothing becomes readable.

| Reason | When |
| --- | --- |
| `file_name` | a name that is not one component of `[A-Za-z0-9][A-Za-z0-9._-]{0,127}` (a separator, `..`, a hidden or empty name, a non-ASCII character), or names that are not a string or a list/tuple of strings; nothing is opened |
| `file_type` | a name without a declared suffix, a directory, a FIFO, a socket or a device node (checked with `lstat` before any open, so a FIFO never blocks and a device is never opened) |
| `file_link` | a symbolic link (never followed, wherever it points) or a regular file with more than one hard link |
| `file_missing` | no entry of that name |
| `file_size` | an empty file, a file above `max_file_bytes`, or a file or bundle above the store's per-artifact bound (checked before reading) |
| `file_count` | no name, a name listed twice, more than `max_files` names or matches, more than `max_entries` entries, or a file list above the 4096-byte descriptor metadata bound |
| `file_changed` | the entry was swapped between the check and the open (a link or another inode), the file grew, shrank or changed size, mtime, ctime or link count while it was read, or its name no longer refers to the inode that was read |
| `file_directory` | the declared directory cannot be reopened without following a link, was replaced, or became writable by every user |
| `file_unreadable` | another operating-system error |

Without an endpoint artifact store the helper raises `MHS.DEVICE.NOT_READY`; once the command is cancelled or
e-stopped it raises `Cancelled` before the directory is opened, between files and before publication; the store's
own refusals (`artifact_size`, `artifact_capacity`, an expired session or deadline) apply unchanged.

## What it does not do

- It is not a boundary against the package's own code: a driver can always publish bytes it read itself
  ([image-artifacts.md](image-artifacts.md)), and a subclass can change the helper's methods; review reads the driver
  (`MHS/handoff/REVIEW.md`, checklist items 8 and 10). It protects against what a command's caller and the
  directory's contents can do.
- It is not a file server. It reads only the names the driver passes. A driver derives them from the native's own
  state (an acquisition id the device reports, a name its API returns) and never passes a string from command input;
  a binding that did would let a caller read any file of the declared directory.
- It does not prove that the native finished writing. A complete read of an unchanged file says only that the file did
  not change while it was read. The driver establishes completion from the native (for example a writer-finished
  status the upstream exposes) and says in its facts what that is.
- It does not follow subdirectories, does not publish a file larger than the store's bound in parts, and does not
  compress.
- It never deletes or changes the native's files (`cleanup="keep"`). The deployment owns their retention. The
  published copy is the artifact store's private, content-addressed blob; it disappears when the grant expires (300 s
  by default) or the endpoint closes.
- A writer of the declared directory (which must not be every user) that swaps a regular file for a device node in
  the window between the `lstat` and the `O_NOFOLLOW` open can make the endpoint open that node; it is never read,
  because the descriptor's inode differs from the checked one and the publication is refused.
- It needs POSIX descriptor-relative opens (`O_NOFOLLOW`, `dir_fd`, `scandir` on a descriptor); elsewhere the
  declaration raises.
- The python-object family has no binding for it: a package whose native writes its output to files is a direct
  `Driver` (driver-authoring.md, "Choosing the shape").

## The acceptance gate

The gate gives a fresh default store (2 MiB per artifact, 32 MiB, 128 grants, 300 s) to every endpoint of a driver
with a binding whose output declares `artifact_ref` or `image_ref`, as it does for image and point-cloud classes, and
closes it with the endpoint. A fake that stands in for a native writing files writes them into its own private
temporary directory (created with `tempfile.mkdtemp`, resolved with `os.path.realpath`, removed by the fake when it is
collected); the gate's in-range call of the action then publishes real bytes through the real helper, and G7 checks
the fake's members against the upstream class as for any direct driver. The gate's child processes end with
`os._exit`, which runs no exit-time cleanup: keep the fake free of reference cycles (a weak reference back to the
fake from its parts), so that it is freed when its endpoint closes; a fake that uncollected SDK objects still
reference when the process ends leaves its directory to the system's temporary-file cleanup.
