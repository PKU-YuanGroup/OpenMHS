"""Describe the native nested pose tuples through public GymnasiumBridge hooks.

The generic bridge leaves Tuple members opaque. This adapter preserves their native
shape and adds numeric schemas and the bounds of environment.py:89-102. It never
imports the upstream environment or changes its actions.
"""

from mhs.bridge.gymnasium import GymnasiumBridge

SPACE_REF = "ravens/environments/environment.py:89-102"


class RavensPoseBridge(GymnasiumBridge):
    def action_schema(self):
        pose = {
            "type": "array", "minItems": 2, "maxItems": 2, "items": False,
            "prefixItems": [
                {"type": "array", "minItems": 3, "maxItems": 3,
                 "items": {"type": "number"}},
                {"type": "array", "minItems": 4, "maxItems": 4,
                 "items": {"type": "number"}},
            ],
        }
        return {"type": "object", "properties": {"pose0": pose, "pose1": pose},
                "required": ["pose0", "pose1"], "additionalProperties": False}

    def action_limits(self):
        limits = {}
        for name in ("pose0", "pose1"):
            # These are the source-defined native spaces, not fake-derived placeholders.
            for index, space in enumerate(self.action_space.spaces[name].spaces):
                for coordinate, (low, high) in enumerate(zip(space.low, space.high)):
                    limits[f"action.{name}[{index}][{coordinate}]"] = {
                        "min": float(low), "max": float(high),
                        "source": "upstream_code", "ref": SPACE_REF,
                    }
        return limits
