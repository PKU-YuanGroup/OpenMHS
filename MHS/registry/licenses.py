#!/usr/bin/env python3
"""Upstream licence identification for the registry and the task cards (stdlib only).

Two inputs are combined:

* the catalogue ``license`` field (an SPDX id for most rows; ``unknown``,
  ``NOASSERTION`` or free prose, partly in Chinese, for the rest), and
* the licence file at the root of the clone (``LICENSE``, ``COPYING`` ...),
  identified from its title (``detect_text``): the licence title, grant
  sentence or SPDX id that comes first in the head of the file decides, so a
  licence named further down (the Affero GPL in section 13 of the GPL-3.0, the
  GNU licences in section 1.12 of the MPL-2.0, a component of a bundle or an
  EULA) never does.  End-user licence agreements and all-rights-reserved files
  are proprietary, non-commercial terms ``LicenseRef-noncommercial``; a bundle
  that assigns licences to parts of the repository is the AND of the licences
  its head names.

``resolve`` returns the SPDX expression the registry publishes
(``license_spdx``), its licence class (``license_class``), where the value came
from and whether a publication review is needed.  The licence file wins only
when the catalogue says unknown or NOASSERTION or names no SPDX id (REGQ-06).

Licence classes (``defs.schema.json#/$defs/licenseClass``) from least to most
restrictive: permissive, weak-copyleft, copyleft, network-copyleft,
source-available, proprietary; ``unknown`` when nothing is known.  SSPL,
PolyForm, BUSL, Elastic and the Creative Commons NonCommercial/NoDerivatives
licences are source-available, never redistributable as open source.

These are evidence for planning, not legal conclusions.
"""

from __future__ import annotations

import re
from typing import Iterable, Mapping

CLASSES = ("permissive", "weak-copyleft", "copyleft", "network-copyleft", "source-available",
           "proprietary", "unknown")
#: classes whose driver packages wait for the user's publication decision (DECISIONS.md #6)
REVIEW_CLASSES = ("network-copyleft", "source-available", "proprietary", "unknown")
_ORDER = {name: i for i, name in enumerate(CLASSES)}

#: SPDX id (or LicenseRef) -> licence class.  Variants ``-only``, ``-or-later``
#: and a trailing ``+`` take the class of their base id.
SPDX_CLASS: dict[str, str] = {}
for _ids, _cls in (
    (("MIT", "MIT-0", "Apache-2.0", "Apache-1.1", "BSD-2-Clause", "BSD-3-Clause", "BSD-3-Clause-Clear",
      "BSD-4-Clause", "0BSD", "ISC", "CECILL-B", "LicenseRef-EPICS-Open", "CERN-OHL-P-2.0",
      "LicenseRef-public-domain", "Zlib", "Unlicense", "CC0-1.0", "BSL-1.0", "PSF-2.0", "Python-2.0",
      "NCSA", "PostgreSQL", "X11", "WTFPL", "CC-BY-3.0", "CC-BY-4.0", "AFL-3.0", "Artistic-2.0", "HPND",
      "UPL-1.0", "ECL-2.0", "BlueOak-1.0.0", "Libpng", "curl", "MIT-CMU", "NIST-PD"), "permissive"),
    (("LGPL-2.0", "LGPL-2.1", "LGPL-3.0", "MPL-1.1", "MPL-2.0", "EPL-1.0", "EPL-2.0", "CDDL-1.0", "CDDL-1.1",
      "MS-RL", "OFL-1.1", "CECILL-C", "CERN-OHL-W-2.0"), "weak-copyleft"),
    (("GPL-1.0", "GPL-2.0", "GPL-3.0", "EUPL-1.1", "EUPL-1.2", "CC-BY-SA-3.0", "CC-BY-SA-4.0", "OSL-3.0",
      "CECILL-2.1", "CERN-OHL-S-2.0", "CERN-OHL-1.2", "TAPR-OHL-1.0"), "copyleft"),
    (("AGPL-1.0", "AGPL-3.0"), "network-copyleft"),
    (("SSPL-1.0", "BUSL-1.1", "Elastic-2.0", "PolyForm-Noncommercial-1.0.0", "PolyForm-Small-Business-1.0.0",
      "PolyForm-Shield-1.0.0", "CC-BY-NC-3.0", "CC-BY-NC-4.0", "CC-BY-NC-SA-3.0", "CC-BY-NC-SA-4.0",
      "CC-BY-NC-ND-4.0", "CC-BY-ND-4.0", "LicenseRef-NVIDIA-Source-Code", "LicenseRef-noncommercial"),
     "source-available"),
    (("LicenseRef-proprietary",), "proprietary"),
    (("NOASSERTION", "LicenseRef-custom"), "unknown"),
):
    for _id in _ids:
        SPDX_CLASS[_id] = _cls
del _ids, _cls

_CANONICAL = {key.lower(): key for key in SPDX_CLASS}

#: free-text names in catalogue prose -> SPDX id (longest match first)
_ALIASES = (
    (r"university of illinois/ncsa open source license", "NCSA"),
    (r"nist 软件声明|nist software (?:disclaimer|notice)", "NIST-PD"),   # 软件声明 = software notice
    (r"nvidia source code license", "LicenseRef-NVIDIA-Source-Code"),
    (r"server side public license", "SSPL-1.0"),
    (r"polyform[ -]noncommercial", "PolyForm-Noncommercial-1.0.0"),
    (r"cc[ -]?by[ -]?nc[ -]?sa[ -]?4\.?0", "CC-BY-NC-SA-4.0"),
    (r"cc[ -]?by[ -]?nc[ -]?4\.?0", "CC-BY-NC-4.0"),
    (r"cc[ -]?by[ -]?sa[ -]?4\.?0", "CC-BY-SA-4.0"),
    (r"cc[ -]?by[ -]?4\.?0", "CC-BY-4.0"),
    (r"affero general public license,? v?(?:ersion )?3", "AGPL-3.0"),
    (r"lesser general public license,? v?(?:ersion )?3", "LGPL-3.0"),
    (r"lesser general public license,? v?(?:ersion )?2", "LGPL-2.1"),
    (r"(?<!lesser )(?<!affero )general public license,? v?(?:ersion )?3", "GPL-3.0"),
    (r"(?<!lesser )(?<!affero )general public license,? v?(?:ersion )?2", "GPL-2.0"),
    (r"apache(?: software)? licen[cs]e,? (?:version )?2(?:\.0)?|apache[ -]2(?:\.0)?(?![0-9])", "Apache-2.0"),
    (r"bsd[- ]3[- ]clause|3-clause bsd|new bsd|modified bsd", "BSD-3-Clause"),
    (r"bsd[- ]2[- ]clause|2-clause bsd|simplified bsd|freebsd licen", "BSD-2-Clause"),
    (r"mozilla public license 2\.0|mpl[- ]?2(?:\.0)?(?![0-9])", "MPL-2.0"),
    (r"the unlicense", "Unlicense"),
    (r"agpl ?v?3", "AGPL-3.0"),
    (r"lgpl ?v?3", "LGPL-3.0"),
    (r"gpl ?v?3", "GPL-3.0"),
    (r"gpl ?v?2", "GPL-2.0"),
)
_ID_TOKEN = re.compile(r"(?<![A-Za-z0-9.+-])(LicenseRef-[A-Za-z0-9.-]+|[A-Za-z][A-Za-z0-9.+-]*[A-Za-z0-9+])"
                       r"(?![A-Za-z0-9-])")
_UNKNOWN_WORDS = ("", "unknown", "noassertion", "none", "n/a", "other")
#: catalogue prose about the repo itself that needs a publication review even
#: when an open-source id is named (proprietary or non-commercial components).
#: The Chinese source words are matched as given: 专有 = proprietary,
#: 非商业 = non-commercial, 自定义 = custom.
_REVIEW_WORDS = re.compile(r"专有|proprietary|非商业|non-?commercial|自定义|custom licen[cs]e|EULA", re.IGNORECASE)


def base_id(spdx_id: str) -> str:
    """``GPL-3.0-or-later`` / ``GPL-3.0-only`` / ``GPL-3.0+`` -> ``GPL-3.0`` (canonical case)."""
    text = spdx_id.strip()
    text = re.sub(r"(-only|-or-later|\+)$", "", text, flags=re.IGNORECASE)
    return _CANONICAL.get(text.lower(), text)


def canonical_id(token: str) -> str | None:
    """Canonical spelling of a known SPDX id or variant, or None."""
    text = token.strip()
    suffix = ""
    match = re.search(r"(-only|-or-later|\+)$", text, flags=re.IGNORECASE)
    if match:
        suffix = match.group(1).lower()
        text = text[: match.start()]
    canon = _CANONICAL.get(text.lower())
    if canon is None:
        return None
    if canon.startswith("LicenseRef-") or canon == "NOASSERTION":
        return canon
    if suffix == "+":
        suffix = "-or-later"
    return canon + suffix


def id_class(spdx_id: str) -> str:
    return SPDX_CLASS.get(base_id(spdx_id), "unknown")


def license_class(expression: str | None) -> str:
    """Class of an SPDX expression: ``OR`` takes the least restrictive term, ``AND`` the most restrictive."""
    if not expression:
        return "unknown"
    text = expression.strip().strip("()")
    if " OR " in text:
        return min((license_class(part) for part in text.split(" OR ")), key=_ORDER.__getitem__)
    if " AND " in text:
        return max((license_class(part) for part in text.split(" AND ")), key=_ORDER.__getitem__)
    return id_class(text)


def most_restrictive(classes: Iterable[str]) -> str:
    items = [c for c in classes if c in _ORDER]
    return max(items, key=_ORDER.__getitem__) if items else "unknown"


def is_unknown(value: str | None) -> bool:
    text = (value or "").strip().lower()
    return text in _UNKNOWN_WORDS or text.startswith(("unknown", "noassertion"))


def ids_in_text(text: str) -> list[str]:
    """Known SPDX ids named in catalogue prose, in order of appearance (duplicates removed)."""
    found: list[tuple[int, str]] = []
    low = text.lower()
    for pattern, spdx in _ALIASES:
        for match in re.finditer(pattern, low):
            found.append((match.start(), spdx))
    for match in _ID_TOKEN.finditer(text):
        canon = canonical_id(match.group(1))
        if canon and canon != "NOASSERTION":
            found.append((match.start(), canon))
    out: list[str] = []
    for _pos, spdx in sorted(found, key=lambda item: item[0]):
        if base_id(spdx) not in {base_id(x) for x in out}:
            out.append(spdx)
    return out


#: prose saying the repository declares no licence (未声明 = not declared, 无 LICENSE = no LICENSE file)
_UNDECLARED = re.compile(r"未声明|无\s*LICENSE|no licen[cs]e (?:file|declared)", re.IGNORECASE)


def _id_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    low = text.lower()
    for pattern, _spdx in _ALIASES:
        spans.extend((m.start(), m.end()) for m in re.finditer(pattern, low))
    for match in _ID_TOKEN.finditer(text):
        canon = canonical_id(match.group(1))
        if canon and canon != "NOASSERTION":
            spans.append((match.start(1), match.end(1)))
    return sorted(spans)


def _first_id_position(text: str) -> int | None:
    spans = _id_spans(text)
    return spans[0][0] if spans else None


def _first_id_end(text: str) -> int:
    spans = _id_spans(text)
    return spans[0][1] if spans else 0


def from_catalog(raw: str | None) -> tuple[str | None, bool]:
    """(SPDX expression or None, review_hint) from the catalogue licence field.

    A plain id (``MIT``) or a simple ``A OR B`` / ``A AND B`` expression is
    returned as is; prose returns its first named id.  ``review_hint`` is True
    when the prose mentions a proprietary, non-commercial or custom component.
    """
    text = (raw or "").strip()
    if is_unknown(text):
        return None, False
    canon = canonical_id(text)
    if canon:
        return (None if canon == "NOASSERTION" else canon), False
    expr = re.match(r"^\s*([A-Za-z0-9.+-]+)\s+(OR|AND)\s+([A-Za-z0-9.+-]+)", text)
    if expr and canonical_id(expr.group(1)) and canonical_id(expr.group(3)):
        return f"{canonical_id(expr.group(1))} {expr.group(2)} {canonical_id(expr.group(3))}", bool(
            _REVIEW_WORDS.search(text))
    review = bool(_REVIEW_WORDS.search(text))
    if _UNDECLARED.search(text):
        # the repo declares no licence of its own; named ids belong to dependencies or assets
        return None, True
    ids = ids_in_text(text)
    first = _first_id_position(text)
    lead = text[:first] if first is not None else text
    # a restrictive term before the first open-source id describes the main code
    # (mixed licences such as a non-commercial core with vendored Apache code)
    if re.search(r"非商业|non-?commercial", lead, re.I):
        return "LicenseRef-noncommercial", True
    if re.search(r"专有|proprietary", lead, re.I):
        return "LicenseRef-proprietary", True
    if re.search(r"自定义|custom", lead, re.I):
        return "LicenseRef-custom", True
    if ids:
        if first is not None and re.match(r"\s*(?:式|-?style)", text[_first_id_end(text):]):
            return "LicenseRef-custom", True   # "MIT式" = MIT-style custom terms
        return ids[0], review
    return None, review


# ---------------------------------------------------------------------------
# licence file identification
# ---------------------------------------------------------------------------

#: characters of the whitespace-normalised licence text that hold its title.
#: A licence file is identified by the title, grant sentence or SPDX id that
#: comes first in this window, never by a licence name further down: the
#: GPL-3.0 text names the Affero GPL in its section 13, the MPL-2.0 text names
#: three GNU licences in its section 1.12, and bundles and EULAs name the
#: licences of their components.
HEAD_CHARS = 2000
#: characters after a title that may hold its version keyword ("Version 3, 29 June 2007")
VERSION_WINDOW = 160
#: characters after a title that may hold a bare version number ("Mozilla Public License 2.0")
BARE_VERSION_WINDOW = 30
#: at most this many terms in the AND expression of a multi-licence bundle
MAX_BUNDLE_TERMS = 4

_NONCOMMERCIAL_TEXT = (r"\bnon-?commercial(?:ly)?\b(?! 4\.0| 3\.0|-sharealike|-noderiv)|\bnon-?profit use\b|"
                       r"not permit any commercial|profit-? ?making is (?:strictly )?prohibited|"
                       r"for (?:academic|research|educational) (?:use|purposes) only")
#: (key, pattern) of every licence title or grant sentence, matched on the
#: lowercased head; the earliest match decides.  Keys are SPDX ids, or a family
#: (``gnu``, ``gpl-short``, ``apache``, ``bsd``, ``bsd-name``, ``mpl``, ``epl``,
#: ``eupl``, ``cddl``, ``cc``, ``cecill``) whose variant and version
#: :func:`_resolve_title` reads from the text around the match, or
#: ``proprietary`` (an end-user licence agreement or a licence that must be
#: bought) and ``noncommercial`` (non-commercial or non-profit terms).
_TITLES: tuple[tuple[str, str], ...] = (
    ("proprietary", r"end[- ]?user licen[cs]e agreement|\beula\b|obtain a (?:valid )?licen[cs]e (?:from|key)|"
                    r"\bnvidia isaac ros software licen[cs]e\b"),
    ("noncommercial", _NONCOMMERCIAL_TEXT),
    ("gnu", r"\bgnu (?:(affero|lesser|library) )?general public licen[cs]e"),
    ("gpl-short", r"(?<![a-z0-9-])(agpl|lgpl|gpl)[ -]?v?([123](?:\.[01])?)(?![0-9])"),
    ("apache", r"\bapache licen[cs]e\b|\bapache[ -]2\.0\b|apache\.org/licenses/licen[cs]e-2\.0|"
               r"terms and conditions for use, reproduction, and distribution"),
    ("MIT", r"permission is hereby granted, free of charge, to any person obtaining a copy|\bmit licen[cs]e\b|"
            r"\bmit \"expat\" licen[cs]e\b|\bexpat licen[cs]e\b"),
    ("bsd", r"redistribution and use in source and binary forms"),
    ("bsd-name", r"\bbsd[- ]?([234])[- ]clause\b|\b([234])[- ]clause bsd\b|\b(new|modified|revised|simplified) bsd\b"),
    ("ISC", r"permission to use, copy, modify, and(?:/or)? distribute this software for any purpose "
            r"with or without fee is hereby granted|\bisc licen[cs]e\b"),
    ("Zlib", r"this software is provided 'as-is', without any express or implied warranty\. in no event will "
             r"the authors be held liable|\bzlib licen[cs]e\b"),
    ("Unlicense", r"this is free and unencumbered software released into the public domain"),
    ("WTFPL", r"do what the fuck you want to public licen[cs]e"),
    ("NCSA", r"university of illinois/ncsa open source licen[cs]e"),
    ("PSF-2.0", r"python software foundation licen[cs]e"),
    ("BSL-1.0", r"boost software licen[cs]e"),
    ("CC0-1.0", r"\bcc0 1\.0 universal\b|creative commons zero"),
    ("cc", r"creative commons (?:legal code )?attribution|\battribution(?:-noncommercial)?(?:-sharealike|"
           r"-noderivatives|-noderivs)? [34]\.0 international"),
    ("mpl", r"mozilla public licen[cs]e"),
    ("epl", r"eclipse public licen[cs]e"),
    ("eupl", r"european union public licen[cs]e"),
    ("cddl", r"common development and distribution licen[cs]e"),
    ("cecill", r"\bcecill(?:-([bc]))?\b"),
    ("cern-ohl", r"\bcern open hardware licen[cs]e,? (?:version |v\.? ?)?(\d\.\d|\d)(?: - (strongly|weakly) reciprocal"
                 r"| - (permissive))?"),
    ("TAPR-OHL-1.0", r"\btapr open hardware licen[cs]e\b"),
    ("NIST-PD", r"developed by employees of the national institute of standards and technology|"
                r"nist-developed software is provided by nist as a public service"),
    ("LicenseRef-public-domain", r"(?:is|are) not subject to copyright protection|"
                                 r"(?:is|are|been) (?:released |placed |dedicated )?(?:in|into|to) the public domain"),
    ("LicenseRef-EPICS-Open", r"epics open licen[cs]e|distributed subject to the following licen[cs]e conditions: "
                              r"software licen[cs]e agreement"),
    ("SSPL-1.0", r"server side public licen[cs]e"),
    ("BUSL-1.1", r"business source licen[cs]e"),
    ("Elastic-2.0", r"elastic licen[cs]e 2\.0"),
    ("PolyForm-Noncommercial-1.0.0", r"polyform noncommercial licen[cs]e"),
    ("PolyForm-Small-Business-1.0.0", r"polyform small business licen[cs]e"),
    ("PolyForm-Shield-1.0.0", r"polyform shield licen[cs]e"),
    ("LicenseRef-NVIDIA-Source-Code", r"nvidia source code licen[cs]e"),
    ("Artistic-2.0", r"the artistic licen[cs]e 2\.0"),
    ("AFL-3.0", r"academic free licen[cs]e"),
    ("OSL-3.0", r"\bopen software licen[cs]e\b"),
    ("UPL-1.0", r"universal permissive licen[cs]e"),
)
_TITLE_RE = tuple((key, re.compile(pattern)) for key, pattern in _TITLES)
#: prose before the first licence named in a file that makes the file a bundle:
#: different licences for different parts of the repository (the AND of the
#: licences named in the head is returned)
_BUNDLE = re.compile(r"\b(?:different|diff\w*rent|multiple|several|two|three|various|separate|following) licen[cs]es\b|"
                     r"\bportions? of (?:this|the) (?:project|repository|code|software)\b|"
                     r"\blicen[cs]e for (?:the )?(?:contents|files)\b|\bdual[- ]licen[cs]ed with\b|"
                     r"\bthe (?:code|source code|meshes|data|assets|models|documentation|artwork) (?:is|are) "
                     r"(?:licensed|released|published|distributed|under)\b|\ball the (?:data|code|files)\b|"
                     r"\bcontains code (?:licensed )?under\b|\btaken from other\b|\boriginally released under\b")
#: prose before the first licence named in a file that offers a choice between licences (an OR expression)
_CHOICE = re.compile(r"\bany one of the following\b|\bat your option\b|\byou may (?:elect|choose)\b|"
                     r"\bdual[- ]licen[cs]ed under\b|\blicen[cs]ed under either\b|\bchoose (?:either|one)\b")
#: prose before the first licence named in a file that lists dependencies' licences, not the project's
_DEPENDENCY_NOTICE = re.compile(r"\bdepend(?:s|ed|encies)? on\b|\bdependencies\b")
#: bare SPDX ids count only when they carry a version or clause number ("BSD-3-Clause",
#: "Apache-2.0") or form the file's whole first line ("MIT")
_BARE_NAMES = {"MIT", "ISC", "0BSD", "WTFPL", "Unlicense"}
#: wording of a licence that grants no open-source rights, used when the head
#: names no licence (non-commercial terms are looked for in the whole text)
_NONCOMMERCIAL = re.compile(_NONCOMMERCIAL_TEXT)
_PROPRIETARY = re.compile(r"all rights? reserved|licen[cs]e is a legal agreement between you and|"
                          r"no (?:public )?(?:distribution )?licen[cs]e(?:, express or implied,)? is granted|"
                          r"\bprivate project\b|\bproprietary\b|\bconfidential\b|licen[cs]e agreement|"
                          r"may not be (?:copied|reproduced|distributed|redistributed|modified|used)|"
                          r"without (?:the )?(?:express )?(?:prior )?written (?:permission|consent)")
_SPDX_LINE = re.compile(r"SPDX-License-Identifier:\s*([A-Za-z0-9.+() -]+?)\s*(?:\*/|-->|$)", re.MULTILINE)
#: root file names that hold the project licence (lowercase), most specific first
LICENSE_FILE = re.compile(r"^(?:licen[cs]e|copying|unlicense)(?:[-_.](?:mit|apache|txt|md|rst|lesser|lgpl))*"
                          r"(?:\.txt|\.md|\.rst)?$", re.IGNORECASE)


def _version_near(low: str, start: int, end: int) -> str | None:
    """The version of the title at ``low[start:end]``: "version 3 of the <title>" or the text right after it."""
    before = re.search(r"\bversion (\d(?:\.\d+)?) of the $", low[max(0, start - 40):start])
    if before:
        return before.group(1)
    after = low[end:end + VERSION_WINDOW]
    match = re.search(r"\b(?:version|v\.?|ver\.?)\s?(\d(?:\.\d+)?)", after)
    if match:
        return match.group(1)
    match = re.search(r"(?<![\d.])(\d\.\d)(?![\d.])", after[:BARE_VERSION_WINDOW])
    return match.group(1) if match else None


def _gnu(kind: str | None, version: str | None) -> str | None:
    major = (version or "").split(".")[0]
    if kind == "affero":
        return "AGPL-3.0"   # the GNU Affero GPL has a single version
    if kind == "lesser":
        return {"2.1": "LGPL-2.1", "2": "LGPL-2.1", "3": "LGPL-3.0", "3.0": "LGPL-3.0"}.get(version or "")
    if kind == "library":
        return "LGPL-2.0" if major in ("", "2") else None
    return {"1": "GPL-1.0", "2": "GPL-2.0", "3": "GPL-3.0"}.get(major)


def _bsd_variant(body: str) -> str:
    """BSD-2/3/4-Clause from the clauses that follow "Redistribution and use in source and binary forms"."""
    if "no express or implied licenses to any party's patent rights" in body:
        return "BSD-3-Clause-Clear"
    if "all advertising materials mentioning" in body:
        return "BSD-4-Clause"
    if re.search(r"\bneither the names?\b|may not be used to endorse|(?:names? of .{0,80}|names?) may not be used",
                 body):
        return "BSD-3-Clause"
    return "BSD-2-Clause"


def _resolve_title(key: str, match: "re.Match[str]", low: str) -> str | None:
    """SPDX id of the title ``key`` matched at ``match`` (variant and version read from the text around it)."""
    start, end = match.start(), match.end()
    if key == "gnu":
        return _gnu(match.group(1), _version_near(low, start, end))
    if key == "gpl-short":
        kind = {"agpl": "affero", "lgpl": "lesser", "gpl": None}[match.group(1)]
        return _gnu(kind, match.group(2))
    if key == "apache":
        text = match.group(0)
        if "2.0" in text or text.startswith("terms and conditions"):
            return "Apache-2.0"
        return {"2.0": "Apache-2.0", "2": "Apache-2.0", "1.1": "Apache-1.1"}.get(_version_near(low, start, end) or "")
    if key == "bsd":
        return _bsd_variant(low[start:start + 2500])
    if key == "bsd-name":
        number = match.group(1) or match.group(2)
        if number:
            return {"2": "BSD-2-Clause", "3": "BSD-3-Clause", "4": "BSD-4-Clause"}[number]
        return "BSD-2-Clause" if match.group(3) == "simplified" else "BSD-3-Clause"
    if key in ("mpl", "epl", "eupl", "cddl"):
        version = _version_near(low, start, end)
        table = {
            "mpl": {"2.0": "MPL-2.0", "2": "MPL-2.0", "1.1": "MPL-1.1"},
            "epl": {"2.0": "EPL-2.0", "2": "EPL-2.0", "1.0": "EPL-1.0", "1": "EPL-1.0"},
            "eupl": {"1.2": "EUPL-1.2", "1.1": "EUPL-1.1"},
            "cddl": {"1.1": "CDDL-1.1", "1.0": "CDDL-1.0", "1": "CDDL-1.0", None: "CDDL-1.0"},
        }[key]
        return table.get(version)
    if key == "cc":
        window = low[start:start + 200]
        version = re.search(r"([34])\.0", window)
        if not version:
            return None
        nc = "noncommercial" in window or "non-commercial" in window
        sa = "sharealike" in window or "share-alike" in window or "share alike" in window
        nd = "noderiv" in window or "no derivatives" in window
        name = "CC-BY" + ("-NC" if nc else "") + ("-ND" if nd else "") + ("-SA" if sa and not nd else "")
        spdx = f"{name}-{version.group(1)}.0"
        return spdx if spdx in SPDX_CLASS else None
    if key == "cecill":
        variant = match.group(1)
        return {"b": "CECILL-B", "c": "CECILL-C"}.get(variant or "", "CECILL-2.1")
    if key == "cern-ohl":
        if match.group(1).startswith("1"):
            return "CERN-OHL-1.2" if match.group(1) == "1.2" else None
        kind = match.group(2) or match.group(3)
        return {"strongly": "CERN-OHL-S-2.0", "weakly": "CERN-OHL-W-2.0", "permissive": "CERN-OHL-P-2.0"}.get(kind or "")
    if key == "proprietary":
        return "LicenseRef-proprietary"
    if key == "noncommercial":
        return "LicenseRef-noncommercial"
    return key


def _bare_ids(flat: str, first_line: str) -> list[tuple[int, str]]:
    """Bare SPDX ids in the head (position, canonical id)."""
    found = []
    for match in _ID_TOKEN.finditer(flat):
        token = match.group(1)
        canon = canonical_id(token)
        if not canon or canon.startswith("LicenseRef-") or canon == "NOASSERTION":
            continue
        if not (re.search(r"\d", token) or (token in _BARE_NAMES and match.start(1) == 0
                                             and len(first_line) <= len(token) + 12)):
            continue
        found.append((match.start(1), canon))
    return found


def _head(text: str) -> tuple[str, str, str]:
    """(case-kept head, lowercased head, first line): whitespace collapsed, typographic quotes made ASCII."""
    raw = text[: HEAD_CHARS * 4].replace("\u2019", "'").replace("\u2018", "'").replace("`", "'")
    raw = re.sub(r"(?m)^[ \t]*>[ \t]?", "", raw)   # Markdown block quotes around a quoted licence
    raw = raw.lstrip("\ufeff").strip()
    first_line = re.sub(r"\s+", " ", raw.split("\n", 1)[0]).strip()
    flat = re.sub(r"\s+", " ", raw)[:HEAD_CHARS]
    return flat, flat.lower(), first_line


def _hits(flat: str, low: str, first_line: str) -> list[tuple[int, int, str, str]]:
    """Every licence named in the head: (position, title order, SPDX id, title key), sorted."""
    hits: list[tuple[int, int, str, str]] = []
    for order, (key, pattern) in enumerate(_TITLE_RE):
        for found in pattern.finditer(low):
            spdx = _resolve_title(key, found, low)
            if spdx:
                hits.append((found.start(), order, spdx, key))
    hits.extend((pos, len(_TITLE_RE), spdx, "bare") for pos, spdx in _bare_ids(flat, first_line))
    return sorted(hits)


def _terms(hits: list[tuple[int, int, str, str]]) -> list[str]:
    """Distinct licences of the hits in order; the generic non-commercial term goes when a specific one is named."""
    terms: list[str] = []
    for _pos, _order, spdx, _key in hits:
        if base_id(spdx) not in {base_id(t) for t in terms}:
            terms.append(spdx)
    if "LicenseRef-noncommercial" in terms and any(
            t != "LicenseRef-noncommercial" and SPDX_CLASS.get(base_id(t)) == "source-available" for t in terms):
        terms.remove("LicenseRef-noncommercial")
    return terms


def detect_text(text: str) -> str | None:
    """SPDX id of a licence file's text from its title, or None when the head names no licence.

    In order: an ``SPDX-License-Identifier`` line; the licence title, grant
    sentence or bare SPDX id that comes first in the first ``HEAD_CHARS``
    characters (an end-user licence agreement, a licence to be bought, and
    non-commercial or non-profit terms count as titles); a bundle (the prose
    before the first licence assigns licences to parts of the repository)
    gives the AND of the distinct licences in the head, and a notice that
    lists dependencies' licences gives None.  When the head names no
    licence: non-commercial wording anywhere in the text
    (``LicenseRef-noncommercial``), then all-rights-reserved and agreement
    wording in the head (``LicenseRef-proprietary``).  Licence names further
    down (a bundle's components, the GPL-3.0 section on the Affero GPL) never
    decide.
    """
    return _detect(text)[0]


def _detect(text: str) -> tuple[str | None, int]:
    """(SPDX expression, strength): 2 for an SPDX line or a title, 1 for restrictive wording only, 0 for nothing."""
    if not text:
        return None, 0
    match = _SPDX_LINE.search(text[:4000])
    if match:
        expr = match.group(1).strip()
        parts = re.split(r"\s+(OR|AND|WITH)\s+", expr)
        ids = [canonical_id(p) for p in parts[::2]]
        if ids and all(ids):
            out = ids[0]
            for op, value in zip(parts[1::2], ids[1:]):
                out += f" {op} {value}"
            return out, 2
    flat, low, first_line = _head(text)
    hits = _hits(flat, low, first_line)
    if hits:
        prefix = low[:hits[0][0]][-600:]
        if _DEPENDENCY_NOTICE.search(prefix):
            return None, 0
        terms = _terms(hits)
        if len(terms) >= 2 and _CHOICE.search(prefix):
            return " OR ".join(terms[:MAX_BUNDLE_TERMS]), 2
        if len(terms) >= 2 and _BUNDLE.search(prefix):
            return " AND ".join(terms[:MAX_BUNDLE_TERMS]), 2
        first = hits[0]
        if first[3] == "bsd-name":
            # a BSD title is checked against the clauses of the grant that follows it
            grant = next((h for h in hits if h[3] == "bsd"), None)
            if grant is not None:
                return grant[2], 2
        return first[2], 2
    if _NONCOMMERCIAL.search(re.sub(r"\s+", " ", text.lower())):
        return "LicenseRef-noncommercial", 1
    if _PROPRIETARY.search(low):
        return "LicenseRef-proprietary", 1
    return None, 0


def license_files(root_names: Iterable[str]) -> list[str]:
    """Root licence files in the order they are read (LICENSE before COPYING, short names first)."""
    names = [n for n in root_names if LICENSE_FILE.match(n)]

    def key(name: str) -> tuple[int, int, str]:
        low = name.lower()
        kind = 0 if low.startswith(("license", "licence")) else (1 if low.startswith("copying") else 2)
        return kind, len(name), name

    return sorted(names, key=key)


def detect_files(texts: Mapping[str, str]) -> tuple[str | None, str | None]:
    """(SPDX expression, file) from the root licence files' texts.

    ``LICENSE-APACHE`` plus ``LICENSE-MIT`` (the dual-licence convention) give
    ``Apache-2.0 OR MIT``; a GPL text beside an LGPL one (``COPYING`` plus
    ``COPYING.LESSER``, the GNU convention for LGPL projects) gives the LGPL.
    Otherwise the first file whose title names a licence wins, and a file that
    only reserves rights (no title) is used when no file names a licence.
    """
    found: list[tuple[str, str, int]] = []
    for name in license_files(texts):
        spdx, strength = _detect(texts[name])
        if spdx:
            found.append((name, spdx, strength))
    if not found:
        return None, None
    by_name = {name.lower(): spdx for name, spdx, _s in found}
    dual = [v for k, v in sorted(by_name.items()) if k.startswith(("license-apache", "license-mit"))]
    if len(dual) == 2 and set(dual) == {"Apache-2.0", "MIT"}:
        return "Apache-2.0 OR MIT", ", ".join(n for n, _x, _s in found
                                              if n.lower().startswith(("license-apache", "license-mit")))
    titled = [item for item in found if item[2] == 2] or found
    first_name, first_spdx, _s = titled[0]
    if base_id(first_spdx).startswith("GPL-"):
        for name, spdx, _s in titled[1:]:
            if base_id(spdx).startswith("LGPL-") and re.search(r"lesser|lgpl", name, re.IGNORECASE):
                return spdx, name
    return first_spdx, first_name


def from_declared(values: Iterable[str]) -> str | None:
    """SPDX id of the licence declared in packaging metadata (``license =`` or a trove classifier)."""
    for value in values or ():
        canon = canonical_id(value.strip())
        if canon and canon != "NOASSERTION":
            return canon
        ids = ids_in_text(value)
        if ids:
            return ids[0]
    return None


def resolve(catalog_raw: str | None, file_spdx: str | None, file_path: str | None = None,
            declared: Iterable[str] = ()) -> dict:
    """Licence facts for one repo: ``{license_spdx, license_class, source, review, ...}``.

    The catalogue wins; when it says unknown or names no SPDX id, the root
    licence file is used, then the licence declared in the packaging metadata
    (pyproject.toml, setup.cfg, setup.py).  ``source`` is ``catalog``,
    ``license-file``, ``package-metadata`` or ``none``.  ``review`` is True when
    the class needs a publication review or the catalogue prose names a
    proprietary, non-commercial or custom component.
    """
    catalog_spdx, hint = from_catalog(catalog_raw)
    declared_spdx = from_declared(declared)
    if catalog_spdx:
        spdx, source = catalog_spdx, "catalog"
    elif file_spdx:
        spdx, source = file_spdx, "license-file"
    elif declared_spdx:
        spdx, source = declared_spdx, "package-metadata"
    else:
        spdx, source = "NOASSERTION", "none"
    cls = license_class(spdx)
    out = {
        "license_spdx": spdx,
        "license_class": cls,
        "source": source,
        "review": cls in REVIEW_CLASSES or hint,
        "catalog_spdx": catalog_spdx,
        "file_spdx": file_spdx,
        "file": file_path,
        "declared_spdx": declared_spdx,
    }
    out["agrees"] = None if not (catalog_spdx and file_spdx) else (
        license_class(catalog_spdx) == license_class(file_spdx) and base_id(catalog_spdx.split(" ")[0])
        == base_id(file_spdx.split(" ")[0]))
    return out
