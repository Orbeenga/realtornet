#!/usr/bin/env bash
set -e

echo "Running end-to-end tests..."
pytest tests/e2e -q
