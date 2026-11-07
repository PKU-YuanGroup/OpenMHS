"""Synthetic Alpaca fake for the tag-bridge SDK fixture (all values are placeholders)."""
from mhs.bridge.tag_fake import RecordingTagTransport


class FakeDome(RecordingTagTransport):
    def __init__(self, **_options):
        super().__init__("alpaca")
        self.properties.update({"azimuth": 0.0, "slewing": False})  # placeholders

    def on_invoke(self, request, args):
        if request["member"] == "slewtoazimuth":
            self.properties["slewing"] = True                   # placeholder: a slew starts
            self.properties["azimuth"] = float(args["Azimuth"])  # placeholder: arrives at once
            return 0
        if request["member"] == "abortslew":
            self.properties["slewing"] = False
            return 0
        return 0x400
