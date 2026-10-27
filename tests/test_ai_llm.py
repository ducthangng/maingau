"""Hessian.AI backend (nba/ai/llm.py) against a local OpenAI-compatible stand-in: no network, no real key."""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from nba.ai import llm as llm_mod
from nba.ai.__main__ import ping
from nba.ai.llm import HESSIAN_MODELS, HessianLLM, LLM, _json_text, from_env, load_env_file

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}


class Gateway:
    """Records each request; answers with `reply` unless the request's response_format type is refused."""

    def __init__(self, reply='{"ok": true}', refuse=(), status=200):
        self.reply, self.refuse, self.status, self.seen = reply, set(refuse), status, []
        gw = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                gw.seen.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
                kind = (body.get("response_format") or {}).get("type", "prompt")
                code = 400 if kind in gw.refuse else gw.status
                out = {"error": "nope"} if code != 200 else {
                    "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": gw.reply}}]}
                data = json.dumps(out).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"

    def close(self):
        self.server.shutdown()


@pytest.fixture
def gateway():
    made = []

    def make(**kw):
        made.append(Gateway(**kw))
        return made[-1]

    yield make
    for g in made:
        g.close()


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    saved = dict(os.environ)  # load_env_file writes os.environ directly: restore it, so nothing leaks to other tests
    for k in ("HAI_API_KEY", "HAI_MODEL", "HAI_BASE_URL", "MAINGAU_LLM", "ANTHROPIC_API_KEY"):
        os.environ.pop(k, None)
    monkeypatch.setattr(llm_mod, "ENV_FILE", tmp_path / ".env")  # never read the developer's real .env
    monkeypatch.setattr(llm_mod, "_ollama_up", lambda *a, **k: False)
    yield
    os.environ.clear()
    os.environ.update(saved)


def test_request_shape_key_and_default_model(gateway):
    gw = gateway()
    llm = HessianLLM(url=gw.url, key="team-key")
    assert llm.structured("system", {"q": 1}, SCHEMA) == {"ok": True}
    req = gw.seen[0]
    assert req["path"] == "/v1/chat/completions" and req["auth"] == "Bearer team-key"
    body = req["body"]
    assert body["model"] == HESSIAN_MODELS[0] == "vllm/Kolibri-1" and body["temperature"] == 0
    assert body["response_format"] == {"type": "json_schema", "json_schema": {"name": "answer", "schema": SCHEMA}}
    assert body["messages"][0]["role"] == "system" and json.dumps(SCHEMA) in body["messages"][0]["content"]
    assert json.loads(body["messages"][1]["content"]) == {"q": 1}


def test_falls_back_when_the_gateway_refuses_json_schema_and_remembers_it(gateway):
    gw = gateway(refuse={"json_schema", "json_object"})
    llm = HessianLLM(url=gw.url, key="k")
    assert llm.structured("s", {}, SCHEMA) == {"ok": True} and llm.mode == "prompt"
    assert [(r["body"].get("response_format") or {}).get("type") for r in gw.seen] == ["json_schema", "json_object", None]
    llm.structured("s", {}, SCHEMA)
    assert "response_format" not in gw.seen[-1]["body"] and len(gw.seen) == 4  # no second round of refusals


def test_cleans_thinking_and_fences():
    assert _json_text('<think>let me see {"x": 1}</think>\n```json\n{"ok": true}\n```') == '{"ok": true}'
    assert _json_text("no json here") is None


def test_bad_key_switches_the_backend_off(gateway):
    gw = gateway(status=401)
    llm = HessianLLM(url=gw.url, key="wrong")
    assert llm.structured("s", {}, SCHEMA) is None and llm.enabled is False
    assert llm.structured("s", {}, SCHEMA) is None and len(gw.seen) == 1  # no more calls this run


def test_from_env_picks_hessian_from_a_dotenv_file(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# team access\nMAINGAU_LLM=hessian\nexport HAI_API_KEY="from-file"\nHAI_MODEL=vllm/GLM-Flash:Latest\n')
    chosen = from_env()
    assert isinstance(chosen, HessianLLM) and chosen.key == "from-file" and chosen.model == "vllm/GLM-Flash:Latest"
    monkeypatch.setenv("HAI_API_KEY", "from-shell")  # a variable already set wins over the file
    load_env_file(env)
    assert from_env().key == "from-shell"


def test_auto_without_any_key_is_code_only_and_hessian_without_key_too(monkeypatch):
    assert from_env().name == "none"
    monkeypatch.setenv("MAINGAU_LLM", "hessian")
    off = from_env()
    assert off.name == "none" and off.structured("s", {}, SCHEMA) is None
    monkeypatch.setenv("MAINGAU_LLM", "auto")
    monkeypatch.setenv("HAI_API_KEY", "k")
    assert from_env().name == "hessian"


def test_ping(gateway, capsys):
    gw = gateway(reply='{"ok": true, "answer": "pong"}')
    assert ping(HessianLLM(url=gw.url, key="k")) == 0
    assert "hessian (vllm/Kolibri-1)" in capsys.readouterr().out
    assert ping(LLM()) == 1


def test_tls_uses_a_ca_bundle_even_without_system_certificates():
    ctx = llm_mod._ssl_context()
    assert ctx.verify_mode.name == "CERT_REQUIRED" and ctx.check_hostname
    assert ctx.cert_store_stats()["x509_ca"] > 100  # certifi's roots are loaded (a python.org build has none by default)


def test_an_unreachable_gateway_fails_fast():
    import socket
    import time

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()  # nothing listens on this port: the connection is refused at once
    llm = HessianLLM(url=f"http://127.0.0.1:{port}/v1", key="k")
    start = time.perf_counter()
    assert llm.structured("s", {}, SCHEMA) is None and llm.enabled is False
    assert time.perf_counter() - start < 6


def test_the_reachability_check_runs_once(gateway):
    gw = gateway()
    llm = HessianLLM(url=gw.url, key="k")
    llm.structured("s", {}, SCHEMA)
    assert llm.checked is True
    llm.url = "http://127.0.0.1:9/v1"  # not checked again: the first check is remembered for the run
    llm.structured("s", {}, SCHEMA)
    assert llm.checked is True
