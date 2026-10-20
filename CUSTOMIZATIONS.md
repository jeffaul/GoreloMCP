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

The `AulTECH customization checks` workflow runs on pull requests and can also be run manually.
It adds plain-English file annotations and a job summary:

- PR changes are compared from the PR's shared base to its head and labeled "modified in this PR."
- Real upstream changes are fetched from `Coach40oz/GoreloMCP` main and compared from its shared
  commit with the PR target branch to the fetched upstream commit. The exact commits appear in
  the summary. This identifies upstream changes since that shared point, including changes
  that the PR may already incorporate. It does not infer upstream changes from a fork diff.
- When upstream cannot be fetched or compared, the check fails and says upstream was not verified.
- File changes produce review warnings. Tests that fail or cannot run produce errors and fail the check.

The offline behavior tests verify the actual startup call for the localhost default and several
`MCP_BIND_HOST` values. They set the variable before importing `main.py`, as systemd does; the
current code reads it at import time, before `load_dotenv()` runs. This does not claim that a
value supplied only in `.env` controls the bind address.

OAuth tests instantiate the real provider without overriding its allowlist and exercise its HTTP
registration and password-approved authorization endpoints for `chatgpt.com`, `openai.com`,
the existing Claude domains and localhost. They also check rejection of unrelated domains,
lookalike domains, insecure ChatGPT HTTP callbacks, userinfo and fragments. The existing
`tests` workflow continues to run the complete offline suite.

No check opens a server socket, accesses Gorelo, verifies AWS networking or tests a live ChatGPT
connection. The workflow has read-only repository permissions and performs no deployment.
Use a PR when syncing upstream rather than updating production `main` directly. To enforce
checks before merging, configure branch protection/rulesets to require both `Preserve AulTECH
bind and ChatGPT OAuth` and the existing `pytest` check; adding this workflow alone does not
make those checks mandatory or block an external deployment system.

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

**Status:** Both customizations implemented and ChatGPT connectivity confirmed. PR customization checks implemented; webhook deployment pending.


## 7. Upstream 1.3.0 integration (2026-10-20)

- Preserve MCP_BIND_HOST from the process environment, as supplied by systemd.
- Preserve chatgpt.com and openai.com in both PersonalAuthProvider defaults and
  settings.BUILTIN_REDIRECT_DOMAINS. Startup now supplies the settings allowlist
  explicitly, so changing only the provider default would break ChatGPT.
- Keep update_custom_asset.client_id as an expected-current-owner argument, never
  a move instruction. Explicit moves use move_to_client_id. When both are supplied,
  ownership is verified before writing. Incorporate upstream single-record reads
  and move read-back checks. The live harness uses the explicit move parameter.
- Adopt upstream dismissed alert terminology; ignored is no longer accepted.
- Use one deployment workflow, gated by customization tests and the full offline
  suite. Remove the duplicate ungated deploy-prod workflow.
- Production toolsets observed before integration: billing,core,forms,projects,
  tickets,time,uptime; gated tools disabled. Documents remain opt-in.

### Server follow-up

Before changing configuration, back up the deployment's .env and .oauth-state
using its established backup procedure; keep these secrets off GitHub. Record
the deployed commit for rollback. This repository does not provide SSH access
or prove a server backup has been taken.

To add Documents while retaining the observed toolsets:

```dotenv
GORELO_TOOLSETS=core,tickets,time,billing,uptime,projects,forms,documents
GORELO_ENABLE_DESTRUCTIVE=0
```

Grant the Gorelo API key the Documents scope with the access required, restart
gorelo-mcp.service, and refresh the connector's tool list. No extra redirect
setting is required for the existing ChatGPT connection in this fork. Do not
replace the existing service unit or bind-address environment with upstream's
localhost-only installation example.

For rollback to pre-1.3.0 code, remove documents from GORELO_TOOLSETS and use
GORELO_ENABLE_DESTRUCTIVE=0 (not a list of names). Restore the recorded fork
commit and frozen dependencies. Preserve OAuth state.
