"""Manifest, declaration, lock and doc-surface consistency."""

from __future__ import annotations

import ast
import hashlib
import json
import re

from support import ROOT

TRIGGERS_SHA256 = "f512170550bec91503a77b19469aaff3a414731bbbd07c492113dfa6490231bf"


def frontmatter(path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, f"{path} has no frontmatter"
    fields = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "#")):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip('"')
    return fields


def test_herdr_declaration_is_the_reviewed_artifact_byte_for_byte() -> None:
    digest = hashlib.sha256((ROOT / ".herdr" / "triggers.json").read_bytes()).hexdigest()
    assert digest == TRIGGERS_SHA256


def test_plugin_manifest_declares_every_skill_and_rule_that_exists() -> None:
    manifest = json.loads((ROOT / ".tessl-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "jbaruch/nanoclaw-tesla"
    assert manifest["version"] == "0.1.0"
    assert manifest["private"] is False
    for skill in manifest["skills"]:
        assert (ROOT / skill / "SKILL.md").is_file(), skill
    for rule in manifest["rules"]:
        assert (ROOT / rule).is_file(), rule
    on_disk_skills = {f"skills/{p.parent.name}" for p in (ROOT / "skills").glob("*/SKILL.md")}
    on_disk_rules = {f"rules/{p.name}" for p in (ROOT / "rules").glob("*.md")}
    assert set(manifest["skills"]) == on_disk_skills
    assert set(manifest["rules"]) == on_disk_rules


def test_tessl_json_floats_the_policy_dependency() -> None:
    config = json.loads((ROOT / "tessl.json").read_text(encoding="utf-8"))
    assert config["mode"] == "managed"
    assert config["dependencies"]["jbaruch/coding-policy"]["version"] == "latest"


def test_cadence_skill_declares_both_cadence_and_script() -> None:
    watch = frontmatter(ROOT / "skills" / "tessie-watch" / "SKILL.md")
    assert watch["cadence"].endswith("(TZ=local)")
    script = watch["script"]
    assert script.endswith(".py") and ".." not in script
    assert (ROOT / "skills" / "tessie-watch" / script).is_file()
    ops = frontmatter(ROOT / "skills" / "tessie-ops" / "SKILL.md")
    assert "cadence" not in ops and "script" not in ops


def test_skill_frontmatter_has_name_and_trigger_description() -> None:
    for skill_md in (ROOT / "skills").glob("*/SKILL.md"):
        fields = frontmatter(skill_md)
        assert fields["name"] == skill_md.parent.name
        assert len(fields["description"]) > 40


def test_rules_have_frontmatter_and_an_h1() -> None:
    for rule in (ROOT / "rules").glob("*.md"):
        text = rule.read_text(encoding="utf-8")
        assert text.startswith("---\n"), rule.name
        fields = frontmatter(rule)
        assert fields["alwaysApply"] in {"true", "false"}
        if fields["alwaysApply"] == "false":
            assert " — " in fields["applyTo"], rule.name
        assert re.search(r"^# [A-Z]", text, re.MULTILINE), rule.name


def test_dev_lock_pins_exactly_what_requirements_dev_declares() -> None:
    lock = (ROOT / "requirements-dev.lock").read_text(encoding="utf-8")
    for line in (ROOT / "requirements-dev.txt").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            assert f"\n{line.strip()} " in "\n" + lock, f"{line} missing from the hashed lock"
    assert "--hash=sha256:" in lock


def test_env_example_documents_the_vault_secret_and_holds_no_token() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "Tessie API token" in text and "dash.tessie.com/settings/api" in text
    assert "FLEET_DISPATCH_TOKEN=" not in text
    for line in text.splitlines():
        if "=" in line and not line.startswith("#"):
            assert line.split("=", 1)[1] == "", f"placeholder value in {line.split('=')[0]}"


def code_strings(path) -> list[str]:
    """String literals a script can send or compare, docstrings excluded."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docstrings.add(id(body[0].value))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def test_shipped_code_has_no_wake_or_energy_surface() -> None:
    for path in (ROOT / "skills").rglob("*.py"):
        for literal in code_strings(path):
            assert "energy_sites" not in literal, path.name
            assert "/wake" not in literal, path.name


def test_workflows_reference_files_the_repo_ships() -> None:
    publish = (ROOT / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")
    assert re.search(r"publish-plugin\.yml@[0-9a-f]{40}", publish)
    assert "stamp-changelog: true" in publish
    assert (ROOT / ".github" / "fleet-review-enabled").is_file()
    workflows = ROOT / ".github" / "workflows"
    assert all("FLEET_DISPATCH_TOKEN" not in path.read_text() for path in workflows.glob("*.yml"))
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "Unreleased" not in changelog
