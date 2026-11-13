#!/usr/bin/env python3
"""BrainBridge on LongMemEval: how well does it remember, with no dreamer?

Two stages:

  retrieval  No model at all. Each question's ~490 chat turns are saved as
             BrainBridge entries (one per turn, the session and date in the
             source), in a throwaway store. Then BrainBridge's own recall()
             is asked for each content word of the question, and entries are
             ranked by how many words they matched. Scored with LongMemEval's
             evidence labels: did a top-k entry come from a session that holds
             the answer? Free, deterministic, all 500 questions.

  qa         The end-to-end score. A model sees the question and the top
             entries recall found, answers, and a judge grades it with
             LongMemEval's yes/no judge prompts. Needs model calls: runs
             through headless `claude -p`. The paper's judge is GPT-4o; ours
             is Claude, so the number is close to, not identical with, theirs.

What "no dreamer" means here: nothing summarises or reorganises memory
between sessions. Entries are the raw turns, kept as saved.

--agent-prefs (run 3) adds what BrainBridge asks an agent to do while it
works: when the user says what they like or how they want things, save a
preference in words a later search would use. A model reads each session's
user turns and writes those preferences, one session at a time, nothing
across sessions. Preferences are long-term, so they load in every session's
index (the wake), and the answer stage sees them all. Cost: one model call
per question (batched over its sessions); --cache keeps them for reruns.

Data: longmemeval_s_cleaned.json from huggingface.co/datasets/xiaowu0162/
longmemeval-cleaned (277 MB). Pass its path; it is never copied into a repo.

  benchmarks/brainbridge-longmemeval.py retrieval DATA.json [--sample 50] [--out results.json]
  benchmarks/brainbridge-longmemeval.py qa DATA.json --sample 50 [--model claude-sonnet-5-5]
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent      # brainbridge.py sits at the repo root

# A throwaway store, set before brainbridge is imported: nothing touches a real brain.
TMP = Path(tempfile.mkdtemp(prefix="bb-lme-"))
os.environ["BRAINBRIDGE_WORKTREE"] = str(TMP / "wt")
os.environ["BRAINBRIDGE_STORE_REPO"] = str(TMP / "repo")
os.environ["BRAINBRIDGE_KEYS"] = str(TMP / "keys")
(TMP / "wt" / "docs" / "brainbridge").mkdir(parents=True)

spec = importlib.util.spec_from_file_location("brainbridge", HERE / "brainbridge.py")
bb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bb)

STOP = set("""a an and are as at be been but by can could did do does for from had has
have how i if in into is it its me my of on or our so than that the their them then there
these they this to was we were what when where which who whom why will with would you your
about after again all also any before being between both during each few more most other
over same should some such through under until very while am just now only own too here
many much tell remember mentioned recommend recommended previous previously last ago
times time days day weeks week months month total current currently""".split())

QTYPES = ["single-session-user", "single-session-assistant", "single-session-preference",
          "multi-session", "knowledge-update", "temporal-reasoning"]


def owner_for(qid: str) -> str:
    return "lme.q" + re.sub(r"[^a-z0-9]", "", qid.lower())


AGENT_PREFS = False
CACHE: Path | None = None
MODEL = "claude-sonnet-5-5"

PREFS_PROMPT = """You are an AI assistant whose memory is BrainBridge. Below are the user's own turns from \
past conversations, session by session. For each session, write down every preference the user expressed \
about themselves: what they like or dislike, the tools, brands, places and styles they use or choose, their \
habits, and how they want answers. Write each one as its own short sentence in plain words a later search \
would use: name the general kind of thing as well as the specific one (for example "Prefers Sichuan food: \
likes spicy Chinese cooking"). Use only what that session says. If a session states no preference, skip it.

Reply with JSON only: a list of {{"session": "<session id>", "text": "<preference>"}}.

{sessions}"""


def agent_preferences(q: dict) -> list[dict]:
    """The preferences an agent following BrainBridge's guidance would have saved, session by session."""
    cache = json.loads(CACHE.read_text()) if CACHE and CACHE.exists() else {}
    if q["question_id"] in cache:
        return cache[q["question_id"]]
    parts = []
    for sid, date, session in zip(q["haystack_session_ids"], q["haystack_dates"], q["haystack_sessions"]):
        said = "\n".join("- " + t["content"][:1500].replace("\n", " ") for t in session if t["role"] == "user")
        if said:
            parts.append(f"## session {sid} ({date})\n{said}")
    raw = ask(PREFS_PROMPT.format(sessions="\n\n".join(parts)), MODEL)
    m = re.search(r"\[.*\]", raw, re.S)
    prefs = [p for p in (json.loads(m.group(0)) if m else []) if p.get("text") and p.get("session")]
    if CACHE:
        cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
        cache[q["question_id"]] = prefs
        CACHE.write_text(json.dumps(cache, indent=1))
    return prefs


def ingest(q: dict) -> tuple[str, int]:
    """Save every turn as an entry (and, with --agent-prefs, the agent's preferences).
    Returns the owner and how many turns were refused."""
    owner = owner_for(q["question_id"])
    refused, rows = 0, []
    if AGENT_PREFS:
        dates = dict(zip(q["haystack_session_ids"], q["haystack_dates"]))
        for p in agent_preferences(q):
            try:
                e = bb.make_entry(owner, "preference", p["text"],
                                  f"agent, from session {p['session']}, {dates.get(p['session'], '')}", records=[])
            except bb.BridgeError:
                continue
            e["_session"] = p["session"]
            rows.append(json.dumps(e))
    for sid, date, session in zip(q["haystack_session_ids"], q["haystack_dates"], q["haystack_sessions"]):
        for i, turn in enumerate(session):
            try:
                e = bb.make_entry(owner, "fact", turn["content"] or "(empty)",
                                  f"{turn['role']}, session {sid} turn {i}, {date}", records=[])
            except bb.BridgeError:          # e.g. text that looks like a credential
                refused += 1
                continue
            e["_session"] = sid
            rows.append(json.dumps(e))
    bb.store_file(owner).write_text("\n".join(rows) + "\n")
    return owner, refused


def words_of(question: str) -> list[str]:
    ws = re.findall(r"[a-z0-9][a-z0-9'\-]*", question.lower())
    return list(dict.fromkeys(w for w in ws if len(w) >= 3 and w not in STOP))


def retrieve(owner: str, question: str) -> list[dict]:
    """BrainBridge's recall, once per content word, ranked by words matched; newer first on ties."""
    score: dict[str, int] = collections.Counter()
    order: dict[str, int] = {}
    by_id: dict[str, dict] = {}
    for w in words_of(question):
        for e in bb.recall(owner, owner, w):
            score[e["id"]] += 1
            by_id[e["id"]] = e
    for n, e in enumerate(bb.live(bb.load(owner))):
        order[e["id"]] = n
    return [by_id[i] for i in sorted(score, key=lambda i: (-score[i], -order.get(i, 0)))]


def stream(path: Path):
    """The questions of a top-level JSON array, one at a time. LongMemEval-M is
    2.7 GB; loading it whole needs well over 10 GB of memory, one question at a
    time needs a few MB. Standard library only."""
    dec = json.JSONDecoder()
    buf, pos, started = "", 0, False
    with path.open(encoding="utf-8") as f:
        while True:
            while True:                                   # skip whitespace, '[' and ','
                while pos < len(buf) and buf[pos] in " \t\r\n,":
                    pos += 1
                if not started and pos < len(buf) and buf[pos] == "[":
                    started, pos = True, pos + 1
                    continue
                break
            if pos < len(buf) and buf[pos] == "]":
                return
            try:
                obj, end = dec.raw_decode(buf, pos)
            except json.JSONDecodeError:
                chunk = f.read(8 << 20)
                if not chunk:
                    if buf[pos:].strip(" \t\r\n]"):
                        raise
                    return
                buf, pos = buf[pos:] + chunk, 0
                continue
            yield obj
            buf, pos = buf[end:], 0


class Questions:
    """The chosen questions, streamed from the file again when iterated: a list's
    len() and for-loop without holding them all in memory."""
    def __init__(self, path: Path, ids: list[str]):
        self.path, self.ids = path, set(ids)
        self.n = len(ids)

    def __len__(self) -> int:
        return self.n

    def __iter__(self):
        for q in stream(self.path):
            if q["question_id"] in self.ids:
                yield q


def choose(path: Path, n: int | None, qtype: str | None) -> Questions:
    """The same stratified sample as sample(), decided from ids and types alone."""
    heads = [{"question_id": q["question_id"], "question_type": q["question_type"]} for q in stream(path)
             if not qtype or q["question_type"] == qtype]
    return Questions(path, [q["question_id"] for q in sample(heads, n)])


def sample(data: list[dict], n: int | None, seed: int = 11) -> list[dict]:
    """Stratified by question type, in proportion, with a fixed seed."""
    if not n or n >= len(data):
        return data
    rng = random.Random(seed)
    by = collections.defaultdict(list)
    for q in data:
        by[q["question_type"]].append(q)
    out = []
    for t, qs in sorted(by.items()):
        k = max(1, round(n * len(qs) / len(data)))
        out += rng.sample(qs, k)
    return out[:n] if len(out) > n else out


def cmd_retrieval(data: list[dict], out: Path | None) -> None:
    ks = (1, 5, 10, 30)
    rows = []
    for j, q in enumerate(data, 1):
        if q["question_id"].endswith("_abs"):
            continue                            # unanswerable: no evidence to find
        owner, refused = ingest(q)
        hits = retrieve(owner, q["question"])
        gold = set(q["answer_session_ids"])
        sess = [e["_session"] for e in hits]
        strict = bb.recall(owner, owner, " ".join(words_of(q["question"])))
        every = [json.loads(l)["_session"] for l in bb.store_file(owner).read_text().splitlines() if l]
        rows.append({
            "id": q["question_id"], "type": q["question_type"], "turns": sum(map(len, q["haystack_sessions"])),
            "refused": refused, "found": len(hits),
            **{f"any@{k}": bool(gold & set(sess[:k])) for k in ks},
            **{f"all@{k}": gold <= set(sess[:k]) for k in ks},
            "strict_hit": bool(gold & {e["_session"] for e in strict}), "strict_n": len(strict),
            "chance@10": bool(gold & set(random.Random(q["question_id"]).sample(every, min(10, len(every))))),
            "woke": bool(gold & {json.loads(l)["_session"] for l in bb.store_file(owner).read_text().splitlines()
                                 if l and json.loads(l)["kind"] == "preference"}),
        })
        bb.store_file(owner).unlink()
        if j % 50 == 0:
            print(f"  {j}/{len(data)}", file=sys.stderr)
    report(rows, ks)
    if out:
        out.write_text(json.dumps(rows, indent=1))


def report(rows: list[dict], ks) -> None:
    def line(label, rs):
        cells = "  ".join(f"{100 * sum(r[f'any@{k}'] for r in rs) / len(rs):5.1f}" for k in ks)
        alls = f"{100 * sum(r['all@10'] for r in rs) / len(rs):5.1f}"
        strict = f"{100 * sum(r['strict_hit'] for r in rs) / len(rs):5.1f}"
        chance = f"{100 * sum(r['chance@10'] for r in rs) / len(rs):5.1f}"
        print(f"  {label:<27}{len(rs):>4}  {cells}   {alls}   {strict}   {chance}")
    print(f"\n  evidence session found in the top k entries (%), BrainBridge recall, no dreamer, no model")
    print(f"  {'question type':<27}{'n':>4}  " + "  ".join(f"{'@' + str(k):>5}" for k in ks) + "   all@10  one-recall  chance@10")
    for t in QTYPES:
        rs = [r for r in rows if r["type"] == t]
        if rs:
            line(t, rs)
    line("ALL", rows)
    print("\n  @k: any evidence session among the top k entries. all@10: every evidence session in the top 10.")
    print("  one-recall: a single recall with every content word (how BrainBridge's recall reads a query today).")
    print("  chance@10: ten turns picked at random, the floor any memory should beat.")
    print(f"  turns refused as secrets: {sum(r['refused'] for r in rows)}")
    if AGENT_PREFS:
        print(f"  wake: a saved preference from an evidence session loads every session for "
              f"{100 * sum(r['woke'] for r in rows) / len(rows):.1f}% of questions")


# ── qa: answer and judge, through headless claude ───────────────────────────

JUDGE = {
    "default": "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response is equivalent to the correct answer or contains all the intermediate steps to get the correct answer, you should also answer yes. If the response only contains a subset of the information required by the answer, answer no.\n\nQuestion: {q}\n\nCorrect Answer: {a}\n\nModel Response: {r}\n\nIs the model response correct? Answer yes or no only.",
    "temporal-reasoning": "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response is equivalent to the correct answer or contains all the intermediate steps to get the correct answer, you should also answer yes. If the response only contains a subset of the information required by the answer, answer no. In addition, do not penalize off-by-one errors for the number of days. If the question asks for the number of days/weeks/months, etc., and the model makes off-by-one errors (e.g., predicting 19 days when the answer is 18), the model's response is still correct.\n\nQuestion: {q}\n\nCorrect Answer: {a}\n\nModel Response: {r}\n\nIs the model response correct? Answer yes or no only.",
    "knowledge-update": "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response contains some previous information along with an updated answer, the response should be considered as correct as long as the updated answer is the required answer.\n\nQuestion: {q}\n\nCorrect Answer: {a}\n\nModel Response: {r}\n\nIs the model response correct? Answer yes or no only.",
    "single-session-preference": "I will give you a question, a rubric for desired personalized response, and a response from a model. Please answer yes if the response satisfies the desired response. Otherwise, answer no. The model does not need to reflect all the points in the rubric. The response is correct as long as it recalls and utilizes the user's personal information correctly.\n\nQuestion: {q}\n\nRubric: {a}\n\nModel Response: {r}\n\nIs the model response correct? Answer yes or no only.",
    "abstention": "I will give you an unanswerable question, an explanation, and a response from a model. Please answer yes if the model correctly identifies the question as unanswerable. The model could say that the information is incomplete, or some other information is given but the asked information is not.\n\nQuestion: {q}\n\nExplanation: {a}\n\nModel Response: {r}\n\nDoes the model correctly identify the question as unanswerable? Answer yes or no only.",
}


def ask(prompt: str, model: str) -> str:
    """One headless call: no tools, no hooks, no settings, no CLAUDE.md (cwd is the temp store)."""
    r = subprocess.run(["claude", "-p", "--setting-sources", "", "--strict-mcp-config", "--tools", "",
                        "--no-session-persistence", "--model", model, "--output-format", "json",
                        "--system-prompt", "You answer from the memories you are given."],
                       input=prompt, capture_output=True, text=True, cwd=TMP, timeout=600)
    d = json.loads(r.stdout)
    if d.get("is_error") or d.get("terminal_reason") == "api_error":
        raise SystemExit(f"model call failed: {d.get('result')}")
    return d["result"].strip()


def cmd_qa(data: list[dict], model: str, top: int, out: Path | None) -> None:
    rows = []
    for q in data:
        owner, _ = ingest(q)
        hits = retrieve(owner, q["question"])[:top]
        hits.sort(key=lambda e: e["source"].rsplit(", ", 1)[-1])     # oldest first, by session date
        mem = "\n\n".join(f"[{e['source']}]\n{e['text'][:2000]}" for e in hits)
        woke = [e for e in bb.live(bb.load(owner)) if e["kind"] == "preference"]
        if woke:                    # long-term: in every session's index, whatever was searched
            mem = ("Preferences (loaded every session):\n" + "\n".join(f"- {e['text']} [{e['source']}]" for e in woke)
                   + "\n\nRecalled for this question:\n\n" + mem)
        answer = ask(f"Memories recalled from BrainBridge:\n\n{mem}\n\nToday is {q['question_date']}.\n"
                     f"Question: {q['question']}\nAnswer briefly. If the memories don't say, say so.", model)
        kind = "abstention" if q["question_id"].endswith("_abs") else q["question_type"]
        grade = ask(JUDGE.get(kind, JUDGE["default"]).format(q=q["question"], a=q["answer"], r=answer), model)
        rows.append({"id": q["question_id"], "type": q["question_type"], "abstention": kind == "abstention",
                     "answer": answer, "gold": q["answer"], "correct": grade.lower().startswith("yes")})
        bb.store_file(owner).unlink()
        print(f"  {len(rows)}/{len(data)} {q['question_type']:<26} {'yes' if rows[-1]['correct'] else 'no '}",
              file=sys.stderr)
        if out:
            out.write_text(json.dumps(rows, indent=1))
    print(f"\n  answered correctly, judged by {model} (%)")
    for t in QTYPES + ["ALL"]:
        rs = rows if t == "ALL" else [r for r in rows if r["type"] == t]
        if rs:
            print(f"  {t:<27}{len(rs):>4}  {100 * sum(r['correct'] for r in rs) / len(rs):5.1f}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("stage", choices=["retrieval", "qa"])
    p.add_argument("data", type=Path)
    p.add_argument("--sample", type=int)
    p.add_argument("--model", default="claude-sonnet-5-5")
    p.add_argument("--top", type=int, default=30, help="entries handed to the model in qa")
    p.add_argument("--out", type=Path)
    p.add_argument("--type", choices=QTYPES, help="only questions of this type")
    p.add_argument("--agent-prefs", action="store_true", help="the agent saves preferences as it works (run 3)")
    p.add_argument("--cache", type=Path, help="keep the agent's preferences here, for reruns")
    a = p.parse_args()
    global AGENT_PREFS, CACHE, MODEL
    AGENT_PREFS, CACHE, MODEL = a.agent_prefs, a.cache, a.model
    data = choose(a.data, a.sample, a.type)
    if a.stage == "retrieval":
        cmd_retrieval(data, a.out)
    else:
        cmd_qa(data, a.model, a.top, a.out)


if __name__ == "__main__":
    main()
