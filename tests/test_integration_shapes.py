"""Capabilities earned by a second consuming application.

Each of these exists because alex needed it: it resolves its project root
itself, ships defaults under a different name, and resolves `${VAR}`
placeholders in file-sourced values.
"""

from __future__ import annotations

from pathlib import Path

from tests.conftest import LoaderFactory, Settings
from xcfg import ConfigLoader, ConfigSpec, RawConfig


def test_explicit_project_path_replaces_the_walk_up(loader: ConfigLoader, tmp_path: Path) -> None:
    """Apps that resolve their own root name the project layer directly."""
    root = tmp_path / "somewhere" / ".myapp"
    root.mkdir(parents=True)
    (root / "config.yml").write_text("output:\n  directory: explicit\n")
    settings = loader.load(project_path=root / "config.yml", environ={}, start_dir=tmp_path)
    assert settings.output.directory == "explicit"


def test_explicit_project_path_absent_is_not_an_error(loader: ConfigLoader, tmp_path: Path) -> None:
    settings = loader.load(project_path=tmp_path / "nope.yml", environ={})
    assert settings.output.directory == "out"


def test_explicit_project_path_wins_over_a_walk_up_candidate(
    loader: ConfigLoader, tmp_path: Path
) -> None:
    work = tmp_path / "work"
    (work / ".myapp").mkdir(parents=True)
    (work / ".myapp" / "config.yml").write_text("output:\n  directory: walked\n")
    explicit = tmp_path / "explicit.yml"
    explicit.write_text("output:\n  directory: named\n")
    settings = loader.load(project_path=explicit, start_dir=work, environ={})
    assert settings.output.directory == "named"


def test_default_config_can_live_under_another_name(config_root: Path, tmp_path: Path) -> None:
    """alex ships `defaults/config.yml`, not `config.default.yml`."""
    alt = tmp_path / "defaults"
    alt.mkdir()
    (alt / "config.yml").write_text("output:\n  directory: alt\n")
    loader = ConfigLoader(
        ConfigSpec(config_root=config_root, default_config=alt / "config.yml"), Settings
    )
    assert loader.load(environ={}).output.directory == "alt"


def test_file_layer_transform_resolves_placeholders(
    make_loader: LoaderFactory, tmp_path: Path
) -> None:
    """The `${VAR}` hook: applied to file values, before env overrides."""

    def expand(raw: RawConfig) -> RawConfig:
        out = dict(raw)
        output = dict(out.get("output", {}))
        if output.get("directory") == "${HOME_DIR}":
            output["directory"] = "expanded"
        out["output"] = output
        return out

    loader = make_loader(file_layer_transform=expand)
    path = tmp_path / "placeholder.yml"
    path.write_text("output:\n  directory: ${HOME_DIR}\n")
    assert loader.load(config_path=path, environ={}).output.directory == "expanded"


def test_transform_does_not_reapply_to_environment_values(
    make_loader: LoaderFactory,
) -> None:
    """Env values arrive after the transform, so they pass through untouched."""

    def mark(raw: RawConfig) -> RawConfig:
        out = dict(raw)
        output = dict(out.get("output", {}))
        output["directory"] = f"transformed:{output.get('directory', '')}"
        out["output"] = output
        return out

    loader = make_loader(file_layer_transform=mark)
    settings = loader.load(environ={"MYAPP_OUTPUT__DIRECTORY": "fromenv"})
    assert settings.output.directory == "fromenv"


def test_no_transform_is_the_default(loader: ConfigLoader) -> None:
    assert loader.load(environ={}).output.directory == "out"


def test_user_config_dir_can_be_dictated_by_the_app(
    make_loader: LoaderFactory, tmp_path: Path
) -> None:
    """alex uses platformdirs, which is not XDG on macOS.

    Without this, migrating an app to xcfg would silently change where its
    user config is read from.
    """
    user_dir = tmp_path / "Application Support" / "myapp"
    user_dir.mkdir(parents=True)
    (user_dir / "config.yml").write_text("output:\n  directory: platformdirs\n")
    loader = make_loader(user_config_dir=user_dir)
    settings = loader.load(environ={}, start_dir=tmp_path)
    assert settings.output.directory == "platformdirs"


def test_explicit_user_dir_ignores_xdg(make_loader: LoaderFactory, tmp_path: Path) -> None:
    xdg = tmp_path / "xdg"
    (xdg / "myapp").mkdir(parents=True)
    (xdg / "myapp" / "config.yml").write_text("output:\n  directory: xdg\n")
    chosen = tmp_path / "chosen"
    chosen.mkdir()
    (chosen / "config.yml").write_text("output:\n  directory: chosen\n")
    loader = make_loader(user_config_dir=chosen)
    settings = loader.load(environ={"XDG_CONFIG_HOME": str(xdg)}, start_dir=tmp_path)
    assert settings.output.directory == "chosen"
