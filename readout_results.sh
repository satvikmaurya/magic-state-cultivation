#!/usr/bin/env bash

set -e

./tools/sinter_plot_echo.py \
    --in assets/readout_stats_ibm.csv \
    --x_func 'm.rd' \
    --y_func '(stat.shots - stat.discards) / stat.shots' \
    --xaxis 'Readout Duration (rd)' \
    --yaxis 'Acceptance Rate' \
    --group_func '{"label": f"rdel={m.rdel}", "color": m.rdel, "marker": m.rdel}' \
    --title 'Acceptance Rates by Readout Configuration' \
    --subtitle 't1=0.00025, t2=0.00015' \
    --ymin 0.4 \
    --ymax 0.6 \
    --fig_size 2048 1024 \
    --dpi 200 \
    --out assets/gen/acceptance_by_config.png