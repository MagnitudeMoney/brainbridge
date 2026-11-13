# BrainBridge

Memory any agent can keep and share: every entry says what was decided, who decided it, and the source.

*Great minds sync alike.*

BrainBridge gives each agent (or person) a brain: an append-only file of decisions, preferences, facts, people, open threads and lessons, kept in a git repository and pushed, so it outlives any one laptop, login or vendor. Brains can be opened by others only when their owner grants it, and every entry carries its source.

## Install

You need:

- `python3` (3.9 or later; standard library only)
- `git`
- `ssh-keygen` (OpenSSH 8.1 or later), for PadLock signatures

Then, in one line:

```sh
curl -fsSL https://brainbridge.sh/install | sh
```

It checks for python3 and git, clones a tagged release into `~/.brainbridge/code`, refuses if the release's commit isn't the one it names, and runs `brainbridge setup`. No sudo, nothing outside your home folder. To read it first:

```sh
curl -fsSL https://brainbridge.sh/install -o brainbridge-install && less brainbridge-install && sh brainbridge-install
```

Or by hand:

```sh
git clone https://github.com/MagnitudeMoney/brainbridge.git ~/.brainbridge/code
python3 ~/.brainbridge/code/brainbridge.py setup
```

`brainbridge setup` checks what you need, asks for your handle and saves it, puts `brainbridge` on your PATH, mints your PadLock key, saves and recalls a first memory, offers to connect the agent apps it finds (Claude Code, Codex, Gemini CLI, Cursor), and asks about TallyTelemetry, which stays off unless you say yes. Run it again any time: each step already done says so. `python3 brainbridge.py selftest` runs every check against a temp store.

## Quick start

If you ran `brainbridge setup`, your handle is saved and you can skip the export below. Otherwise pick one: lowercase words joined by dots, such as `agent.one`.

```sh
export BRAINBRIDGE_AS=agent.one

# init: creates the store on first use and mints your PadLock signing key
brainbridge init

# save: every entry needs a source
brainbridge save "Releases go out on Tuesdays" --kind decision --source "team review, 2026-11-11"

# recall: every word must match, in any order
brainbridge recall "releases tuesdays"

# wake: what is live, with anything due for review first
brainbridge wake

# connect: add the MCP server to another agent's CLI (codex, gemini, cursor or claude)
brainbridge connect codex           # shows what it would write
brainbridge connect codex --yes     # writes it, keeping everything else in the file
```

The store lives in `~/.brainbridge/store`, a git repository with a local origin beside it. To share brains between machines, point that origin at a private remote:

```sh
git -C ~/.brainbridge/store remote set-url origin git@github.com:you/your-brains.git
```

Or set `BRAINBRIDGE_STORE_REPO` to a clone of an existing store. Brains are personal data: keep them out of the repository that holds this code.

To share a brain, its owner grants another handle access, and sees exactly what will be exposed before anything is written:

```sh
brainbridge grant agent.two --scope read --source "pairing on the release" --yes
brainbridge --as agent.two open agent.one
```

`brainbridge --help` lists every command, including `mindmeld`, `beam`, `onboard`, `verify` and `doctor`.

## MCP setup

`brainbridge-mcp.py` serves the same brains to any MCP client over stdio. It needs no SDK.

Claude Code:

```sh
claude mcp add brainbridge --scope user -e BRAINBRIDGE_AS=agent.one -- python3 /path/to/brainbridge-mcp.py
```

Codex, Gemini CLI and Cursor: `brainbridge connect <client> --yes` writes the entry for you. For any other client, `brainbridge connect --print` prints a generic `mcpServers` snippet.

The server sends the PrimeDirective and your brain's index as its instructions on connect, and offers `brain_open`, `brain_recall`, `brain_save`, `brain_grant` and the rest as tools.

Identity on one machine is declared, not proven: grants stop accidents, not adversaries. PadLock signatures prove who wrote each entry.

## How recall stays fast

Recall answers from an index beside each brain (`~/.cache/brainbridge/index`, or `BRAINBRIDGE_INDEX`): SQLite FTS5 with trigrams, plus each entry's current state and PadLock mark. The log is the only truth. The index is never committed, reads only new lines, rebuilds itself when the log is rewritten, and can be deleted at any time. `BRAINBRIDGE_INDEX=off` turns it off, and recall scans the log as before. At 100,000 entries a recall takes 88 ms instead of 1.3 s ([results](docs/brainbridge-longmemeval-results.md)).

## Configuration

All optional. Each is an environment variable.

| Variable | Default | What it sets |
|---|---|---|
| `BRAINBRIDGE_AS` | none | Who this agent is |
| `BRAINBRIDGE_STORE_REPO` | `~/.brainbridge/store` | The brains' git repository |
| `BRAINBRIDGE_WORKTREE` | `~/.brainbridge/worktree` | The data worktree saves commit in |
| `BRAINBRIDGE_ROOT` | none | A handle that can open every brain |
| `BRAINBRIDGE_AUTOLOAD` | none | Handles whose shared entries load into every Claude Code session |
| `BRAINBRIDGE_MEMDIRS` | none | `handle=/path/to/project` pairs: the Claude Code project whose memory folder mirrors that brain |
| `BRAINBRIDGE_KEYS` | `~/.config/brainbridge/keys` | Where PadLock keys are kept |
| `BRAINBRIDGE_FEEDBACK_CMD` | none | A command that receives each feedback record as JSON |
| `BRAINBRIDGE_TELEMETRY_URL` | none | Where opt-in telemetry is sent; unset, nothing leaves the machine |

## Roadmap

What's done, with its evidence, and what's next: [docs/brainbridge-roadmap.md](docs/brainbridge-roadmap.md).

## Spec

The format is specified in [docs/brainbridge-spec-v0.1.md](docs/brainbridge-spec-v0.1.md).

## License

Code: Apache 2.0. Spec text: CC BY 4.0. No patent, no trademark.

The code is licensed under the Apache License 2.0 (see [LICENSE](LICENSE)). The specification text in `docs/` is licensed under Creative Commons Attribution 4.0 International.
