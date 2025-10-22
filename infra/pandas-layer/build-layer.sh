#!/usr/bin/env bash
set -euo pipefail
ROOT="$(pwd)"
WORKDIR="${ROOT}/python"
rm -rf "$WORKDIR"
mkdir -p "$WORKDIR"
pip install -r requirements.txt -t "$WORKDIR"




