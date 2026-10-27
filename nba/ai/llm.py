"""One small interface for the AI steps: send a JSON payload, get JSON that matches a schema back.

Backends, picked by `MAINGAU_LLM` (auto | hessian | claude | ollama | none; default auto = the first that works):
  hessian Hessian.AI inference gateway (OpenAI-compatible chat completions, vLLM models): HAI_API_KEY, HAI_MODEL
  claude  Anthropic API (`anthropic` package + ANTHROPIC_API_KEY or an `ant auth login` profile)
  ollama  an open model served locally by Ollama (free; data stays on the machine), MAINGAU_OLLAMA_MODEL
  none    no AI: callers keep their deterministic result
Settings come from the environment or from a `.env` file at the repo root (git-ignored; see `.env.example`).
A backend that fails once (bad key, server down) is switched off for the rest of the run.
"""
from __future__ import annotations

import json
import logging
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
HESSIAN_URL = "https://hip-gw.hessian.ai/v1"
HESSIAN_MODELS = ("vllm/Kolibri-1", "vllm/GLM-Flash:Latest")  # the two models on the team's Hessian.AI access sheet
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


class HessianLLM(LLM):
    """Hessian.AI gateway: POST {HAI_BASE_URL}/chat/completions with the team key as a Bearer token.

    Structured output is asked for as `response_format: json_schema` (vLLM guided decoding). If the gateway
    refuses that, the backend falls back to `json_object` and then to the schema in the prompt only. The
    answer is cleaned (thinking blocks, code fences) before parsing.
    """

    name = "hessian"
    MODES = ("json_schema", "json_object", "prompt")

    def __init__(self, model: str | None = None, url: str | None = None, key: str | None = None, timeout: float = 120):
        super().__init__()
        self.key = key or os.environ.get("HAI_API_KEY", "").strip()
        if not self.key:
            raise RuntimeError("HAI_API_KEY is not set (export it or put it in .env)")
        self.model = model or os.environ.get("HAI_MODEL", "").strip() or HESSIAN_MODELS[0]
        self.url = (url or os.environ.get("HAI_BASE_URL", "").strip() or HESSIAN_URL).rstrip("/")
        self.timeout, self.mode = timeout, self.MODES[0]

    def _post(self, body: dict) -> dict:
        req = urllib.request.Request(f"{self.url}/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.key}"})
        for attempt in range(3):  # a busy gateway (429, 5xx) gets two more tries; anything else fails at once
            try:
                with urllib.request.urlopen(req, timeout=self.timeout, context=_ssl_context()) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
        raise RuntimeError("unreachable")

    def _complete(self, system, user, schema, effort):
        system = f"{system}\n\nAnswer with one JSON object that matches this JSON schema and nothing else:\n{json.dumps(schema)}"
        body = {"model": self.model, "temperature": 0, "max_tokens": 8192,  # room for a reasoning model's thinking
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        while True:
            fmt = ({"response_format": {"type": "json_schema", "json_schema": {"name": "answer", "schema": schema}}}
                   if self.mode == "json_schema" else {"response_format": {"type": "json_object"}} if self.mode == "json_object" else {})
            try:
                data = self._post(body | fmt)
                break
            except urllib.error.HTTPError as exc:
                if exc.code not in (400, 422) or self.mode == self.MODES[-1]:
                    raise
                log.info("hessian: %s not accepted (HTTP %s), trying the next format", self.mode, exc.code)
                self.mode = self.MODES[self.MODES.index(self.mode) + 1]  # remembered for the rest of the run
        choice = (data.get("choices") or [{}])[0]
        if choice.get("finish_reason") == "length":
            return None
        return _json_text((choice.get("message") or {}).get("content") or "")


def _ssl_context() -> ssl.SSLContext:
    """Verify TLS against certifi's CA bundle when it is installed: a python.org Python on macOS has no CA
    file of its own until "Install Certificates" is run (CERTIFICATE_VERIFY_FAILED); else the system default."""
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def _json_text(text: str) -> str | None:
    """The JSON object inside a model answer: drops <think> blocks and ``` fences, keeps the outermost {...}."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start != -1 and end > start else None


def load_env_file(path: Path | None = None) -> None:
    """KEY=VALUE lines of a git-ignored .env into the environment; a variable that is already set wins."""
    path = path or ENV_FILE
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        value = value.strip().strip("\"'")
        if key.strip() and value:
            os.environ.setdefault(key.strip(), value)


def _ollama_up(url: str = OLLAMA_URL) -> bool:
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/api/tags", timeout=2):
            return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def from_env(choice: str | None = None) -> LLM:
    """The configured backend; `auto` tries Hessian.AI (if HAI_API_KEY is set), Claude (if the SDK and a
    credential exist), then a local Ollama."""
    load_env_file()
    choice = (choice or os.environ.get("MAINGAU_LLM", "auto")).lower()
    if choice == "hessian" or (choice == "auto" and os.environ.get("HAI_API_KEY", "").strip()):
        try:
            return HessianLLM()
        except Exception as exc:  # no key
            log.warning("Hessian.AI backend unavailable: %s", exc)
            if choice == "hessian":
                return LLM()
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
