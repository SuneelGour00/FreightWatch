# Token / cost log - one full run over shipment_records.csv (2,940 rows)

| Item | Value |
|---|---|
| LLM calls | 0 |
| Total input tokens | 0 |
| Total output tokens | 0 |
| Cost at published rate | $0.00 |
| Retrieval | local TF-IDF (scikit-learn) over 10 notes; no API, no GPU |
| Source of truth | `out/flags_run_log.json` (written by `run.py`) |

Reason for zero: the metrics are arithmetic, retrieval is local, and explanations are templated from the matched
note's own sentence. An LLM would add cost and non-determinism without improving the verdict.
