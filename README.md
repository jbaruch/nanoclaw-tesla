# nanoclaw-tesla

[![tessl](https://img.shields.io/endpoint?url=https%3A%2F%2Fapi.tessl.io%2Fv1%2Fbadges%2Fjbaruch%2Fnanoclaw-tesla)](https://tessl.io/registry/jbaruch/nanoclaw-tesla)

A NanoClaw overlay plugin that reads and controls Tesla vehicles through the [Tessie](https://developer.tessie.com/llms.txt) REST API. Everything the agent does is a deterministic script: the model picks the script and words the result, it does not drive the API call by call.

## Status

This is the Tesla1 foundation ([issue #1](https://github.com/jbaruch/nanoclaw-tesla/issues/1)): the Tessie client, vehicle allowlist, chat authorization, cached reads, confirmed controls, a no-wake health check, packaging and CI. Tesla2–6 remain separate work. Running-late ([#7](https://github.com/jbaruch/nanoclaw-tesla/issues/7)) adds the event-bound consumer and protected host companion; source publication still requires installed authority and actual native acceptance. Solar and Powerwall ([#8](https://github.com/jbaruch/nanoclaw-tesla/issues/8)) stays deferred.

Merged source is not an installed plugin and a passing test suite is not a live smoke test; see `docs/setup.md` for the owner steps that remain.

## What it guarantees

- **Credential stays in the vault.** The host broker uses the existing normal OneCLI gateway and vaulted Tessie key. Scripts use native IPC; key values never enter containers, logs or chat.
- **Default deny.** The protected host policy selects current non-archived vehicles dynamically from fresh Tessie inventory. Active OWNER and DRIVER vehicles are admitted under that explicit owner predicate; unknown access and archived vehicles are refused. Unnamed vehicles receive stable aliases. Explicit protected lists remain an optional mode.
- **Chat authorization.** Controls need a control or owner chat; precise location needs an owner chat. The host resolves the registered source directory and enforces protected VIN/role policy on every request; agent-writable allowlists grant nothing.
- **Reads never wake the car.** Each read probes status and uses Tessie's cache. No wake action exists.
- **Acceptance is not state.** Tessie's `result: true` is reported as `accepted`; only matching cached state at or after actual host dispatch produces `confirmed`. Failed readback preserves accepted receipts.
- **Bounded retries.** One request per call; controls ask Tessie for at most 3 attempts. HTTP 429, 408 and 5xx fail with a diagnostic instead of looping.

## Skills

| Skill | Purpose |
| --- | --- |
| `tessie-ops` | Action router: list vehicles, inspect the allowlist, read state, read location, preview and run controls, confirm state, tag drives |
| `tessie-running-late` | Event-specific approval, native three-minute polling and a shared two-message limit across owner and approved recipient |
| `tessie-watch` | Daily precheck that wakes the agent only for a low unplugged battery, a credential or API failure, or unreadable state |

## Rules

| Rule | Purpose |
| --- | --- |
| `rules/running-late-approval.md` | Native per-event delegation, fixed host transport and the shared delivery budget |
| `rules/tessie-credentials.md` | The token lives in the vault; the agent never holds, requests or prints it |
| `rules/vehicle-allowlist.md` | Current vehicle access follows the protected dynamic or explicit host predicate |
| `rules/provider-identity.md` | Provider namespace and declared surfaces remain consistent |
| `rules/location-privacy.md` | Precise location stays in owner chats |
| `rules/command-authorization.md` | Controls need an authorized chat, a named plan and a reported outcome |
| `rules/nanoclaw-skill-root.md` | Command blocks use the container's skill root |

## Install

Install the published provider with `tessl install jbaruch/nanoclaw-tesla`.

The overlay loads per chat through `containerConfig.additionalTiles` with the bare name `nanoclaw-tesla`, on a protected owner-authorized chat, including the existing owner main chat. Token, allowlist, install and verification steps are in `docs/setup.md`; the supported commands and their limits are in `docs/command-surface.md`.

## Development

```bash
python3 -m venv .venv && . .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.lock
python -m pre_commit install
python -m ruff check tests skills && python -m ruff format --check tests skills
python -m pyright
python -m pytest
```

The normal commit hook runs pinned Gitleaks source through pre-commit 4.7.0. Keep the hook installed; Renovate’s enabled pre-commit manager in `renovate.json` renews its source SHA.

Tests use synthetic VINs, a frozen clock and a fake transport; nothing reaches Tessie. `requirements-dev.lock` is compiled from `requirements-dev.txt` with `uv pip compile requirements-dev.txt --python-version 3.11 --generate-hashes -o requirements-dev.lock`.

The owner enrolls this repository in the existing central review GitHub App. Publication uses the repository `TESSL_TOKEN` secret; never create a broad review token or store CI credentials in `.env`.

The development `jbaruch/coding-policy` dependency pins 0.5.10. This new provider
is outside the host contract’s enumerated floating-manifest set. No committed
scanner tracks the Tessl registry; the maintainer checks it monthly with
`tessl update jbaruch/coding-policy --yes` and lands any reviewed manifest update
as a separate change. Dependabot renews external action digests; Renovate tracks
the exact CI Python patch weekly within 3.11.
