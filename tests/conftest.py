"""Shared fixtures: a small application config tree built in a temp dir."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, Field

from xcfg import ConfigLoader, ConfigSpec


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DatabaseSettings(Section):
    driver: str = "sqlite"
    pool_size: int = Field(default=5, ge=1)


class OutputSettings(Section):
    directory: str = "out"
    verbose: bool = False


class Settings(Section):
    database: DatabaseSettings = DatabaseSettings()
    output: OutputSettings = OutputSettings()


LoaderFactory = Callable[..., ConfigLoader]


@pytest.fixture
def config_root(tmp_path: Path) -> Path:
    """A packaged-config tree: a default env, a named env, and two profiles."""
    root = tmp_path / "resources" / "config"
    (root / "database").mkdir(parents=True)

    (root / "config.default.yml").write_text("database: sqlite\noutput:\n  directory: out\n")
    (root / "config.staging.yml").write_text("database: postgres\n")
    (root / "database" / "sqlite.yml").write_text("driver: sqlite\npool_size: 1\n")
    (root / "database" / "postgres.yml").write_text("driver: postgres\npool_size: 20\n")
    return root


@pytest.fixture
def make_loader(config_root: Path) -> LoaderFactory:
    """Build a loader over the fixture tree, with spec fields overridable."""

    def _make(**overrides: object) -> ConfigLoader:
        fields: dict[str, object] = {
            "config_root": config_root,
            "env_prefix": "MYAPP_",
            "profiled_sections": ("database",),
            "app_name": "myapp",
            "project_dir": ".myapp",
        }
        fields.update(overrides)
        return ConfigLoader(ConfigSpec(**fields), Settings)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def loader(make_loader: LoaderFactory) -> ConfigLoader:
    return make_loader()
