"""Keep the required-action schema when a Gymnasium step declares an envelope.

The generic family's automatic descriptions and required action are skipped for
an explicitly declared Action. This public schema hook keeps both in the served
contract without changing the native reset/step interface.
"""

from mhs.bridge.gymnasium import GymnasiumBridge


class AmpContractBridge(GymnasiumBridge):
    def step_input_schema(self):
        schema = super().step_input_schema()
        schema["properties"]["ticks"]["description"] = "Control transitions to advance; the action repeats at each tick"
        schema["properties"]["action"]["description"] = "21 raw action inputs in DR02_DOF_ORDER; operator envelope required"
        schema["required"] = ["action"]
        return schema
