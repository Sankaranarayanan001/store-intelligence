#!/bin/bash
# run.sh — process all clips for one store

STORE_ID="STORE_BLR_002"
DATA_DIR="./data"
OUTPUT="./events.jsonl"

> $OUTPUT  # clear output

python pipeline/detect.py \
  --video "$DATA_DIR/cam1.mp4" --camera cam1 \
  --video "$DATA_DIR/cam2.mp4" --camera cam2 \
  --video "$DATA_DIR/cam3.mp4" --camera cam3 \
  --video "$DATA_DIR/cam5.mp4" --camera cam5 \
  --output $OUTPUT

echo "Done. Events written to $OUTPUT"