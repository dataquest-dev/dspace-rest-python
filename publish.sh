#!/bin/bash
set -euo pipefail

rm -rf build dist
python -m build
python -m twine check dist/*
python -m twine upload dist/*