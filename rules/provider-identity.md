---
alwaysApply: false
applyTo: ".tessl-plugin/plugin.json, README.md, tessl.json — when maintaining this provider's identity or installation references"
---

# Provider Identity

## Namespace

- Use `jbaruch/nanoclaw-tesla` as this plugin's provider name.
- Keep repository and registry references under that namespace.
- Keep installation references consistent with the manifest name.

## Declarations

- Declare committed rule paths in the manifest's `rules` field.
- Declare committed skill paths in the manifest's `skills` field.
- Keep declared paths inside this plugin.
- Synchronize README tables with the declared surfaces.

## Authority

- Provider metadata grants no account access or vehicle-control authority.
- Claim runtime features only after their implementation and acceptance.
- Follow the installed NanoClaw host contracts for runtime access.
