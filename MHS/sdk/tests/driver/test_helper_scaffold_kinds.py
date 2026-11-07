"""Every task-card helper maps to an existing scaffold template kind (``mhs.driver new`` and ``new --like``)."""

import unittest

from mhs.driver import scaffold
from mhs.driver.package import HELPER_KINDS, card_kind


class HelperKindTests(unittest.TestCase):
    def test_every_mapped_helper_has_a_template_kind(self):
        # an unknown kind made `new` fail for every card of a family ("unknown template kind 'ophyd'")
        for helper, kind in HELPER_KINDS.items():
            with self.subTest(helper=helper):
                self.assertIn(kind, scaffold.KINDS)

    def test_the_registry_helpers_of_the_new_families_are_mapped(self):
        self.assertEqual(card_kind({"helper": "PyLabRobotDriver"}), "python-object")
        self.assertEqual(card_kind({"helper": "McpClientDriver"}), "direct")
        self.assertEqual(card_kind({"helper": "TagDriver"}), "direct")
        self.assertEqual(card_kind({"helper": "Sila2Driver"}), "direct")
        for helper in ("QcodesDriver", "OphydDriver"):
            self.assertEqual(card_kind({"helper": helper}), "python-object", helper)


if __name__ == "__main__":
    unittest.main()
