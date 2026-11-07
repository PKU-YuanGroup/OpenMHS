"""Bounded ROS Image/CompressedImage conversion; no ROS imports or I/O.

Raw samples become lossless PNG (including unsigned 16-bit mono/depth). The
compressed path lazily requires Pillow. 8-bit images are normalized to fresh PNG of decoded pixels. Only strictly
validated metadata-free mono16 PNG retains its original sample encoding. No resizing, exposure adjustment or depth unit claim.
"""
from __future__ import annotations

import base64
import binascii
import io
import re
import struct
import zlib
from typing import Any, Mapping

from ..artifacts import DEFAULT_ARTIFACT_BYTES, MAX_ARTIFACT_BYTES
from ..pixels import encode_png_rows

IMAGE_TYPES = {"sensor_msgs/Image", "sensor_msgs/msg/Image"}
COMPRESSED_TYPES = {"sensor_msgs/CompressedImage", "sensor_msgs/msg/CompressedImage"}
_ENCODINGS = {"mono8": (1, 8, 0), "rgb8": (3, 8, 2), "bgr8": (3, 8, 2),
              "rgba8": (4, 8, 6), "bgra8": (4, 8, 6),
              "mono16": (2, 16, 0), "16UC1": (2, 16, 0)}
_PNG = b"\x89PNG\r\n\x1a\n"


def _integer(value: Any, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in {low}..{high}")
    return value


def camera_sources(value: Any) -> dict[str, Any]:
    """A finite trusted selector map, never a request-selected ROS endpoint."""
    if not isinstance(value, Mapping) or not 1 <= len(value) <= 16:
        raise ValueError("cameras must declare between one and sixteen sources")
    if any(type(name) is not str or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", name) is None
           or not isinstance(spec, Mapping) for name, spec in value.items()):
        raise ValueError("camera names must be bounded identifiers with object bindings")
    return dict(value)


def source_metadata(message: Any, ros_type: str, *, camera: str, topic: str) -> dict[str, Any]:
    """The exact bounded source header from this image packet, with no age claim."""
    if not isinstance(message, Mapping):
        raise ValueError("ROS image must be an object")
    version = 2 if ros_type in ("sensor_msgs/msg/Image", "sensor_msgs/msg/CompressedImage") else 1
    header = message.get("header")
    expected = {"stamp", "frame_id"} | ({"seq"} if version == 1 else set())
    if not isinstance(header, Mapping) or set(header) != expected:
        raise ValueError("ROS image header fields do not match its declared version")
    stamp = header["stamp"]
    sec, nsec = ("secs", "nsecs") if version == 1 else ("sec", "nanosec")
    if not isinstance(stamp, Mapping) or set(stamp) != {sec, nsec}:
        raise ValueError("ROS image stamp fields do not match its declared version")
    seconds = _integer(stamp[sec], sec, 0 if version == 1 else -(2 ** 31),
                       2 ** 32 - 1 if version == 1 else 2 ** 31 - 1)
    nanos = _integer(stamp[nsec], nsec, 0, 999999999)
    frame = header["frame_id"]
    if (type(frame) is not str or len(frame) > 256 or len(frame.encode("utf-8")) > 256
            or any(ord(char) < 32 or ord(char) == 127 for char in frame)):
        raise ValueError("ROS frame_id must be at most 256 UTF-8 bytes without control characters")
    detached = {"stamp": {sec: seconds, nsec: nanos}, "frame_id": frame}
    if version == 1:
        detached["seq"] = _integer(header["seq"], "seq", 0, 2 ** 32 - 1)
    return {"openmhs.ros_image": {"camera": camera, "topic": topic, "type": ros_type,
                                  "ros_version": version, "header": detached}}


def image_config(value: Any, ros_type: Any) -> dict[str, int]:
    if ros_type not in IMAGE_TYPES | COMPRESSED_TYPES:
        raise ValueError("image conversion requires sensor_msgs Image or CompressedImage")
    if not isinstance(value, Mapping) or set(value) - {"max_input_bytes", "max_pixels"}:
        raise ValueError("image mapping permits only max_input_bytes and max_pixels")
    return {"max_input_bytes": _integer(value.get("max_input_bytes", 8 * 1024 * 1024),
                                        "max_input_bytes", 1, 32 * 1024 * 1024),
            "max_pixels": _integer(value.get("max_pixels", 4 * 1024 * 1024),
                                   "max_pixels", 1, 16 * 1024 * 1024)}


def require_decoder() -> Any:
    try:
        from PIL import Image, ImageFile, __version__
    except ImportError as exc:
        raise ValueError("compressed ROS images require the optional openmhs[images] decoder") from exc
    try:
        major = int(__version__.split(".", 1)[0])
    except (ValueError, AttributeError) as exc:
        raise ValueError("cannot verify the installed image decoder version") from exc
    if major != 13:
        raise ValueError("compressed ROS images require Pillow 13.x")
    if ImageFile.LOAD_TRUNCATED_IMAGES:
        raise ValueError("compressed ROS images refuse a decoder configured to accept truncated images")
    return Image


def _data(value: Any, limit: int) -> bytes:
    if isinstance(value, str):
        if not value or len(value) > 4 * ((limit + 2) // 3):
            raise ValueError("ROS image base64 exceeds the byte limit")
        try:
            data = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("ROS image data is not strict base64") from exc
        if base64.b64encode(data).decode("ascii") != value:
            raise ValueError("ROS image base64 must use canonical padding")
    elif isinstance(value, list):
        if not value or len(value) > limit:
            raise ValueError("ROS image byte array exceeds the byte limit")
        if any(type(item) is not int or not 0 <= item <= 255 for item in value):
            raise ValueError("ROS image byte array contains a non-byte value")
        data = bytes(value)
    else:
        raise ValueError("ROS image data must be base64 or a JSON byte array")
    if not 0 < len(data) <= limit:
        raise ValueError("ROS image data exceeds the byte limit")
    return data


def _dimensions(width: Any, height: Any, max_pixels: int) -> tuple[int, int]:
    w = _integer(width, "width", 1, 8192)
    h = _integer(height, "height", 1, 8192)
    if w * h > max_pixels:
        raise ValueError("ROS image exceeds the pixel limit")
    return w, h


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def _raw(message: Mapping[str, Any], config: Mapping[str, int], max_output: int) -> tuple[bytes, int, int, str]:
    width, height = _dimensions(message.get("width"), message.get("height"), config["max_pixels"])
    encoding = message.get("encoding")
    if not isinstance(encoding, str) or encoding not in _ENCODINGS:
        raise ValueError("unsupported ROS image encoding")
    bpp, depth, color = _ENCODINGS[encoding]
    step = _integer(message.get("step"), "step", width * bpp, config["max_input_bytes"])
    endian = _integer(message.get("is_bigendian"), "is_bigendian", 0, 1)
    expected = step * height
    if expected > config["max_input_bytes"]:
        raise ValueError("ROS image rows exceed the byte limit")
    data = _data(message.get("data"), config["max_input_bytes"])
    if len(data) != expected:
        raise ValueError("ROS image data length does not equal height * step")
    # Encode rows incrementally: padding is excluded; PNG 16-bit samples are big
    # endian. Byte swapping preserves exact values, including zero and 65535.
    def rows():
        for y in range(height):
            row = bytearray(data[y * step:y * step + width * bpp])
            if encoding in ("bgr8", "bgra8"):
                for x in range(0, len(row), bpp):
                    row[x], row[x + 2] = row[x + 2], row[x]
            elif depth == 16 and not endian:
                row[0::2], row[1::2] = row[1::2], row[0::2]
            yield row
    try:
        output = encode_png_rows(width, height, depth, color, rows(), max_bytes=max_output)
    except ValueError as exc:
        if str(exc) == "encoded image exceeds artifact limit":
            raise ValueError("encoded ROS image exceeds artifact limit") from exc
        raise
    return output, width, height, "image/png"


def _check_png(data: bytes, max_pixels: int) -> None:
    """Validate one bounded, noninterlaced PNG including the exact zlib stream.

    Ancillary metadata, palettes, sub-byte samples, multichannel16, animation
    and interlacing are outside this deliberately limited surface. Decoding pixels is still Pillow's job.
    """
    if not data.startswith(_PNG):
        raise ValueError("PNG signature is invalid")
    offset, stride, expected, count = 8, 0, 0, 0
    decoder = zlib.decompressobj()
    idat_seen = idat_ended = False
    allowed = {b"IHDR", b"IDAT", b"IEND"}
    while offset + 12 <= len(data):
        size = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + size
        if end > len(data) or kind not in allowed:
            raise ValueError("unsupported or truncated PNG chunk")
        payload = data[offset + 8:end - 4]
        crc = struct.unpack_from(">I", data, end - 4)[0]
        if zlib.crc32(kind + payload) != crc:
            raise ValueError("PNG chunk checksum is invalid")
        if offset == 8:
            if kind != b"IHDR" or size != 13:
                raise ValueError("PNG requires a bounded initial IHDR")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            _dimensions(width, height, max_pixels)
            depths = {0: (8, 16), 2: (8,), 4: (8,), 6: (8,)}
            if depth not in depths.get(color, ()) or compression or filtering or interlace:
                raise ValueError("unsupported PNG samples or interlacing")
            channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
            stride = 1 + (width * channels * depth + 7) // 8
            expected = stride * height
        elif kind == b"IHDR":
            raise ValueError("duplicate PNG header")
        if kind == b"IDAT":
            if idat_ended:
                raise ValueError("PNG IDAT chunks must be contiguous")
            idat_seen = True
            pending = payload
            while pending:
                try:
                    decoded = decoder.decompress(pending, min(65536, expected - count + 1))
                except zlib.error as exc:
                    raise ValueError("invalid PNG compressed stream") from exc
                if decoder.unused_data:
                    raise ValueError("PNG IDAT has bytes after its zlib stream")
                if count + len(decoded) > expected:
                    raise ValueError("PNG decoded scanlines exceed the declared dimensions")
                # Each scanline starts with a filter byte 0..4. Keep only this
                # bounded decoder window, never a full decompressed frame.
                if any(decoded[i] > 4 for i in range((-count) % stride, len(decoded), stride)):
                    raise ValueError("PNG scanline filter is invalid")
                count += len(decoded)
                tail = decoder.unconsumed_tail
                if tail == pending and not decoded:
                    raise ValueError("PNG decoder made no progress")
                pending = tail
        elif idat_seen:
            idat_ended = True
        if kind == b"IEND":
            if (size or end != len(data) or not idat_seen or not decoder.eof
                    or decoder.unused_data or decoder.unconsumed_tail or count != expected):
                raise ValueError("PNG has trailing, incomplete or malformed scanline data")
            return
        offset = end
    raise ValueError("PNG is incomplete")


def _check_jpeg(data: bytes, max_pixels: int) -> None:
    """Bound marker segments and require the first terminal EOI to end the file.

    Baseline/progressive 8-bit Huffman JPEG only. Entropy scan escapes and
    restart markers are distinguished from marker boundaries; Pillow then
    verifies and decodes the pixels. Multiple images/tails are never stripped.
    """
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("JPEG signature is invalid")
    offset, frame, scans, entropy = 2, False, 0, False
    while offset < len(data):
        if entropy:
            marker_at = data.find(b"\xff", offset)
            if marker_at < 0:
                raise ValueError("JPEG entropy scan is incomplete")
            offset = marker_at
        elif data[offset] != 255:
            raise ValueError("JPEG has bytes outside a marker segment")
        while offset < len(data) and data[offset] == 255:
            offset += 1
        if offset >= len(data):
            raise ValueError("JPEG marker is truncated")
        marker = data[offset]
        offset += 1
        if entropy and (marker == 0 or 0xD0 <= marker <= 0xD7):
            continue
        entropy = False
        if marker == 0xD9:
            if not frame or not scans or offset != len(data):
                raise ValueError("JPEG has trailing data or no complete image")
            return
        if marker not in (0xC0, 0xC2, 0xC4, 0xDB, 0xDD, 0xDA, 0xFE) and not 0xE0 <= marker <= 0xEF:
            raise ValueError("unsupported JPEG marker")
        if offset + 2 > len(data):
            raise ValueError("JPEG segment is truncated")
        length = struct.unpack_from(">H", data, offset)[0]
        end = offset + length
        if length < 2 or end > len(data):
            raise ValueError("JPEG segment length is invalid")
        payload = data[offset + 2:end]
        if marker in (0xC0, 0xC2):
            if frame or len(payload) < 6 or payload[0] != 8:
                raise ValueError("unsupported JPEG frame")
            height, width = struct.unpack_from(">HH", payload, 1)
            channels = payload[5]
            if channels not in (1, 3, 4) or len(payload) != 6 + 3 * channels:
                raise ValueError("JPEG frame components are invalid")
            _dimensions(width, height, max_pixels)
            frame = True
        elif marker == 0xDA:
            if not frame or not payload or len(payload) != 4 + 2 * payload[0]:
                raise ValueError("JPEG scan header is invalid")
            scans += 1
            entropy = True
        offset = end
    raise ValueError("JPEG is missing its terminal EOI")


def _compressed(message: Mapping[str, Any], config: Mapping[str, int], max_output: int) -> tuple[bytes, int, int, str]:
    Image = require_decoder()
    codec = message.get("format")
    if codec not in ("jpeg", "jpg", "png"):
        raise ValueError("only simple jpeg/jpg/png CompressedImage formats are supported")
    data = _data(message.get("data"), min(config["max_input_bytes"], max_output))
    expected_format = "PNG" if codec == "png" else "JPEG"
    if expected_format == "PNG":
        _check_png(data, config["max_pixels"])
    else:
        _check_jpeg(data, config["max_pixels"])
    try:
        with Image.open(io.BytesIO(data), formats=[expected_format]) as image:
            if image.format != expected_format or getattr(image, "n_frames", 1) != 1:
                raise ValueError("compressed ROS image format or frame count is unsupported")
            width, height = _dimensions(image.width, image.height, config["max_pixels"])
            image.verify()
        with Image.open(io.BytesIO(data), formats=[expected_format]) as image:
            if expected_format == "JPEG" and image.mode not in ("L", "RGB"):
                raise ValueError("JPEG normalization supports only decoded L/RGB8 pixels")
            image.load()  # verify() alone does not decode JPEG pixels
            if image.size != (width, height):
                raise ValueError("compressed ROS image dimensions changed while decoding")
            preserve_mono16 = expected_format == "PNG" and data[24:26] == bytes((16, 0))
            if not preserve_mono16:
                if image.mode not in ("L", "RGB", "LA", "RGBA"):
                    raise ValueError("unsupported decoded pixel mode")
                # Pillow does not prove entropy-byte consumption. Never expose
                # the original JPEG as validated: emit only decoded pixels,
                # without metadata or unused compressed input. No color-mode
                # conversion or 16-bit downcast is performed here.
                channels, color = {"L": (1, 0), "RGB": (3, 2), "LA": (2, 4), "RGBA": (4, 6)}[image.mode]
                pixels = image.tobytes()
                compressor = zlib.compressobj()
                encoded = bytearray()
                stride = width * channels
                for y in range(height):
                    encoded.extend(compressor.compress(b"\0" + pixels[y * stride:(y + 1) * stride]))
                    if len(encoded) + 57 > max_output:
                        raise ValueError("normalized image exceeds artifact limit")
                encoded.extend(compressor.flush())
                data = (_PNG + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8,
                                                          color, 0, 0, 0))
                        + _chunk(b"IDAT", bytes(encoded)) + _chunk(b"IEND", b""))
                if len(data) > max_output:
                    raise ValueError("normalized image exceeds artifact limit")
    except (OSError, SyntaxError, ValueError) as exc:
        raise ValueError("compressed ROS image cannot be fully decoded") from exc
    return data, width, height, "image/png"


def convert_image(message: Any, ros_type: str, config: Mapping[str, int], *,
                  max_output_bytes: int = DEFAULT_ARTIFACT_BYTES) -> tuple[bytes, int, int, str]:
    if not isinstance(message, Mapping):
        raise ValueError("ROS image must be an object")
    _integer(max_output_bytes, "max_output_bytes", 1, MAX_ARTIFACT_BYTES)
    if ros_type in IMAGE_TYPES:
        return _raw(message, config, max_output_bytes)
    if ros_type in COMPRESSED_TYPES:
        return _compressed(message, config, max_output_bytes)
    raise ValueError("unsupported ROS image type")
