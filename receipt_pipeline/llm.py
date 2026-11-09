"""Vision-LLM fallback. Providers: gemini (free tier), ollama (local, free), anthropic.

Select with env RECEIPT_PROVIDER (default: first one configured).
  gemini    -> GEMINI_API_KEY   (model: RECEIPT_MODEL, default gemini-3.5-flash)
  ollama    -> local server at OLLAMA_URL (default http://localhost:11434), model default qwen2.5vl
  anthropic -> ANTHROPIC_API_KEY
"""
import base64
import json
import os
import re
import time
import urllib.error
import urllib.request

from .parser import Parsed

PROMPT = (
    "Extract fields from this receipt (English or Chinese). Reply with ONLY JSON: "
    '{"date":"YYYY-MM-DD"|null,"merchant":str|null,"currency":"ISO 4217 code"|null,'
    '"total":"grand total as decimal string, e.g. 12.50"|null,"confidence":0..1,"notes":str}. '
    "Use null for any field that is unreadable or ambiguous (e.g. dd/mm vs mm/dd, '$' with no "
    "country clue). Never guess. Merchant = the shop's name as printed (romanised or original)."
)


def available_provider() -> str | None:
    p = os.environ.get("RECEIPT_PROVIDER")
    if p:
        return p
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


def _post(url, body, headers=None):
    req = urllib.request.Request(url, json.dumps(body).encode(),
                                 {"Content-Type": "application/json", **(headers or {})})
    for wait in (15, 30, 60, 90, None):  # free tiers rate-limit (429) / overload (503)
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or wait is None:
                raise
            time.sleep(wait)


def _gemini(pages):
    model = os.environ.get("RECEIPT_MODEL", "gemini-3.5-flash")
    parts = [{"inline_data": {"mime_type": "image/png", "data": base64.b64encode(p).decode()}}
             for p in pages] + [{"text": PROMPT}]
    r = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
              {"contents": [{"parts": parts}],
               "generationConfig": {"responseMimeType": "application/json", "temperature": 0}},
              {"x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    return r["candidates"][0]["content"]["parts"][0]["text"]


def _ollama(pages):
    base = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    r = _post(f"{base}/api/chat", {
        "model": os.environ.get("RECEIPT_MODEL", "qwen2.5vl"), "stream": False, "format": "json",
        "options": {"temperature": 0},
        "messages": [{"role": "user", "content": PROMPT,
                      "images": [base64.b64encode(p).decode() for p in pages]}]})
    return r["message"]["content"]


def _anthropic(pages):
    import anthropic
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                            "data": base64.b64encode(p).decode()}}
               for p in pages] + [{"type": "text", "text": PROMPT}]
    msg = anthropic.Anthropic().messages.create(
        model=os.environ.get("RECEIPT_MODEL", "claude-sonnet-5-5"), max_tokens=400,
        messages=[{"role": "user", "content": content}])
    return msg.content[0].text


PROVIDERS = {"gemini": _gemini, "ollama": _ollama, "anthropic": _anthropic}


def extract(pages_png: list[bytes]) -> tuple[Parsed, float]:
    raw = PROVIDERS[available_provider()](pages_png)
    m = re.search(r"\{.*\}", raw, re.S)
    d = json.loads(m.group(0)) if m else {}
    p = Parsed(date=d.get("date"), merchant=d.get("merchant"),
               currency=d.get("currency"), total=d.get("total"))
    if p.total is not None:
        p.total = str(p.total)
    for name in ("date", "merchant", "currency", "total"):
        if not getattr(p, name):
            p.issues.append(f"missing {name}")
    if d.get("notes") and p.issues:
        p.issues.append(str(d["notes"])[:120])
    return p, float(d.get("confidence") or 0)
