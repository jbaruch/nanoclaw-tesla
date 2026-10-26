---
alwaysApply: true
description: Tessie credentials live in the OneCLI vault; the agent never holds, requests or prints a token
---

# Tessie Credentials

## Where the Credential Lives

- The Tessie access token lives in the OneCLI vault as secret `Tessie API token`, host pattern `api.tessie.com`
- The host broker uses the existing normal OneCLI gateway route
- Reuse the configured Tessie key without creating another credential or identity
- The OneCLI gateway injects `Authorization` on the wire; no container holds the token
- Scripts under `skills/tessie-ops/scripts/` use version-1 native IPC
- Missing host authority denies the operation without direct HTTP fallback

## What the Agent Does

- Reach Tessie only through the `tessie-ops` scripts
- Never call `api.tessie.com` with `curl`, `WebFetch`, a browser or ad-hoc code
- Never ask the user for a Tessie token, and never paste one into chat, a file, a log or a commit
- Never add a token to `.env`, `.env.example`, a compose file or the plugin repository
- Never pass a URL, host or `Authorization` value to a script

## When Authentication Fails

- HTTP 401 means the vaulted token is missing, expired or revoked
- Report the script's stderr diagnostic and point the user to `docs/setup.md` Recovery
- Do not retry in a loop and do not look for another credential
