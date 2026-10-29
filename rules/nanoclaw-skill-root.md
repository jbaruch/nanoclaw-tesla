---
alwaysApply: false
applyTo: "skills/**/SKILL.md, skills/**/references/*.md — when writing or reviewing a command block that runs a co-shipped script"
---

# NanoClaw Skill Root

## Lookup

- NanoClaw installs each of this plugin's skills at `/home/node/.claude/skills/tessl__<skill>/` inside the agent container
- That directory is the only skill root the container mounts
- Command blocks invoke a co-shipped script as `python3 /home/node/.claude/skills/tessl__<skill>/scripts/<file>`
- `<skill>` is one of this plugin's skills: `tessie-ops`, `tessie-watch`, `tessie-running-late`, `tessie-charge`
- `<file>` is a script under `skills/<skill>/scripts/` in this repository
- No other root, fallback or computed lookup is used in a command block

## Scope

- Authored scope: the four skills' `SKILL.md` files
- Co-shipped targets: every `tessie-*.py` under those four skills' `scripts/` directories
- Input and output contracts: each script's own docstring

## Authority

- This rule names a path and grants no runtime authority
- It waives no check a script applies after the lookup
- Regression coverage: `tests/test_skill_script_paths.py` resolves every such command path to an existing co-shipped script
