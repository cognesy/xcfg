"""Error types.

One family, so a consuming application can catch `ConfigError` and map it to
whatever its own error surface needs.
"""

from __future__ import annotations


class ConfigError(Exception):
    """Configuration could not be located, parsed, merged, or validated."""


__all__ = ["ConfigError"]
