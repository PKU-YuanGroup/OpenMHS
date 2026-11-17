"""Preserve the required Gymnasium action when declaring an explicit envelope.

The family's automatic input descriptions and required action are skipped for an
explicit Action. This public schema hook keeps them in the served contract and
in the bridge's own input validation; native step/reset and stop paths are unchanged.
"""

from mhs.bridge.gymnasium import GymnasiumBridge


class TrackerContractBridge(GymnasiumBridge):
    def step_input_schema(self):
        schema = super().step_input_schema()
        schema["properties"]["ticks"]["description"] = "Control transitions to advance; the action repeats at each tick"
        schema["properties"]["action"]["description"] = (
            "23 raw fake joint-action coordinates; the operator must supply their envelope")
        schema["required"] = sorted(set(schema.get("required", [])) | {"action"})
        return schema
