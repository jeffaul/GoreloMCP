# AulTECH deployment

Upstream: Coach40oz/GoreloMCP. Fork: jeffaul/GoreloMCP.
Production branch: main. Service: gorelo-mcp.service.

## Minimal differences

All API tools, validation, OAuth security, settings parsing and upstream tests
are unchanged. There are no custom asset-move, invoice, document or maintenance
behaviour overrides.

Only main.py has an application change: pass MCP_BIND_HOST to the HTTP listener,
falling back to upstream localhost. Configuration uses upstream's process
environment and .env support. No redirect domains are hardcoded in the fork.

Relevant server settings (no variable renames):

```dotenv
MCP_BIND_HOST=172.26.3.23
MCP_EXTRA_REDIRECT_DOMAINS=chatgpt.com,openai.com
GORELO_TOOLSETS=core,tickets,time,billing,uptime,projects,forms,documents
GORELO_ENABLE_DESTRUCTIVE=0
```

The bind address is specific to this installation. Preserve the server's actual
.env, systemd environment, credentials and .oauth-state across updates.
Destructive tools and public sharing stay disabled under the current settings.

## Update and deploy

1. Fetch upstream main and merge it into a fork branch.
2. Resolve changes to the listener line and the deployment workflow only.
   Prefer upstream implementations for tools and tests; configure settings rather
   than introducing behaviour patches.
3. Open a PR. The tests workflow runs the complete offline suite once, including
   tests/test_deployment_configuration.py. New PR revisions cancel obsolete runs.
4. Merge after checks pass. The same workflow tests main once, then calls the
   existing authenticated deployment endpoint using PROD_DEPLOY_URL and
   PROD_DEPLOY_TOKEN. It does not deploy PRs or deploy after a failed test.
5. Confirm deployment completion and health_check, including the new spec hash,
   expected toolsets and destructive=false.

There is one workflow, no separate customization-report script, and no duplicate
full-suite job per revision. Run focused startup tests locally when changing the
startup configuration; CI owns the full regression run. Do not run the live write
harness during a routine update.
