"""Bounded, lossless ROS PointCloud2 artifacts without ROS or PCL imports.

The ZIP contains a small pointcloud.json manifest and the exact data.bin bytes.
No point filtering, coordinate conversion or floating-point decoding occurs.
Source is_dense and timestamps are preserved declarations, not verified claims.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
from typing import Any, Mapping
import zipfile

from ..artifacts import MAX_ARTIFACT_BYTES

POINT_TYPES = {"sensor_msgs/PointCloud2", "sensor_msgs/msg/PointCloud2"}
FORMAT = "openmhs.ros-pointcloud2.v1"
MEDIA_TYPE = "application/zip"
_TYPE_BYTES = {1: 1, 2: 1, 3: 2, 4: 2, 5: 4, 6: 4, 7: 4, 8: 8}
_MESSAGE_FIELDS = {"header", "height", "width", "fields", "is_bigendian",
                   "point_step", "row_step", "data", "is_dense"}


def _integer(value: Any, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in {low}..{high}")
    return value


def _text(value: Any, name: str, limit: int, *, empty: bool = False) -> str:
    if (type(value) is not str or (not value and not empty) or len(value) > limit
            or len(value.encode("utf-8")) > limit
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ValueError(f"{name} must be bounded UTF-8 text without control characters")
    return value


def pointcloud_config(value: Any, ros_type: Any) -> dict[str, int]:
    if ros_type not in POINT_TYPES:
        raise ValueError("point_cloud requires a ROS PointCloud2 message type")
    if not isinstance(value, Mapping) or set(value) - {"max_input_bytes", "max_points", "max_fields"}:
        raise ValueError("point_cloud permits only max_input_bytes, max_points and max_fields")
    return {
        "max_input_bytes": _integer(value.get("max_input_bytes", 8 * 1024 * 1024),
                                    "max_input_bytes", 1, MAX_ARTIFACT_BYTES),
        "max_points": _integer(value.get("max_points", 1_048_576), "max_points", 1, 10_000_000),
        "max_fields": _integer(value.get("max_fields", 64), "max_fields", 1, 128),
    }


def _header(message: Mapping[str, Any], version: int) -> dict[str, Any]:
    value = message["header"]
    keys = {"stamp", "frame_id"} | ({"seq"} if version == 1 else set())
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError("PointCloud2 header fields do not match its ROS version")
    sec, nsec = ("secs", "nsecs") if version == 1 else ("sec", "nanosec")
    stamp = value["stamp"]
    if not isinstance(stamp, Mapping) or set(stamp) != {sec, nsec}:
        raise ValueError("PointCloud2 stamp fields do not match its ROS version")
    result = {"stamp": {
        sec: _integer(stamp[sec], sec, 0 if version == 1 else -(2 ** 31),
                      2 ** 32 - 1 if version == 1 else 2 ** 31 - 1),
        nsec: _integer(stamp[nsec], nsec, 0, 999_999_999),
    }, "frame_id": _text(value["frame_id"], "frame_id", 256, empty=True)}
    if version == 1:
        result["seq"] = _integer(value["seq"], "seq", 0, 2 ** 32 - 1)
    return result


def _data(value: Any, expected: int) -> bytes:
    if type(value) is str:
        if len(value) != 4 * ((expected + 2) // 3):
            raise ValueError("PointCloud2 base64 length does not match its declared data size")
        try:
            result = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("PointCloud2 data is not strict base64") from exc
        if len(result) != expected or base64.b64encode(result).decode("ascii") != value:
            raise ValueError("PointCloud2 base64 must have exact length and canonical padding")
        return result
    if type(value) is list:
        if len(value) != expected or any(type(item) is not int or not 0 <= item <= 255 for item in value):
            raise ValueError("PointCloud2 byte array has wrong length or non-byte elements")
        return bytes(value)
    raise ValueError("PointCloud2 data must be canonical base64 or a JSON byte array")


def convert_pointcloud(message: Any, ros_type: str, config: Mapping[str, int], *,
                       topic: str, max_output_bytes: int) -> tuple[bytes, int, str, dict[str, Any]]:
    """Validate the complete message and return one deterministic primary artifact.

    Unknown field datatypes and malformed layouts refuse the whole capture. Field
    order, overlaps, point/row padding, invalid floating-point bit patterns and
    the source density flag are preserved without reinterpretation.
    """
    if ros_type not in POINT_TYPES:
        raise ValueError("unsupported PointCloud2 type")
    if not isinstance(message, Mapping) or set(message) != _MESSAGE_FIELDS:
        raise ValueError("PointCloud2 requires its exact standard message fields")
    _text(topic, "topic", 512)
    _integer(max_output_bytes, "max_output_bytes", 1, MAX_ARTIFACT_BYTES)
    # Revalidate direct callers too; bridge compilation is not the sole guard.
    config = pointcloud_config(config, ros_type)
    version = 1 if ros_type == "sensor_msgs/PointCloud2" else 2
    header = _header(message, version)
    width = _integer(message["width"], "width", 0, 2 ** 32 - 1)
    height = _integer(message["height"], "height", 0, 2 ** 32 - 1)
    count = width * height
    if count > config["max_points"]:
        raise ValueError("PointCloud2 exceeds the point budget")
    step = _integer(message["point_step"], "point_step", 0, config["max_input_bytes"])
    row_step = _integer(message["row_step"], "row_step", 0, config["max_input_bytes"])
    size = row_step * height
    if row_step < width * step or size > config["max_input_bytes"]:
        raise ValueError("PointCloud2 row layout exceeds its byte budget or overlaps points")
    if (count and step == 0) or (count == 0 and (width != 0 or height not in (0, 1) or size != 0)):
        raise ValueError("PointCloud2 has an unsupported empty or zero-width point layout")
    fields = message["fields"]
    if (type(fields) is not list or len(fields) > config["max_fields"]
            or (count and not fields)):
        raise ValueError("PointCloud2 fields must be a bounded list with a layout for nonempty data")
    detached_fields, names = [], set()
    for field in fields:
        if not isinstance(field, Mapping) or set(field) != {"name", "offset", "datatype", "count"}:
            raise ValueError("PointCloud2 field requires exactly name, offset, datatype and count")
        name = _text(field["name"], "field name", 128)
        if name in names:
            raise ValueError("PointCloud2 field names must be unique")
        names.add(name)
        kind = _integer(field["datatype"], "datatype", 1, 8)
        offset = _integer(field["offset"], "offset", 0, step)
        elements = _integer(field["count"], "field count", 1, config["max_input_bytes"])
        if offset + elements * _TYPE_BYTES[kind] > step:
            raise ValueError("PointCloud2 field extends beyond point_step")
        detached_fields.append({"name": name, "offset": offset, "datatype": kind, "count": elements})
    for flag in ("is_bigendian", "is_dense"):
        if type(message[flag]) is not bool:
            raise ValueError(f"PointCloud2 {flag} must be a boolean")
    data = _data(message["data"], size)
    manifest = {
        "format": FORMAT, "type": ros_type, "topic": topic, "header": header,
        "width": width, "height": height, "fields": detached_fields,
        "is_bigendian": message["is_bigendian"], "point_step": step,
        "row_step": row_step, "is_dense": message["is_dense"],
        "data_file": "data.bin", "data_sha256": hashlib.sha256(data).hexdigest(),
    }
    metadata = json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(metadata) > 64 * 1024:
        raise ValueError("PointCloud2 metadata exceeds its byte budget")
    entries = (("pointcloud.json", metadata), ("data.bin", data))
    # ZIP_STORED, fixed ASCII names, no extra fields/comments/data descriptors.
    expected_size = 22 + sum(76 + 2 * len(name) + len(value) for name, value in entries)
    if expected_size > max_output_bytes:
        raise ValueError("complete PointCloud2 artifact exceeds the configured limit")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        for name, value in entries:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100600 << 16
            archive.writestr(info, value)
    result = output.getvalue()
    if len(result) != expected_size:
        raise ValueError("PointCloud2 archive layout differs from its bounded size")
    extension = {"openmhs.ros_point_cloud": {"format": FORMAT, "topic": topic,
                 "type": ros_type, "ros_version": version, "header": header}}
    return result, count, header["frame_id"], extension
