# xcfg

Layered, profile-composable configuration for Python applications.

Configuration arrives from several places at once — packaged defaults, a named
environment, a user file, a project file, environment variables, explicit
overrides. `xcfg` composes them in a documented order and validates the result
with a pydantic model **your application owns**.

The library owns the *mechanism*. The model, the YAML files, and every policy
decision stay with you.

```bash
pip install xcfg     # or: uv add xcfg
```

## Quick start

```python
from pathlib import Path

from pydantic import BaseModel
from xcfg import ConfigLoader, ConfigSpec


class Database(BaseModel):
    driver: str = "sqlite"
    pool_size: int = 5


class Settings(BaseModel):
    database: Database = Database()


loader = ConfigLoader(
    ConfigSpec(
        config_root=Path(__file__).parent / "resources" / "config",
        env_prefix="MYAPP_",          # MYAPP_DATABASE__POOL_SIZE=20
        app_name="myapp",             # ~/.config/myapp/config.yml
        project_dir=".myapp",         # ./.myapp/config.yml, found by walking up
        profiled_sections=("database",),
    ),
    Settings,
)

settings = loader.load(env_name="staging")
```

## Resolution order

A base config is selected first:

1. an explicit path — the `config_path` argument, or `MYAPP_CONFIG`
2. a named env — the `env_name` argument, or `MYAPP_ENV`, loading `config.<name>.yml`
3. otherwise `config.default.yml`

Then these layers merge over it, **later winning**:

4. user config at `${XDG_CONFIG_HOME}/myapp/config.yml`
5. project config at `.myapp/config.yml`, nearest walking up from the CWD
6. environment variables, `MYAPP_<SECTION>__<KEY>`
7. explicit dotted-path overrides, `{"database.pool_size": "20"}`

Merging is deep, so a layer setting one key leaves its siblings intact. Scalars
from the environment and from overrides are parsed as YAML would parse them, so
`"20"` becomes an `int` and `"true"` becomes a `bool`.

Every layer is optional: an app with a single config file sets only
`config_root`.

## Profiles: the string-or-mapping rule

For any section listed in `profiled_sections`, the value may be:

- a **string** — a profile name, resolving to `<config_root>/<section>/<name>.yml`
- a **mapping** — used inline, as-is

```yaml
# resources/config/config.staging.yml
database: postgres            # -> resources/config/database/postgres.yml
storage: {backend: s3}        # inline; storage is not profiled
```

Profiles stay independent, so the file count is additive — N database profiles
plus M cache profiles, never N×M combined files.

```
resources/config/
  config.default.yml
  config.staging.yml
  database/
    sqlite.yml
    postgres.yml
```

## Per-source rules

When a setting belongs to *one input* rather than a whole tree, declare a
`source_rules_key` and bind by glob:

```yaml
sources:
  "*measure-anything*": {chaptering: toc-depth1}
  "*/decks/*.pptx": {naming: verbose}
```

```python
settings = loader.load(source=Path("measure-anything.mobi"))
loader.matching_source_rules(path)   # -> ("*measure-anything*",)
```

Patterns match the full path and the bare filename. Rules apply after the file
layers and before explicit overrides — specific enough to beat a project
default, never specific enough to beat an explicit flag. The key is loader
machinery and never reaches your model.

## Discovery

```python
loader.available_envs()               # ("default", "staging")
loader.available_profiles("database") # ("postgres", "sqlite")
loader.load_raw()                     # the merged mapping, before validation
```

## Errors

Everything raises `ConfigError` with an actionable message — an unknown profile
names the alternatives, a validation failure names the field:

```
unknown database profile 'postgres9' (available: postgres, sqlite)
invalid configuration: database.pool_size: Input should be a valid integer
```

Use `extra="forbid"` on your models so a typo in a config file fails loudly
instead of vanishing.

## Agent skill

`resources/skills/use-xcfg/SKILL.md` covers structuring configuration
correctly — in particular the N x M layout mistake, what belongs in a profile
versus inline, and how to adopt xcfg in a project with a hand-rolled loader.
`tests/test_skill.py` checks it against the real surface, so a renamed spec
field fails the build rather than misleading a reader.

## License

MIT
