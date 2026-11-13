#!/usr/bin/env python3
"""How fast is BrainBridge's recall as a brain grows?

Fills a throwaway brain with N entries of realistic text and times recall()
at each size: a one-word query, a three-word query, and a whole question. No
model, no network, no real brain touched.

  benchmarks/brainbridge-recall-scale.py [--sizes 1000,10000,100000] [--repeat 5] [--scan-max 100000]

Since run 5 recall answers from an index beside the log (index_recall), so
this times both: the scan that reads the whole brain (recall_scan), and the
index: its one-time build, a recall once it is built, and the cost of
picking up one appended entry. The index is checked against the scan on
every query it times.
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
os.environ["BRAINBRIDGE_INDEX"] = str(TMP / "index")
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


def ms(fn, repeat: int) -> float:
    times = []
    for _ in range(repeat):
        t = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t) * 1000)
    return statistics.median(times)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sizes", default="1000,10000,100000")
    p.add_argument("--repeat", type=int, default=5)
    p.add_argument("--scan-max", type=int, default=100000, help="skip the scan above this size")
    a = p.parse_args()
    rng = random.Random(11)
    q = QUERIES["a question"]
    print(f"  {'entries':>9}  {'log MB':>7}  {'scan ms':>8}  {'build s':>8}  {'index MB':>8}  "
          f"{'recall ms':>9}  {'append+recall ms':>16}  {'wake scan ms':>12}  {'wake ms':>8}  same")
    for n in (int(x) for x in a.sizes.split(",")):
        owner = f"scale.n{n}"
        fill(owner, n, rng)
        mb = bb.store_file(owner).stat().st_size / 1e6
        scan = ms(lambda: bb.recall_scan(owner, owner, q), a.repeat) if n <= a.scan_max else float("nan")
        t = time.perf_counter()
        bb.index_refresh(owner).close()
        build = time.perf_counter() - t
        imb = sum(f.stat().st_size for f in (TMP / "index").glob(f"{owner}-*")) / 1e6
        warm = statistics.median(ms(lambda: bb.index_recall(owner, owner, x), a.repeat) for x in QUERIES.values())

        def append_then_recall():
            with bb.store_file(owner).open("a") as f:
                f.write(json.dumps(bb.make_entry(owner, "fact", "partner bank pricing appended", "t", records=[])) + "\n")
            bb.index_recall(owner, owner, q)
        app = ms(append_then_recall, a.repeat)
        bb._INDEX_OK = False
        wscan = ms(lambda: bb.brief(owner, owner), a.repeat) if n <= a.scan_max else float("nan")
        plain = bb.brief(owner, owner) if n <= a.scan_max else None
        bb._INDEX_OK = None
        widx = ms(lambda: bb.brief(owner, owner), a.repeat)
        same = None if n > a.scan_max else all(
            [e["id"] for e in bb.recall_scan(owner, owner, x)] == [e["id"] for e in bb.index_recall(owner, owner, x)]
            for x in QUERIES.values()) and plain == bb.brief(owner, owner)
        print(f"  {n:>9}  {mb:>7.1f}  {scan:>8.0f}  {build:>8.1f}  {imb:>8.1f}  {warm:>9.0f}  {app:>16.0f}  {wscan:>12.0f}  {widx:>8.0f}  "
              f"{'not checked' if same is None else 'yes' if same else 'NO'}", flush=True)
        bb.store_file(owner).unlink()


if __name__ == "__main__":
    main()
