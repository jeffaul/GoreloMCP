"""The fork changes startup configuration only; all tool behaviour is upstream."""

import runpy
from types import SimpleNamespace

import pytest
from dotenv import load_dotenv


@pytest.mark.parametrize("source", ["defaults", "dotenv", "process"])
def test_startup_configuration_precedence(monkeypatch, tmp_path, source):
    for key in ("MCP_BIND_HOST", "MCP_EXTRA_REDIRECT_DOMAINS", "GORELO_TOOLSETS", "GORELO_ENABLE_DESTRUCTIVE"):
        monkeypatch.setenv(key, "")
        monkeypatch.delenv(key)
    monkeypatch.setenv("GORELO_API_KEY", "test-key-not-real")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://mcp.example.test")
    monkeypatch.setenv("MCP_AUTH_PASSWORD", "test-password-not-real")
    local_env = tmp_path / ".env"
    local_env.write_text("")
    host, domains = "127.0.0.1", []
    if source in ("dotenv", "process"):
        local_env.write_text("MCP_BIND_HOST=172.26.3.23\nMCP_EXTRA_REDIRECT_DOMAINS=example.org\n")
        host, domains = "172.26.3.23", ["example.org"]
    if source == "process":
        monkeypatch.setenv("MCP_BIND_HOST", "127.0.0.2")
        monkeypatch.setenv("MCP_EXTRA_REDIRECT_DOMAINS", "example.net")
        host, domains = "127.0.0.2", ["example.net"]
    entry = runpy.run_path("main.py")
    scope = entry["main"].__globals__
    monkeypatch.setitem(scope, "APP_DIR", tmp_path)
    monkeypatch.setitem(scope, "load_dotenv", lambda path=None: load_dotenv(path or local_env))
    calls, auth = [], []
    monkeypatch.setitem(scope, "PersonalAuthProvider", lambda **kwargs: auth.append(kwargs) or object())
    monkeypatch.setitem(scope, "build_server", lambda *a, **k: SimpleNamespace(run=lambda **kwargs: calls.append(kwargs)))
    entry["main"]()
    assert calls == [{"transport": "http", "host": host, "port": 8765}]
    assert auth[0]["allowed_redirect_domains"] == ["claude.ai", "claude.com", "localhost", *domains]
