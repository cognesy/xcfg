"""Assert the git tag and the package version agree.

The release workflow runs this before building anything, so a stale version
never ships under a fresh tag.

The package version has a single source -- ``__version__`` in the package
``__init__``, which hatchling reads at build time -- so there is no second
place to drift. This check exists for the one pairing that *can* disagree: the
tag a human typed, and the version the code declares.

Usage:

    uv run python tools/check_release_version.py v0.3.0
    uv run python tools/check_release_version.py "$GITHUB_REF_NAME"

The tag may be given with or without a leading ``v``. Exit 0 when they agree,
1 with a diagnostic when they do not.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parents[1]
VERSION_FILE: Path = REPO_ROOT / "src" / "xcfg" / "__init__.py"

#: `__version__ = "1.2.3"`, single- or double-quoted.
_VERSION_RE = re.compile(r"^__version__\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)

#: Releases are `MAJOR.MINOR.PATCH`, optionally with a pre-release suffix.
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+([.-]?(a|b|rc|dev|post)\d*)?$")


def normalize_tag(tag: str) -> str:
    """Strip a leading ``v`` and surrounding whitespace; reject empty input."""
    cleaned = tag.strip()
    if not cleaned:
        raise SystemExit("error: empty tag")
    return cleaned.removeprefix("v")


def package_version(path: Path = VERSION_FILE) -> str:
    """Read ``__version__`` without importing the package.

    Importing would require dependencies to be installed, which the release
    workflow should not need before it has even built.
    """
    if not path.is_file():
        raise SystemExit(f"error: version file not found: {path}")
    match = _VERSION_RE.search(path.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"error: no __version__ assignment in {path}")
    return match.group(1)


def check(tag: str) -> list[str]:
    """Return a list of problems; empty means the release is consistent."""
    version = normalize_tag(tag)
    problems: list[str] = []

    if not _SEMVER_RE.match(version):
        problems.append(f"tag {tag!r} is not a MAJOR.MINOR.PATCH version")

    declared = package_version()
    if declared != version:
        problems.append(f"tag says {version!r} but {VERSION_FILE.name} declares {declared!r}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tag", help="Release tag, e.g. v0.3.0")
    args = parser.parse_args(argv)

    problems = check(args.tag)
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1
    print(f"release version OK: {normalize_tag(args.tag)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
