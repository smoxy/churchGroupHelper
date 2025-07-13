#!/usr/bin/env bash
set -e

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Prepare data directories
data_dir="$(pwd)/data"
mkdir -p "$data_dir/whisper"
touch "$data_dir/bot.db"

echo "Setup complete. Activate the virtual environment with 'source .venv/bin/activate'"
