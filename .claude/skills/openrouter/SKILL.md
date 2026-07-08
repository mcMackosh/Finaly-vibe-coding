---
name: openrouter
description: Use this to write code that calls an LLM for free using OpenRouter's free-tier models (e.g. GPT-OSS, Llama, DeepSeek).
---

# Calling an LLM via OpenRouter (free tier)

Instructions for wiring up a free LLM call through [OpenRouter](https://openrouter.ai) — works from any
language/runtime since it's a plain HTTPS JSON API. Python examples are given since that's the language this
project's backend is built in, but the same request/response shape applies everywhere (Node.js, curl, etc.).

## Setup

1. Get a free API key at https://openrouter.ai/keys.
2. Store it as `OPENROUTER_API_KEY` in an env var / `.env` file — never hardcode it in source.
3. Pick a free model id from https://openrouter.ai/models?max_price=0 (they all end in `:free`, e.g.
   `openai/gpt-oss-20b:free`, `meta-llama/llama-3.3-70b-instruct:free`, `deepseek/deepseek-chat-v3.1:free`).
   Read the model id from an env var (e.g. `OPENROUTER_MODEL`) too, not hardcoded — free models get rate-limited
   or deprecated and you'll want to swap them without a code change.
4. No SDK is required — plain HTTPS POST with any HTTP client (`fetch`, `requests`, `curl`, ...) works.

## Request shape

```
POST https://openrouter.ai/api/v1/chat/completions
Authorization: Bearer <OPENROUTER_API_KEY>
Content-Type: application/json

{
  "model": "<model id, e.g. openai/gpt-oss-20b:free>",
  "messages": [
    { "role": "system", "content": "..." },
    { "role": "user", "content": "..." }
  ]
}
```

Response: `body.choices[0].message.content` is the model's reply text.

## Python example (using `httpx`, or swap in `requests`)

```python
import os
import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

async def ask_openrouter(messages: list[dict[str, str]]) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                "Content-Type": "application/json",
            },
            json={"model": os.environ["OPENROUTER_MODEL"], "messages": messages},
        )
        response.raise_for_status()
        body = response.json()
        return body["choices"][0]["message"]["content"]
```

## Getting JSON-shaped output

Free models/providers vary in whether they honor `response_format` (Structured Outputs). Check a model's
`supported_parameters` at `GET https://openrouter.ai/api/v1/models` before relying on it. If it's not supported
(or you want to stay swappable across free models without re-verifying each one), enforce the JSON shape via
prompt instructions instead ("Reply with ONLY a single JSON object, no markdown fences, no extra text") and
parse leniently in case the model still wraps it in prose:

```python
import json
import re

def extract_json_object(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            raise ValueError("no JSON object found in response")
        return json.loads(match.group(0))
```

If the model/provider does support it, pass a schema instead:

```python
json={
    "model": model,
    "messages": messages,
    "response_format": {
        "type": "json_schema",
        "json_schema": {"name": "MySchema", "schema": my_schema, "strict": True},
    },
}
```

## Handling free-tier flakiness

Free models are prone to `429` rate-limiting and occasional malformed completions (invalid JSON, or JSON missing
expected keys — not a bug in your code). Retry the whole request/parse/validate cycle a few times with a short
backoff before giving up:

```python
import asyncio

async def ask_with_retry(messages: list[dict[str, str]], retries: int = 3, backoff_s: float = 1.5):
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        if attempt > 0:
            await asyncio.sleep(backoff_s)
        try:
            content = await ask_openrouter(messages)
            return extract_json_object(content)  # or just `content` for plain text
        except Exception as err:
            last_error = err
    raise last_error
```
