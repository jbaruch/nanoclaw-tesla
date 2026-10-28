"""Every command path in the authored skills resolves to a co-shipped script."""

from __future__ import annotations

import re
import shlex

import pytest

from support import ROOT

INSTALLED_ROOT = re.compile(
    r"/home/node/\.claude/skills/tessl__(?P<skill>[a-z-]+)/scripts/(?P<file>[A-Za-z0-9_.-]+)"
)


def command_targets(markdown: str):
    """Every command statement must invoke one literal co-shipped script root."""
    targets = []
    for block in re.findall(r"```[^\n]*\n(.*?)```", markdown, re.DOTALL):
        for line in block.replace("\\\n", " ").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            assert "$(" not in line and "`" not in line, "computed shell invocation"
            lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|()")
            lexer.whitespace_split = True
            tokens = list(lexer)
            assert len(tokens) >= 2 and tokens[0] == "python3", "nonliteral script invocation"
            assert not any(re.fullmatch(r"[;&|()]+", token) for token in tokens), (
                "shell fallback or extra invocation"
            )
            match = INSTALLED_ROOT.fullmatch(tokens[1])
            assert match, f"wrong script root: {tokens[1]}"
            target = ROOT / "skills" / match["skill"] / "scripts" / match["file"]
            assert target.resolve().is_relative_to(ROOT.resolve()) and target.is_file(), (
                f"missing co-shipped script: {target}"
            )
            targets.append(target)
    return targets


def test_skill_command_blocks_point_at_real_scripts() -> None:
    found = 0
    for skill_md in sorted((ROOT / "skills").glob("*/SKILL.md")):
        found += len(command_targets(skill_md.read_text(encoding="utf-8")))
    assert found >= 8


@pytest.mark.parametrize(
    "command",
    [
        "python3 /tmp/tessie-read.py state",
        "python3 .tessl/plugins/jbaruch/nanoclaw-tesla/"
        "skills/tessie-ops/scripts/tessie-read.py state",
        'python3 "$(pwd)/skills/tessie-ops/scripts/tessie-read.py" state',
        "ROOT=/home/node/.claude/skills/tessl__tessie-ops\n"
        'python3 "$ROOT/scripts/tessie-read.py" state',
        "python3 /home/node/.claude/skills/tessl__tessie-ops/scripts/tessie-read.py "
        "state || python3 /tmp/fallback.py",
        "python3 /home/node/.claude/skills/tessl__tessie-ops/scripts/missing.py",
    ],
)
def test_unapproved_added_script_invocations_are_not_silently_ignored(command):
    with pytest.raises(AssertionError):
        command_targets(f"```bash\n{command}\n```")


def test_shipped_scripts_are_executable_entry_points() -> None:
    for script in sorted((ROOT / "skills").glob("*/scripts/tessie-*.py")):
        text = script.read_text(encoding="utf-8")
        assert script.stat().st_mode & 0o111, script.name
        assert text.startswith("#!/usr/bin/env python3"), script.name
        assert 'if __name__ == "__main__":' in text, script.name
