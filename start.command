#!/bin/bash
set -e
cd -- "$(dirname -- "$0")"
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python -m openfix serve
fi
exec python3 -m openfix serve
