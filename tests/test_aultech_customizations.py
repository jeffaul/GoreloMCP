"""AulTECH contracts: real startup arguments and the default provider's HTTP gate.

No sockets or real credentials. The final server.run call is recorded, not invoked.
OAuth uses the real FastMCP app and provider with temporary state and ASGI requests.
"""

import runpy
from types import SimpleNamespace

import pytest

# Reuse the upstream suite's real-provider, temporary-state and HTTP-app fixtures.
from test_personal_auth_gate import make_provider, serve, state_dir  # noqa: F401


@pytest.mark.parametrize("host", [None, "172.26.3.23", "0.0.0.0", "::1"])
def test_bind_host_reaches_server_run(monkeypatch, host):
    if host is None:
        monkeypatch.delenv("MCP_BIND_HOST", raising=False)
    else:
        monkeypatch.setenv("MCP_BIND_HOST", host)
    monkeypatch.setenv("GORELO_API_KEY", "test-key-not-real")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://mcp.example.test")
    monkeypatch.setenv("MCP_AUTH_PASSWORD", "test-password-not-real")
    monkeypatch.delenv("GORELO_TOOLSETS", raising=False)
    monkeypatch.delenv("GORELO_ENABLE_DESTRUCTIVE", raising=False)
    entry = runpy.run_path("main.py")
    globals_ = entry["main"].__globals__
    calls = []
    monkeypatch.setitem(globals_, "load_dotenv", lambda: None)
    monkeypatch.setitem(globals_, "install_log_value_filter", lambda: None)
    monkeypatch.setitem(globals_, "PersonalAuthProvider", lambda **kwargs: object())
    monkeypatch.setitem(globals_, "build_server", lambda *a, **k: SimpleNamespace(run=lambda **kw: calls.append(kw)))
    entry["main"]()
    assert calls == [{"transport": "http", "host": host or "127.0.0.1", "port": 8765}], (
        "main.py no longer passes the configured MCP_BIND_HOST (or the localhost default) to server.run."
    )


@pytest.mark.anyio
@pytest.mark.parametrize("domain", ["chatgpt.com", "openai.com", "claude.ai", "claude.com", "localhost"])
async def test_default_oauth_allowlist_accepts_registration_and_consent(state_dir, make_provider, serve, domain):
    provider = make_provider(state_dir)  # Do not supply a replacement allowlist.
    redirect = f"{'http' if domain == 'localhost' else 'https'}://{domain}/callback"
    async with serve(provider) as gate:
        http = gate.at()
        registration = await http.post("/register", json={"redirect_uris": [redirect], "client_name": "AulTECH test"})
        assert registration.status_code == 201, f"The default OAuth allowlist rejected {domain}."
        query = {
            "client_id": registration.json()["client_id"], "redirect_uri": redirect,
            "response_type": "code", "code_challenge": "a" * 43, "code_challenge_method": "S256",
        }
        consent = await http.get("/authorize", params=query)
        assert consent.status_code == 200, f"The authorization gate rejected registered {domain}."
        approved = await http.post("/authorize", data={**query, "password": provider.password, "decision": "approve"})
        assert approved.status_code == 302
        assert approved.headers["location"].startswith(redirect + "?")


@pytest.mark.anyio
@pytest.mark.parametrize("redirect", [
    "https://evil.example/callback", "https://chatgpt.com.evil.example/callback",
    "https://fakechatgpt.com/callback", "https://openai.com.evil.example/callback",
    "http://chatgpt.com/callback", "http://openai.com/callback",
    "https://user@chatgpt.com/callback", "https://chatgpt.com/callback#fragment",
])
async def test_default_oauth_allowlist_rejects_unsafe_redirects(state_dir, make_provider, serve, redirect):
    provider = make_provider(state_dir)
    async with serve(provider) as gate:
        response = await gate.at().post("/register", json={"redirect_uris": [redirect]})
        assert response.status_code == 400, f"OAuth accepted an unsafe redirect: {redirect}"
        assert not provider.clients, "A refused registration must not store a client."
