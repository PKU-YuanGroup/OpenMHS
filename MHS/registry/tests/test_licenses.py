#!/usr/bin/env python3
"""Licence identification: catalogue prose, licence-file fingerprints, packaging metadata, classes."""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, REG)

import licenses as L  # noqa: E402

MIT = """MIT License

Copyright (c) 2024 Someone

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
"""
BSD3 = """Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products"""
BSD2 = "Redistribution and use in source and binary forms, with or without modification, are permitted"
GPL3 = "GNU GENERAL PUBLIC LICENSE\n Version 3, 29 June 2007"
LGPL3 = "GNU LESSER GENERAL PUBLIC LICENSE\n Version 3, 29 June 2007"
AGPL3 = "GNU AFFERO GENERAL PUBLIC LICENSE\n Version 3, 19 November 2007"
APACHE = "Apache License\n Version 2.0, January 2004\n http://www.apache.org/licenses/"


class CatalogueTests(unittest.TestCase):
    def test_plain_ids_and_unknowns(self):
        self.assertEqual(L.from_catalog("MIT"), ("MIT", False))
        self.assertEqual(L.from_catalog("Apache-2.0"), ("Apache-2.0", False))
        self.assertEqual(L.from_catalog("GPL-3.0-or-later")[0], "GPL-3.0-or-later")
        for value in ("unknown", "NOASSERTION", "", None, "unknown (not identified)"):
            self.assertEqual(L.from_catalog(value), (None, False), value)

    def test_prose_names_its_first_id(self):
        self.assertEqual(L.from_catalog("MIT (LICENSE read); assets licensed separately")[0], "MIT")
        self.assertEqual(L.from_catalog("MIT OR Apache-2.0 (README)")[0], "MIT OR Apache-2.0")
        self.assertEqual(L.from_catalog("AGPLv3 (pyproject.toml)")[0], "AGPL-3.0")
        self.assertEqual(L.from_catalog("University of Illinois/NCSA Open Source License")[0], "NCSA")

    def test_sspl_and_polyform_are_source_available(self):
        # REGQ-06: SSPL must never count as redistributable open source
        spdx, _ = L.from_catalog("SSPL-1.0 (since 2.0.0); <=1.0.0 AGPL-3.0")
        self.assertEqual(spdx, "SSPL-1.0")
        self.assertEqual(L.license_class(spdx), "source-available")
        self.assertEqual(L.license_class("PolyForm-Noncommercial-1.0.0"), "source-available")
        self.assertEqual(L.license_class("CC-BY-NC-4.0"), "source-available")

    def test_restrictive_terms_before_the_first_id_describe_the_code(self):
        # 非商业 = non-commercial, 专有 = proprietary, 自定义 = custom (catalogue source words)
        self.assertEqual(L.from_catalog("混合：Core 非商业学术研究许可；vendored Apache-2.0"),
                         ("LicenseRef-noncommercial", True))
        self.assertEqual(L.from_catalog("核心专有许可；examples MIT"), ("LicenseRef-proprietary", True))
        self.assertEqual(L.from_catalog("自定义BSD-3-Clause式许可"), ("LicenseRef-custom", True))
        self.assertEqual(L.from_catalog("MIT式自定义条款"), ("LicenseRef-custom", True))
        # a proprietary dependency after the repo's own id only asks for a review
        self.assertEqual(L.from_catalog("MIT（运行需 NI 专有驱动）"), ("MIT", True))

    def test_no_licence_declared(self):
        # 未声明 = not declared; the named proprietary runtime is a dependency
        self.assertEqual(L.from_catalog("仓库无 LICENSE 文件(未声明许可); Isaac Sim 为 NVIDIA 专有许可"), (None, True))


class FileTests(unittest.TestCase):
    def test_fingerprints(self):
        cases = {MIT: "MIT", BSD3: "BSD-3-Clause", BSD2: "BSD-2-Clause", GPL3: "GPL-3.0", LGPL3: "LGPL-3.0",
                 AGPL3: "AGPL-3.0", APACHE: "Apache-2.0", "This is free and unencumbered software released into "
                 "the public domain.": "Unlicense", "Server Side Public License VERSION 1": "SSPL-1.0"}
        for text, spdx in cases.items():
            self.assertEqual(L.detect_text(text), spdx, text[:40])
        # a file that only reserves rights grants no licence at all
        self.assertEqual(L.detect_text("Copyright (c) 2024 Acme. All rights reserved."), "LicenseRef-proprietary")
        self.assertIsNone(L.detect_text("See the documentation."))
        self.assertEqual(L.detect_text("# SPDX-License-Identifier: MIT OR Apache-2.0\n"), "MIT OR Apache-2.0")

    def test_root_file_selection_and_dual_licence(self):
        self.assertEqual(L.license_files(["COPYING", "LICENSE", "README.md", "LICENSE.md.meta", "License.pdf"]),
                         ["LICENSE", "COPYING"])
        spdx, used = L.detect_files({"LICENSE-MIT": MIT, "LICENSE-APACHE": APACHE})
        self.assertEqual(spdx, "Apache-2.0 OR MIT")
        self.assertEqual(L.license_class(spdx), "permissive")

    def test_declared_metadata(self):
        self.assertEqual(L.from_declared(["GNU General Public License v3 (GPLv3)"]), "GPL-3.0")
        self.assertEqual(L.from_declared(["LGPLv3"]), "LGPL-3.0")
        self.assertEqual(L.from_declared(["Apache License, Version 2.0"]), "Apache-2.0")
        self.assertIsNone(L.from_declared(["BSD License"]))   # ambiguous: no SPDX id


class ResolveTests(unittest.TestCase):
    def test_catalogue_wins_then_file_then_metadata(self):
        self.assertEqual(L.resolve("MIT", "GPL-3.0")["license_spdx"], "MIT")
        r = L.resolve("unknown", "BSD-3-Clause", "LICENSE", ["MIT License"])
        self.assertEqual((r["license_spdx"], r["source"], r["license_class"]), ("BSD-3-Clause", "license-file", "permissive"))
        r = L.resolve("NOASSERTION", None, None, ["LGPLv3"])
        self.assertEqual((r["license_spdx"], r["source"]), ("LGPL-3.0", "package-metadata"))
        r = L.resolve(None, None)
        self.assertEqual((r["license_spdx"], r["license_class"], r["source"], r["review"]),
                         ("NOASSERTION", "unknown", "none", True))

    def test_classes_and_review(self):
        self.assertEqual(L.license_class("LGPL-2.1-or-later"), "weak-copyleft")
        self.assertEqual(L.license_class("GPL-3.0+"), "copyleft")
        self.assertEqual(L.license_class("AGPL-3.0-only"), "network-copyleft")
        self.assertEqual(L.license_class("MIT AND GPL-3.0"), "copyleft")
        self.assertEqual(L.license_class("MIT OR GPL-3.0"), "permissive")
        self.assertTrue(L.resolve("AGPL-3.0", None)["review"])
        self.assertFalse(L.resolve("MIT", None)["review"])
        for cls in L.REVIEW_CLASSES:
            self.assertIn(cls, L.CLASSES)


# Full-text fixtures (REGQ-06 verification): licence texts name other licences
# further down; only the title decides.  Excerpts of the real texts, joined by
# filler where the real text is long.
FILLER = "\n".join("Terms and conditions paragraph %d of the licence text." % i for i in range(60))
GPL3_FULL = (GPL3 + "\n\n Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>\n Everyone is "
             "permitted to copy and distribute verbatim copies\n of this license document, but changing it is not "
             "allowed.\n\n Preamble\n\n The GNU General Public License is a free, copyleft license for\nsoftware "
             "and other kinds of works.\n" + FILLER + "\n  13. Use with the GNU Affero General Public License.\n\n"
             "  Notwithstanding any other provision of this License, you have\npermission to link or combine any "
             "covered work with a work licensed\nunder version 3 of the GNU Affero General Public License\n")
GPL2_FULL = ("GNU GENERAL PUBLIC LICENSE\n Version 2, June 1991\n\n Copyright (C) 1989, 1991 Free Software "
             "Foundation, Inc.\n\n Preamble\n (Some other Free Software Foundation software is covered by\nthe GNU "
             "Lesser General Public License instead.)  You can apply it to\nyour programs, too.\n" + FILLER)
MPL2_FULL = ("Mozilla Public License Version 2.0\n==================================\n\n1. Definitions\n"
             "--------------\n" + FILLER + "\n1.12. \"Secondary License\"\n    means either the GNU General Public "
             "License, Version 2.0, the GNU Lesser\n    General Public License, Version 2.1, the GNU Affero General "
             "Public\n    License, Version 3.0, or any later versions of those licenses.\n")
LGPL3_FULL = (LGPL3 + "\n\n  This version of the GNU Lesser General Public License incorporates\nthe terms and "
              "conditions of version 3 of the GNU General Public\nLicense, supplemented by the additional "
              "permissions listed below.\n" + FILLER)
EULA = ("ACME SIMULATOR END-USER LICENSE AGREEMENT\nLast updated: 2026\n\n1. LICENSE GRANT. Acme grants you a "
        "limited, non-transferable licence.\n2. THIRD-PARTY COMPONENTS. The Software includes components under the "
        "GNU Lesser General Public License version 3 and the MIT License.\n" + FILLER)
BUNDLE = ("The files of this project are provided under different licenses:\n* The paper is published under the "
          "Creative Commons Attribution 4.0 International license.\n* The plugin is published under the MIT "
          "license.\n* The workflow is published under the GNU General Public License v3.0.\n")
NOTICE = ("This project depended on:\n1. ROS. Ros is licensed under the BSD 3-Clause License.\n"
          "Redistribution and use in source and binary forms, with or without modification, are permitted\n")
CHOICE = ("This project is dual licensed under the Apache License, Version 2.0 or the MIT license, at your option.\n"
          + FILLER)
BSD3_TITLED_2 = ("BSD 2-Clause License\n\nCopyright (c) 2015, Someone\nAll rights reserved.\n\nRedistribution and "
                 "use in source and binary forms, with or without\nmodification, are permitted provided that the "
                 "following conditions are met:\n* Neither the name of Someone nor the names of its contributors "
                 "may be used to endorse or promote products\n")


class FullTextTests(unittest.TestCase):
    def test_gpl3_is_not_agpl(self):
        # the GPL-3.0 section 13 names the Affero GPL; the title decides
        self.assertEqual(L.detect_text(GPL3_FULL), "GPL-3.0")
        self.assertEqual(L.license_class(L.detect_text(GPL3_FULL)), "copyleft")

    def test_gpl2_is_not_lgpl(self):
        self.assertEqual(L.detect_text(GPL2_FULL), "GPL-2.0")

    def test_mpl2_is_not_a_gnu_licence(self):
        self.assertEqual(L.detect_text(MPL2_FULL), "MPL-2.0")

    def test_lgpl3_text_and_the_gnu_file_convention(self):
        self.assertEqual(L.detect_text(LGPL3_FULL), "LGPL-3.0")
        # COPYING (GPL) beside COPYING.LESSER (LGPL) is an LGPL project
        self.assertEqual(L.detect_files({"COPYING": GPL3_FULL, "COPYING.LESSER": LGPL3_FULL}),
                         ("LGPL-3.0", "COPYING.LESSER"))

    def test_eula_is_proprietary_even_when_it_names_open_components(self):
        spdx = L.detect_text(EULA)
        self.assertEqual(spdx, "LicenseRef-proprietary")
        self.assertIn(L.license_class(spdx), L.REVIEW_CLASSES)
        self.assertEqual(L.detect_text("Copyright (C) Acme - All Rights Reserved. Proprietary and confidential."),
                         "LicenseRef-proprietary")
        self.assertEqual(L.detect_text("Acme License. Copyright Acme. The Software is provided for academic and "
                                       "non-commercial research purposes only. MIT License components inside."),
                         "LicenseRef-noncommercial")

    def test_bundles_notices_and_choices(self):
        bundle = L.detect_text(BUNDLE)
        self.assertEqual(bundle, "CC-BY-4.0 AND MIT AND GPL-3.0")
        self.assertEqual(L.license_class(bundle), "copyleft")   # AND takes the most restrictive term
        self.assertIsNone(L.detect_text(NOTICE))                # dependencies' licences, not the project's
        self.assertEqual(L.detect_text(CHOICE), "Apache-2.0 OR MIT")

    def test_bsd_title_is_checked_against_its_clauses(self):
        self.assertEqual(L.detect_text(BSD3_TITLED_2), "BSD-3-Clause")
        self.assertEqual(L.detect_text(BSD3.replace("3. Neither the name of the copyright holder nor",
                                                    "3. Neither the name Acme, Acme University, nor")),
                         "BSD-3-Clause")

    def test_titles_beat_names_in_later_prose(self):
        self.assertEqual(L.detect_text("The MIT License (MIT)\n\nCopyright 2018 Zaber\n\n" + MIT.split("\n", 3)[3]
                                       + FILLER + "\nGNU General Public License version 3"), "MIT")
        self.assertEqual(L.detect_text("BSD-3-Clause\n\n" + BSD3 + "\nSee COPYING for the GNU GPL v2 parts."),
                         "BSD-3-Clause")
        self.assertEqual(L.detect_text("GNU GENERAL PUBLIC LICENSE\n Version 2 or (at your option) any later version, "
                                       "June 1991\n" + FILLER), "GPL-2.0")
        self.assertEqual(L.detect_text("released under version 3 of the GNU Affero General Public License (AGPLv3)"),
                         "AGPL-3.0")


if __name__ == "__main__":
    unittest.main()
