#!/usr/bin/env bash
# Downloads BIRD dataset (Mini-Dev or Full Dev) and prepares local backend files.
# Usage: bash scripts/setupbird.sh [mini|full]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RAW_DIR="$ROOT_DIR/data/bird/raw"
PROCESSED_DIR="$ROOT_DIR/data/bird/processed"
DEMO_DIR="$ROOT_DIR/data/bird/demo"
DATASET="${1:-mini}"
MINIDEV_OSS="https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip"
DEV_OSS="https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip"

mkdir -p "$RAW_DIR" "$PROCESSED_DIR" "$DEMO_DIR"
cd "$ROOT_DIR"

echo "=== Installing dependencies ==="
uv pip install -e .
pip install huggingface_hub 2>/dev/null || true

echo "=== Downloading BIRD dataset: ${DATASET} ==="

if [ "$DATASET" = "mini" ]; then
  # --- Mini-Dev: 500 questions, 11 databases (~200MB) ---

  # Step 1: Download questions from HuggingFace (fast, reliable)
  if [ ! -f "$RAW_DIR/mini_dev_sqlite.json" ]; then
    echo "Downloading Mini-Dev questions from HuggingFace..."
    python3 -c "
from huggingface_hub import hf_hub_download
import json, os
path = hf_hub_download('birdsql/bird_mini_dev', 'data/mini_dev_sqlite-00000-of-00001.json', repo_type='dataset')
data = json.load(open(path))
os.makedirs('$RAW_DIR', exist_ok=True)
with open('$RAW_DIR/mini_dev_sqlite.json', 'w') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f'Downloaded {len(data)} Mini-Dev questions')
" || { echo "HuggingFace download failed."; exit 1; }
  fi

  # Step 2: Download databases from Alibaba OSS (includes questions too, but that's fine)
  if [ ! -d "$RAW_DIR/dev_databases" ] && [ ! -d "$RAW_DIR/mini_dev/mini_dev_data/dev_databases" ]; then
    MINIDEV_ZIP="$RAW_DIR/minidev.zip"
    echo "Downloading Mini-Dev databases from OSS..."
    if command -v curl &>/dev/null; then
      curl -L --retry 3 -o "$MINIDEV_ZIP" "$MINIDEV_OSS" || {
        echo "OSS download failed. Trying wget..."
        wget -O "$MINIDEV_ZIP" "$MINIDEV_OSS" 2>/dev/null || true
      }
    fi
    if [ -f "$MINIDEV_ZIP" ] && [ -s "$MINIDEV_ZIP" ]; then
      echo "Extracting Mini-Dev databases..."
      unzip -o "$MINIDEV_ZIP" -d "$RAW_DIR" >/dev/null
      rm -f "$MINIDEV_ZIP"
    else
      echo "OSS download failed. Trying GitHub sparse checkout..."
      git clone --depth 1 --filter=blob:none --sparse \
        https://github.com/bird-bench/mini_dev.git \
        "$RAW_DIR/mini_dev_tmp" 2>/dev/null || {
        echo "All download methods failed."
        echo "Please download Mini-Dev databases manually from:"
        echo "  https://bird-bench.github.io/"
        echo "  Extract to: $RAW_DIR/"
        exit 1
      }
      cd "$RAW_DIR/mini_dev_tmp"
      git sparse-checkout set mini_dev_data/dev_databases
      cd "$ROOT_DIR"
      mkdir -p "$RAW_DIR/mini_dev_data"
      mv "$RAW_DIR/mini_dev_tmp/mini_dev_data/dev_databases" "$RAW_DIR/mini_dev_data/" 2>/dev/null || true
      rm -rf "$RAW_DIR/mini_dev_tmp"
    fi
  fi

  echo "Mini-Dev download complete."
  uv run askdata prepare-bird --rawdir "$RAW_DIR" --outdir "$PROCESSED_DIR" --demodir "$DEMO_DIR" --force

elif [ "$DATASET" = "full" ]; then
  # --- Full Dev: 1534 questions, 73 databases (~33GB) ---

  # Step 1: Download questions from HuggingFace
  if [ ! -f "$RAW_DIR/dev.json" ]; then
    echo "Downloading Full Dev questions from HuggingFace..."
    python3 -c "
from huggingface_hub import hf_hub_download
import json, os
path = hf_hub_download('birdsql/bird_sql_dev_20251106', 'data/dev_20251106-00000-of-00001.json', repo_type='dataset')
data = json.load(open(path))
os.makedirs('$RAW_DIR', exist_ok=True)
with open('$RAW_DIR/dev.json', 'w') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f'Downloaded {len(data)} Full Dev questions')
" || { echo "HuggingFace download failed."; exit 1; }
  fi

  # Step 2: Download databases from OSS (~33GB)
  if [ ! -d "$RAW_DIR/dev_databases" ]; then
    DEV_ZIP="$RAW_DIR/dev.zip"
    if [ ! -f "$DEV_ZIP" ]; then
      echo "Downloading Full Dev databases from OSS (~33GB, this will take a while)..."
      curl -L --retry 3 -C - -o "$DEV_ZIP" "$DEV_OSS" || {
        echo "OSS download failed."
        echo "Please download dev.zip manually from https://bird-bench.github.io/"
        echo "Extract it to: $RAW_DIR/"
        exit 1
      }
    fi
    echo "Extracting Full Dev databases..."
    unzip -o "$DEV_ZIP" -d "$RAW_DIR" >/dev/null
  fi

  echo "Full Dev download complete."
  uv run askdata prepare-bird --rawdir "$RAW_DIR" --outdir "$PROCESSED_DIR" --demodir "$DEMO_DIR" --force --split dev

else
  echo "Unknown dataset: $DATASET"
  echo "Usage: bash scripts/setupbird.sh [mini|full]"
  exit 1
fi

echo "=== Running smoke test ==="
uv run askdata smoke

echo ""
echo "=== BIRD dataset is ready ==="
echo "Run server: uv run askdata serve"
