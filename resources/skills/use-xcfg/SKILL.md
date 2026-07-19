---
name: use-xcfg
description: Use when adding, structuring, or reviewing layered YAML configuration in a Python application with xcfg — declaring a ConfigSpec, laying out resources/config so profiles compose additively instead of combinatorially, deciding what belongs in a profile versus inline versus a model default, wiring the loader into an application's own error family, and adopting xcfg in a project that already has a hand-rolled loader. Covers the string-or-mapping profile rule, env configs extending the default, per-source rules, and the N x M layout mistake that looks correct until a second axis appears.
version: 0.1.0
---

# Using xcfg

xcfg composes configuration from several places — packaged defaults, a named
environment, user and project files, environment variables, explicit overrides
— and validates the result with a pydantic model **the application owns**.

The library owns the *mechanism*. The model, the YAML, and every policy
decision stay with the application.

## When to invoke

Trigger this skill when:

- adding configuration to an application, or reviewing how it is laid out
- deciding whether a setting belongs in a profile, inline, or a model default
- adopting xcfg in a project with a hand-rolled loader
- a config directory is growing faster than the number of things being
  configured — the symptom of the mistake below

## The mistake worth naming first

The layout inverts easily, and the inverted form looks reasonable until a
second axis of variation appears.

**Wrong — a profile is a directory of sections:**

```
resources/config/
  default/         render.yaml  llm.yaml  paths.yaml
  gitbook/         render.yaml
  gitbook-openai/  render.yaml  llm.yaml     ← re-states render
  github-openai/   render.yaml  llm.yaml     ← re-states render
```

Every combination of choices needs its own directory, and each one restates the
axes it did not change. **N × M**, and the duplicates drift.

**Right — a section is a directory of profiles, and an env config picks one of each:**

```
resources/config/
  config.default.yaml    render: github
                         llm: bedrock
                         paths: {...}          # inline; does not vary
  config.gitbook.yaml    render: gitbook       # states only what changes
  render/                github.yaml  gitbook.yaml
  llm/                   bedrock.yaml  openai.yaml
```

**N + M.** A new render flavour is one file. A new provider is one file. Any
combination is a two-line env config.

The tell that you have it backwards: adding one variant means copying settings
that have nothing to do with the thing you changed.

## Declaring the spec

```python
from pathlib import Path
from xcfg import ConfigLoader, ConfigSpec

SPEC = ConfigSpec(
    config_root=Path(__file__).resolve().parents[2] / "resources" / "config",
    config_name="config.yaml",        # the suffix every config file shares
    profiled_sections=("render", "llm"),
    env_prefix="MYAPP_",              # MYAPP_RENDER__TRANSTYPE=...
    env_name_var="MYAPP_PROFILE",     # defaults to MYAPP_ENV
    env_extends_default=True,         # an env states only what it changes
    app_name="myapp",                 # ~/.config/myapp/config.yaml
    project_dir=".myapp",             # ./.myapp/config.yaml, found by walking up
)

LOADER = ConfigLoader(SPEC, Settings)   # Settings is your pydantic model
settings = LOADER.load(env_name="gitbook")
```

Every layer is optional. An application with a single config file sets only
`config_root`.

**Keep every config file on one suffix.** The suffix comes from `config_name`
and applies to env configs and profiles alike; mixing `.yml` and `.yaml` makes
a profile silently unfindable.

## Layer order

Base config, in order:

1. an explicit path — the `config_path` argument, or `MYAPP_CONFIG`
2. a named env — the `env_name` argument, or `MYAPP_PROFILE`, loading `config.<name>.yaml`
3. otherwise `config.default.yaml`

Then, later winning: user config → project config → `MYAPP_<SECTION>__<KEY>`
env vars → dotted overrides. Merging is deep, so a layer that sets one key
leaves its siblings intact. Scalars from the environment and from overrides are
parsed as YAML parses them, so `"20"` becomes an `int`.

With `env_extends_default=True`, a named env layers *over* the default rather
than replacing it. Without it every env config must restate every shared
section — the same duplication as the wrong layout, one level up.

## What goes where

| Put it in | When | Example |
| --- | --- | --- |
| a profile, `<section>/<name>.yaml` | it varies with a choice, independently of other sections | a render flavour, an LLM provider |
| inline in the env config | it does not vary by scenario | paths, file markers, run policy |
| a model default | it is the sensible value and rarely stated | timeouts, list defaults |

Two judgement calls that recur:

- **Provider-specific limits go in the provider profile**, not inline. Timeouts
  and concurrency differ per provider; putting them inline forces every
  provider to share one number.
- **A setting only one profile overrides may still belong inline.** If a
  cleanup rule is corpus-wide and one flavour happens not to change it, inline
  is right — otherwise every profile must repeat it.

## Wiring it into an application

Delegate the mechanism; keep the surface. A good adapter preserves the
application's existing `load_config` signature so no call site changes:

```python
def load_config(profile: str | None = None) -> Config:
    load_secrets()                     # yours; xcfg does not do secrets
    name = profile or os.environ.get("MYAPP_PROFILE") or "default"
    merged = LOADER.load_raw(env_name=None if name == "default" else name)
    return Config(profile=name, **merged)
```

**Translate errors into the application's own family** rather than letting
`xcfg.ConfigError` escape — the application's error type is its contract:

```python
from xcfg import ConfigError as XcfgConfigError

try:
    settings = LOADER.load(...)
except XcfgConfigError as exc:
    raise MyAppConfigError(str(exc)) from exc
```

Prefer checking a precondition over matching an error message. To keep a
"missing profile is a missing file" contract, test the path:

```python
path = SPEC.env_config_path(name)
if not path.is_file():
    raise FileNotFoundError(f"Config profile not found: {name} (expected {path})")
```

## Escape hatches for awkward applications

| Need | Use |
| --- | --- |
| defaults are package data, not a readable path | `load(base_config=mapping)` |
| the project root is resolved by the app, not by walking up | `load(project_path=...)` |
| the user dir comes from `platformdirs`, not XDG | `ConfigSpec(user_config_dir=...)` |
| `${VAR}` placeholders in file values | `ConfigSpec(file_layer_transform=...)` |
| defaults live under another filename | `ConfigSpec(default_config=...)` |
| the explicit-path env var is not `<PREFIX>CONFIG` | `ConfigSpec(config_env_var=...)` |
| env vars nest with something other than `__` | `ConfigSpec(env_nested_delimiter=...)` |
| a top-level key is loader machinery, not a setting | `ConfigSpec(non_settings_keys=(...))` |

`file_layer_transform` runs over the merged file layers *before* environment
overrides, so env values are not re-substituted.

`non_settings_keys` strips top-level keys the loader consumes before the model
validates, which matters when the model uses `extra="forbid"`. The
`source_rules_key` below is stripped automatically.

## Per-source rules

When a setting belongs to one *input* rather than a whole tree, declare
`source_rules_key` and bind by glob:

```yaml
sources:
  "*measure-anything*": {chaptering: toc-depth1}
```

```python
settings = LOADER.load(source=Path("measure-anything.mobi"))
LOADER.matching_source_rules(path)   # which rules applied
```

Patterns match the full path and the bare filename. Rules apply after the file
layers and before explicit overrides — specific enough to beat a project
default, never specific enough to beat a flag. The key never reaches the model.

## Discovery and diagnostics

```python
LOADER.available_envs()               # ("default", "gitbook")
LOADER.available_profiles("render")   # ("github", "gitbook")
LOADER.load_raw(...)                  # the merged mapping, before validation
```

Expose these in a `config` command: "what is in force, and what else could be"
is the question a user asks when configuration surprises them.

## Adopting xcfg in an existing project

1. **Do not move the models.** They stay pydantic and stay yours.
2. **Do not move secrets.** `.env` loading is not xcfg's business.
3. Check the existing merge. A hand-rolled `{**base, **overlay}` is *shallow* —
   overriding one nested key silently drops its siblings. This is the most
   common latent bug in a hand-rolled loader; `xcfg.deep_merge` is exported and
   fixes it on its own if you adopt nothing else.
4. Restructure the YAML only if the layout is inverted. That is the change that
   removes N × M; adopting the loader without it fixes merging and leaves the
   growth problem.
5. Preserve the public loader signature, then prove equivalence: load every
   profile with both implementations and compare `model_dump()`. Running the
   old loader from a `git worktree` of `HEAD` lets it read the old layout while
   the new one reads the new.

## Use `extra="forbid"`

```python
class Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
```

Without it a typo in a config file is silently ignored and the default applies
— the failure mode that wastes an afternoon. With it, `dpeth: 1` fails loudly
naming the field.
