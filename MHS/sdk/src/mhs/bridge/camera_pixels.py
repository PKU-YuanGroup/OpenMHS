"""Primary camera pixels. NumPy is required only when this boundary is used."""
from __future__ import annotations

from dataclasses import dataclass

from ..pixels import encode_png_rows


@dataclass(frozen=True)
class CameraPixels:
    width: int
    height: int
    depth: int
    color: int
    data: bytes
    native_dtype: str

    def png(self, max_bytes: int) -> bytes:
        stride = self.width * (3 if self.color == 2 else self.depth // 8)
        return encode_png_rows(self.width, self.height, self.depth, self.color,
                               (self.data[y * stride:(y + 1) * stride] for y in range(self.height)),
                               max_bytes=max_bytes)


def require_numpy():
    try:
        import numpy
    except ImportError as exc:
        raise ValueError("camera pixels require the optional NumPy dependency") from exc
    return numpy


def detach_pixels(frame, *, pixel_format: str, width: int, height: int,
                  max_pixels: int, max_bytes: int) -> CameraPixels:
    """Detach the complete array, preserving exact logical samples and channel order."""
    np = require_numpy()
    if type(frame) is not np.ndarray:
        raise ValueError("camera must return an exact ndarray, not an array-conversion object")
    if pixel_format not in {"mono8", "mono16", "rgb8"}:
        raise ValueError("unsupported camera pixel profile")
    if (any(type(n) is not int or not 1 <= n <= 8192 for n in (width, height))
            or type(max_pixels) is not int or not 1 <= max_pixels <= 16 * 1024 * 1024
            or type(max_bytes) is not int or not 1 <= max_bytes <= 16 * 1024 * 1024):
        raise ValueError("invalid camera pixel bounds")
    depth = 16 if pixel_format == "mono16" else 8
    color = 2 if pixel_format == "rgb8" else 0
    shape = (height, width, 3) if color == 2 else (height, width)
    if frame.shape != shape or width * height > max_pixels or frame.nbytes > max_bytes:
        raise ValueError("camera array shape or size differs from its bounded profile")
    dtype = frame.dtype
    if (dtype.kind != "u" or dtype.itemsize != depth // 8 or dtype.hasobject
            or dtype.fields is not None or dtype.subdtype is not None
            or dtype.byteorder not in {"=", "<", ">", "|"}):
        raise ValueError("camera array dtype differs from its lossless profile")
    owned = np.array(frame, copy=True, order="C", subok=False)
    if depth == 16:
        owned = owned.astype(">u2", copy=False)
    data = owned.tobytes(order="C")
    if len(data) != width * height * (3 if color == 2 else depth // 8):
        raise ValueError("camera pixel copy has unexpected size")
    return CameraPixels(width, height, depth, color, data, dtype.str)
