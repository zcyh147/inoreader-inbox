#!/usr/bin/env python3
"""Pull Inoreader articles and write a Markdown inbox."""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import html
import http.server
import json
import os
import re
import secrets
import textwrap
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = SKILL_DIR / "config"
OUTPUT_DIR = SKILL_DIR / "out"
INOREADER_STREAM_CONTENTS = "https://www.inoreader.com/reader/api/0/stream/contents"
INOREADER_USER_INFO = "https://www.inoreader.com/reader/api/0/user-info"
INOREADER_TOKEN_ENDPOINT = "https://www.inoreader.com/oauth2/token"
INOREADER_AUTH_ENDPOINT = "https://www.inoreader.com/oauth2/auth"
DEFAULT_REDIRECT_URI = "https://127.0.0.1:8765/callback"
DEFAULT_OUTPUT_PATH = OUTPUT_DIR / "inbox.md"
DEFAULT_TOKEN_PATH = CONFIG_DIR / "token.json"


@dataclass
class Article:
    id: str
    title: str
    url: str
    source: str
    author: str
    published: int | None
    content_html: str
    content_text: str
    raw: dict[str, Any]


SAMPLE_ITEMS: list[dict[str, Any]] = [
    {
        "id": "sample-1",
        "title": "A guide to local RSS workflows for agents",
        "published": 1777046400,
        "canonical": [{"href": "https://example.com/rss-agents"}],
        "summary": {
            "content": "<p>This article explores RSS normalization and agent-friendly inboxes.</p>"
        },
        "author": "Codex",
        "origin": {"title": "Example Research"},
    },
    {
        "id": "sample-2",
        "title": "A short update from a normalized feed",
        "published": 1777046500,
        "canonical": [{"href": "https://example.com/update"}],
        "summary": {"content": "<p>This entry demonstrates source URL preservation.</p>"},
        "origin": {"title": "Example Feed"},
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")

    add_auth_arguments(subparsers.add_parser("auth", help="Authorize this tool with Inoreader"))
    add_auth_arguments(subparsers.add_parser("login", help="First-time Inoreader authorization wizard"))

    status_parser = subparsers.add_parser("status", help="Show current Inoreader authorization status")
    status_parser.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN_PATH)

    run_parser = subparsers.add_parser("run", help="Pull articles and write the inbox")
    add_run_arguments(run_parser)

    add_run_arguments(parser)
    parser.set_defaults(command="run")
    args = parser.parse_args()

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.command in {"auth", "login"}:
        return authorize_inoreader(args)
    if args.command == "status":
        return show_status(args)
    return run_pipeline(args)


def add_auth_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--client-id", default=os.environ.get("INOREADER_CLIENT_ID"))
    parser.add_argument("--client-secret", default=os.environ.get("INOREADER_CLIENT_SECRET"))
    parser.add_argument("--scope", default="read write")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--redirect-uri", default=DEFAULT_REDIRECT_URI)
    parser.add_argument("--manual", action="store_true", help="Paste redirected URL/code manually.")
    parser.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN_PATH)


def add_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sample", action="store_true", help="Use built-in sample articles")
    parser.add_argument("--stream", default="user/-/state/com.google/reading-list")
    parser.add_argument("--unread-only", action="store_true")
    parser.add_argument("--limit", type=int, default=50, help="Number of articles to fetch")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN_PATH)


def run_pipeline(args: argparse.Namespace) -> int:
    token = get_access_token(args.token_file)
    items = SAMPLE_ITEMS if args.sample else fetch_inoreader_items(
        stream=args.stream,
        limit=args.limit,
        unread_only=args.unread_only,
        token=token,
    )
    articles = [article_from_item(item) for item in items]
    write_markdown(articles, args.output)
    print(f"Wrote {args.output} with {len(articles)} articles.")
    return 0


def authorize_inoreader(args: argparse.Namespace) -> int:
    if not args.client_id or not args.client_secret:
        print_first_login_instructions(args.redirect_uri, args.scope)
    if not args.client_id:
        args.client_id = input("Inoreader App ID / Client ID: ").strip()
    if not args.client_secret:
        args.client_secret = getpass.getpass("Inoreader App Key / Client Secret: ").strip()
    if not args.client_id or not args.client_secret:
        raise SystemExit(
            "Provide --client-id/--client-secret or set "
            "INOREADER_CLIENT_ID/INOREADER_CLIENT_SECRET."
        )

    redirect_uri = args.redirect_uri or DEFAULT_REDIRECT_URI
    manual_callback = args.manual or redirect_uri.startswith("https://127.0.0.1")
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": args.client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": args.scope,
        "state": state,
    }
    auth_url = f"{INOREADER_AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"
    print("Opening browser for Inoreader authorization...")
    print(f"Redirect URI must match your Inoreader app settings: {redirect_uri}")
    webbrowser.open(auth_url)

    callback = (
        read_manual_oauth_callback(expected_state=state)
        if manual_callback
        else wait_for_oauth_callback(args.host, args.port)
    )
    if callback.get("state") != state:
        raise SystemExit("OAuth state mismatch; refusing to exchange the code.")
    if "error" in callback:
        raise SystemExit(f"Inoreader authorization failed: {callback['error']}")
    code = callback.get("code")
    if not code:
        raise SystemExit("No authorization code received.")

    token_data = exchange_authorization_code(
        code=code,
        redirect_uri=redirect_uri,
        client_id=args.client_id,
        client_secret=args.client_secret,
        scope=args.scope,
    )
    token_data["client_id"] = args.client_id
    token_data["client_secret"] = args.client_secret
    token_data["obtained_at"] = utc_timestamp()
    token_data["expires_at"] = token_data["obtained_at"] + int(token_data.get("expires_in", 0))
    save_token(args.token_file, token_data)
    print(f"Saved token to {args.token_file}")
    return 0


def print_first_login_instructions(redirect_uri: str, scope: str) -> None:
    print(
        textwrap.dedent(
            f"""
            First-time setup:
            1. Open Inoreader in your browser and go to Preferences -> Developer.
            2. Create an API application with these values:
               - Name: Inoreader Inbox
               - URL: https://127.0.0.1:8765
               - Platform: Web/Desktop/Other, whichever is available
               - Redirect URI: {redirect_uri}
               - OAuth Scope: {"Readable and writable" if "write" in scope else "Read only"}
            3. Save the app, then paste its App ID and App Key below.
            4. After approval, paste the redirected URL immediately. The OAuth code is one-time use
               and short-lived; Inoreader does not publish an exact lifetime in the OAuth docs.
            """
        ).strip()
    )


def read_manual_oauth_callback(expected_state: str) -> dict[str, str]:
    print()
    print("After approving in Inoreader, paste the full redirected URL from the browser address bar.")
    print("The local HTTPS page may fail to load; that is fine, the URL still contains the code.")
    print("Paste it immediately: the OAuth code is one-time use and short-lived.")
    value = input("Redirected URL: ").strip()
    if value.startswith(("http://", "https://")):
        parsed = urllib.parse.urlparse(value)
        params = urllib.parse.parse_qs(parsed.query)
        return {key: values[0] for key, values in params.items() if values}
    return {"code": value, "state": expected_state, "state_unverified": "1"}


def show_status(args: argparse.Namespace) -> int:
    token_path = args.token_file
    if not token_path.exists():
        print("Not logged in: config/token.json does not exist.")
        print("Run: python scripts/run.py rss_ai_inbox.py login")
        return 1

    token_data = json.loads(token_path.read_text(encoding="utf-8"))
    token = get_access_token(token_path)
    if not token:
        print("Not logged in: token file exists but has no access token.")
        return 1
    token_data = json.loads(token_path.read_text(encoding="utf-8"))

    user_info = http_json(INOREADER_USER_INFO, headers={"Authorization": f"Bearer {token}"})
    print("Logged in to Inoreader.")
    print(f"User: {user_info.get('userName') or user_info.get('userId') or 'unknown'}")
    if user_info.get("userEmail"):
        print(f"Email: {user_info['userEmail']}")
    if user_info.get("userProfileId"):
        print(f"Profile ID: {user_info['userProfileId']}")
    print(f"Scope: {token_data.get('scope', 'unknown')}")
    print(f"Token file: {token_path}")
    return 0


def wait_for_oauth_callback(host: str, port: int) -> dict[str, str]:
    result: dict[str, str] = {}

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            result.update({key: values[0] for key, values in params.items() if values})
            body = b"Inoreader authorization received. You can close this tab."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = http.server.HTTPServer((host, port), CallbackHandler)
    server.handle_request()
    server.server_close()
    return result


def exchange_authorization_code(
    code: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
    scope: str,
) -> dict[str, Any]:
    fields = [
        ("code", code),
        ("redirect_uri", redirect_uri),
        ("client_id", client_id),
        ("client_secret", client_secret),
        ("scope", scope),
        ("grant_type", "authorization_code"),
    ]
    return http_post_json(INOREADER_TOKEN_ENDPOINT, fields)


def refresh_access_token(token_path: Path, token_data: dict[str, Any]) -> dict[str, Any]:
    refresh_token = token_data.get("refresh_token")
    client_id = token_data.get("client_id")
    client_secret = token_data.get("client_secret")
    if not refresh_token or not client_id or not client_secret:
        raise SystemExit(f"{token_path} cannot refresh; run auth again.")

    fields = [
        ("client_id", client_id),
        ("client_secret", client_secret),
        ("grant_type", "refresh_token"),
        ("refresh_token", refresh_token),
    ]
    refreshed = http_post_json(INOREADER_TOKEN_ENDPOINT, fields)
    refreshed["client_id"] = client_id
    refreshed["client_secret"] = client_secret
    refreshed["obtained_at"] = utc_timestamp()
    refreshed["expires_at"] = refreshed["obtained_at"] + int(refreshed.get("expires_in", 0))
    save_token(token_path, refreshed)
    return refreshed


def get_access_token(token_path: Path) -> str | None:
    env_token = os.environ.get("INOREADER_TOKEN")
    if env_token:
        return env_token
    if not token_path.exists():
        return None
    token_data = json.loads(token_path.read_text(encoding="utf-8"))
    now = utc_timestamp()
    if int(token_data.get("expires_at", 0)) - now < 60:
        token_data = refresh_access_token(token_path, token_data)
    return token_data.get("access_token")


def save_token(path: Path, token_data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(token_data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def utc_timestamp() -> int:
    return int(dt.datetime.now(tz=dt.timezone.utc).timestamp())


def fetch_inoreader_items(
    stream: str,
    limit: int,
    unread_only: bool,
    token: str | None,
) -> list[dict[str, Any]]:
    if not token:
        raise SystemExit(
            "Authorize first with `python scripts/run.py rss_ai_inbox.py auth`, "
            "set INOREADER_TOKEN, or run with --sample."
        )

    items: list[dict[str, Any]] = []
    continuation: str | None = None
    while len(items) < limit:
        batch_size = min(100, limit - len(items))
        params = {"n": str(batch_size), "output": "json"}
        if unread_only:
            params["xt"] = "user/-/state/com.google/read"
        if continuation:
            params["c"] = continuation

        encoded_stream = urllib.parse.quote(stream, safe="")
        url = f"{INOREADER_STREAM_CONTENTS}/{encoded_stream}?{urllib.parse.urlencode(params)}"
        data = http_json(url, headers={"Authorization": f"Bearer {token}"})
        items.extend(data.get("items", []))
        continuation = data.get("continuation")
        if not continuation:
            break
    return items[:limit]


def http_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} from {url}: {detail}") from exc


def http_post_json(url: str, fields: list[tuple[str, str]]) -> dict[str, Any]:
    response = http_post_form(
        url,
        fields=fields,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "inoreader-inbox-skill/0.1",
        },
    )
    return json.loads(response)


def http_post_form(url: str, fields: list[tuple[str, str]], headers: dict[str, str]) -> str:
    body = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} from {url}: {detail}") from exc


def article_from_item(item: dict[str, Any]) -> Article:
    content_html = item.get("summary", {}).get("content", "") or ""
    return Article(
        id=str(item.get("id", "")),
        title=item.get("title", "(untitled)"),
        url=article_url(item),
        source=item.get("origin", {}).get("title", ""),
        author=item.get("author", ""),
        published=item.get("published"),
        content_html=content_html,
        content_text=html_to_text(content_html),
        raw=item,
    )


def article_url(item: dict[str, Any]) -> str:
    for key in ("canonical", "alternate"):
        for candidate in item.get(key, []) or []:
            href = candidate.get("href")
            if href:
                return href
    return ""


def html_to_text(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    value = re.sub(r"(?i)<br\s*/?>", "\n", value)
    value = re.sub(r"(?i)</p\s*>", "\n\n", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n\s+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def write_markdown(articles: list[Article], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    lines = ["# Inoreader Inbox", "", f"Generated: {now}", ""]

    for article in articles:
        excerpt = textwrap.shorten(" ".join(article.content_text.split()), width=900, placeholder="...")
        published = format_published(article.published)
        lines.extend([
            f"## {article.title}",
            "",
            f"- Source: {article.source or 'unknown'}",
            f"- Author: {article.author or 'unknown'}",
            f"- Published: {published}",
            f"- URL: {article.url}",
            "",
            excerpt or "_No content available._",
            "",
        ])

    output_path.write_text("\n".join(lines), encoding="utf-8")


def format_published(value: int | None) -> str:
    if not value:
        return "unknown"
    return dt.datetime.fromtimestamp(value).astimezone().strftime("%Y-%m-%d %H:%M %Z")


if __name__ == "__main__":
    raise SystemExit(main())
