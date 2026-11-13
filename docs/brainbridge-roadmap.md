# BrainBridge roadmap

What's done, with its evidence, and what's next, in the order it can land. A status without evidence is a claim, so every "done" row names its pull request or measurement. Questions and suggestions are welcome as issues.

**The rule every item keeps:** the append-only log of JSON lines is the only truth. Anything built for speed (caches, indexes, segments, embeddings, a hosted database) is derived from the log, can be deleted, and rebuilds from it with nothing lost. Signatures, sources and history live in the log and nowhere else.

Results and measurements: [docs/brainbridge-longmemeval-results.md](brainbridge-longmemeval-results.md). What changed in each release: the Changelog on [brainbridge.sh](https://brainbridge.sh/#changelog).

---

## Done

| Version | What | Evidence |
|---|---|---|
| v0.1 | Released at 11:11 am PST on 2026-11-11: the spec, the CLI and the MCP server, under Apache 2.0 | This repository; brainbridge.sh |
| v0.1 | LongMemEval run 1, the baseline: evidence in the top 10 for 93.8% of questions, and 38 of 50 answered correctly | #2 |
| v0.1 | Recall ranks partial matches. Run 2: one search went from 18.7% to 78.1% | #3 |
| v0.1 | Agents save preferences in searchable words. Run 3: preference answers went from 20 to 29 of 30 | #5 |
| v0.1.1 | `brainbridge setup`, and `curl -fsSL https://brainbridge.sh/install \| sh`, pinned to a verified commit | #7 |
| v0.1.2 | A recall index beside the log: SQLite FTS5 trigram, each entry's current state, and PadLock marks checked once. It gives the same answers as the scan (640 queries on 40 brains, 0 differences). Recall goes from 1.33 s to 88 ms at 100,000 entries | #9, #10 |
| v0.1.3 | Session start reads the index: wake on 300 signed entries went from 1.95 s to 3 ms, with byte-identical output. Fix: any change to the log rebuilds the index, so a cached "signed" can't outlive an edit | #11 |

## Next

Ordered by what each one unblocks.

### 1. Encryption of private entries (PadLock), v0.2
Today a private entry is hidden by BrainBridge's own rules: only its owner and the people it names see it through the tool. On disk, though, it's plain text in the log, so anyone with access to the folder or repository can read it. This closes that gap.
- **How:** each owner gets a second key, for encryption, beside the Ed25519 signing key they already have. Private and `between` entries are encrypted in the [age](https://age-encryption.org) format: X25519 to open, ChaCha20-Poly1305 to encrypt. That's the design in spec v0.1.
- **Proposed:** the fields that make the log work (id, date, kind, owner, signature) stay readable, so the index and `verify` keep working. Only the text, title and hook are locked. Settled in spec v0.2.
- **Lossless:** an encrypted entry decrypts back to exactly what was saved. A test proves it for every entry kind.
- **Done means:**
  - A private entry on disk shows no readable text.
  - Its owner and the people it names read it as before.
  - `brainbridge verify` still checks every signature.
  - Spec v0.2, with a changelog entry.

### 2. LongMemEval-M, run 4
The benchmark's larger set: the same 500 questions, with about 10 times the history each. The harness already streams it one question at a time.
- **Done means:** a retrieval table for all 470 answerable questions, published beside run 1's.

### 3. Counting across sessions
At 38.5% in run 1, this is the weakest kind of answer. These questions need every piece, and recall often returns only some of them.
- **Try, in this order:**
  - hand the model more entries (50 instead of 30);
  - have the agent save running counts and totals as it works, as it now does for preferences;
  - only then, a consolidation pass.
- **Done means:** a run on the 133 multi-session questions, before and after.

### 4. One full answer run, every type
Run 3 reran only the preference questions. A 50-question run across all six types, with preferences on, shows whether saving them helps or hurts elsewhere.

### 5. Time segments, a format change
Split each brain's log into monthly files.
- Old months never change, so each gets its own index and checksum once.
- Signatures still verify file by file.
- **Lossless:** joining the segments gives the original log back, byte for byte.

### 6. Embeddings, an optional second index
The fix for paraphrase misses, where a question uses different words from the memory. Derived from the log, rebuildable and off by default. It brings a model dependency, so it's a choice, never a requirement.
- **Done means:** a LongMemEval run with it on and off, published either way.

### 7. Hosted at scale
A database with full-text indexes, for organizations that run many brains.
- **Rule:** every brain exports back to identical JSONL, checked by a conformance test.
- **Boundary:** BrainBridge never depends on a hosted service. Hosting is a convenience, never a requirement.

## Alongside

| Item | Waits on |
|---|---|
| The opt-in usage counts (TallyTelemetry) go live, with the privacy review's fixes, a way to delete one install's events on request, and a public label shown only once 5 installs have used it | The collector's database changes |
| Live tests inside Codex, Gemini CLI, Cursor and ChatGPT, beyond the protocol tests that pass today | Accounts with each |
| BrainBridge exports to the format the W3C AI agent memory work converges on, and imports back with nothing lost | That format settling |
