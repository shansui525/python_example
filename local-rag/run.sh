#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -q -U pip
pip install -q -r requirements.txt
mkdir -p data/docs data/index
exec python -m uvicorn src.app:app --host 127.0.0.1 --port 8780 --reload
