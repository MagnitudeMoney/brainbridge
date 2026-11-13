# BrainBridge on LongMemEval

How well does BrainBridge remember without a dreamer? We measured it on [LongMemEval](https://github.com/xiaowu0162/LongMemEval), a public benchmark for long-term memory in chat assistants, and publish the code so anyone can rerun it.

- Code: [`benchmarks/brainbridge-longmemeval.py`](../benchmarks/brainbridge-longmemeval.py)
- Data: LongMemEval-S, `longmemeval_s_cleaned.json` (277 MB, Hugging Face `xiaowu0162/longmemeval-cleaned`). 500 questions, each hidden in about 490 turns of past conversation.

## Run 5: an index, same answers, faster

v0.1.2 answers recall from a SQLite index beside the log. The index uses FTS5 with trigrams, so a word matches inside other words exactly as before. It also holds each entry's current state and its PadLock mark, checked once. It reads only the lines added since last time, and rebuilds itself if the log is rewritten or the keys change. The log stays the only truth: delete the index and it comes back. Recall with `--history`, and any machine without FTS5, still scans.

**The same answers.**
- Retrieval on all 470 answerable LongMemEval-S questions gives run 2's table exactly.
- 640 queries on 40 LongMemEval brains: 0 differences between the index and the scan.
- Five self-test rows cover supersedes, retires, amendments, private entries, a scoped grant, appends after the build and a rewritten log.

**Faster**, with the same `brainbridge-recall-scale.py` on the same MacBook Air:

| entries | log | scan | index build (once) | index on disk | recall | append + recall | same as scan |
|---|---|---|---|---|---|---|---|
| 1,000 | 0.4 MB | 13 ms | 0.0 s | 1.8 MB | 2 ms | 3 ms | yes |
| 10,000 | 3.9 MB | 130 ms | 0.3 s | 19 MB | 9 ms | 9 ms | yes |
| 100,000 | 40 MB | 1.33 s | 4.2 s | 173 MB | 88 ms | 61 ms | yes |
| 1,000,000 | 397 MB | 16.7 s | 65 s | 1.7 GB | 1.09 s | 0.6 s | not checked |

- Peak memory at a million entries fell from 5.8 GB to 1.8 GB.
- Recall now costs about the number of entries it returns, not the size of the brain. These test brains are dense: their common words appear in about a third of all entries, so a real brain with sparser matches is faster.
- The cost is disk. A trigram index is about four times the log.

## v0.1.3: wake from the index, and a fix

**Wake reads the index.** Session start (`wake`, `open`, the MCP server's `brain_open`) now reads each entry's current state and PadLock mark from the index, instead of reading the whole log and re-checking every signature. The output is byte for byte the same; a self-test compares it with and without the index, including signed and INVALID entries.

| brain | wake before | wake now | recall before | recall now |
|---|---|---|---|---|
| 300 signed entries | 1.95 s | 3 ms | 1.92 s | 2 ms |
| 100,000 unsigned entries | 1.27 s | 1.03 s | 1.37 s | 93 ms |

On a signed brain, the old wake started `ssh-keygen` once for every entry, every session. Unsigned, wake still prints a line for every long-term entry, so it stays near the size of the brain.

**The fix.** In v0.1.2 the index checked only the end of the log for changes. If an entry was edited in place, even to the same length, recall could keep showing a stale "signed" for it. v0.1.3 hashes everything the index has read (SHA-256, about 0.14 s for a 400 MB brain) on every refresh, and rebuilds the index on any difference. A self-test edits an entry in place to prove it's caught. `brainbridge verify` was never affected: it checks every signature from the log.

## Speed before the index: recall as a brain grows

Measured 2026-11-12 on a MacBook Air (Apple M-series, 16 GB) with `benchmarks/brainbridge-recall-scale.py`. A throwaway brain is filled with N entries of 8 to 30 words each, then `recall()` is timed for three queries: one word, three words and a whole question. The table shows the median.

| entries | file | one word | three words | a question | peak memory |
|---|---|---|---|---|---|
| 1,000 | 0.4 MB | 11 ms | 12 ms | 12 ms | |
| 10,000 | 3.9 MB | 120 ms | 124 ms | 125 ms | |
| 100,000 | 40 MB | 1.27 s | 1.27 s | 1.30 s | |
| 1,000,000 | 397 MB | 16.7 s | 17.3 s | 16.3 s | 5.8 GB |

- Time grows in a straight line with the number of entries, and hardly at all with the length of the query.
- Recall reads and parses the whole brain on every call. That's fine to tens of thousands of entries. At a million it's too slow, and it needs nearly 6 GB of memory.
- The answer is an index, so that a search reads only the entries that can match. Run 5 adds it.

## Runs

| run | when | what changed | evidence in top 10 | one search finds it | answered |
|---|---|---|---|---|---|
| 6 | Nov 13, 2026 | Wake reads the index; the index notices in-place edits (v0.1.3) | 93.8% (unchanged) | 78.1% (unchanged) | unchanged |
| 5 | Nov 12, 2026 | Recall answers from an index beside the log (v0.1.2) | 93.8% (unchanged) | 78.1% (unchanged) | unchanged |
| 3 | Nov 12, 2026, 5:41 pm PST | The agent saves preferences in searchable words; they load every session | 30 preference questions only | — | preferences **96.7%** (was 66.7%) |
| 2 | Nov 12, 2026, 5:01 pm PST | `recall` ranks partial matches; a name's random id no longer matches | 93.8% | **78.1%** | 76.0% (not rerun: unchanged by this) |
| 1 | Nov 12, 2026, 4:34 pm PST | Baseline: raw turns, word recall, no dreamer | 93.8% | 18.7% | 76.0% |

### Run 3: the agent saves preferences in plain words

BrainBridge now tells agents, through the MCP server and the AGENTS.md block, to do this: "When the user says what they like or how they want things, save a preference in the words a later search would use: the general kind as well as the specific one."

Preferences are long-term, so they load in every session's index, whatever is searched. `--agent-prefs` simulates an agent that follows the guidance. A model reads each session's user turns and saves the preferences that session states. It works session by session and never across sessions, so nothing is reorganized later. For cost, the calls are batched, one per question, and cached with `--cache`.

On the same 30 preference questions, with the same model and judge:

| | answered correctly |
|---|---|
| Before: recall alone (runs 1 and 2) | 20 of 30 (66.7%) |
| After: preferences saved as the agent works | **29 of 30 (96.7%)** |

- 9 questions went from wrong to right, and none from right to wrong.
- On average, the agent saved 77 preferences per question.
- For every question, a preference from the session that holds the answer was among those loaded.
- Recall's own ranking is unchanged, at 53.3% @10. The gain comes from the wake, not from search.
- Caveats: 30 questions. The judge is the same model family that wrote the preferences. The other five question types were not rerun with preferences.

Reproduce with `retrieval` and then `qa`, each with `--type single-session-preference --agent-prefs --cache prefs.json`.

### Run 2: recall ranks partial matches

Until run 2, `recall` returned only entries holding every word of the query, so one search with a whole question rarely found anything. Now entries holding every word come first, as before, followed by the best partial matches: entries holding at least half the words, most words first, at most 20. `--strict` keeps the old behaviour.

Run 2 also fixed a small bug. Recall searched each entry's name, and a name ends in six random hex characters of the entry's id. A query word like "cafe" or "bed" could therefore match by chance. That is why run 1 scored 93.6 instead of 93.8 at @10 once. Two consecutive runs of run 2 gave identical tables.

| question type | n | @1 | @10 | all@10 | one search, run 1 | one search, run 2 |
|---|---|---|---|---|---|---|
| single-session-user | 64 | 73.4 | 93.8 | 93.8 | 35.9 | 90.6 |
| single-session-assistant | 56 | 96.4 | 100.0 | 100.0 | 0.0 | 80.4 |
| single-session-preference | 30 | 16.7 | 53.3 | 53.3 | 3.3 | 23.3 |
| multi-session | 121 | 79.3 | 97.5 | 61.2 | 12.4 | 77.7 |
| knowledge-update | 72 | 94.4 | 100.0 | 95.8 | 51.4 | 98.6 |
| temporal-reasoning | 127 | 71.7 | 93.7 | 72.4 | 9.4 | 72.4 |
| **all** | **470** | **76.8** | **93.8** | **78.1** | **18.7** | **78.1** |

The answer score is not rerun, because the benchmark's answers already used the ranking by words matched. Preferences are still the gap, at 53.3% @10. Run 1 follows, as published.

## Run 1 · Nov 12, 2026, 4:34 pm PST

## Setup, no dreamer

- Each question's chat turns are saved as BrainBridge entries, one per turn, with the role, session and date in the source.
- Entries stay as they were saved. Nothing summarizes or reorganizes them between sessions.
- Everything goes into a throwaway store, so no real brain is touched.
- Retrieval is BrainBridge's own `recall()`, called once for each content word of the question. Entries are ranked by how many words they matched, newer first on ties.
- No embeddings.

## Retrieval: all 470 answerable questions, no model

Does an entry from a session holding the answer appear in the top k?

| question type | n | @1 | @5 | @10 | @30 | all@10 | one recall | chance@10 |
|---|---|---|---|---|---|---|---|---|
| single-session-user | 64 | 73.4 | 92.2 | 93.8 | 96.9 | 93.8 | 35.9 | 21.9 |
| single-session-assistant | 56 | 96.4 | 98.2 | 100.0 | 100.0 | 100.0 | 0.0 | 14.3 |
| single-session-preference | 30 | 16.7 | 50.0 | 53.3 | 83.3 | 53.3 | 3.3 | 13.3 |
| multi-session | 121 | 79.3 | 91.7 | 97.5 | 99.2 | 61.2 | 12.4 | 49.6 |
| knowledge-update | 72 | 94.4 | 98.6 | 100.0 | 100.0 | 95.8 | 51.4 | 45.8 |
| temporal-reasoning | 127 | 70.9 | 89.0 | 93.7 | 97.6 | 70.1 | 9.4 | 40.2 |
| **all** | **470** | **76.6** | **90.2** | **93.8** | **97.7** | **77.4** | **18.7** | **36.2** |

- **@k**: any evidence session is among the top k entries.
- **all@10**: every evidence session is in the top 10.
- **one recall**: a single `recall` with every content word, the way the CLI reads a query today.
- **chance@10**: ten random turns.
- The 30 abstention questions are left out, because they have no evidence to find.
- 42 turns were refused by BrainBridge's secret guard, and count as not saved.
- One of our runs scored 93.6 at @10 instead of 93.8: a single question changed. Found and fixed in run 2.

## Answers: 50 questions, stratified sample (seed 11)

A model reads the top 30 recalled entries and answers. A judge then grades each answer with LongMemEval's yes/no judge prompts for its question type. Model and judge are both `claude-sonnet-5-5`; the paper's judge is GPT-4o, so this score is comparable with the paper's but not identical.

| question type | n | correct |
|---|---|---|
| single-session-user | 7 | 100.0 |
| single-session-assistant | 6 | 100.0 |
| single-session-preference | 3 | 66.7 |
| multi-session | 13 | 38.5 |
| knowledge-update | 8 | 100.0 |
| temporal-reasoning | 13 | 76.9 |
| **all** | **50** | **76.0** |

All 4 abstention questions in the sample were answered correctly ("the memories don't say").

## What it says

- **Word-by-word recall finds the evidence:** 93.8% of questions have it in the top 10 entries, against 36.2% by chance.
- **Counting across sessions is the weak spot, at 38.5%.** "How many…" and "how much in total…" need every piece, and only 61.2% of multi-session questions have every piece in the top 10. A model handed part of the evidence correctly says the count is partial.
- **Preferences come next,** at 53.3% found in the top 10. A request for a recommendation rarely uses the words someone used to say what they like. A dreamer that writes the preference down in plain words would close this gap, and so would embeddings.
- **A single all-words recall misses,** at 18.7%. Agents should issue several short recalls, and `recall` should rank partial matches instead of requiring every word.
- **Caveat:** LongMemEval's filler conversations are mostly unrelated chats, which helps keyword matching. The answer score is the number to quote. Fifty questions is a sample, so expect a few points either way.
