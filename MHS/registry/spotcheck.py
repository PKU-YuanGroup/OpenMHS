#!/usr/bin/env python3
"""Print a reproducible random sample of task cards for a human spot check (stdlib only).

    python3 MHS/registry/spotcheck.py --seed 2030 --n 30                      # readable summary
    python3 MHS/registry/spotcheck.py --seed 2033 --n 20 --pool dispatchable  # dispatchable cards only
    python3 MHS/registry/spotcheck.py --seed 2030 --n 30 --json               # the sampled cards
    python3 MHS/registry/spotcheck.py --ids gh.owner/repo gh.other/repo       # named cards

The sample is ``random.Random(seed).sample`` over the sorted package ids of
the pool (``all`` cards, the ``dispatchable`` ones, or the ``direct-driver``
ones), so the same seed and pool print the same cards as long as the pool is
unchanged (a triage fix can change the dispatchable pool; ``--ids`` prints the
cards a recorded sample named).  For each card it shows the decision,
the triage rule and evidence, the entry symbols, the hints and the clone path,
which is what a reviewer opens to judge whether the strategy is right.  The
verdicts are recorded in ``MHS/registry/tasks/SPOTCHECK.md``.
"""

from __future__ import annotations

import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import taskcards as TC  # noqa: E402


POOLS = {
    "all": lambda card: True,
    "dispatchable": TC.dispatchable_now,
    "direct-driver": lambda card: card["decision"] == "direct-driver",
}


def sample(cards: dict, n: int, seed: int, pool: str = "all") -> list[str]:
    ids = sorted(pid for pid, card in cards.items() if POOLS[pool](card))
    return random.Random(seed).sample(ids, min(n, len(ids)))


def describe(card: dict, record: dict | None) -> str:
    triage = ((record or {}).get("x-vendor") or {}).get("triage") or {}
    lines = [f"== {card['package_id']}  ({card['local_path']})",
             f"   decision {card['decision']} / role {card['role']} / reason {card['reason_code']} "
             f"(rule {triage.get('rule')}); family {card['family']}; helper {card['helper']} "
             f"({card['helper_status']}); blocked_on {card['blocked_on']}; wave {card['wave']} rank {card['rank']}",
             f"   licence {card['upstream']['license_spdx']} ({card['upstream']['license_class']}); commit "
             f"{(card['upstream']['commit'] or 'none')[:12]}; quarantine {card['quarantine']}; "
             f"variant_of {card['variant_of']}; package {card.get('package_status')}"]
    for item in triage.get("evidence") or []:
        lines.append(f"   evidence: {item}")
    if card["skip_reason"]:
        lines.append(f"   skip_reason: {card['skip_reason']}")
    for sym in card["entry_symbols"][:3]:
        lines.append(f"   entry: {sym['symbol']} ({sym['file']}:{sym['line']}, {sym['confidence']})")
    hints = card["hints"]
    if hints["candidate_classes"]:
        lines.append(f"   classes: {', '.join(hints['candidate_classes'])}; risk floor {card['safety']['risk_floor']}; "
                     f"expected mode {card['safety']['expected_mode']}")
    lines.append(f"   install: {card['install']['commands'] or 'none'}; mock: {card['mock_strategy']['preferred']}")
    if record:
        lines.append(f"   record: tier {record['tier']}, family {record['families'][0]}, modes {record['modes']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--seed", type=int, default=2030, help="tasks/SPOTCHECK.md lists the seeds it used")
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--pool", choices=sorted(POOLS), default="all")
    parser.add_argument("--ids", nargs="+", metavar="PACKAGE_ID",
                        help="print these cards instead of a random sample (a sample's ids as SPOTCHECK.md lists them)")
    parser.add_argument("--json", action="store_true", help="print the sampled cards as JSON")
    args = parser.parse_args(argv)
    cards = TC.load_cards()
    if not cards:
        print("[spotcheck] no task cards under MHS/registry/tasks/", file=sys.stderr)
        return 2
    picked = list(args.ids) if args.ids else sample(cards, args.n, args.seed, args.pool)
    missing = [pid for pid in picked if pid not in cards]
    if missing:
        print(f"[spotcheck] no card for {', '.join(missing)}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps([cards[p] for p in picked], ensure_ascii=False, indent=1))
        return 0
    for i, pid in enumerate(picked, 1):
        card = cards[pid]
        path = os.path.join(HERE, "repos", card["track"], card["driver_dir"].rsplit("/", 1)[1] + ".json")
        record = None
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                record = json.load(fh)
        print(f"[{i:02d}] " + describe(card, record))
    return 0


if __name__ == "__main__":
    sys.exit(main())
