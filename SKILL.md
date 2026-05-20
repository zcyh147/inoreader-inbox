---
name: inoreader-inbox
description: Use this skill whenever the user wants to connect Inoreader, check the current Inoreader login, or pull unread/stream articles from Inoreader into a local Markdown inbox. It treats Inoreader as the feed/subscription normalizer and preserves article metadata, summaries, and source URLs for downstream agents or skills.
---

# Inoreader Inbox

Use Inoreader as the subscription/feed normalizer, then write a local Markdown inbox that preserves article metadata, summaries, and source URLs for downstream agents or skills.

## Critical: Always Use `run.py`

Always run scripts through the launcher:

```bash
python scripts/run.py rss_ai_inbox.py run --unread-only --limit 50
```

The launcher:

- Creates `.venv` on first use.
- Installs dependencies from `requirements.txt` into the skill-local `.venv`.
- Reinstalls dependencies when `requirements.txt` changes.
- Runs the requested script with the skill-local Python.

Do not run `scripts/rss_ai_inbox.py` directly unless debugging the launcher itself.

## Local Storage

Configuration and credentials are stored under this skill's `config/` directory:

- `config/token.json`: Inoreader OAuth token. Sensitive. Never print or copy into chat.

Generated output is stored separately:

- `out/inbox.md`: latest Markdown inbox.

The `.gitignore` excludes token and output files.

## Common Commands

Check or create the local Python environment:

```bash
python scripts/run.py --check
```

First-time login or account replacement:

```bash
python scripts/run.py rss_ai_inbox.py login
```

If you already captured the redirected callback URL and want to finish login non-interactively:

```bash
python scripts/run.py rss_ai_inbox.py login \
  --client-id "$INOREADER_CLIENT_ID" \
  --client-secret "$INOREADER_CLIENT_SECRET" \
  --callback-url "https://127.0.0.1:8765/callback?code=...&state=..." \
  --auth-state "copied-from-the-original-auth-url"
```

The login wizard explains how to create an Inoreader API application. Use these app-registration values:

- Name: `Inoreader Inbox`
- URL: `https://127.0.0.1:8765`
- Platform: choose `Web`, `Desktop`, or `Other`, whichever is available in the UI.
- Redirect URI: `https://127.0.0.1:8765/callback`
- OAuth Scope: `Readable and writable`

After approving the OAuth consent page, paste the full redirected URL immediately. The `code` in that URL is one-time use and short-lived. Inoreader's OAuth docs say to exchange the authorization code immediately, but do not publish an exact lifetime.

The login command generates an authorization URL with a required `state` parameter. If you open the URL outside the script and later pass the callback with `--callback-url`, also pass that same value via `--auth-state`; mismatches are rejected on purpose.

Check the current login:

```bash
python scripts/run.py rss_ai_inbox.py status
```

Use a non-default token file when explicitly requested:

```bash
python scripts/run.py rss_ai_inbox.py status --token-file config/other-token.json
```

Pull unread articles and write the inbox:

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

Pull starred articles:

```bash
python scripts/run.py rss_ai_inbox.py run \
  --stream "user/-/state/com.google/starred" \
  --limit 50
```

## OAuth Pitfalls Worth Remembering

- `user/-/state/com.google/starred` is the stream ID for hearted/starred items.
- Inoreader requires the OAuth authorization URL to include `state`; do not remove it.
- `--callback-url` is meant for a full redirected URL, not a bare authorization code. Pair it with `--auth-state` from the original authorization URL.
- Authorization codes are one-time use and short-lived. If exchange fails because the code expired, restart `login` and use a fresh callback URL.
- Refresh tokens can expire or be revoked. If `status` or `run` fails with `invalid_grant` / `Invalid refresh token`, rerun `python scripts/run.py rss_ai_inbox.py login`.
- The local `https://127.0.0.1:8765/callback` page may fail to render in the browser. That is fine; the URL in the address bar still contains the code you need.

## Downstream Handoff

This skill does not fetch full article pages, classify articles, or mark articles as read. It should preserve each article's original URL in `out/inbox.md`. For full-text reading, platform-specific sources, classification, summarization, or discard decisions, let the agent choose an appropriate downstream browser/tool/skill.

## Safety Notes

Never expose `config/token.json` or OAuth client secrets in responses.
