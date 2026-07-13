#!/usr/bin/env python3
"""Validate the dual Claude Code + Codex plugin layout without third-party deps."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SKILLS = [
    "jitx",
    "jitx-component-modeler",
    "jitx-circuit-builder",
    "jitx-substrate-modeler",
    "jitx-physical-layout",
    "jitx-interconnect-constraints",
    "jitx-pin-assignment",
    "jitx-code-review",
    "jitx-mechanical",
]
NAME_RE = re.compile(r"^[a-z0-9-]+$")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plugin_root", nargs="?", default=".")
    args = parser.parse_args()
    root = Path(args.plugin_root).resolve()
    errors: list[str] = []

    validate_manifests(root, errors)
    validate_skills(root, errors)
    validate_no_old_layout(root, errors)

    if errors:
        print("Dual plugin validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Dual plugin validation passed: {root}")
    return 0


def load_json(path: Path, errors: list[str]) -> dict:
    if not path.is_file():
        errors.append(f"missing {path.relative_to(path.parents[1]) if len(path.parents) > 1 else path}")
        return {}
    try:
        value = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path} must contain a JSON object")
        return {}
    return value


def validate_manifests(root: Path, errors: list[str]) -> None:
    codex = load_json(root / ".codex-plugin" / "plugin.json", errors)
    if codex:
        if codex.get("name") != "jitx-skills":
            errors.append("Codex plugin name must be jitx-skills")
        if codex.get("skills") != "./skills/":
            errors.append("Codex plugin must use skills path ./skills/")
        if "interface" not in codex:
            errors.append("Codex plugin manifest must include interface metadata")

    claude = load_json(root / ".claude-plugin" / "plugin.json", errors)
    if claude and claude.get("name") != "jitx-skills":
        errors.append("Claude plugin name must be jitx-skills")

    marketplace = load_json(root / ".claude-plugin" / "marketplace.json", errors)
    if marketplace and marketplace.get("name") != "jitx":
        errors.append("Claude marketplace name must be jitx")
    plugins = marketplace.get("plugins") if marketplace else None
    if isinstance(plugins, list) and plugins:
        skill_paths = plugins[0].get("skills")
        expected = [f"./skills/{skill}" for skill in SKILLS]
        if skill_paths != expected:
            errors.append("Claude marketplace skill paths must point at ./skills/<skill>")
    else:
        errors.append("Claude marketplace must contain at least one plugin entry")

    codex_marketplace = load_json(root / ".agents" / "plugins" / "marketplace.json", errors)
    if codex_marketplace:
        if codex_marketplace.get("name") != "jitx":
            errors.append("Codex marketplace name must be jitx")
        entries = codex_marketplace.get("plugins")
        if isinstance(entries, list) and len(entries) == 1:
            entry = entries[0]
            if entry.get("name") != "jitx-skills":
                errors.append("Codex marketplace plugin entry must be named jitx-skills")
            if entry.get("source") != {"source": "local", "path": "./"}:
                errors.append("Codex marketplace plugin source must be local at ./")
            policy = entry.get("policy") or {}
            if policy.get("installation") != "AVAILABLE":
                errors.append("Codex marketplace installation policy must be AVAILABLE")
            if policy.get("authentication") != "ON_INSTALL":
                errors.append("Codex marketplace authentication policy must be ON_INSTALL")
            if entry.get("category") != "Developer Tools":
                errors.append("Codex marketplace category must be Developer Tools")
        else:
            errors.append("Codex marketplace must contain exactly one plugin entry")


def parse_frontmatter(path: Path, errors: list[str]) -> dict[str, str]:
    text = path.read_text()
    match = FRONTMATTER_RE.match(text)
    if not match:
        errors.append(f"{path} must start with YAML frontmatter")
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.startswith(" "):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"')
    return fields


def validate_skills(root: Path, errors: list[str]) -> None:
    skills_root = root / "skills"
    if not skills_root.is_dir():
        errors.append("missing skills/ directory")
        return
    actual = sorted(path.name for path in skills_root.iterdir() if path.is_dir() and not path.name.startswith("."))
    if actual != sorted(SKILLS):
        errors.append(f"skills/ directories mismatch: {actual}")
    for skill in SKILLS:
        skill_dir = skills_root / skill
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            errors.append(f"{skill} missing SKILL.md")
            continue
        frontmatter = parse_frontmatter(skill_md, errors)
        name = frontmatter.get("name")
        description = frontmatter.get("description")
        if name != skill:
            errors.append(f"{skill} frontmatter name must match directory")
        if not name or not NAME_RE.fullmatch(name):
            errors.append(f"{skill} frontmatter name must be lowercase kebab-case")
        if not description:
            errors.append(f"{skill} missing description")
        agent_yaml = skill_dir / "agents" / "openai.yaml"
        if not agent_yaml.is_file():
            errors.append(f"{skill} missing agents/openai.yaml")
        elif "default_prompt:" not in agent_yaml.read_text():
            errors.append(f"{skill} agents/openai.yaml missing default_prompt")


def validate_no_old_layout(root: Path, errors: list[str]) -> None:
    for skill in SKILLS:
        if (root / skill).exists():
            errors.append(f"old root-level skill directory remains: {skill}")
    for path in root.rglob("*.md"):
        text = path.read_text(errors="ignore")
        if "jitx-skills:jitx-" in text:
            errors.append(f"old Claude-only skill reference remains in {path.relative_to(root)}")
        if 'skill: "jitx-skills:' in text:
            errors.append(f"old Skill tool invocation remains in {path.relative_to(root)}")


if __name__ == "__main__":
    sys.exit(main())
