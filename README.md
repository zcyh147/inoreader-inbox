# Inoreader Inbox

Pull unread or stream-specific articles from Inoreader into a local Markdown inbox.

Inoreader Inbox treats Inoreader as the feed/subscription normalizer. It preserves article titles, summaries, authors, sources, publish times, and original URLs so an agent can decide what to read, summarize, search, or hand off to another skill next.

## LLM Quickstart

Ask your coding agent to use this skill:

```text
Use $inoreader-inbox to pull my unread Inoreader articles into a local Markdown inbox.
```

The generated inbox is written to:

```text
out/inbox.md
```

## Human Quickstart

1. Check or create the local Python environment:

```bash
python scripts/run.py --check
```

2. Log in to Inoreader:

```bash
python scripts/run.py rss_ai_inbox.py login
```

The login wizard will ask you to create an Inoreader API application and paste its App ID and App Key. Use these values when creating the app:

```text
Name: Inoreader Inbox
URL: https://127.0.0.1:8765
Platform: Web/Desktop/Other, whichever is available
Redirect URI: https://127.0.0.1:8765/callback
OAuth Scope: Readable and writable
```

After approving the OAuth page, paste the full redirected URL immediately. The `code` in that URL is one-time use and short-lived.

3. Pull unread articles:

```bash
python scripts/run.py rss_ai_inbox.py run --unread-only --limit 50
```

## CLI

Check the current login:

```bash
python scripts/run.py rss_ai_inbox.py status
```

Pull unread articles:

```bash
python scripts/run.py rss_ai_inbox.py run --unread-only --limit 50
```

Pull a specific stream:

```bash
python scripts/run.py rss_ai_inbox.py run \
  --stream "user/-/state/com.google/reading-list" \
  --unread-only \
  --limit 50
```

Run without an Inoreader account using sample articles:

```bash
python scripts/run.py rss_ai_inbox.py run --sample
```

Use another token file:

```bash
python scripts/run.py rss_ai_inbox.py status --token-file config/other-token.json
```

## Skill Layout

```text
SKILL.md
scripts/
  run.py
  setup_environment.py
  rss_ai_inbox.py
requirements.txt
```

Local runtime files are intentionally ignored by git:

```text
.venv/
agents/
config/
out/
```

`config/token.json` contains OAuth credentials and must never be committed.

## What This Does Not Do

This skill does not:

- Fetch full article pages.
- Classify articles.
- Summarize articles with an LLM.
- Mark articles as read.
- Decide what to discard.

The intended workflow is to use Inoreader Inbox as the first step. It creates a clean Markdown inbox with source URLs, then the agent can choose browser tools, web search, or platform-specific skills for deeper reading.

## FAQ

### Why use Inoreader here?

Inoreader is good at normalizing many feed sources, including normal RSS feeds and feeds created from web pages. This skill keeps that responsibility in Inoreader instead of reimplementing subscription management locally.

### Does this use a global Python environment?

No. Always run commands through `scripts/run.py`. The launcher creates and uses a skill-local `.venv`.

### Does this consume Inoreader API requests?

Real `run` and `status` commands call the Inoreader API. `--sample` does not.

### Where is the OAuth token stored?

By default:

```text
config/token.json
```

That file is ignored by git.

### Why is there no full-text extraction?

Full-text extraction is platform-specific and often fragile. This skill preserves original URLs so a downstream agent or specialized skill can decide the best way to read each source.
