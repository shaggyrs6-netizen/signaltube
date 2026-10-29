#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export PYTHONPATH="$PWD/src"
export PYTHONPYCACHEPREFIX="$PWD/.cache/pycache"
umask 077
if [[ ! -x .venv/bin/python ]]; then
  echo 'Missing local environment. See README.md for the explicit setup command.' >&2
  exit 1
fi
if [[ $# -eq 0 ]]; then set -- launch; fi
exec .venv/bin/python -m signaltube.cli "$@"
