# TallyTelemetry: privacy note

Version of 2026-11-12. Applies to BrainBridge v0.1 and later.

## The short version

TallyTelemetry is **off** unless you turn it on. When it is on, BrainBridge counts what happens, for example "an entry was saved". It **never** records what was said. Each count is written to a file on your own machine first, so you can read exactly what leaves. When it's off, nothing is recorded and nothing is sent.

## Who can turn it on

Only a person at a terminal can turn it on. `brainbridge telemetry on` counts and sends; `brainbridge telemetry local` counts on your machine only and never sends. Each shows what would be recorded and asks you to type `yes`. If you said yes before events could be sent, nothing is sent until you say yes again. An AI agent cannot turn it on, because its shell has no terminal to answer at. `brainbridge telemetry off` turns it off at any time.

## What one event contains, and nothing more

| Field | Example | What it is |
|---|---|---|
| `event` | `saved` | One of: saved, recalled, wake, mindmeld, transport, padlock_signed, report |
| `day` | `2026-11-11` | The date, with no time of day |
| `install` | `3f9a…` | A random id **replaced every month**, so one month's events can't be linked to the next |
| `version` | `0.1` | The BrainBridge version |
| `os` | `darwin` | The operating system family only |
| `kind` | `decision` | For a saved entry: which of the six kinds |
| `client` | `codex` | The app the agent ran in, if known |
| `model` | `claude-opus-5-5` | The model the agent **reports itself** to be: a hint, not proof |

**Never included:** entry text, titles, hooks, sources, names, handles, file paths, account details, or anything you or your agent wrote.

## Where it goes

- **On your machine:** events are kept in `~/.cache/brainbridge/telemetry.jsonl`, one line each. `brainbridge telemetry show` prints the setting, where events go and the last ten. You can delete the file at any time.
- **Sent:** only while telemetry is on. Events go to the collector at `https://www.magnitude.money/api/brainbridge/tally`, run by Magnitude Inc., in batches of 20 or hourly. A failed send waits for next time. Only events recorded after your yes are sent. To keep everything on your machine, use `brainbridge telemetry local`: the choice is saved and holds in every terminal, app and scheduled job.

## What the collector keeps

- **No stored IP address.** The server sees it to answer, holds it in memory for up to a minute to limit abuse, and our hosting provider's routine request logs may hold it briefly. It is never saved with your events. Request headers aren't stored either.
- **Events are kept for 13 months**, then deleted.
- **Deletion:** your install id changes every month and isn't tied to you. To delete this month's events, send the id shown by `brainbridge telemetry show` to privacy@magnitude.money. Ids from earlier months live only in your local log; you can send those too. To stop contributing, turn telemetry off and delete the local file.
- **No re-identification:** we don't try to work out who sent an event, and we won't.
- **Public counts:** the totals are published at `https://www.magnitude.money/api/brainbridge/tally/counts`. Anyone sees what we see: totals by event, model and client, installs per month, and daily totals. No install ids are published.

## What you get back

After opting in, `brainbridge report` shows you your own agents' decision-making as eight funnel tiles. It reads only your local log. Running it is counted as a `report` event, and nothing else about it is sent. With `brainbridge telemetry local` you get the whole report without sending anything. If you don't opt in at all, you lose nothing else: BrainBridge works the same.

## Questions

Write to privacy@magnitude.money, or ask in public at [github.com/MagnitudeMoney/brainbridge/issues](https://github.com/MagnitudeMoney/brainbridge/issues).

## Why it exists

To see whether BrainBridge helps: how often memories are saved and recalled, and which agents and models use it. PrimeDirective rule 3, "Share only with consent", sets its shape: it's off until a person agrees, it records counts only, and everything is visible before anything leaves.
