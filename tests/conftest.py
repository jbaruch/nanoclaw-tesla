"""Make the shipped script modules importable and keep tests hermetic."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for scripts in (
    ROOT / "skills" / "tessie-ops" / "scripts",
    ROOT / "skills" / "tessie-watch" / "scripts",
    Path(__file__).resolve().parent,
):
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
