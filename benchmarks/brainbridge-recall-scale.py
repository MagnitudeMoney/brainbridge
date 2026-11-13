#!/usr/bin/env python3
"""How fast is BrainBridge's recall as a brain grows?

Fills a throwaway brain with N entries of realistic text and times recall()
at each size: a one-word query, a three-word query, and a whole question. No
model, no network, no real brain touched.

  benchmarks/brainbridge-recall-scale.py [--sizes 1000,10000,100000] [--repeat 5]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import statistics
import tempfile
import time
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="bb-scale-"))
os.environ["BRAINBRIDGE_WORKTREE"] = str(TMP / "wt")
os.environ["BRAINBRIDGE_STORE_REPO"] = str(TMP / "repo")
os.environ["BRAINBRIDGE_KEYS"] = str(TMP / "keys")
(TMP / "wt" / "docs" / "brainbridge").mkdir(parents=True)
spec = importlib.util.spec_from_file_location("brainbridge", Path(__file__).resolve().parent.parent / "brainbridge.py")
bb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bb)

WORDS = ("decided launch budget review partner bank payroll design copy deck invest save give enjoy need "
         "meeting customer pricing account agent memory model release spec draft signed source monday "
         "green blue team hire contract legal tax quarter plan goal coffee travel paycheck rent groceries "
         "school doctor insurance car house garden music book movie recipe running yoga weekend").split()
QUERIES = {"one word": "pricing", "three words": "partner bank pricing",
           "a question": "what did we decide about the partner bank pricing review"}


def fill(owner: str, n: int, rng: random.Random) -> None:
    rows = []
    for i in range(n):
        text = " ".join(rng.choice(WORDS) for _ in range(rng.randint(8, 30)))
        e = bb.make_entry(owner, rng.choice(("fact", "decision", "lesson")), text,
                          f"person.{i % 50}, 2026-{1 + i % 12:02d}-{1 + i % 28:02d}", records=[])
        rows.append(json.dumps(e))
    bb.store_file(owner).write_text("\n".join(rows) + "\n")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sizes", default="1000,10000,100000")
    p.add_argument("--repeat", type=int, default=5)
    a = p.parse_args()
    rng = random.Random(11)
    print(f"  {'entries':>9}  {'file MB':>8}  " + "  ".join(f"{q:>14}" for q in QUERIES) + "   (median ms per recall)")
    for n in (int(x) for x in a.sizes.split(",")):
        owner = f"scale.n{n}"
        fill(owner, n, rng)
        mb = bb.store_file(owner).stat().st_size / 1e6
        cells = []
        for q in QUERIES.values():
            times = []
            for _ in range(a.repeat):
                t = time.perf_counter()
                bb.recall(owner, owner, q)
                times.append((time.perf_counter() - t) * 1000)
            cells.append(f"{statistics.median(times):>14.0f}")
        print(f"  {n:>9}  {mb:>8.1f}  " + "  ".join(cells), flush=True)
        bb.store_file(owner).unlink()


if __name__ == "__main__":
    main()
