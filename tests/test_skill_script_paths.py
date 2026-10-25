"""Every command path in the authored skills resolves to a co-shipped script."""

from __future__ import annotations

import re

from support import ROOT

INSTALLED_ROOT = re.compile(
    r"/home/node/\.claude/skills/tessl__(?P<skill>[a-z-]+)/scripts/(?P<file>[A-Za-z0-9_.-]+)"
)


def test_skill_command_blocks_point_at_real_scripts() -> None:
    found = 0
    for skill_md in sorted((ROOT / "skills").glob("*/SKILL.md")):
        for match in INSTALLED_ROOT.finditer(skill_md.read_text(encoding="utf-8")):
            target = ROOT / "skills" / match["skill"] / "scripts" / match["file"]
            assert target.is_file(), f"{skill_md.relative_to(ROOT)} names missing {target}"
            found += 1
    assert found >= 8


def test_shipped_scripts_are_executable_entry_points() -> None:
    for script in sorted((ROOT / "skills").glob("*/scripts/tessie-*.py")):
        text = script.read_text(encoding="utf-8")
        assert text.startswith("#!/usr/bin/env python3"), script.name
        assert 'if __name__ == "__main__":' in text, script.name
