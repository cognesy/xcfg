# Development setup and inner-loop commands.

[group('dev'), doc('Install the local development environment')]
setup:
    uv sync --extra dev

[group('dev'), doc('Lint with ruff')]
lint:
    uv run ruff check .

[group('dev'), doc('Auto-fix lint findings and format')]
fix:
    uv run ruff check . --fix
    uv run ruff format .

[group('dev'), doc('Format Python files')]
format:
    uv run ruff format .

[group('dev'), doc('Verify formatting without writing changes')]
format-check:
    uv run ruff format --check .

[group('dev'), doc('Strict static type checking with mypy')]
typecheck:
    uv run mypy

[group('dev'), doc('Alias for typecheck')]
type: typecheck
