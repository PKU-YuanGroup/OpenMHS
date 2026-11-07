"""Lossless bounded PNG rows, independent of transport and optional decoders."""
from __future__ import annotations

import struct
import zlib
from collections.abc import Iterable

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def encode_png_rows(width: int, height: int, depth: int, color: int,
                    rows: Iterable[bytes], *, max_bytes: int) -> bytes:
    """Encode exact big-endian sample rows without scaling or color conversion.

    The compressor and framing match the existing raw ROS image encoder. The
    caller owns source interpretation and memory; this function validates only
    the finite logical pixel rows it receives.
    """
    if any(type(n) is not int or not 1 <= n <= 8192 for n in (width, height)):
        raise ValueError("PNG dimensions must be integers in 1..8192")
    if type(depth) is not int or type(color) is not int or (depth, color) not in {
        (8, 0), (16, 0), (8, 2), (8, 4), (8, 6)
    }:
        raise ValueError("unsupported lossless PNG pixel format")
    if type(max_bytes) is not int or not 1 <= max_bytes <= 16 * 1024 * 1024:
        raise ValueError("PNG output bound must be in 1..16 MiB")
    stride = width * {0: 1, 2: 3, 4: 2, 6: 4}[color] * (depth // 8)
    compressor = zlib.compressobj()
    compressed = bytearray()
    count = 0
    for row in rows:
        if count >= height or not isinstance(row, (bytes, bytearray)) or len(row) != stride:
            raise ValueError("PNG row count/length does not match its declared pixels")
        compressed.extend(compressor.compress(b"\0" + row))
        count += 1
        if len(compressed) + 57 > max_bytes:
            raise ValueError("encoded image exceeds artifact limit")
    if count != height:
        raise ValueError("PNG row count does not match height")
    compressed.extend(compressor.flush())
    data = (PNG_SIGNATURE + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, depth, color, 0, 0, 0))
            + png_chunk(b"IDAT", bytes(compressed)) + png_chunk(b"IEND", b""))
    if len(data) > max_bytes:
        raise ValueError("encoded image exceeds artifact limit")
    return data
