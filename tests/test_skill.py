"""The packaged skill must describe the library that exists.

A skill naming a parameter that was renamed is worse than no skill: an agent
trusts it. Every spec field, loader method, and export the skill names is
checked against the real surface.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

import xcfg
from xcfg import ConfigLoader, ConfigSpec

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "resources" / "skills" / "use-xcfg" / "SKILL.md"


@pytest.fixture(scope="module")
def text() -> str:
    assert SKILL.is_file(), "the use-xcfg skill is missing"
    return SKILL.read_text(encoding="utf-8")


def test_frontmatter_is_complete(text: str) -> None:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "skill is missing YAML frontmatter"
    block = match.group(1)
    assert "name: use-xcfg" in block
    assert re.search(r"^version: \d+\.\d+\.\d+$", block, re.MULTILINE)
    description = re.search(r"^description: (.+)$", block, re.MULTILINE)
    assert description and len(description.group(1)) > 120


def test_named_spec_fields_exist(text: str) -> None:
    """Every `ConfigSpec(field=...)` shown must be a real field."""
    fields = {f.name for f in dataclasses.fields(ConfigSpec)}
    named = set(re.findall(r"ConfigSpec\((\w+)=", text)) | set(
        re.findall(r"^\s{4}(\w+)=", text, re.MULTILINE)
    )
    unknown = {name for name in named if name not in fields}
    assert unknown == set(), f"skill names spec fields that do not exist: {unknown}"


def test_every_spec_field_is_documented(text: str) -> None:
    """An undocumented field is one nobody will discover."""
    undocumented = {f.name for f in dataclasses.fields(ConfigSpec) if f.name not in text}
    assert undocumented == set(), f"skill omits spec fields: {undocumented}"


def test_named_loader_methods_exist(text: str) -> None:
    for method in set(re.findall(r"LOADER\.(\w+)\(", text)):
        assert hasattr(ConfigLoader, method), f"skill names a missing method: {method}"


def test_named_load_arguments_exist(text: str) -> None:
    import inspect

    accepted = set(inspect.signature(ConfigLoader.load).parameters)
    accepted |= set(inspect.signature(ConfigLoader.load_raw).parameters)
    for argument in set(re.findall(r"load(?:_raw)?\((\w+)=", text)):
        assert argument in accepted, f"skill names a missing load argument: {argument}"


def test_named_exports_exist(text: str) -> None:
    for line in re.findall(r"^from xcfg import (.+)$", text, re.MULTILINE):
        for name in (part.strip().split(" as ")[0] for part in line.split(",")):
            assert name in xcfg.__all__, f"skill imports a missing export: {name}"


def test_the_nxm_lesson_is_stated(text: str) -> None:
    """The layout mistake is the reason this skill exists."""
    assert "N × M" in text or "N x M" in text
    assert "N + M" in text
