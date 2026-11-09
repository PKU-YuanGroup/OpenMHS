# Local image artifacts

An endpoint can publish complete ROS camera images as bounded, immutable local
artifacts. The capability output remains `image_ref`, actual `width`, actual
`height`, and `media_type`. Image bytes are retrieved separately through MCP
resources. CameraInfo, header fields and startup dimensions are not images.

## Enable local retrieval

```sh
python3 -m mhs serve path/to/camera-driver --backend fake --mcp --artifacts
```

This explicit option creates a private temporary store owned by that endpoint.
It is limited to the in-process MCP launcher. Programmatic applications can
pass `artifact_store=LocalArtifactStore(...)` to `build_server`, `MHSServer` or
`mhs.adapter.load`; `MHSClient(InProcessTransport(server))` then supports
`read_artifact(uri, session_id=original_session_id)`.

The store retains at most 32 MiB of blob bytes and 128 grants by default. One
artifact defaults to at most 2 MiB; an explicit programmatic
`LocalArtifactStore(max_artifact_bytes=...)` can raise that bound to at most
16 MiB. The default total budget stays 32 MiB and still covers all staged and
committed blobs. A grant expires after 300 seconds. Expired entries
are pruned on store activity; shutdown removes the store's own temporary
directory. It neither reads nor deletes existing files in a supplied parent
directory. There is no persistent artifact index or restart recovery. Capacity
exhaustion refuses a new capture instead of evicting an unexpired image.

MCP image tools return a normal command receipt and, with MCP 2025-06-18 or
newer, a resource link. `resources/read` returns a base64 `blob` with an image
MIME type. Ordinary responses and all incoming frames retain the 4 MiB MCP
ceiling. Only an authenticated, registered local artifact resource response can
use a larger response budget derived from the store's explicit per-artifact bound
(absolute response ceiling 24 MiB, including base64 and JSON). This does not
raise tool, notification, arbitrary-resource or incoming-request limits.
HTTP and remote stdio MHS transports have no artifact-fetch method in this
implementation; they do not open file or network URLs as a fallback.

The public reference is `mhs+artifact://<endpoint-authority>/<artifact-ULID>`.
For example, `mhs://localhost/lab` uses authority `localhost`. The store is
bound to the exact endpoint instance; distinct artifact grants
scope identical deduplicated bytes to their owning sessions; ULIDs are not an
authorization secret. Reading requires the original live
session, its endpoint token principal and device/capability/resource grant.
MCP additionally requires its own session and current host hardware/enabled
policy. A newly opened session, external session or URI copied from evidence
does not inherit image access.

Bytes are staged during execution. Successful schema validation prepares the
descriptor. Receipt/index preparation and store preflight precede evidence
recording. Grant activation and retained-index publication then make the result
visible together through the endpoint; evidence export waits for this boundary.
Postcommit notification/journal delivery failure never revokes an already
published grant or rewrites its completed receipt. Failed output,
cancelled/expired execution and failed evidence recording discard staged grants.
An early running/unknown receipt contains no staged artifact, and a later final
receipt has its own immutable descriptors. Replaying a command does not capture
another frame or extend its retention. The receipt remains evidence after the
bytes expire. This publication boundary covers the endpoint API and MCP; directly
reading an evidence file or private SDK objects is not a transactional retrieval
API. Local artifacts are ephemeral and are not restored after a process crash.

## Bind a fixed ROS image stream

```python
class Camera(RosDriver):
    # Usual identity, backends, facts and human hardware review still apply.
    ros_version = 2
    max_message_bytes = 4 * 1024 * 1024
    commands = {
        "cap.sensing.image.v1": {
            "topic": "/deployment/camera/image_raw",
            "type": "sensor_msgs/msg/Image",
            "operation": "subscribe",
            "image": {"max_input_bytes": 8 * 1024 * 1024,
                      "max_pixels": 4 * 1024 * 1024},
            "source_ref": "publisher.cpp:42",
            "type_ref": "publisher.cpp:42",
        }
    }
```

The names and references above are illustrative; a package must cite its pinned
publisher and deployment namespace. ROS 1 uses `sensor_msgs/Image` or
`sensor_msgs/CompressedImage`; ROS 2 uses `sensor_msgs/msg/Image` or
`sensor_msgs/msg/CompressedImage`. A fixed subscription accepts `{}` only.
It does not change resolution/exposure, switch cameras or implement requested
format conversion. For a finite set of streams in one driver package, use the
selector profile below. Images are explicit commands, never automatic resource
snapshot fields. Legacy flat subscriptions keep their existing output and do not
add source headers to artifact descriptors.

Raw `Image` supports `rgb8`, `bgr8`, `rgba8`, `bgra8`, `mono8`, `mono16`, and
`16UC1`. It checks width/height, exact `height * step` data length and row padding,
then emits lossless PNG. Both byte orders of 16-bit samples are preserved;
depth units, calibration and a visualization colormap are not inferred. Float
depth, YUV, Bayer and other encodings are refused.

`CompressedImage` supports simple `jpeg`, `jpg`, and `png` format strings. It
requires the optional `openmhs[images]` extra (Pillow 12.3+ or 13.x, Python 3.10+), loaded
only when compressed images are requested. Missing/unsupported decoders refuse
before subscription. Actual dimensions come from decoded content.

JPEG is a decoded-pixel input, not an original-codestream archival format. The
supported 8-bit baseline/progressive Huffman JPEG must have valid marker framing
and end at its first terminal EOI. Pillow decodes only L/RGB8; those pixels become
a fresh bounded PNG with `media_type=image/png`. Source metadata, ICC profiles
and unused compressed bytes are not copied or applied. Pillow cannot prove
consumption of every entropy byte; the returned artifact claims the decoded
pixels, never preservation or full validation of the original JPEG. CMYK and
other unsupported pixel modes are refused without implicit color conversion.

PNG accepts only IHDR, contiguous IDAT and IEND, with one complete bounded zlib
stream, exact scanline lengths, valid filter bytes and checksums. 8-bit grayscale,
RGB, grayscale-alpha and RGBA become fresh canonical PNG of decoded pixels.
Metadata-free 16-bit grayscale PNG preserves the exact validated stream/sample
bits without conversion through an 8-bit image. Palette/sub-byte PNG,
multichannel 16-bit PNG, ancillary metadata, interlacing and animation are refused.
These restrictions avoid silently dropping sample precision or trusting ignored
metadata. Truncated images and codec mismatches are refused. Raw conversion
remains stdlib-only.

## Select among declared streams and retain each source header

One `RosDriver` class can bind a finite set of independent image streams to the
existing `cap.sensing.image.v1` input `camera`. For example:

```python
commands = {
    "cap.sensing.image.v1": {
        "cameras": {
            "color": {"topic": "/deployment/color", "type": "sensor_msgs/Image",
                      "operation": "subscribe", "image": {},
                      "source_ref": "publisher.cpp:42"},
            "depth": {"topic": "/deployment/depth", "type": "sensor_msgs/Image",
                      "operation": "subscribe", "image": {},
                      "source_ref": "publisher.cpp:56"},
            "ir": {"topic": "/deployment/ir", "type": "sensor_msgs/Image",
                   "operation": "subscribe", "image": {},
                   "source_ref": "publisher.cpp:70"},
        }
    }
}
```

This ROS1 example is illustrative; each endpoint/type needs its own pinned
source evidence and deployment namespace. Set `ros_version = 1`; ROS2 uses its
own `sensor_msgs/msg/...` types and `ros_version = 2`. The map has one to sixteen
camera identifiers, each beginning with an ASCII letter and containing at most
64 letters, digits, dots, underscores or hyphens. Static absolute topic names
are at most 512 characters. Every child must be a full image subscription.
Nested maps, resource overrides, write/stop bindings, argument/result mappings
and caller-supplied endpoints are refused. G7 checks all declared children even
when a fake test captures only one of them.

The family derives a closed schema requiring exactly `{"camera": "color"}`
(or another declared key). Do not separately declare an `Action.input` schema.
Capture does not configure the camera. Each call returns one complete selected
image through the same standard package loader, endpoint and MCP paths. It does
not return a synchronized color/depth/IR tuple or infer depth units, calibration
or producer freshness. Other-stream packets and delayed replies carrying an old
subscription id cannot supply this subscription's image. An untagged message
from the selected topic still describes an observed packet, not a proven fresh
producer acquisition.

The stable output stays `image_ref`, `width`, `height`, `media_type`. Its matching
receipt artifact descriptor adds:

```json
{"x-vendor": {"openmhs.ros_image": {
  "camera": "color", "topic": "/deployment/color", "type": "sensor_msgs/Image",
  "ros_version": 1,
  "header": {"seq": 17, "stamp": {"secs": 1, "nsecs": 23456789},
             "frame_id": "color_optical_frame"}
}}}
```

The header comes from the same returned ROS packet as the pixels. ROS1 retains
uint32 `seq`, uint32 `stamp.secs` and `stamp.nsecs` in 0..999999999. ROS2 retains
int32 `stamp.sec`, `stamp.nanosec` in the same nanosecond range, and no `seq`.
`frame_id` is preserved exactly, including an empty identifier, with an SDK bound
of 256 UTF-8 bytes and no ASCII C0 or DEL control characters. Missing/extra fields, profile
mismatches, booleans/floats in integer fields and invalid/oversized UTF-8 refuse
the whole capture before publication. Stamps are not converted to wall time;
different captures keep their different values without synchronization or age
claims. The same rule applies to supported `CompressedImage` packets; their
existing strict format/codec rules still apply.

MCP hosts obtain this metadata in `structuredContent.receipt.artifacts`, tied to
the `image_ref`/resource-link URI. `resources/read` returns the image blob. The
local client artifact read also returns the matching descriptor. Nested data
returned to a caller does not alias the stored grant or MCP route. Metadata
remains in replayed receipt evidence after expiry, but gives no new access to
expired pixels or to another session's grant.

## Bounded artifact descriptor extensions

`ArtifactPublisher.publish(data, media_type, x_vendor=...)` can attach a small
JSON object as descriptor `x-vendor`. It is detached before storage allocation:
at most 4096 UTF-8 JSON bytes, 128 value nodes, six nested levels, and 128-character
keys. Values must be plain finite JSON, with integers within the exact IEEE-754
integer range; cyclic/oversized/custom objects are refused. This is a per-grant
extension, not data embedded in the PNG or part of the pixel-byte digest. Receipt
evidence binds the descriptor. Identical pixel blobs can therefore share storage
while retaining different source headers and session grants. Metadata does not
change output schemas, quotas for blob bytes, original-session authorization,
TTL, abort/commit semantics, or ownership of cleanup.

A non-ROS driver can publish source-backed opaque image bytes through
`publisher_from_context(self.ctx).publish(data, media_type)` and return its URI,
width, height and truthful media type. For example, a 10,027,008-byte 2448x2048
vendor raw16 frame requires an explicit larger store bound; the default refuses
it. A vendor raw MIME resource carries bytes without claiming endianness,
calibration, color conversion or host preview support. The driver never calls
publisher prepare/commit/abort; the endpoint owns publication and shutdown.
A file that the native wrote to disk (an HDF5 frame file, an exported report)
is published from a declared directory with `mhs.file_artifacts`
([file-artifacts.md](file-artifacts.md)), never by reading a caller's path.

Data must be canonical base64 or a JSON byte array. The raw input, pixel,
transport JSON and final artifact bounds all apply separately. Width and height
are each at most 8192. The default ROS transport limit is 1 MiB, which some RGB
frames exceed after base64 encoding; packages must explicitly choose a suitable
bounded transport setting. The websocket transport currently checks frame size
after receiving it, so this is not a preallocation network-memory guarantee.

Freshness means the message arrived after this subscription was sent. It does
not establish a source measurement timestamp or physical camera latency.
Controlled-peer tests establish packet/contract behavior, not live ROS or
camera compatibility. Image support never provides an emergency stop or replaces
human hardware review.
