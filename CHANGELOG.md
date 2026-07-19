# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - 2026-07-19

### Changed

- The package version now has a single source: `__version__` in
  `src/xcfg/__init__.py`, read by hatchling at build time. It was previously
  duplicated in `pyproject.toml`, where it had to be edited by hand.

### Added

- `justfile` with `dev`, `qa`, and `release` recipe groups.
- `tools/check_release_version.py`, asserting a tag matches the declared
  version before anything is built.
- `.github/workflows/release.yml`: tag-triggered, validates then gates then
  builds, attaches artifacts to a GitHub Release. PyPI publishing is opt-in
  via `workflow_dispatch` and uses OIDC trusted publishing — no stored token.
- `tests/test_release_pipeline.py`, locking the checker's behaviour and the
  workflow's ordering.

## [0.3.0] - 2026-07-19

### Added

- `load(base_config=...)` supplies the base layer as an already-loaded mapping,
  for defaults that do not live in a readable file. alex ships its defaults as
  package data and its architecture tests forbid reading resources by raw path,
  so it must supply them through its own `ResourceLoader`.

## [0.2.1] - 2026-07-19

### Added

- `ConfigSpec.user_config_dir` lets an application dictate its user-config
  directory instead of accepting the XDG derivation. Applications using
  `platformdirs` get a non-XDG location on macOS and Windows; without this,
  adopting xcfg would silently move where a user's config is read from.

## [0.2.0] - 2026-07-19

### Added

Three capabilities earned by a second consuming application (alex), each stated
generally rather than for that one caller:

- `load(project_path=...)` names the project layer directly, for applications
  that resolve their own project root instead of walking up from the working
  directory.
- `ConfigSpec.default_config` points at a base config that is not
  `<config_root>/config.default.yml`.
- `ConfigSpec.file_layer_transform` runs over the merged file layers before
  environment overrides — the hook for `${VAR}` placeholder resolution, which
  should apply to file-sourced values without re-applying to env values.

`RawConfig` now lives in `xcfg.spec` and is re-exported unchanged.

## [0.1.1] - 2026-07-19

### Changed

- Lowered `requires-python` to `>=3.10` and added 3.10 to the CI matrix. The
  first consuming application (cxtk) supports 3.10; a library should be the
  permissive side of that boundary.

## [0.1.0] - 2026-07-19

### Added

- `ConfigSpec` describing one application's configuration setup: config root,
  env prefix, profiled sections, user/project layers, per-source rules.
- `ConfigLoader` composing packaged defaults, a named env config, user config
  (XDG), project config (walk-up), environment variables, and dotted-path
  overrides into a validated pydantic model.
- String-or-mapping profile rule: a profiled section may name a profile file or
  be written inline, keeping profile files additive rather than combinatorial.
- Per-source rules binding settings to the input being processed, matched by
  glob against the full path and the filename.
- Discovery helpers: `available_envs`, `available_profiles`,
  `matching_source_rules`, and `load_raw` for diagnostics.
- `ConfigError` with actionable messages naming the alternatives or the field.

Extracted from three independent implementations (alex, pcmm, cxtk) that had
converged on the same shape.
