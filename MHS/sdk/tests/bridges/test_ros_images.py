"""Exact pixels and bounded conversion, without ROS or camera execution."""
import base64
import io
import struct
import unittest
from unittest.mock import patch
import zlib

from mhs.bridge.ros_images import convert_image, image_config, _chunk, _PNG

try:
    from PIL import Image
except ImportError:
    Image = None

RAW = "sensor_msgs/msg/Image"
COMPRESSED = "sensor_msgs/msg/CompressedImage"


def raw_message(data=None, *, encoding="rgb8", width=2, height=1, step=6, endian=0):
    return {"width": width, "height": height, "encoding": encoding, "step": step,
            "is_bigendian": endian, "data": list(data if data is not None else [255, 0, 0, 0, 255, 0])}


def png_rows(data):
    offset, compressed = 8, bytearray()
    while offset < len(data):
        size = int.from_bytes(data[offset:offset + 4], "big")
        kind = data[offset + 4:offset + 8]
        if kind == b"IDAT":
            compressed.extend(data[offset + 8:offset + 8 + size])
        offset += size + 12
    return zlib.decompress(bytes(compressed))


def compressed_message(codec="jpeg", size=(3, 2)):
    stream = io.BytesIO()
    Image.new("RGB", size, (33, 77, 120)).save(stream, format="JPEG" if codec == "jpeg" else "PNG")
    return {"format": codec, "data": base64.b64encode(stream.getvalue()).decode("ascii")}


class RosImageCodecTests(unittest.TestCase):
    def convert(self, message, ros_type=RAW, **limits):
        return convert_image(message, ros_type, image_config(limits, ros_type))

    def test_padding_and_channel_order_are_lossless(self):
        for encoding, source, expected in (
            ("rgb8", [1,2,3,4,5,6], [1,2,3,4,5,6]),
            ("bgr8", [1,2,3,4,5,6], [3,2,1,6,5,4]),
            ("rgba8", [1,2,3,4,5,6,7,8], [1,2,3,4,5,6,7,8]),
            ("bgra8", [1,2,3,4,5,6,7,8], [3,2,1,4,7,6,5,8]),
            ("mono8", [1,250], [1,250]),
        ):
            with self.subTest(encoding=encoding):
                row = source + [99, 98]
                output, width, height, media = self.convert(raw_message(row * 2, encoding=encoding,
                                                                       height=2, step=len(row)))
                self.assertEqual((width, height, media), (2, 2, "image/png"))
                self.assertEqual(png_rows(output), (b"\0" + bytes(expected)) * 2)

    def test_mono16_and_depth_preserve_all_samples_and_endianness(self):
        values = [0, 1, 256, 32768, 65535]
        for encoding in ("mono16", "16UC1"):
            for endian in (0, 1):
                with self.subTest(encoding=encoding, endian=endian):
                    source = b"".join(value.to_bytes(2, "big" if endian else "little") for value in values)
                    message = raw_message(source + b"PAD", encoding=encoding, width=5, step=13, endian=endian)
                    output, _, _, _ = self.convert(message)
                    expected = b"\0" + b"".join(value.to_bytes(2, "big") for value in values)
                    self.assertEqual(png_rows(output), expected)
                    if Image is not None:
                        with Image.open(io.BytesIO(output)) as decoded:
                            self.assertEqual(list(decoded.get_flattened_data()), values)

    def test_invalid_rows_types_encodings_and_bounds(self):
        overrides = [{"width": True}, {"height": 0}, {"step": 5}, {"step": True},
                     {"is_bigendian": True}, {"is_bigendian": 2}, {"encoding": "32FC1"},
                     {"encoding": "yuv422"}, {"encoding": "8UC3"}, {"data": [True] * 6},
                     {"data": [256] * 6}, {"data": [1] * 5}, {"data": [1] * 7},
                     {"data": "!!!!"}, {"data": "AQ==junk"}, {"data": "AR=="}]
        for override in overrides:
            with self.subTest(override=override), self.assertRaises(ValueError):
                self.convert({**raw_message(), **override})
        with self.assertRaises(ValueError):
            self.convert(raw_message(), max_pixels=1)
        with self.assertRaises(ValueError):
            self.convert(raw_message(), max_input_bytes=5)
        with self.assertRaises(ValueError):
            convert_image(raw_message(), RAW, image_config({}, RAW), max_output_bytes=20)

    @unittest.skipIf(Image is None, "optional Pillow decoder is not installed")
    def test_compressed_dimensions_and_normalized_pixels(self):
        for codec in ("jpeg", "png"):
            with self.subTest(codec=codec):
                message = compressed_message(codec)
                message.update(width=640, height=480)  # untrusted metadata is ignored
                data, width, height, media = self.convert(message, COMPRESSED)
                self.assertEqual((width, height), (3, 2))
                self.assertEqual(media, "image/png")
                with Image.open(io.BytesIO(base64.b64decode(message["data"]))) as source:
                    pixels = source.tobytes()
                with Image.open(io.BytesIO(data)) as decoded:
                    decoded.load()
                    self.assertEqual(decoded.size, (3, 2))
                    self.assertEqual(decoded.tobytes(), pixels)

    @unittest.skipIf(Image is None, "optional Pillow decoder is not installed")
    def test_corrupt_truncated_mismatch_animation_and_bombs_refused(self):
        message = compressed_message()
        data = base64.b64decode(message["data"])
        for codec, malformed in (("jpeg", data[:-2]), ("png", data), ("compressedDepth", data),
                                 ("jpeg", data + b"tail"), ("jpeg", b"\xff\xd8broken\xff\xd9")):
            with self.subTest(codec=codec), self.assertRaises(ValueError):
                self.convert({"format": codec, "data": list(malformed)}, COMPRESSED)
        with self.assertRaises(ValueError):
            self.convert(compressed_message(size=(3, 2)), COMPRESSED, max_pixels=5)
        header = _chunk(b"IHDR", struct.pack(">IIBBBBB", 8192, 8192, 8, 2, 0, 0, 0))
        bomb = _PNG + header + _chunk(b"IEND", b"")
        with self.assertRaises(ValueError):
            self.convert({"format": "png", "data": list(bomb)}, COMPRESSED)
        png = base64.b64decode(compressed_message("png")["data"])
        animated = png[:33] + _chunk(b"acTL", struct.pack(">II", 2, 0)) + png[33:]
        with self.assertRaises(ValueError):
            self.convert({"format": "png", "data": list(animated)}, COMPRESSED)

    def test_invalid_config_refuses_unbounded_options(self):
        for mapping in ({"max_pixels": True}, {"max_input_bytes": 0}, {"unknown": 1}):
            with self.assertRaises(ValueError):
                image_config(mapping, RAW)


    @unittest.skipIf(Image is None, "optional Pillow unavailable")
    def test_png_scanline_length_filter_and_interlace_are_exact(self):
        def png(rows, interlace=0):
            return (_PNG + _chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 1, 8, 2, 0, 0, interlace))
                    + _chunk(b"IDAT", zlib.compress(rows)) + _chunk(b"IEND", b""))
        valid = b"\0\1\2\3\4\5\6"
        for data in (png(valid[:-1]), png(valid + b"\0"), png(b"\5" + valid[1:]), png(valid, 1)):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.convert({"format": "png", "data": base64.b64encode(data).decode()}, COMPRESSED)
        data = png(valid)
        self.assertEqual(self.convert({"format": "png", "data": base64.b64encode(data).decode()}, COMPRESSED)[0], data)

    @unittest.skipIf(Image is None, "optional Pillow unavailable")
    def test_progressive_jpeg_and_marker_bytes_in_metadata_are_supported(self):
        output = io.BytesIO()
        Image.new("RGB", (7, 4), (23, 91, 67)).save(output, format="JPEG", progressive=True)
        jpeg = output.getvalue()
        comment = b"marker bytes inside declared comment: \xff\xd9 and \xff\xd8"
        jpeg = jpeg[:2] + b"\xff\xfe" + struct.pack(">H", len(comment) + 2) + comment + jpeg[2:]
        result = self.convert({"format": "jpeg", "data": base64.b64encode(jpeg).decode()}, COMPRESSED)
        self.assertEqual(result[1:], (7, 4, "image/png"))
        self.assertNotIn(comment, result[0])
        with Image.open(io.BytesIO(jpeg)) as source, Image.open(io.BytesIO(result[0])) as decoded:
            self.assertEqual(source.tobytes(), decoded.tobytes())

    @unittest.skipIf(Image is None, "optional Pillow unavailable")
    def test_png_multiple_idat_chunks_and_mono16_values_are_preserved(self):
        source = b"\0\0\1\0\xff\xff"
        png, _, _, _ = self.convert(raw_message(source, encoding="mono16", width=3, step=6, endian=1))
        # Split the one zlib stream across legal contiguous IDAT chunks.
        length = struct.unpack_from(">I", png, 33)[0]
        compressed = png[41:41 + length]
        split = (png[:33] + _chunk(b"IDAT", compressed[:3]) + _chunk(b"IDAT", compressed[3:])
                 + _chunk(b"IEND", b""))
        result = self.convert({"format": "png", "data": base64.b64encode(split).decode()}, COMPRESSED)
        self.assertEqual(result[0], split)
        self.assertEqual(png_rows(result[0]), b"\0" + source)

    @unittest.skipIf(Image is None, "optional Pillow unavailable")
    def test_ignored_jpeg_entropy_and_metadata_are_not_retained(self):
        jpeg = base64.b64decode(compressed_message()["data"])
        outputs = []
        for payload in (jpeg, jpeg[:-2] + b"UNRELATED-TRAILING-PAYLOAD" + jpeg[-2:],
                        jpeg[:-2] + bytes(64) + jpeg[-2:]):
            outputs.append(self.convert({"format": "jpeg", "data": base64.b64encode(payload).decode()}, COMPRESSED))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])
        self.assertEqual(outputs[0][3], "image/png")
        self.assertNotIn(b"UNRELATED-TRAILING-PAYLOAD", outputs[0][0])

    @unittest.skipIf(Image is None, "optional Pillow unavailable")
    def test_png_metadata_palette_and_multichannel16_are_explicitly_refused(self):
        png = base64.b64decode(compressed_message("png")["data"])
        for kind, payload in ((b"tIME", b"x" * 120), (b"pHYs", b"x" * 30),
                              (b"PLTE", b"x" * 13), (b"tIME", bytes(7))):
            candidate = png[:33] + _chunk(kind, payload) + png[33:]
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.convert({"format": "png", "data": base64.b64encode(candidate).decode()}, COMPRESSED)
        for mode in ("P", "1"):
            out = io.BytesIO(); Image.new(mode, (2, 2)).save(out, format="PNG")
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.convert({"format": "png", "data": base64.b64encode(out.getvalue()).decode()}, COMPRESSED)


class DecoderVersionTests(unittest.TestCase):
    @unittest.skipIf(Image is None, "optional Pillow unavailable")
    def test_supported_major_versions_and_future_version_refusal(self):
        import PIL
        from unittest.mock import patch
        from mhs.bridge.ros_images import require_decoder

        for version in ("12.3.0", "13.0.0"):
            with self.subTest(version=version), patch.object(PIL, "__version__", version):
                self.assertIs(require_decoder(), Image)
        for version in ("11.0.0", "14.0.0", "unknown"):
            with self.subTest(version=version), patch.object(PIL, "__version__", version):
                with self.assertRaises(ValueError):
                    require_decoder()
