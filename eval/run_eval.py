"""Eval harness. Run: python eval/run_eval.py
 1. Number check  - the 3 rows printed in the brief's sample file (independent ground truth for the maths).
 2. Label check   - hand-labelled route-weeks (verdict + cited note), read directly from the notes.
 3. No-false-alarm check - quiet weeks must not be flagged.
 4. Adversarial verifier tests - synthetic notes that a careless system would wrongly accept.
Exits non-zero on any failure."""
import sys, os
from datetime import date
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from freight_watch.pipeline import build_output
from freight_watch.notes import Note
from freight_watch.verify import check_note

fails = []
def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond: fails.append(name)

out, metrics = build_output("data/shipment_records.csv", "data/context_notes.csv")
o = out.set_index(["route", "week_of"])

# 1. numbers from the brief's sample file
# the sample file has an unquoted comma inside one reason, so split on the first 7 commas only
lines = open("data/sample_output_format_v2.csv", encoding="utf-8").read().splitlines()
rows = [l.split(",", 7) for l in lines]
sample = pd.DataFrame(rows[1:], columns=rows[0])
for r in sample.itertuples():
    k = (r.route, r.week_of)
    ok = k in o.index and all(o.loc[k, c] == getattr(r, c) for c in
         ["cost_per_tonne_km", "vs_own_history", "vs_similar_routes", "flagged", "matched_note_id"])
    check(f"sample row {k}", ok, str(o.loc[k].to_dict()) if k in o.index else "row missing")
check("column names/order match sample", list(out.columns) == list(sample.columns))

# 2. labelled verdicts
for r in pd.read_csv("eval/labeled_cases.csv", dtype=str, keep_default_na=False).itertuples():
    k = (r.route, r.week_of)
    ok = k in o.index and o.loc[k, "flagged"] == r.expected_flagged and o.loc[k, "matched_note_id"] == r.expected_note
    check(f"label {k} -> {r.expected_flagged} {r.expected_note}", ok)

# 3. quiet weeks
for k in [("Ahmedabad-Mumbai", "2025-01-27"), ("Delhi-Chennai", "2024-02-05"), ("Kolkata-Bhubaneswar", "2025-06-09"),
          ("Delhi-Jaipur", "2024-11-25"), ("Mumbai-Pune", "2024-01-08")]:
    check(f"not flagged {k}", k not in o.index)
check("no look-ahead: first week of each route has no own-history number",
      metrics[metrics.week_of == metrics.week_of.min()]["vs_own"].isna().all())
check("<=8 prior weeks used", metrics["n_prior_weeks"].dropna().max() <= 8)

# 4. adversarial verifier tests
wk = pd.Timestamp("2025-03-03")
mk = lambda **kw: Note(**{**dict(note_id="T1", date=date(2025, 3, 3), applies_to="Delhi-Jaipur", text="x",
                                  effect="increase", start=date(2025, 3, 3), end=date(2025, 3, 9), max_pct=None), **kw})
check("wrong route rejected", not check_note(mk(applies_to="Mumbai-Pune"), "Delhi-Jaipur", wk, .3, True, True)[0])
check("wrong window rejected", not check_note(mk(start=date(2024, 1, 1), end=date(2024, 1, 7)), "Delhi-Jaipur", wk, .3, True, True)[0])
check("'costs not affected' rejected", not check_note(mk(effect="no_effect"), "Delhi-Jaipur", wk, .3, True, True)[0])
check("correct note accepted", check_note(mk(), "Delhi-Jaipur", wk, .3, True, True)[0])
g = mk(applies_to="All Routes", start=date(2025, 3, 3), end=None, max_pct=0.07)
check("nationwide note cannot explain a 30% spike", not check_note(g, "Delhi-Jaipur", wk, .30, True, False)[0])
check("nationwide note cannot explain peer-only gap", not check_note(g, "Delhi-Jaipur", wk, .03, False, True)[0])
check("nationwide note explains a 8% rise inside its first 8 weeks", check_note(g, "Delhi-Jaipur", wk, .08, True, False)[0])
check("nationwide note stale after 8 weeks", not check_note(g, "Delhi-Jaipur", pd.Timestamp("2025-06-02"), .08, True, False)[0])

# 5. hallucination guard: every justified row cites a real note whose id/route/dates were verified above
notes = pd.read_csv("data/context_notes.csv").set_index("note_id")
for r in out[out.matched_note_id != ""].itertuples():
    check(f"cited note exists & is quoted ({r.route} {r.week_of})",
          r.matched_note_id in notes.index and notes.loc[r.matched_note_id, "note"].split(". ")[0].rstrip(".") in r.reason)
print(f"\n{len(fails)} failure(s)"); sys.exit(1 if fails else 0)
