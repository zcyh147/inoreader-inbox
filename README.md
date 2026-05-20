# Inoreader Inbox

**A small skill that turns Inoreader into a clean local Markdown inbox for downstream reading, classification, summarization, and routing workflows.**

This skill is not a full-text extractor.
It is the intake layer: pull unread or stream-specific entries from Inoreader, preserve useful metadata, and hand the result to the next step.

---

## The Problem

If you try to build a personal reading workflow directly from raw URLs, feeds, and platform links, the same problems keep showing up:

- **Source formats are inconsistent** across RSS feeds, web-generated feeds, and platform exports
- **Subscription management leaks into later stages** instead of staying in one place
- **Downstream tools start too early** before there is a clean normalized article list
- **You lose metadata** like author, source, publish time, and original URL if you only copy text around

When what you really need is a stable inbox, mixing “feed collection” and “content reading” in one tool creates unnecessary fragility.

---

## The Solution

`inoreader-inbox` keeps Inoreader responsible for subscription and stream normalization, then writes a local Markdown inbox that downstream tools can consume.

```text
Inoreader unread / stream entries
→ local Markdown inbox
→ downstream reading / summarization / routing skills
```

This skill does **not** try to decide what each article means.
It prepares a reliable inbox so later tools can do higher-value work.

---

## Why use this instead of fetching full articles immediately?

| Approach | Good at | Weak at |
| --- | --- | --- |
| Fetch full article pages directly from every source | Rich text when it works | Fragile, platform-specific, hard to scale across mixed feeds |
| Use Inoreader only in browser | Easy manual browsing | Weak automation handoff |
| `inoreader-inbox` | Normalized intake + metadata preservation + local handoff | Does not fetch full article bodies |

### Pros

- **Keeps subscription logic upstream** in Inoreader, where it belongs
- **Produces a stable Markdown inbox** that other skills or agents can consume
- **Preserves useful metadata** such as title, author, source, publish time, and original URL
- **Separates concerns cleanly**: intake first, deep reading later
- **Runs locally** with a skill-specific virtual environment and local output files

### Cons

- **No full-text extraction** — article bodies are not fetched here
- **No classification or summarization** — this skill is intake, not interpretation
- **No read-state decisions** — it does not decide what to discard or archive
- **Depends on Inoreader API access** — you need OAuth setup before real runs work

---

## What This Skill Actually Does

### Primary job

Pull unread or stream-specific items from Inoreader and write them into a local Markdown inbox.

### Core output

The canonical output is:

```text
out/inbox.md
```

This file is intended to become a clean handoff artifact for later steps.

### Preserved fields

The exact formatting depends on the script output, but the intended preserved information includes:

- title
- summary / snippet
- author
- source / feed name
- publish time
- original article URL

---

## What This Skill Does Not Do

This skill does **not**:

- fetch full article pages
- classify articles
- summarize articles with an LLM
- mark articles as read
- decide what to discard
- replace downstream browser / reader / extraction skills

That boundary is a feature, not a missing piece.
It keeps this skill focused on intake and keeps fragile source-specific reading logic out of the feed layer.

---

## How It Works

### 1. Always run through the launcher

All commands should go through `scripts/run.py`.
That launcher is responsible for creating and using the skill-local Python environment.

```bash
python scripts/run.py --check
```

### 2. Authenticate once

First-time login:

```bash
python scripts/run.py rss_ai_inbox.py login
```

If you already have the redirected callback URL and want to finish the token exchange without interactive prompts:

```bash
python scripts/run.py rss_ai_inbox.py login \
  --client-id "$INOREADER_CLIENT_ID" \
  --client-secret "$INOREADER_CLIENT_SECRET" \
  --callback-url "https://127.0.0.1:8765/callback?code=...&state=..." \
  --auth-state "copied-from-the-original-auth-url"
```

The skill expects you to create an Inoreader API application and provide:

- Name: `Inoreader Inbox`
- URL: `https://127.0.0.1:8765`
- Redirect URI: `https://127.0.0.1:8765/callback`
- OAuth Scope: `Readable and writable`

The generated authorization URL includes a required OAuth `state` parameter. If you copy the auth URL into another browser or tool, keep that `state` paired with the callback URL and pass it back with `--auth-state`. Inoreader rejects missing `state`, and the script rejects mismatched `state`.

### 3. Pull inbox items

Unread entries:

```bash
python scripts/run.py rss_ai_inbox.py run --unread-only --limit 50
```

Specific stream:

```bash
python scripts/run.py rss_ai_inbox.py run \
  --stream "user/-/state/com.google/reading-list" \
  --unread-only \
  --limit 50
```

Starred / hearted items:

```bash
python scripts/run.py rss_ai_inbox.py run \
  --stream "user/-/state/com.google/starred" \
  --limit 50
```

### 4. Hand off downstream

Once `out/inbox.md` exists, another tool can decide how to read, extract, summarize, route, or file the linked content.

---

## Typical Uses

### Example 1: Pull unread articles into a local inbox

```text
Use Inoreader as my feed normalizer and give me a Markdown inbox of unread items
```

Expected path:

```text
Inoreader unread items → out/inbox.md
```

### Example 2: Pull a specific stream for later processing

```text
Pull one stream into Markdown first, then let another skill decide what to read in full
```

Expected path:

```text
Inoreader stream → out/inbox.md → downstream fetch / summarize skill
```

### Example 3: Use sample data without a real account

```bash
python scripts/run.py rss_ai_inbox.py run --sample
```

Useful when testing downstream workflows without live API access.

### OAuth troubleshooting

- If you see `invalid_grant` with `Invalid refresh token`, the saved refresh token is no longer usable. Re-run `python scripts/run.py rss_ai_inbox.py login` to replace `config/token.json`.
- Authorization codes are one-time use and short-lived. If the token exchange says the code expired, start over with a fresh approval and paste the new callback URL immediately.
- The browser may fail to load `https://127.0.0.1:8765/callback` locally. That is still fine; copy the full URL from the address bar.
- If you finish the browser step elsewhere, use `--callback-url` plus the matching `--auth-state` to hand the full callback URL back to the script.

---

## Local Storage

### Sensitive files

Configuration and credentials live under:

```text
config/
```

Important file:

```text
config/token.json
```

This is sensitive and must never be committed or pasted into chat.

### Generated files

Output lives under:

```text
out/
```

### Ignored runtime state

These are intentionally kept out of git:

```text
.venv/
agents/
config/
out/
```

---

## Repository Structure

```text
inoreader-inbox/
├── SKILL.md
├── README.md
├── requirements.txt
├── scripts/
│   ├── run.py
│   ├── setup_environment.py
│   └── rss_ai_inbox.py
├── config/
├── out/
└── agents/
```

---

## Current Limitations

- This skill stops at the inbox layer; it intentionally does not fetch article bodies
- Real runs depend on valid Inoreader OAuth credentials
- It assumes Inoreader is the subscription normalizer instead of replacing that layer locally
- The Markdown inbox is only as good as the metadata Inoreader exposes for each item

---

## When This Skill Is the Right Choice

Use `inoreader-inbox` when the problem is:

- “I need a normalized inbox of unread items”
- “I want to preserve article URLs and metadata before deeper processing”
- “I do not want to mix subscription management with full-text extraction”

Do **not** use it when the problem is:

- “I need the full body of this article right now”
- “I want one tool to both ingest feeds and deeply read every page”
- “I need summarization or classification from the same step”

---

## The Bottom Line

**Without this skill**: your reading workflow starts too late, after feed normalization has already been mixed with extraction, classification, or summarization.

**With this skill**: you get a clean intake layer — unread items become a local Markdown inbox with preserved metadata and URLs, ready for the next tool to decide how deep to go.

It is not a universal reader.
It is a practical feed-to-inbox bridge for downstream agent workflows.
