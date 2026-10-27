#!/usr/bin/env bash
# Run the same measured scenario on Linux/macOS or from Git Bash on Windows.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "${PYTHON:-python3}" "$HERE/measure_task2.py" "$@"
