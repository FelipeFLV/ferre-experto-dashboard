#!/bin/zsh
set -e
cd "$(dirname "$0")"

python3 build.py
python3 serve.py
