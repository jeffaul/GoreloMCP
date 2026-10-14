# AulTECH Gorelo MCP — Customizations

## Purpose

This repository is a fork of [Coach40oz/GoreloMCP](https://github.com/Coach40oz/GoreloMCP).

AulTECH maintains a small number of customizations to support ChatGPT integration and deployment on a private AWS Lightsail server.

**These modifications must be preserved when incorporating upstream changes.**

## 1. Configurable MCP Bind Address

**File:** `main.py`

**Original code:**

```python
HOST = "127.0.0.1"
```

**AulTECH modification:**

```python
HOST = os.environ.get("MCP_BIND_HOST", "127.0.0.1")
```

**Reason:**

The Gorelo MCP server runs on an AWS Lightsail instance and is accessed through a Cloudflare Tunnel hosted on a separate AWS EC2 instance.

The two instances communicate over private AWS networking.

Binding exclusively to `127.0.0.1` prevents the Cloudflare Tunnel host from reaching the MCP service.

The modification allows the bind address to be configured through the `MCP_BIND_HOST` environment variable while retaining localhost as the default.

**Deployment requirement:**

The systemd service must provide:

```ini
[Service]
Environment="MCP_BIND_HOST=172.26.3.23"
```

The private IP address is specific to the current Lightsail deployment and may need updating if the infrastructure changes.

**Verification:**

- The MCP service starts successfully.
- It listens on the configured private interface.
- The Cloudflare Tunnel host can reach the MCP endpoint.
- Unauthenticated requests to `/mcp` receive HTTP 401.

## 2. ChatGPT OAuth Redirect Support

**File:** `personal_auth.py`

**Original default redirect domains:**

```python
[
    "claude.ai",
    "claude.com",
    "localhost"
]
```

**AulTECH modification:**

```python
[
    "claude.ai",
    "claude.com",
    "chatgpt.com",
    "openai.com",
    "localhost"
]
```

The usage example near the beginning of the file was also updated to reflect the additional domains.

**Reason:**

The original OAuth implementation was designed primarily for Claude.ai.

ChatGPT uses an OAuth callback on `chatgpt.com`. Without that domain in the redirect allowlist, the MCP server rejects ChatGPT's dynamic client registration.

The server logs showed:

```text
register outcome=refused reason=redirect_not_allowed redirect=chatgpt.com
POST /register HTTP/1.1 400 Bad Request
```

Adding the domain resolved the registration failure and allowed ChatGPT to connect successfully.

**Security requirement:**

Keep OAuth redirect validation enabled. Do not replace the allowlist with unrestricted domains or disable redirect URI validation.

**Verification:**

- ChatGPT can register an OAuth client.
- The Gorelo authentication page appears.
- Authentication completes successfully.
- ChatGPT can discover and use the Gorelo MCP tools.

## 3. Deployment Architecture

The current architecture is:

```text
ChatGPT
   |
   | HTTPS
   v
Cloudflare Tunnel
   |
   | Private AWS networking
   v
AWS Lightsail (Debian 13)
   |
   v
Gorelo MCP Server
   |
   v
Gorelo API
```

**Public MCP endpoint:**

`https://gorelo-mcp.aultech.ca/mcp`

The Lightsail server does not require a public inbound connection to port 8765.

The Cloudflare Tunnel runs on a separate AWS EC2 instance.

## 4. Upstream Update Procedure

Before deploying updates from the original developer:

1. Sync changes from `Coach40oz/GoreloMCP` into the AulTECH fork.
2. Review GitHub merge conflicts and changes affecting `main.py` or `personal_auth.py`.
3. Confirm both customizations described above are preserved.
4. Check for upstream changes to the server's binding configuration or OAuth implementation that could make these modifications obsolete.
5. Verify the required behavior through automated checks and, when appropriate, a manual connection test.
6. Merge approved changes into the fork's `main` branch.
7. Deploy the approved version to Lightsail.

**Important:** A successful Git merge does not guarantee that the customizations still work. Upstream changes can alter behavior without producing a merge conflict.

Do not automatically deploy unreviewed upstream updates.

## 5. Automated Validation Requirements

Future GitHub Actions checks should verify that:

- `main.py` supports the `MCP_BIND_HOST` environment variable, or an equivalent configurable bind address.
- OAuth redirect validation permits the required ChatGPT callback domain.
- Existing redirect security restrictions remain enforced.
- The MCP application passes its available automated tests.

If these checks fail, deployment should be blocked until the changes are reviewed.

These checks have not yet been implemented.

## 6. GitHub and Deployment Policy

**Upstream repository:** `Coach40oz/GoreloMCP`

**AulTECH fork:** `jeffaul/GoreloMCP`

**Production branch:** `main`

The production server uses a read-only GitHub deploy key.

Code modifications should be committed to the AulTECH fork through an authorized GitHub account.

The server should pull approved commits from the AulTECH fork rather than directly from upstream.

A future GitHub webhook deployment process should use authenticated webhook requests and fail safely if Git detects conflicts or the deployment fails.

---

**Maintained by:** AulTECH LTD

**Created:** October 14, 2026

**Status:** Both customizations implemented and ChatGPT connectivity confirmed. Automated validation and webhook deployment pending.
