#!/usr/bin/env bash
# Only needed if ONE person runs both halves on ONE computer.
# If you and your teammate each work on your own machine, skip this:
# just clone the repo and make branches as usual.
set -euo pipefail

git worktree add ../texas-wildlife-a -b person-a
git worktree add ../texas-wildlife-b -b person-b

echo "Created ../texas-wildlife-a (Person A) and ../texas-wildlife-b (Person B)."
echo "In each folder: make a venv, pip install -r requirements.txt, and copy your .env over."
