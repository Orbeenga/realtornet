#!/usr/bin/env bash
set -e

echo "Running pytest..."
pytest tests/ -q

echo "Running coverage..."
pytest tests/ --cov=app --cov-report=term-missing

echo "Running dependency audit if pip-audit exists..."
if command -v pip-audit >/dev/null 2>&1; then
  pip-audit
else
  echo "pip-audit not installed, skipping."
fi
