"""LLM providers through the real SDKs against a local fake server (no API keys, no network).

Checks what is actually sent on the wire: current Claude and OpenAI reasoning models reject sampling
parameters, so they must not be in the request body.
"""

import asyncio
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kiwis.models.base import ChatMessage, ModelConfig


def _sse(events):
    return "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events).encode()


def claude_stream(text="Hello", stop_reason="end_turn", thinking=True):
    blocks, i = [], 0
    if thinking:
        blocks += [("content_block_start", {"type": "content_block_start", "index": 0,
                                            "content_block": {"type": "thinking", "thinking": "", "signature": ""}}),
                   ("content_block_stop", {"type": "content_block_stop", "index": 0})]
        i = 1
    blocks += [("content_block_start", {"type": "content_block_start", "index": i, "content_block": {"type": "text", "text": ""}}),
               ("content_block_delta", {"type": "content_block_delta", "index": i, "delta": {"type": "text_delta", "text": text}}),
               ("content_block_stop", {"type": "content_block_stop", "index": i})]
    msg = {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5", "content": [],
           "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 5, "output_tokens": 1}}
    return _sse([("message_start", {"type": "message_start", "message": msg}), *blocks,
                 ("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                                    "usage": {"output_tokens": 7}}),
                 ("message_stop", {"type": "message_stop"})])


class FakeServer:
    """Records each request (path, headers, JSON body) and answers with ``self.reply``."""

    def __init__(self):
        self.requests, self.reply, self.content_type = [], b"", "application/json"
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                outer.requests.append({"path": self.path, "headers": dict(self.headers), "body": json.loads(body)})
                self.send_response(200)
                self.send_header("Content-Type", outer.content_type)
                self.send_header("Content-Length", str(len(outer.reply)))
                self.end_headers()
                self.wfile.write(outer.reply)

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


@pytest.fixture
def server():
    s = FakeServer()
    yield s
    s.close()


MSGS = [ChatMessage("system", "You are a reviewer."), ChatMessage("user", "Review this.")]


# ------------------------------------------------------------------ Anthropic

def anthropic_provider(server):
    pytest.importorskip("anthropic")
    import anthropic
    from kiwis.models.providers.anthropic_provider import AnthropicProvider
    p = AnthropicProvider(api_key="test-key")
    p._client = anthropic.AsyncAnthropic(api_key="test-key", base_url=server.url, max_retries=0)
    return p


def test_claude_request_has_no_sampling_params_and_uses_fallbacks(server):
    server.reply, server.content_type = claude_stream("Looks good."), "text/event-stream"
    p = anthropic_provider(server)
    cfg = ModelConfig(model_name="claude-opus-5-5", temperature=0.1, max_tokens=32000, stop_sequences=["END"])
    out = asyncio.run(p.chat(MSGS, cfg))

    assert out.content == "Looks good."  # thinking block skipped, text returned
    req = server.requests[0]
    body = req["body"]
    assert "temperature" not in body and "top_p" not in body and "top_k" not in body
    assert body["model"] == "claude-opus-5-5" and body["max_tokens"] == 32000 and body["stream"] is True
    assert body["system"] == "You are a reviewer." and body["messages"] == [{"role": "user", "content": "Review this."}]
    assert body["stop_sequences"] == ["END"] and body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in req["headers"].get("anthropic-beta", "")


def test_claude_without_fallback_support_uses_plain_endpoint(server):
    server.reply, server.content_type = claude_stream("ok", thinking=False), "text/event-stream"
    p = anthropic_provider(server)
    asyncio.run(p.chat(MSGS, ModelConfig(model_name="claude-haiku-5-5")))
    req = server.requests[0]
    assert "fallbacks" not in req["body"] and "anthropic-beta" not in {k.lower() for k in req["headers"]}


def test_claude_refusal_raises(server):
    from kiwis.models.providers.anthropic_provider import AnthropicRefusal
    server.reply, server.content_type = claude_stream("", stop_reason="refusal"), "text/event-stream"
    with pytest.raises(AnthropicRefusal):
        asyncio.run(anthropic_provider(server).chat(MSGS, ModelConfig(model_name="claude-opus-5-5")))


def test_claude_truncation_is_logged(server, caplog):
    server.reply, server.content_type = claude_stream('{"partial": ', stop_reason="max_tokens"), "text/event-stream"
    with caplog.at_level("WARNING"):
        out = asyncio.run(anthropic_provider(server).chat(MSGS, ModelConfig(model_name="claude-opus-5-5")))
    assert out.content == '{"partial": ' and "max_tokens" in caplog.text


# ------------------------------------------------------------------ OpenAI

def completion(text="Hi", finish="stop"):
    return json.dumps({"id": "c1", "object": "chat.completion", "created": 1, "model": "m",
                       "choices": [{"index": 0, "finish_reason": finish,
                                    "message": {"role": "assistant", "content": text}}],
                       "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}).encode()


def openai_provider(server, base_url=None):
    pytest.importorskip("openai")
    import openai
    from kiwis.models.providers.openai_provider import OpenAIProvider
    p = OpenAIProvider(api_key="test-key", base_url=base_url)
    p._client = openai.AsyncOpenAI(api_key="test-key", base_url=server.url + "/v1", max_retries=0)
    return p


def test_openai_reasoning_model_gets_max_completion_tokens_only(server):
    server.reply = completion("Hypothesis")
    out = asyncio.run(openai_provider(server).chat(MSGS, ModelConfig(model_name="gpt-6.2-sol", temperature=0.7, max_tokens=32000)))
    body = server.requests[0]["body"]
    assert out.content == "Hypothesis"
    assert body["max_completion_tokens"] == 32000
    for key in ("max_tokens", "temperature", "top_p", "presence_penalty", "frequency_penalty"):
        assert key not in body


def test_openai_classic_model_and_compatible_servers_keep_sampling(server):
    server.reply = completion()
    asyncio.run(openai_provider(server).chat(MSGS, ModelConfig(model_name="gpt-4o", temperature=0.7, max_tokens=100)))
    asyncio.run(openai_provider(server, base_url="http://vllm.local/v1").chat(
        MSGS, ModelConfig(model_name="my-local-model", temperature=0.2, max_tokens=50)))
    classic, compat = server.requests[0]["body"], server.requests[1]["body"]
    assert classic["temperature"] == 0.7 and classic["max_tokens"] == 100 and "max_completion_tokens" not in classic
    assert compat["temperature"] == 0.2 and compat["max_tokens"] == 50


def test_openai_truncation_is_logged(server, caplog):
    server.reply = completion("cut", finish="length")
    with caplog.at_level("WARNING"):
        asyncio.run(openai_provider(server).chat(MSGS, ModelConfig(model_name="gpt-6.2-sol")))
    assert "truncated" in caplog.text


def test_default_models_are_current():
    from kiwis.config.settings import Settings
    from kiwis.models.factory import infer_provider_name
    s = Settings.default()
    assert s.default_model == "gpt-6.2-sol" and s.agents.writer.max_tokens == 32000
    assert s.providers.providers["anthropic"].default_model == "claude-opus-5-5"
    assert s.providers.providers["deepseek"].default_model == "deepseek-v4-pro"
    assert infer_provider_name("gpt-6.2-sol") == "openai" and infer_provider_name("claude-opus-5-5") == "anthropic"
    assert infer_provider_name("deepseek-flash") == "deepseek"
