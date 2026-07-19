"""Validation and error reporting."""

from __future__ import annotations

from pathlib import Path

import pytest

from xcfg import ConfigError, ConfigLoader, deep_merge, set_dotted


def test_unknown_keys_are_rejected_rather_than_ignored(
    loader: ConfigLoader, tmp_path: Path
) -> None:
    """A typo must fail loudly, not vanish."""
    path = tmp_path / "typo.yml"
    path.write_text("output:\n  drectory: x\n")
    with pytest.raises(ConfigError, match="invalid configuration"):
        loader.load(config_path=path, environ={})


def test_out_of_range_values_are_rejected(loader: ConfigLoader, tmp_path: Path) -> None:
    path = tmp_path / "bad.yml"
    path.write_text("database:\n  driver: x\n  pool_size: 0\n")
    with pytest.raises(ConfigError, match="pool_size"):
        loader.load(config_path=path, environ={})


def test_error_names_the_offending_field(loader: ConfigLoader, tmp_path: Path) -> None:
    path = tmp_path / "bad.yml"
    path.write_text("database:\n  driver: x\n  pool_size: not-a-number\n")
    with pytest.raises(ConfigError) as caught:
        loader.load(config_path=path, environ={})
    assert "database.pool_size" in str(caught.value)


def test_load_raw_returns_the_merged_mapping(loader: ConfigLoader) -> None:
    raw = loader.load_raw(environ={})
    assert raw["database"]["driver"] == "sqlite"


def test_deep_merge_recurses_into_nested_mappings() -> None:
    merged = deep_merge({"a": {"b": 1, "c": 2}}, {"a": {"c": 3}})
    assert merged == {"a": {"b": 1, "c": 3}}


def test_deep_merge_does_not_mutate_its_inputs() -> None:
    base = {"a": {"b": 1}}
    deep_merge(base, {"a": {"b": 2}})
    assert base == {"a": {"b": 1}}


def test_overlay_scalar_replaces_a_mapping() -> None:
    assert deep_merge({"a": {"b": 1}}, {"a": 5}) == {"a": 5}


def test_set_dotted_creates_intermediate_levels() -> None:
    target: dict[str, object] = {}
    set_dotted(target, "a.b.c", 1)
    assert target == {"a": {"b": {"c": 1}}}


def test_set_dotted_replaces_a_non_mapping_on_the_path() -> None:
    target: dict[str, object] = {"a": 5}
    set_dotted(target, "a.b", 1)
    assert target == {"a": {"b": 1}}
