#!/usr/bin/env bash
set -e

TARGET="$1"

if [ -z "$TARGET" ]; then
  echo "Usage: ./scripts/test_target.sh <test-path-or-node>"
  exit 1
fi

pytest "$TARGET" -q
