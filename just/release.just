# Versioning, packaging, and releasing.
#
# The version has one source: `__version__` in src/xcfg/__init__.py, which
# hatchling reads at build time. `just version-set` is the only thing that
# writes it, so pyproject and the package can never disagree.
#
# Release flow:
#
#   just version-set 0.4.0     # bump the single source
#   just changelog-stub 0.4.0  # start the changelog entry, then edit it
#   git commit -am "Release 0.4.0"
#   just release v0.4.0        # validate, tag, push -> workflow takes over

[group('release'), doc('Print the version the package declares')]
version:
    @uv run python -c "import re,pathlib; print(re.search(r'__version__\\s*=\\s*\"([^\"]+)\"', pathlib.Path('src/xcfg/__init__.py').read_text()).group(1))"

[group('release'), doc('Set the package version (the single source of truth)')]
version-set new:
    #!/usr/bin/env bash
    set -euo pipefail
    file="src/xcfg/__init__.py"
    current="$(just version)"
    python3 - "$file" "{{new}}" <<'PY'
    import pathlib, re, sys
    path, new = pathlib.Path(sys.argv[1]), sys.argv[2]
    if not re.fullmatch(r"\d+\.\d+\.\d+([.-]?(a|b|rc|dev|post)\d*)?", new):
        raise SystemExit(f"error: {new!r} is not a MAJOR.MINOR.PATCH version")
    text = path.read_text()
    updated, count = re.subn(r'(__version__\s*=\s*")[^"]+(")', rf"\g<1>{new}\g<2>", text)
    if count != 1:
        raise SystemExit(f"error: expected one __version__ assignment, found {count}")
    path.write_text(updated)
    PY
    echo "version: $current -> {{new}}"

[group('release'), doc('Start a CHANGELOG entry for a version')]
changelog-stub new:
    #!/usr/bin/env bash
    set -euo pipefail
    if grep -q "^## \[{{new}}\]" CHANGELOG.md; then
        echo "CHANGELOG already has an entry for {{new}}"; exit 0
    fi
    today="$(date +%Y-%m-%d)"
    python3 - "{{new}}" "$today" <<'PY'
    import pathlib, sys
    version, today = sys.argv[1], sys.argv[2]
    path = pathlib.Path("CHANGELOG.md")
    text = path.read_text()
    marker = "\n## ["
    entry = f"\n## [{version}] - {today}\n\n### Added\n\n- \n"
    index = text.find(marker)
    path.write_text(text[:index] + entry + text[index:] if index != -1 else text + entry)
    PY
    echo "CHANGELOG.md: added a stub for {{new}} — edit it before releasing"

[group('release'), doc('Validate a tag against the declared version')]
version-check tag:
    uv run python tools/check_release_version.py "{{tag}}"

[group('release'), doc('Build source distribution and wheel')]
build:
    rm -rf dist
    uv build

[group('release'), doc('Install the built wheel in isolation and import it')]
smoke: build
    #!/usr/bin/env bash
    set -euo pipefail
    wheel="$(find dist -name 'xcfg-*.whl' -type f | head -n 1)"
    uv run --isolated --with "$wheel" python -c "import xcfg; print('import OK', xcfg.__version__)"
    uv run --isolated --with "$wheel" python -c "import importlib.resources as r; assert r.files('xcfg').joinpath('py.typed').is_file(); print('py.typed OK')"

[group('release'), doc('Validate a tag, run the full gate, and build artifacts')]
release-check tag: (version-check tag) qa

[group('release'), doc('Validate, tag, and push — the release workflow does the rest')]
release tag: (release-check tag)
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -n "$(git status --short)" ]; then
        echo "error: working tree is dirty; commit before releasing"; exit 1
    fi
    if git rev-parse "{{tag}}" >/dev/null 2>&1; then
        echo "error: tag {{tag}} already exists"; exit 1
    fi
    git tag -a "{{tag}}" -m "xcfg {{tag}}"
    git push origin main --tags
    echo "pushed {{tag}} — watch: gh run watch"
