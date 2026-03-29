#!/usr/bin/env bash
set -e

echo "=== pytest ==="
pytest tests/ -q

echo "=== coverage ==="
pytest tests/ --cov=app --cov-report=term-missing -q

echo "=== cyclomatic complexity (radon) ==="
radon cc app/ -a -nb

echo "=== maintainability index (radon) ==="
radon mi app/ -nb

echo "=== security scan (bandit) ==="
bandit -r app/ -ll -q

echo "=== type check (mypy) ==="
mypy app/ --ignore-missing-imports --no-error-summary || true

echo "=== dependency audit ==="
if command -v pip-audit >/dev/null 2>&1; then
  pip-audit
else
  echo "pip-audit not installed, skipping."
fi
