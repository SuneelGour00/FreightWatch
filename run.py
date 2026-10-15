"""Usage: python run.py [--shipments data/shipment_records.csv] [--notes data/context_notes.csv] [--out out/flags.csv]"""
import argparse, hashlib, json, os
from freight_watch.pipeline import build_output


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shipments", default="data/shipment_records.csv")
    ap.add_argument("--notes", default="data/context_notes.csv")
    ap.add_argument("--out", default="out/flags.csv")
    a = ap.parse_args()
    out, metrics = build_output(a.shipments, a.notes)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    out.to_csv(a.out, index=False, lineterminator="\n")
    metrics.to_csv(a.out.replace(".csv", "_all_weeks.csv"), index=False, lineterminator="\n")   # full audit trail
    log = {  # no timestamps on purpose: this file must be identical across runs
        "weekly_rows": len(metrics), "flagged_rows": len(out),
        "unexplained_Yes": int((out.flagged == "Yes").sum()), "justified": int((out.flagged != "Yes").sum()),
        "llm_calls": 0, "llm_input_tokens": 0, "llm_output_tokens": 0, "llm_cost_usd": 0.0,
        "retrieval": "TF-IDF cosine over 10 notes, local CPU, no API",
        "output_sha256": hashlib.sha256(open(a.out, "rb").read()).hexdigest(),
    }
    json.dump(log, open(a.out.replace(".csv", "_run_log.json"), "w"), indent=2)
    print(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
