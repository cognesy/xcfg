# Test lanes and local quality gates.

[group('qa'), doc('Run the test suite')]
test:
    uv run pytest

[group('qa'), doc('Run tests matching a keyword expression')]
test-k pattern:
    uv run pytest -k "{{pattern}}"

[group('qa'), doc('Test suite with a coverage report')]
coverage:
    uv run pytest --cov=xcfg --cov-report=term-missing

[group('qa'), doc('Fast local QA gate for ordinary edits')]
qa-fast: lint format-check typecheck test

[group('qa'), doc('Full local gate, including a wheel smoke test')]
qa: qa-fast smoke

[group('qa'), doc('Local reproduction of the CI gate')]
check: qa
