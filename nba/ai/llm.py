"""One small interface for the AI steps: send a JSON payload, get JSON that matches a schema back.

Backends, picked by `MAINGAU_LLM` (auto | claude | ollama | none; default auto = the first that works):
  claude  Anthropic API (`anthropic` package + ANTHROPIC_API_KEY or an `ant auth login` profile)
  ollama  an open model served locally by Ollama (free; data stays on the machine), MAINGAU_OLLAMA_MODEL
  none    no AI: callers keep their deterministic result
A backend that fails once (no key, server down) is switched off for the rest of the run.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

log = logging.getLogger(__name__)
CLAUDE_MODEL = "claude-opus-5-5"
OLLAMA_URL = os.environ.get("MAINGAU_OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("MAINGAU_OLLAMA_MODEL", "qwen2.5:7b-instruct")


class LLM:
    name = "none"

    def __init__(self):
        self.enabled = True
        self.calls = 0

    def structured(self, system: str, payload: dict, schema: dict, effort: str = "low") -> dict | None:
        """Parsed JSON matching `schema`, or None (no backend, refusal, error, or invalid JSON)."""
        if not self.enabled:
            return None
        try:
            text = self._complete(system, json.dumps(payload, ensure_ascii=False, default=str), schema, effort)
        except Exception as exc:  # a backend that cannot answer is switched off, the caller falls back
            log.warning("%s backend off: %s", self.name, exc)
            self.enabled = False
            return None
        self.calls += 1
        try:
            return json.loads(text) if text else None
        except json.JSONDecodeError:
            return None

    def _complete(self, system, user, schema, effort) -> str | None:
        return None


class ClaudeLLM(LLM):
    name = "claude"

    def __init__(self, client=None, model: str = CLAUDE_MODEL):
        super().__init__()
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.client, self.model = client, model

    def _complete(self, system, user, schema, effort):
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # a policy decline is retried on a fallback model inside the same call
            system=system,
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": user}],
        )
        if response.stop_reason in ("refusal", "max_tokens"):
            return None
        return next((b.text for b in response.content if b.type == "text"), None)


class OllamaLLM(LLM):
    name = "ollama"

    def __init__(self, model: str = OLLAMA_MODEL, url: str = OLLAMA_URL):
        super().__init__()
        self.model, self.url = model, url.rstrip("/")

    def _complete(self, system, user, schema, effort):
        body = {"model": self.model, "stream": False, "format": schema, "options": {"temperature": 0},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        req = urllib.request.Request(f"{self.url}/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())["message"]["content"]


def _ollama_up(url: str = OLLAMA_URL) -> bool:
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/api/tags", timeout=2):
            return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def from_env(choice: str | None = None) -> LLM:
    """The configured backend; `auto` tries Claude (if the SDK and a credential exist), then a local Ollama."""
    choice = (choice or os.environ.get("MAINGAU_LLM", "auto")).lower()
    if choice in ("claude", "auto"):
        has_key = any(os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"))
        if choice == "claude" or has_key:
            try:
                return ClaudeLLM()
            except Exception as exc:  # SDK missing
                log.warning("Claude backend unavailable: %s", exc)
    if choice == "ollama" or (choice == "auto" and _ollama_up()):
        return OllamaLLM()
    return LLM()
