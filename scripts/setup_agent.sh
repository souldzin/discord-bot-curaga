#!/usr/bin/env bash

set -euo pipefail

mise trust
mise install
eval "$(mise activate bash)"
echo 'eval "$(mise activate bash)"' >>~/.bashrc

make setup
