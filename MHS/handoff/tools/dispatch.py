#!/usr/bin/env python3
"""List the task cards that can be given to a model now.  Standard library only.

A card is dispatchable when all of these hold (MHS/handoff/PLAYBOOK.md section 1):

* ``decision`` is ``direct-driver`` or ``family-config``;
* ``helper_status`` is ``available`` and ``blocked_on`` is empty;
* ``quarantine`` is false;
* ``package_status`` is ``none`` or ``in_progress`` (a passing package is maintained, not given out again).

Two other kinds of card are given to a model as *recon* tasks, not driver tasks (``--recon`` lists them): cards whose
only blockers are ``recon:*`` codes (confirm the entry symbol first) and ``untriaged`` cards (decide first what the
repository is).  A recon task writes one proposal file, MHS/handoff/recon/<owner>__<repo>.json (PLAYBOOK.md section 7).

Examples (from the repository root)::

    python3 MHS/handoff/tools/dispatch.py                       # all dispatchable cards, wave then rank
    python3 MHS/handoff/tools/dispatch.py --pilot               # only the cards of MHS/handoff/pilot-20.json
    python3 MHS/handoff/tools/dispatch.py --track labs --family scpi --limit 10
    python3 MHS/handoff/tools/dispatch.py --ids --limit 5       # package ids only, one per line
    python3 MHS/handoff/tools/dispatch.py --publishable         # without the cards that need a publication decision
    python3 MHS/handoff/tools/dispatch.py --recon --json        # recon cards as JSON
    python3 MHS/handoff/tools/dispatch.py --todo --ids --limit 1   # the next card nobody has started (driver directory absent)
    python3 MHS/handoff/tools/dispatch.py --todo --ids --limit 1 --only gh.a/b gh.c/d   # the same, within one session's share
    python3 MHS/handoff/tools/dispatch.py --stats               # how many cards are in which state
    python3 MHS/handoff/tools/dispatch.py --check-pilot         # exit 1 when pilot-20.json is not dispatchable
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parents[2]  # MHS/handoff/tools -> repository root
DISPATCH_DECISIONS = ("direct-driver", "family-config")
OPEN_STATUSES = ("none", "in_progress")
# Pilot files ship with the kit; pilot-20.json is the one the playbook names.
PILOT_FILE = "MHS/handoff/pilot-20.json"


def load_cards(root: Path) -> list[dict]:
    cards = []
    for path in sorted((root / "MHS" / "registry" / "tasks").glob("*/*.json")):
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"warning: unreadable card {path}: {exc}", file=sys.stderr)
            continue
        if isinstance(card, dict) and "package_id" in card:
            card["_path"] = str(path.relative_to(root))
            cards.append(card)
    return cards


def status_of(card: dict) -> str:
    return card.get("package_status") or "none"


def kind_of(card: dict) -> str:
    """The state of a card: dispatch, recon, waiting-helper, done, quarantine, or its decision (skip, reference, ...)."""
    if card.get("quarantine"):
        return "quarantine"
    if status_of(card) not in OPEN_STATUSES:
        return "done"
    decision = card.get("decision")
    if decision == "untriaged":
        return "recon"
    if decision in DISPATCH_DECISIONS:
        blocked = card.get("blocked_on") or []
        if not blocked and card.get("helper_status") == "available":
            return "dispatch"
        if blocked and all(code.startswith("recon:") for code in blocked):
            return "recon"
        return "waiting-helper"
    return str(decision)


def reasons_not_dispatchable(card: dict) -> list[str]:
    """Why a card cannot be given out as a driver task now (empty when it can)."""
    if kind_of(card) == "dispatch":
        return []
    why = []
    if card.get("decision") not in DISPATCH_DECISIONS:
        why.append(f"decision {card.get('decision')!r}")
    if card.get("helper_status") != "available":
        why.append(f"helper_status {card.get('helper_status')!r}")
    if card.get("blocked_on"):
        why.append("blocked_on " + ",".join(card["blocked_on"]))
    if card.get("quarantine"):
        why.append("quarantine")
    if status_of(card) not in OPEN_STATUSES:
        why.append(f"package_status {status_of(card)}")
    return why or [f"kind {kind_of(card)}"]


def sort_key(card: dict):
    return (card.get("wave", 9), card.get("rank", 10**9), card["package_id"])


def pilot_ids(root: Path) -> list[str]:
    path = root / PILOT_FILE
    if not path.exists():
        raise SystemExit(f"error: {PILOT_FILE} not found (run from the repository root or pass --root)")
    return [entry["package_id"] for entry in json.loads(path.read_text(encoding="utf-8"))["entries"]]


def check_pilot(root: Path, cards: list[dict]) -> int:
    path = root / PILOT_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    by_id = {card["package_id"]: card for card in cards}
    problems = []
    seen = set()
    buckets: dict[str, int] = {}
    finished: dict[str, int] = {}  # a pilot card with a result is done, not a problem of the file
    for entry in data["entries"]:
        pid = entry["package_id"]
        if pid in seen:
            problems.append(f"{pid}: listed twice")
        seen.add(pid)
        card = by_id.get(pid)
        if card is None:
            problems.append(f"{pid}: no task card")
            continue
        if entry.get("card") != card["_path"]:
            problems.append(f"{pid}: card path {entry.get('card')!r} should be {card['_path']!r}")
        status = card.get("package_status")
        if status in ("pass", "blocked", "skip-proposed"):
            finished[status] = finished.get(status, 0) + 1
        else:
            for reason in reasons_not_dispatchable(card):
                problems.append(f"{pid}: not dispatchable ({reason})")
        if card.get("wave") != 1:
            problems.append(f"{pid}: wave {card.get('wave')} (a pilot repo is wave 1)")
        if entry.get("exemplar_driver_dir") and not (root / entry["exemplar_driver_dir"]).is_dir():
            problems.append(f"{pid}: exemplar {entry['exemplar_driver_dir']} is missing")
        buckets[entry["bucket"]] = buckets.get(entry["bucket"], 0) + 1
    if buckets != data.get("bucket_counts"):
        problems.append(f"bucket_counts {data.get('bucket_counts')} != actual {buckets}")
    if len(data["entries"]) != data.get("count"):
        problems.append(f"count {data.get('count')} != {len(data['entries'])} entries")
    for problem in problems:
        print("PROBLEM:", problem)
    done = f", finished {sum(finished.values())} {finished}" if finished else ""
    print(f"{PILOT_FILE}: {len(data['entries'])} entries, buckets {buckets}{done}, {len(problems)} problem(s)")
    return 1 if problems else 0


def started(root: Path, card: dict, wanted_kind: str) -> bool:
    """Whether work on a card has begun: its driver directory (driver tasks) or its proposal file (recon tasks) exists."""
    slug = card["driver_dir"].rsplit("/", 1)[-1]
    if wanted_kind == "recon":
        return (root / "MHS" / "handoff" / "recon" / f"{slug}.json").exists()
    return (root / card["driver_dir"]).exists()


def select_cards(root: Path, cards: list[dict], *, wanted_kind: str = "dispatch", pilot: bool = False, publishable: bool = False,
                 track: str | None = None, family: str | None = None, wave: int | None = None,
                 ids: list[str] | None = None, todo: bool = False) -> list[dict]:
    """The cards of one state (``dispatch`` or ``recon``) that pass the filters, in order: wave, then rank.

    ``todo`` leaves out the cards whose work has begun (:func:`started`), whatever came of it: the cards keep saying
    ``package_status: none`` until the registry is rebuilt, so this is how a loop finds the next one."""
    selected = [card for card in cards if kind_of(card) == wanted_kind]
    if todo:
        selected = [card for card in selected if not started(root, card, wanted_kind)]
    if pilot:
        wanted = set(pilot_ids(root))
        selected = [card for card in selected if card["package_id"] in wanted]
    if ids:
        selected = [card for card in selected if card["package_id"] in set(ids)]
    if publishable:
        selected = [card for card in selected if card.get("publish_review") != "required"]
    if track:
        selected = [card for card in selected if card.get("track") == track]
    if family:
        selected = [card for card in selected if card.get("family") == family]
    if wave is not None:
        selected = [card for card in selected if card.get("wave") == wave]
    selected.sort(key=sort_key)
    return selected


def row(card: dict) -> str:
    return "{wave:>2} {rank:>6}  {pid:<46} {track:<6} {family:<13} {mode:<9} {risk:<2} {pub:<3} {recon}".format(
        wave=card.get("wave", "-"),
        rank=card.get("rank", "-"),
        pid=card["package_id"],
        track=card.get("track", ""),
        family=card.get("family") or "-",
        mode=(card.get("safety") or {}).get("expected_mode", "-"),
        risk=(card.get("safety") or {}).get("risk_floor", "-"),
        pub="PUB" if card.get("publish_review") == "required" else "",
        recon=",".join(card.get("needs_recon") or []),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="repository root (default: found from this file)")
    parser.add_argument("--track", choices=("labs", "robots"))
    parser.add_argument("--family", help="card family, for example scpi, serial, python-object, gymnasium, mujoco")
    parser.add_argument("--wave", type=int)
    parser.add_argument("--limit", type=int, help="show at most this many cards")
    parser.add_argument("--pilot", action="store_true", help="only the cards of " + PILOT_FILE)
    parser.add_argument("--publishable", action="store_true",
                        help="leave out cards with publish_review required (copyleft, source-available, proprietary or unknown licence: the owner decides before publication)")
    parser.add_argument("--recon", action="store_true", help="list recon cards (untriaged, recon-first) instead of dispatchable ones")
    parser.add_argument("--stats", action="store_true", help="print how many cards are in each state and exit")
    parser.add_argument("--todo", action="store_true",
                        help="leave out cards whose work has begun (the driver directory, or with --recon the proposal file, exists)")
    parser.add_argument("--only", nargs="+", metavar="PACKAGE_ID",
                        help="only these cards (the share of one session when several run side by side)")
    parser.add_argument("--ids", action="store_true", help="print package ids only")
    parser.add_argument("--json", action="store_true", help="print the selected cards as JSON")
    parser.add_argument("--check-pilot", action="store_true", help="verify " + PILOT_FILE + "; exit 1 on a problem")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    cards = load_cards(root)
    if not cards:
        print(f"error: no task cards under {root}/MHS/registry/tasks", file=sys.stderr)
        return 2
    if args.check_pilot:
        return check_pilot(root, cards)

    if args.stats:
        by_kind: dict[str, int] = {}
        by_wave: dict[int, int] = {}
        for card in cards:
            by_kind[kind_of(card)] = by_kind.get(kind_of(card), 0) + 1
            if kind_of(card) == "dispatch":
                by_wave[card.get("wave", 9)] = by_wave.get(card.get("wave", 9), 0) + 1
        print(json.dumps({"cards": len(cards), "by_kind": dict(sorted(by_kind.items())),
                          "dispatchable_by_wave": dict(sorted(by_wave.items()))}, indent=1))
        return 0
    selected = select_cards(root, cards, wanted_kind="recon" if args.recon else "dispatch", pilot=args.pilot,
                            publishable=args.publishable, track=args.track, family=args.family, wave=args.wave, ids=args.only,
                            todo=args.todo)
    total = len(selected)
    if args.limit is not None:
        selected = selected[: args.limit]

    if args.json:
        print(json.dumps([{k: v for k, v in card.items() if k != "_path"} | {"card": card["_path"]} for card in selected],
                         indent=1, ensure_ascii=False))
    elif args.ids:
        for card in selected:
            print(card["package_id"])
    else:
        print("wave   rank  package_id                                     track  family        mode      rk  PUB needs_recon")
        for card in selected:
            print(row(card))
        print("PUB = publish_review required: the driver may be written, but the owner decides before it is published")
        print(f"-- {len(selected)} of {total} {'recon' if args.recon else 'dispatchable'} card(s); {len(cards)} cards in total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
