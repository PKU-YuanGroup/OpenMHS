"""Synthetic Modbus register fake for the tag-bridge SDK fixture (all numbers are placeholders)."""
from mhs.bridge.tag_fake import RecordingTagTransport


class FakePlc(RecordingTagTransport):
    def __init__(self, **_options):
        super().__init__("modbus")
        self.registers.update({
            ("coil", 0): False,              # placeholder
            ("discrete", 10): True,          # placeholder
            ("input", 100): 0xFF38,          # placeholder: -20.0 in signed tenths
            ("holding", 200): 0,             # placeholder
            ("holding", 300): 0x0001,        # placeholder high word
            ("holding", 301): 0x0002,        # placeholder low word
            ("input", 400): 0x0000,          # placeholder float32 low word
            ("input", 401): 0x3FC0,          # placeholder float32 high word (1.5)
            ("holding", 500): 0,             # placeholder
        })
