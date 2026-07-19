"""Per-source rules: settings bound to the document being processed."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import LoaderFactory
from xcfg import ConfigError, ConfigLoader, matches_source


@pytest.fixture
def rules_loader(make_loader: LoaderFactory) -> ConfigLoader:
    return make_loader(source_rules_key="sources")


def _with_rules(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "rules.yml"
    path.write_text(body)
    return path


def test_rule_applies_to_a_matching_source(rules_loader: ConfigLoader, tmp_path: Path) -> None:
    path = _with_rules(tmp_path, 'sources:\n  "*deep*": {database: postgres}\n')
    settings = rules_loader.load(config_path=path, environ={}, source=Path("deep-book.epub"))
    assert settings.database.driver == "postgres"


def test_rule_leaves_other_sources_alone(rules_loader: ConfigLoader, tmp_path: Path) -> None:
    path = _with_rules(tmp_path, 'sources:\n  "*deep*": {database: postgres}\n')
    settings = rules_loader.load(config_path=path, environ={}, source=Path("other.epub"))
    assert settings.database.driver == "sqlite"


def test_rules_are_ignored_without_a_source(rules_loader: ConfigLoader, tmp_path: Path) -> None:
    path = _with_rules(tmp_path, 'sources:\n  "*": {database: postgres}\n')
    assert rules_loader.load(config_path=path, environ={}).database.driver == "sqlite"


def test_explicit_override_still_beats_a_rule(rules_loader: ConfigLoader, tmp_path: Path) -> None:
    path = _with_rules(tmp_path, 'sources:\n  "*": {database: postgres}\n')
    settings = rules_loader.load(
        config_path=path,
        environ={},
        source=Path("a.epub"),
        overrides={"database.driver": "mysql"},
    )
    assert settings.database.driver == "mysql"


def test_rules_key_never_reaches_the_model(rules_loader: ConfigLoader, tmp_path: Path) -> None:
    """The model forbids extra keys; `sources` is loader machinery."""
    path = _with_rules(tmp_path, 'sources:\n  "*": {database: postgres}\n')
    assert rules_loader.load(config_path=path, environ={}, source=Path("a.epub")) is not None


def test_malformed_rule_is_reported(rules_loader: ConfigLoader, tmp_path: Path) -> None:
    path = _with_rules(tmp_path, 'sources:\n  "*": not-a-mapping\n')
    with pytest.raises(ConfigError, match="must be a mapping"):
        rules_loader.load(config_path=path, environ={}, source=Path("a.epub"))


def test_matching_rules_are_reportable(rules_loader: ConfigLoader, tmp_path: Path) -> None:
    path = _with_rules(tmp_path, 'sources:\n  "*deep*": {database: postgres}\n')
    matched = rules_loader.matching_source_rules(Path("deep.epub"), config_path=path, environ={})
    assert matched == ("*deep*",)


def test_source_rules_disabled_when_no_key_is_declared(
    loader: ConfigLoader, tmp_path: Path
) -> None:
    path = _with_rules(tmp_path, 'sources:\n  "*": {database: postgres}\n')
    with pytest.raises(ConfigError, match="invalid configuration"):
        loader.load(config_path=path, environ={}, source=Path("a.epub"))


def test_patterns_match_full_path_and_filename() -> None:
    assert matches_source(Path("/corpus/deep/x.epub"), "*/deep/*")
    assert matches_source(Path("/corpus/deep/x.epub"), "x.epub")
    assert not matches_source(Path("/corpus/deep/x.epub"), "*.pdf")
