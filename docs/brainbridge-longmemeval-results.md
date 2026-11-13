# BrainBridge on LongMemEval

How well does BrainBridge remember without a dreamer? We measured it on [LongMemEval](https://github.com/xiaowu0162/LongMemEval), a public benchmark for long-term memory in chat assistants, and publish the code so anyone can rerun it.

- Code: [`benchmarks/brainbridge-longmemeval.py`](../benchmarks/brainbridge-longmemeval.py)
- Data: LongMemEval-S, `longmemeval_s_cleaned.json` (277 MB, Hugging Face `xiaowu0162/longmemeval-cleaned`). 500 questions, each hidden in about 490 turns of past conversation.

## Runs

| run | when | what changed | evidence in top 10 | one search finds it | answered |
|---|---|---|---|---|---|
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
