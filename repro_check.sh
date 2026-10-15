#!/usr/bin/env bash
# Three untouched runs on the same input; outputs must be byte-identical.
set -e
cd "$(dirname "$0")"
for i in 1 2 3; do python3 run.py --out out/run$i/flags.csv > /dev/null; done
for f in flags.csv flags_all_weeks.csv flags_run_log.json; do
  diff -q out/run1/$f out/run2/$f && diff -q out/run1/$f out/run3/$f
done
echo "REPRODUCIBLE: 3 runs identical"; sha256sum out/run*/flags.csv
cp out/run1/flags.csv out/flags.csv; cp out/run1/flags_all_weeks.csv out/flags_all_weeks.csv
cp out/run1/flags_run_log.json out/flags_run_log.json
