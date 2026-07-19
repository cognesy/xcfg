# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
