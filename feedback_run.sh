#!/usr/bin/env bash

set -e
cd "$( dirname "${BASH_SOURCE[0]}" )"
cd "$(git rev-parse --show-toplevel)"

PYTHONPATH=src sinter collect \
    --metadata_func auto \
    --circuits out/*.stim \
    --decoders desaturation \
    --max_shots 1_000_000_000 \
    --custom_decoders "cultiv:sinter_samplers" \
    --save_resume_filepath assets/feedback_stats.csv

./tools/write_historical_data_csv.py \
  --in assets/feedback_stats.csv \
  > assets/new-emulated-historical-stats.csv