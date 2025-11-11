#!/usr/bin/env bash

set -e
cd "$( dirname "${BASH_SOURCE[0]}" )"
cd "$(git rev-parse --show-toplevel)"

PYTHONPATH=src sinter collect \
    --metadata_func auto \
    --circuits out_ibm_real/*.stim \
    --decoders desaturation \
    --max_shots 1_000_000_000 \
    --max_errors 1_000_000 \
    --custom_decoders "cultiv:sinter_samplers" \
    --save_resume_filepath assets/readout_stats_ibm_real.csv


PYTHONPATH=src sinter collect \
    --metadata_func auto \
    --circuits out_ibm_future/*.stim \
    --decoders desaturation \
    --max_shots 1_000_000_000 \
    --max_errors 1_000_000 \
    --custom_decoders "cultiv:sinter_samplers" \
    --save_resume_filepath assets/readout_stats_ibm_future.csv

# ./tools/write_historical_data_csv.py \
#   --in assets/readout_stats_ibm.csv \
#   > assets/new-emulated-historical-stats.csv

PYTHONPATH=src sinter collect \
  --metadata_func auto \
  --circuits out_google_real/*.stim \
  --decoders desaturation \
  --max_shots 1_000_000_000 \
  --max_errors 1_000_000 \
  --custom_decoders "cultiv:sinter_samplers" \
  --save_resume_filepath assets/readout_stats_google.csv

# ./tools/write_historical_data_csv.py \
# --in assets/readout_stats_google.csv \
# > assets/new-emulated-historical-stats.csv