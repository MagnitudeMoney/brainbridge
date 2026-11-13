# BrainBridge on LongMemEval

How well does BrainBridge remember without a dreamer? We measured it on [LongMemEval](https://github.com/xiaowu0162/LongMemEval), a public benchmark for long-term memory in chat assistants, and publish the code so anyone can rerun it.

- Code: [`benchmarks/brainbridge-longmemeval.py`](../benchmarks/brainbridge-longmemeval.py)
- Data: LongMemEval-S, `longmemeval_s_cleaned.json` (277 MB, Hugging Face `xiaowu0162/longmemeval-cleaned`). 500 questions, each hidden in about 490 turns of past conversation.

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
- One of our runs scored 93.6 at @10 instead of 93.8: a single question changed. We haven't found why yet.

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
