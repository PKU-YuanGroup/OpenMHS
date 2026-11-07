"""Synthetic Channel Access fake for the tag-bridge SDK fixture (all values are placeholders)."""
from mhs.bridge.tag_fake import RecordingTagTransport


class FakeIoc(RecordingTagTransport):
    def __init__(self, **_options):
        super().__init__("epics-ca")
        self.pvs.update({"state": 0, "brightness": 0.0, "label": "idle"})  # placeholders

    def on_write(self, request, raw):
        if request["pv"] == "state":
            self.pvs["brightness"] = 1.0 if raw else 0.0   # placeholder
            self.pvs["label"] = "on" if raw else "idle"     # placeholder
