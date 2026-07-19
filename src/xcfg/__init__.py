"""xcfg — layered, profile-composable configuration for Python applications.

Configuration arrives from several places at once: packaged defaults, a named
environment, a user file, a project file, environment variables, and explicit
overrides. xcfg composes them in a documented order and validates the result
with a pydantic model the application owns.

    from pathlib import Path
    from pydantic import BaseModel
    from xcfg import ConfigLoader, ConfigSpec

    class Settings(BaseModel):
        database: DatabaseSettings = DatabaseSettings()

    loader = ConfigLoader(
        ConfigSpec(
            config_root=Path(__file__).parent / "resources" / "config",
            env_prefix="MYAPP_",
            app_name="myapp",
            project_dir=".myapp",
            profiled_sections=("database",),
        ),
        Settings,
    )

    settings = loader.load(env_name="staging")

The library owns the *mechanism*. The model, the YAML files, and every policy
decision stay with the application.
"""

from .errors import ConfigError
from .loader import (
    ConfigLoader,
    RawConfig,
    coerce_scalar,
    deep_merge,
    matches_source,
    read_yaml,
    set_dotted,
)
from .spec import DEFAULT_CONFIG_NAME, ENV_CONFIG_PREFIX, ConfigSpec

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_CONFIG_NAME",
    "ENV_CONFIG_PREFIX",
    "ConfigError",
    "ConfigLoader",
    "ConfigSpec",
    "RawConfig",
    "__version__",
    "coerce_scalar",
    "deep_merge",
    "matches_source",
    "read_yaml",
    "set_dotted",
]
