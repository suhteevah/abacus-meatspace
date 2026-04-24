"""Probe with the exact Claude Code request signature from Matt's api-client crate."""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx

token = json.loads((Path.home() / ".claude" / ".credentials.json").read_text())["claudeAiOauth"]["accessToken"]
print(f"Token prefix: {token[:30]}...\n")

headers = {
    "Authorization": f"Bearer {token}",
    "content-type": "application/json",
    "anthropic-version": "2023-06-01",
    "user-agent": "claude-code/1.0.24",
    "anthropic-beta": "claude-code-20250219,prompt-caching-scope-2026-01-05",
}
body = {
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 50,
    "messages": [{"role": "user", "content": "say hi in exactly 3 words"}],
}

r = httpx.post("https://api.anthropic.com/v1/messages",
               headers=headers, json=body, timeout=30.0)
print(f"status: {r.status_code}")
print(f"body: {r.text[:600]}")
